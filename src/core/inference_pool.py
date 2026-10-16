"""Restartable process workers for inference that must be cancellable."""

import multiprocessing
import time
from dataclasses import dataclass, field
from multiprocessing.queues import Queue as ProcessQueue
from queue import Empty, Queue
from threading import Lock
from typing import Callable, Protocol


class Detector(Protocol):
    """Detector contract used by an isolated inference worker."""

    def detect(self, file_path: str) -> list[dict[str, object]]:
        """Return detections for one file path."""


DetectorFactory = Callable[[], Detector]


class RemoteDetectionError(RuntimeError):
    """A detector raised an exception inside its worker process."""


@dataclass
class _DetectionWorker:
    """Parent-side resources for one child process."""

    process: multiprocessing.Process
    requests: ProcessQueue
    responses: ProcessQueue
    ready: bool = False
    cleanup_lock: Lock = field(default_factory=Lock)
    stopped: bool = False


def _run_detection_worker(
    requests: ProcessQueue,
    responses: ProcessQueue,
    detector_factory: DetectorFactory,
) -> None:
    """Load one detector and serialize requests until the parent closes the worker."""
    try:
        detector = detector_factory()
    except Exception as error:
        responses.put(("startup_error", type(error).__name__, str(error)))
        return

    responses.put(("ready",))
    while True:
        file_path = requests.get()
        if file_path is None:
            return
        try:
            responses.put(("result", detector.detect(file_path)))
        except Exception as error:
            responses.put(("error", type(error).__name__, str(error)))


class RestartableDetectionPool:
    """Run detector calls in reusable processes that can be terminated on timeout.

    Args:
        detector_factory: Picklable, module-level callable that constructs a detector.
        worker_count: Maximum number of concurrent detector processes.
        startup_timeout_seconds: Maximum time to load each worker's detector.
    """

    def __init__(
        self,
        detector_factory: DetectorFactory,
        worker_count: int,
        startup_timeout_seconds: int = 120,
    ) -> None:
        if worker_count < 1:
            raise ValueError(f"worker_count must be at least 1, got {worker_count}")
        if startup_timeout_seconds < 1:
            raise ValueError(f"startup_timeout_seconds must be at least 1, got {startup_timeout_seconds}")
        self._detector_factory = detector_factory
        self._startup_timeout_seconds = startup_timeout_seconds
        self._context = multiprocessing.get_context("spawn")
        self._workers: list[_DetectionWorker | None] = [None] * worker_count
        self._available_slots: Queue[int] = Queue(maxsize=worker_count)
        for slot in range(worker_count):
            self._available_slots.put(slot)
        self._state_lock = Lock()
        self._closed = False

    def detect(self, file_path: str, timeout_seconds: float) -> list[dict[str, object]]:
        """Detect one file, terminating its worker if the call exceeds its deadline.

        Args:
            file_path: Image or video frame to classify.
        timeout_seconds: Limit for acquiring a slot and waiting for inference; model startup has its own limit.

        Returns:
            The detector's list of detection records.

        Raises:
            TimeoutError: If no worker becomes available or inference times out.
            RemoteDetectionError: If detector startup or inference fails.
            RuntimeError: If the pool is closed or a worker exits unexpectedly.
        """
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}")
        try:
            slot = self._available_slots.get(timeout=timeout_seconds)
        except Empty:
            raise TimeoutError(f"Detection worker was not available for {file_path}") from None

        worker: _DetectionWorker | None = None
        discard_worker = False
        try:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("Detection worker pool is closed")
                worker = self._workers[slot]
                if worker is not None and not worker.process.is_alive():
                    self._stop_worker(worker, graceful=False)
                    self._workers[slot] = None
                    worker = None
                if worker is None:
                    worker = self._start_worker()
                    self._workers[slot] = worker

            if not worker.ready:
                startup_deadline = time.monotonic() + self._startup_timeout_seconds
                startup = self._wait_for_message(worker, startup_deadline)
                if startup[0] == "startup_error":
                    discard_worker = True
                    raise RemoteDetectionError(f"Detector startup failed ({startup[1]}): {startup[2]}")
                if startup[0] != "ready":
                    discard_worker = True
                    raise RuntimeError("Detection worker sent an invalid startup response")
                worker.ready = True

            deadline = time.monotonic() + timeout_seconds
            worker.requests.put(file_path)
            response = self._wait_for_message(worker, deadline)
            if response[0] == "result":
                result = response[1]
                if not isinstance(result, list):
                    discard_worker = True
                    raise RemoteDetectionError("Detector returned a non-list result")
                detections: list[dict[str, object]] = []
                for item in result:
                    if not isinstance(item, dict):
                        discard_worker = True
                        raise RemoteDetectionError("Detector returned a malformed detection record")
                    detection: dict[str, object] = {}
                    for key, value in item.items():
                        if not isinstance(key, str):
                            discard_worker = True
                            raise RemoteDetectionError("Detector returned a non-string detection key")
                        detection[key] = value
                    detections.append(detection)
                return detections
            if response[0] == "error":
                raise RemoteDetectionError(f"Detector failed ({response[1]}): {response[2]}")
            discard_worker = True
            raise RuntimeError("Detection worker sent an invalid response")
        except TimeoutError:
            discard_worker = True
            raise
        except RemoteDetectionError:
            raise
        except RuntimeError:
            discard_worker = True
            raise
        except (EOFError, OSError) as error:
            discard_worker = True
            raise RuntimeError(f"Detection worker communication failed for {file_path}: {error}") from error
        finally:
            if discard_worker and worker is not None:
                self._stop_worker(worker, graceful=False)
                with self._state_lock:
                    if self._workers[slot] is worker:
                        self._workers[slot] = None
            with self._state_lock:
                closed = self._closed
            if not closed:
                self._available_slots.put(slot)

    def close(self) -> None:
        """Stop every worker, including inference still running during scan shutdown."""
        with self._state_lock:
            self._closed = True
            workers = [worker for worker in self._workers if worker is not None]

        errors: list[RuntimeError] = []
        for worker in workers:
            try:
                self._stop_worker(worker, graceful=True)
            except RuntimeError as error:
                errors.append(error)
        if errors:
            raise RuntimeError(f"Could not stop {len(errors)} detection worker process(es)") from errors[0]

    def _start_worker(self) -> _DetectionWorker:
        """Start a child process with fresh IPC queues."""
        requests = self._context.Queue()
        responses = self._context.Queue()
        process = self._context.Process(
            target=_run_detection_worker,
            args=(requests, responses, self._detector_factory),
            daemon=True,
        )
        try:
            process.start()
        except Exception:
            requests.cancel_join_thread()
            responses.cancel_join_thread()
            requests.close()
            responses.close()
            raise
        return _DetectionWorker(process, requests, responses)

    def _wait_for_message(self, worker: _DetectionWorker, deadline: float) -> tuple[object, ...]:
        """Read one IPC response while observing pool shutdown and child exit."""
        while True:
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("Detection worker pool closed during inference")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Detection worker response deadline expired")
            try:
                return worker.responses.get(timeout=min(remaining, 0.1))
            except Empty:
                if not worker.process.is_alive():
                    raise RuntimeError("Detection worker exited without a response")

    @staticmethod
    def _stop_worker(worker: _DetectionWorker, graceful: bool) -> None:
        """Release queues and terminate a child without allowing work to outlive its owner."""
        with worker.cleanup_lock:
            if worker.stopped:
                return
            process = worker.process
            if process.is_alive() and graceful:
                try:
                    worker.requests.put(None)
                    process.join(timeout=1)
                except (EOFError, OSError, ValueError):
                    pass
            if process.is_alive():
                try:
                    process.terminate()
                except OSError:
                    pass
                process.join(timeout=1)
            if process.is_alive():
                try:
                    process.kill()
                except OSError:
                    pass
                process.join(timeout=1)
            if process.is_alive():
                raise RuntimeError(f"Could not stop detection worker process {process.pid}")
            worker.stopped = True
            for channel in (worker.requests, worker.responses):
                try:
                    channel.cancel_join_thread()
                    channel.close()
                except (OSError, ValueError):
                    pass

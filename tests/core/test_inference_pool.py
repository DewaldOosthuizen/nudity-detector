"""Lifecycle tests for process-isolated inference workers."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from src.core.inference_pool import RestartableDetectionPool


class _ControlledDetector:
    """Detector whose slow path remains active until its process is stopped."""

    def detect(self, file_path: str) -> list[dict[str, object]]:
        action, separator, marker = file_path.partition("|")
        if separator:
            Path(marker).touch()
        if action == "slow":
            time.sleep(10)
        return [{"path": action}]


def _create_controlled_detector() -> _ControlledDetector:
    return _ControlledDetector()


class _ExitingDetector:
    """Detector that simulates an unexpected native worker exit."""

    def detect(self, file_path: str) -> list[dict[str, object]]:
        if file_path == "exit":
            os._exit(7)
        return [{"path": file_path}]


def _create_exiting_detector() -> _ExitingDetector:
    return _ExitingDetector()


def _create_failing_detector() -> _ControlledDetector:
    raise ValueError("model initialization failed")


def _wait_for_marker(path: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    raise AssertionError("detector did not start inference")


def test_timed_out_slot_waits_for_termination_before_retry(tmp_path):
    pool = RestartableDetectionPool(
        _create_controlled_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        slow_started = tmp_path / "slow-started"
        fast_started = tmp_path / "fast-started"
        second_call_started = Event()

        def run_fast_detection():
            second_call_started.set()
            return pool.detect(f"fast|{fast_started}", timeout_seconds=10)

        with ThreadPoolExecutor(max_workers=2) as executor:
            slow_detection = executor.submit(
                pool.detect, f"slow|{slow_started}", timeout_seconds=0.5
            )
            _wait_for_marker(slow_started)
            fast_detection = executor.submit(run_fast_detection)
            assert second_call_started.wait(timeout=2)
            time.sleep(0.1)
            assert not fast_started.exists()

            with pytest.raises(TimeoutError):
                slow_detection.result(timeout=5)
            assert fast_detection.result(timeout=10) == [{"path": "fast"}]
            assert fast_started.exists()

        with pytest.raises(TimeoutError):
            pool.detect("slow", timeout_seconds=0.2)
        assert pool._workers[0] is None
        assert pool.detect("fast", timeout_seconds=5) == [{"path": "fast"}]
        assert pool._workers[0] is not None
    finally:
        pool.close()


def test_scan_shutdown_stops_active_inference_process(tmp_path):
    pool = RestartableDetectionPool(
        _create_controlled_detector, worker_count=1, startup_timeout_seconds=5
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        marker = tmp_path / "slow-started"
        detection = executor.submit(pool.detect, f"slow|{marker}", 10)
        _wait_for_marker(marker)
        worker = pool._workers[0]
        pool.close()

        with pytest.raises(RuntimeError, match="closed"):
            detection.result(timeout=5)
        assert worker is not None
        assert not worker.process.is_alive()


def test_unexpected_worker_exit_is_cleaned_up_and_retried():
    pool = RestartableDetectionPool(
        _create_exiting_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        with pytest.raises(RuntimeError, match="exited without a response"):
            pool.detect("exit", timeout_seconds=5)
        assert pool._workers[0] is None
        assert pool.detect("retry", timeout_seconds=5) == [{"path": "retry"}]
    finally:
        pool.close()


def test_worker_startup_error_is_reported_and_slot_is_recovered():
    pool = RestartableDetectionPool(
        _create_failing_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        with pytest.raises(RuntimeError, match="ValueError.*model initialization failed"):
            pool.detect("image", timeout_seconds=5)
        assert pool._workers[0] is None
    finally:
        pool.close()

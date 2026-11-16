"""Extended tests for src/core/utils.py to boost coverage."""
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy optional deps before importing source modules
sys.modules.setdefault("nudenet", MagicMock())

from src.core import constants
from src.core.inference_pool import RemoteDetectionError, RestartableDetectionPool
from src.core.scan_session import ScanSession
from src.core.utils import (
    _checkpoint_writers,
    _get_or_create_checkpoint_writer,
    _raise_checkpoint_writer_error,
    count_supported_files,
    create_session_state,
    delete_file_safely,
    detect_media_type_utils,
    detect_with_timeout,
    get_report_path,
    get_session_path,
    get_thumbnail,
    handle_results,
    load_existing_report,
    load_report_entries,
    load_scan_session,
    open_file,
    open_file_location,
    process_file,
    record_error,
    save_nudity_report,
    validate_report_dir,
)


class _TimeoutTestDetector:
    """Small picklable detector used to exercise the process boundary."""

    def detect(self, path: str) -> list[dict[str, object]]:
        if path == "slow":
            time.sleep(10)
        if path == "error":
            raise ValueError("bad file")
        return [{"label": "safe", "path": path}]


def _create_timeout_test_detector() -> _TimeoutTestDetector:
    return _TimeoutTestDetector()

# ---------------------------------------------------------------------------
# create_session_state
# ---------------------------------------------------------------------------

def test_create_session_state_empty():
    state = create_session_state()
    assert isinstance(state, dict)
    assert "results" in state


def test_create_session_state_with_config():
    state = create_session_state(scan_config={"source_folder": "/tmp", "model_name": "nudenet",
                                               "threshold_percent": 60.0, "theme_mode": "system"},
                                  results=[])
    assert state["scan_config"]["source_folder"] == "/tmp"


# ---------------------------------------------------------------------------
# get_session_path / get_report_path / load_report_entries / load_scan_session
# ---------------------------------------------------------------------------

def test_get_session_path_returns_json(tmp_path):
    report = str(tmp_path / "nudity_report.xlsx")
    session = get_session_path(report)
    assert session.endswith(".json")


def test_get_report_path_contains_xlsx(tmp_path):
    path = get_report_path(str(tmp_path))
    assert path.endswith(".xlsx")


def test_load_report_entries_missing_file():
    entries = load_report_entries("/nonexistent/path.xlsx")
    assert entries == []


def test_load_scan_session_missing_file():
    # Should return an empty/default session without raising
    state = load_scan_session("/nonexistent/report.xlsx")
    assert isinstance(state, dict)


# ---------------------------------------------------------------------------
# save_nudity_report / load_existing_report
# ---------------------------------------------------------------------------

def test_save_and_load_report(tmp_path):
    report_path = str(tmp_path / "report.xlsx")
    data = [
        {
            "file": str(tmp_path / "img.jpg"),
            "media_type": "image",
            "model_name": "nudenet",
            "threshold_percent": 60.0,
            "confidence_percent": 0.0,
            "nudity_detected": False,
            "detected_classes": "[]",
            "thumbnail": "",
            "date_classified": "2024-01-01 00:00:00",
        }
    ]
    save_nudity_report(data, report_path)
    assert os.path.exists(report_path)

    existing = load_existing_report(report_path)
    assert isinstance(existing, set)


# ---------------------------------------------------------------------------
# validate_report_dir
# ---------------------------------------------------------------------------

def test_validate_report_dir_valid(tmp_path):
    ok, msg = validate_report_dir(str(tmp_path))
    assert ok is True
    assert msg == ""


def test_validate_report_dir_empty():
    ok, msg = validate_report_dir("")
    assert ok is False


# ---------------------------------------------------------------------------
# detect_media_type_utils
# ---------------------------------------------------------------------------

def test_detect_media_type_utils_image(monkeypatch):
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "image/jpeg",
    )
    assert detect_media_type_utils("photo.jpg") == "image"


def test_detect_media_type_utils_video(monkeypatch):
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "video/mp4",
    )
    assert detect_media_type_utils("clip.mp4") == "video"


def test_detect_media_type_utils_unknown():
    assert detect_media_type_utils("file.pdf") == "unknown"


# ---------------------------------------------------------------------------
# detect_with_timeout
# ---------------------------------------------------------------------------

def test_detect_with_timeout_success():
    detector = RestartableDetectionPool(
        _create_timeout_test_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        result = detect_with_timeout(detector, "dummy.jpg", timeout_seconds=5)
        assert result == [{"label": "safe", "path": "dummy.jpg"}]
    finally:
        detector.close()


def test_detect_with_timeout_raises_on_detector_error():
    detector = RestartableDetectionPool(
        _create_timeout_test_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        with pytest.raises(RemoteDetectionError, match="ValueError.*bad file"):
            detect_with_timeout(detector, "error", timeout_seconds=5)
        assert detect_with_timeout(detector, "dummy.jpg", timeout_seconds=5) == [
            {"label": "safe", "path": "dummy.jpg"}
        ]
    finally:
        detector.close()


def test_detect_with_timeout_raises_timeout():
    detector = RestartableDetectionPool(
        _create_timeout_test_detector, worker_count=1, startup_timeout_seconds=5
    )
    try:
        with pytest.raises(TimeoutError):
            detect_with_timeout(detector, "slow", timeout_seconds=1)
        assert detector._workers[0] is None
    finally:
        detector.close()


# ---------------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------------

def test_open_file_missing():
    ok, msg = open_file("/nonexistent/file.jpg")
    assert ok is False
    assert "does not exist" in msg


def test_open_file_existing(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ok, msg = open_file(str(f))
    assert ok is True


# ---------------------------------------------------------------------------
# delete_file_safely
# ---------------------------------------------------------------------------

def test_delete_file_safely_missing():
    ok, msg = delete_file_safely("/nonexistent/file.jpg")
    assert ok is False


def test_delete_file_safely_existing(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    # Patch send2trash to be None to use os.remove fallback
    with patch("src.core.utils.send2trash", None):
        ok, msg = delete_file_safely(str(f))
    assert ok is True
    assert not f.exists()


def test_delete_file_safely_with_trash(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    mock_trash = MagicMock()
    with patch("src.core.utils.send2trash", mock_trash):
        ok, msg = delete_file_safely(str(f))
    assert ok is True
    mock_trash.assert_called_once_with(str(f))


# ---------------------------------------------------------------------------
# open_file_location
# ---------------------------------------------------------------------------

def test_open_file_location_existing_dir(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ok, msg = open_file_location(str(tmp_path))
    assert ok is True


def test_open_file_location_existing_file(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ok, msg = open_file_location(str(f))
    assert ok is True


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------

def test_process_file_image(tmp_path, monkeypatch):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "image/jpeg",
    )
    image_cb = MagicMock()
    video_cb = MagicMock()
    process_file(str(f), image_cb, video_cb)
    image_cb.assert_called_once_with(str(f))
    video_cb.assert_not_called()


def test_process_file_video(tmp_path, monkeypatch):
    f = tmp_path / "test.mp4"
    f.write_bytes(b"data")
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "video/mp4",
    )
    image_cb = MagicMock()
    video_cb = MagicMock()
    process_file(str(f), image_cb, video_cb)
    video_cb.assert_called_once_with(str(f))
    image_cb.assert_not_called()


def test_process_file_unsupported(tmp_path):
    f = tmp_path / "test.pdf"
    f.write_bytes(b"data")
    image_cb = MagicMock()
    video_cb = MagicMock()
    process_file(str(f), image_cb, video_cb)
    image_cb.assert_not_called()
    video_cb.assert_not_called()


# ---------------------------------------------------------------------------
# count_supported_files
# ---------------------------------------------------------------------------

def test_count_supported_files(tmp_path, monkeypatch):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")

    def fake_from_file(path, mime=True):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "text/plain"
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file", fake_from_file,
    )
    count = count_supported_files(str(tmp_path))
    assert count == 2


def test_count_supported_files_empty(tmp_path):
    assert count_supported_files(str(tmp_path)) == 0


def test_count_supported_files_with_file_list(tmp_path, monkeypatch):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")

    def fake_from_file(path, mime=True):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "text/plain"
    monkeypatch.setattr("src.processing.media_processor.magic.from_file", fake_from_file)

    file_list = [str(tmp_path / "a.jpg"), str(tmp_path / "b.mp4"), str(tmp_path / "c.txt")]
    count = count_supported_files(str(tmp_path), file_list=file_list)
    assert count == 2


def test_count_supported_files_file_list_empty(tmp_path):
    count = count_supported_files(str(tmp_path), file_list=[])
    assert count == 0


# ---------------------------------------------------------------------------
# classify_files_in_folder
# ---------------------------------------------------------------------------

def test_classify_files_in_folder_basic(tmp_path, monkeypatch):
    from src.core.utils import classify_files_in_folder

    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")

    def fake_from_file(path, mime=True):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "text/plain"
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file", fake_from_file,
    )

    image_cb = MagicMock()
    video_cb = MagicMock()
    classify_files_in_folder(str(tmp_path), image_cb, video_cb, worker_count=2)

    assert image_cb.call_count == 1
    assert video_cb.call_count == 1


def test_classify_files_in_folder_invalid_worker_count(tmp_path):
    from src.core.utils import classify_files_in_folder

    with pytest.raises(ValueError, match="worker_count must be at least 1"):
        classify_files_in_folder(str(tmp_path), MagicMock(), MagicMock(), worker_count=0)


def test_classify_files_in_folder_with_file_list(tmp_path, monkeypatch):
    from src.core.utils import classify_files_in_folder

    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")

    def fake_from_file(path, mime=True):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "text/plain"
    monkeypatch.setattr("src.processing.media_processor.magic.from_file", fake_from_file)

    image_cb = MagicMock()
    video_cb = MagicMock()
    file_list = [str(tmp_path / "a.jpg"), str(tmp_path / "b.mp4")]
    classify_files_in_folder(str(tmp_path), image_cb, video_cb, worker_count=2, file_list=file_list)

    assert image_cb.call_count == 1
    assert video_cb.call_count == 1


def test_classify_files_in_folder_single_walk_same_as_double_walk(tmp_path, monkeypatch):
    """Regression: single walk via file_list must produce same results as two separate walks."""
    from src.core.utils import classify_files_in_folder, count_supported_files

    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")

    def fake_from_file(path, mime=True):
        if path.endswith(".jpg"):
            return "image/jpeg"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "text/plain"
    monkeypatch.setattr("src.processing.media_processor.magic.from_file", fake_from_file)

    # Two-walk approach (old behaviour)
    count_old = count_supported_files(str(tmp_path))
    image_cb_old = MagicMock()
    video_cb_old = MagicMock()
    classify_files_in_folder(str(tmp_path), image_cb_old, video_cb_old, worker_count=2)
    old_image_calls = image_cb_old.call_count
    old_video_calls = video_cb_old.call_count

    # Single-walk approach (new behaviour)
    all_files = []
    for root, _, files in os.walk(str(tmp_path)):
        for file_name in files:
            all_files.append(os.path.join(root, file_name))
    count_new = count_supported_files(str(tmp_path), file_list=all_files)
    image_cb_new = MagicMock()
    video_cb_new = MagicMock()
    classify_files_in_folder(str(tmp_path), image_cb_new, video_cb_new, worker_count=2, file_list=all_files)

    assert count_new == count_old
    assert image_cb_new.call_count == old_image_calls
    assert video_cb_new.call_count == old_video_calls


# ---------------------------------------------------------------------------
# get_thumbnail (delegates to ThumbnailGenerator)
# ---------------------------------------------------------------------------

def test_get_thumbnail_nonexistent():
    result = get_thumbnail("/nonexistent/file.jpg")
    assert result is None


# ---------------------------------------------------------------------------
# handle_results with nudity_detected=True (exercises thumbnail path)
# ---------------------------------------------------------------------------

def test_handle_results_nudity_detected(tmp_path):
    session = ScanSession()
    with patch("src.core.utils.ThumbnailGenerator.generate", return_value=None):
        entry = handle_results(
            file_path=str(tmp_path / "nude.jpg"),
            nudity_detected=True,
            raw_result=[{"class": "EXPOSED_BREAST_F", "score": 0.9}],
            session=session,
            confidence_score=0.9,
            media_type="image",
            model_name="nudenet",
            threshold_percent=60.0,
            report_dir=str(tmp_path),
        )
    assert entry["nudity_detected"] is True
    assert len(session.get_results()) == 1


# ---------------------------------------------------------------------------
# handle_results checkpoint writer: creation, error propagation, periodicity,
# concurrent registry access
# ---------------------------------------------------------------------------

def _wait_until(predicate, timeout=5.0, interval=0.01):
    """Poll *predicate* until it becomes truthy or *timeout* seconds elapse.

    The checkpoint writer thread never calls ``Queue.task_done()``, so
    ``Queue.join()`` would block forever; polling is the only safe way to wait
    for asynchronous writer progress.

    Args:
        predicate: Zero-argument callable whose truthy return means the
            expected condition has been reached.
        timeout: Maximum number of seconds to keep polling.
        interval: Seconds to sleep between polls.

    Returns:
        The final predicate result (True on success, False on timeout).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _shutdown_checkpoint_writer(session, timeout=2.0):
    """Stop *session*'s checkpoint writer thread via the ``None`` sentinel.

    Production code never sends the sentinel (src/core/utils.py:621-622), so a
    writer thread would otherwise linger for the process lifetime. Every test
    must call this to avoid leaking daemon threads across tests.

    Args:
        session: ScanSession whose checkpoint writer should be stopped.
        timeout: Maximum seconds to wait for the writer thread to exit.
    """
    writer_state = _checkpoint_writers.get(session)
    if writer_state is None:
        return
    writer_state['queue'].put(None)
    writer_state['thread'].join(timeout=timeout)


def _make_handle_kwargs(tmp_path, idx, session):
    """Build the ``handle_results`` keyword set for a synthetic result.

    ``nudity_detected=False`` keeps thumbnail generation and report-directory
    creation out of the test path, and ``media_type`` is pinned so no file-type
    probing runs against a non-existent file.

    Args:
        tmp_path: Pytest ``tmp_path`` fixture, used for file paths and report_dir.
        idx: Index giving each synthetic file a distinct path.
        session: ScanSession the result is appended to.

    Returns:
        dict of keyword arguments for ``handle_results``.
    """
    return {
        'file_path': str(tmp_path / f'file_{idx}.jpg'),
        'nudity_detected': False,
        'raw_result': [],
        'session': session,
        'confidence_score': 0.0,
        'media_type': 'image',
        'model_name': 'nudenet',
        'threshold_percent': 60.0,
        'report_dir': str(tmp_path),
    }


def _make_recording_save(save_calls, delay=0.0):
    """Return a fake ``save_entries`` that records ``(len(entries), path)``.

    Args:
        save_calls: List the recorded ``(length, path)`` tuples are appended to.
        delay: Optional seconds to sleep before recording, so the writer
            thread's progress is observable by a test.

    Returns:
        Callable suitable as a ``save_entries`` side effect.
    """
    def _save(entries, path):
        if delay:
            time.sleep(delay)
        save_calls.append((len(entries), path))
        return True

    return _save


class _ThreadFactory:
    """Callable stand-in for ``threading.Thread`` that records constructions."""

    def __init__(self, real_thread):
        self._real_thread = real_thread
        self.created = []

    def __call__(self, *args, **kwargs):
        thread = self._real_thread(*args, **kwargs)
        self.created.append(thread)
        return thread


# --- AC-1: writer creation -------------------------------------------------

def test_no_checkpoint_writer_before_500_boundary(tmp_path):
    """No checkpoint writer is registered until the 500th result is appended."""
    session = ScanSession()
    save_calls = []
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(499):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))
        assert save_calls == []
        assert _checkpoint_writers.get(session) is None
    finally:
        _shutdown_checkpoint_writer(session)


def test_checkpoint_writer_created_at_500_boundary(tmp_path):
    """The checkpoint writer is created lazily at the 500-entry boundary.

    Deviation from the issue's literal wording: the writer is NOT created on the
    first ``nudity_detected=True`` result. ``_get_or_create_checkpoint_writer``
    is only reached from the ``count % 500 == 0`` branch of ``handle_results``
    (src/core/utils.py:714-718), so it appears on the 500th result of any kind.
    """
    session = ScanSession()
    save_calls = []
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(499):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))
            assert _checkpoint_writers.get(session) is None

            handle_results(**_make_handle_kwargs(tmp_path, 499, session))

            state = _checkpoint_writers.get(session)
            assert state is not None
            assert set(state.keys()) == {'queue', 'errors', 'thread'}
            assert state['thread'].name == 'checkpoint-writer'
            assert state['thread'].daemon is True
            assert state['thread'].is_alive()
            assert state['errors'] == []
            assert _wait_until(lambda: len(save_calls) == 1)
    finally:
        _shutdown_checkpoint_writer(session)


def test_checkpoint_writer_lookup_is_idempotent(tmp_path):
    """Repeated lookups return the identical writer state dict and thread object."""
    session = ScanSession()
    try:
        first = _get_or_create_checkpoint_writer(session)
        second = _get_or_create_checkpoint_writer(session)
        assert second is first
        assert second['thread'] is first['thread']
        assert _checkpoint_writers.get(session) is first
    finally:
        _shutdown_checkpoint_writer(session)


# --- AC-2: error propagation ----------------------------------------------

def test_checkpoint_writer_error_is_reraised(tmp_path):
    """A failure recorded by the writer thread is re-raised on demand.

    Production ``ReportManager.save_entries`` swallows every exception and
    returns ``False`` (src/reporting/report_manager.py:198-200), so the writer's
    ``except Exception`` (src/core/utils.py:626-628) is reachable in production
    only when ``save_entries`` itself raises. This test simulates that by
    patching ``save_entries`` to raise; it does not verify the issue's stated
    disk-full failure mode end to end.
    """
    session = ScanSession()

    def failing_save(entries, path):
        raise RuntimeError('disk full')

    try:
        with patch('src.core.utils.ReportManager.save_entries', side_effect=failing_save):
            for i in range(500):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))

            state = _checkpoint_writers.get(session)
            assert state is not None
            assert _wait_until(lambda: len(state['errors']) == 1)

            with pytest.raises(RuntimeError, match='disk full'):
                _raise_checkpoint_writer_error(session)
    finally:
        _shutdown_checkpoint_writer(session)


def test_handle_results_reraises_checkpoint_error_before_append(tmp_path):
    """The next handle_results call re-raises a stored writer error pre-append.

    The error is raised at the pre-append check (src/core/utils.py:682), so the
    session's result count is left unchanged. See
    ``test_checkpoint_writer_error_is_reraised`` for why ``save_entries`` is
    patched to raise instead of relying on a real save failure.
    """
    session = ScanSession()

    def failing_save(entries, path):
        raise RuntimeError('disk full')

    try:
        with patch('src.core.utils.ReportManager.save_entries', side_effect=failing_save):
            for i in range(500):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))

            state = _checkpoint_writers.get(session)
            assert _wait_until(lambda: len(state['errors']) == 1)

            count_before = len(session.get_results())
            with pytest.raises(RuntimeError, match='disk full'):
                handle_results(**_make_handle_kwargs(tmp_path, 9999, session))
            assert len(session.get_results()) == count_before
    finally:
        _shutdown_checkpoint_writer(session)


def test_raise_checkpoint_writer_error_without_writer_is_silent(tmp_path):
    """A session with no registered writer produces no error."""
    session = ScanSession()
    assert _checkpoint_writers.get(session) is None
    assert _raise_checkpoint_writer_error(session) is None


def test_raise_checkpoint_writer_error_without_errors_is_silent(tmp_path):
    """A writer that has only saved successfully produces no error."""
    session = ScanSession()
    save_calls = []
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(500):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))

            state = _checkpoint_writers.get(session)
            assert state is not None
            assert _wait_until(lambda: len(save_calls) == 1)
            assert state['errors'] == []
            assert _raise_checkpoint_writer_error(session) is None
    finally:
        _shutdown_checkpoint_writer(session)


# --- AC-3: periodic save trigger -------------------------------------------

def test_no_checkpoint_save_below_500(tmp_path):
    """No checkpoint save fires for the first 499 results."""
    session = ScanSession()
    save_calls = []
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(499):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))
        assert save_calls == []
    finally:
        _shutdown_checkpoint_writer(session)


def test_checkpoint_saves_at_every_500_boundary(tmp_path):
    """Exactly one save fires per 500 results, with snapshots 500/1000/1500.

    The loop is sequential and single-threaded, so the snapshot lengths are
    deterministic.
    """
    session = ScanSession()
    save_calls = []
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(1500):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))
            assert _wait_until(lambda: len(save_calls) == 3)
        assert [length for length, _ in save_calls] == [500, 1000, 1500]
    finally:
        _shutdown_checkpoint_writer(session)


def test_checkpoint_uses_report_path_for_report_dir(tmp_path):
    """Each checkpoint is handed the path returned by get_report_path(report_dir)."""
    session = ScanSession()
    save_calls = []
    expected_path = get_report_path(str(tmp_path))
    try:
        with patch('src.core.utils.ReportManager.save_entries',
                   side_effect=_make_recording_save(save_calls)):
            for i in range(500):
                handle_results(**_make_handle_kwargs(tmp_path, i, session))
            assert _wait_until(lambda: len(save_calls) == 1)
        assert [path for _, path in save_calls] == [expected_path]
    finally:
        _shutdown_checkpoint_writer(session)


# --- AC-4: concurrent registry access --------------------------------------

def test_concurrent_writer_creation_returns_single_writer(tmp_path):
    """Simultaneous callers create exactly one writer and share its state dict."""
    session = ScanSession()
    barrier = threading.Barrier(8)
    results = []
    worker_errors = []
    results_lock = threading.Lock()
    factory = _ThreadFactory(threading.Thread)

    def worker():
        barrier.wait()
        try:
            state = _get_or_create_checkpoint_writer(session)
        except Exception as exc:
            with results_lock:
                worker_errors.append(exc)
            return
        with results_lock:
            results.append(state)

    try:
        with patch('src.core.utils.Thread', factory):
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        assert not worker_errors
        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 8
        assert all(state is results[0] for state in results)
        assert len(factory.created) == 1
        assert factory.created[0].name == 'checkpoint-writer'
        assert _checkpoint_writers.get(session) is results[0]
    finally:
        _shutdown_checkpoint_writer(session)


def test_concurrent_handle_results_single_writer(tmp_path):
    """8 threads x 125 results yield one writer, two checkpoints, no errors."""
    thread_count = 8
    entries_per_thread = 125
    session = ScanSession()
    save_calls = []
    worker_errors = []
    errors_lock = threading.Lock()
    factory = _ThreadFactory(threading.Thread)

    def slow_save(entries, path):
        time.sleep(0.05)
        save_calls.append((len(entries), path))
        return True

    def worker(thread_idx):
        try:
            for i in range(entries_per_thread):
                handle_results(**_make_handle_kwargs(tmp_path, thread_idx * 1000 + i, session))
        except Exception as exc:
            with errors_lock:
                worker_errors.append(exc)

    try:
        # The patch must stay active while the writer thread drains the queue:
        # the writer is a daemon that can still be processing a checkpoint after
        # the worker threads have joined, and an exited patch would hand that
        # checkpoint to the real save_entries.
        with patch('src.core.utils.ReportManager.save_entries', side_effect=slow_save), \
                patch('src.core.utils.Thread', factory):
            threads = [threading.Thread(target=worker, args=(idx,)) for idx in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

            assert all(not thread.is_alive() for thread in threads)
            assert worker_errors == []
            # The second save may still be in flight when the workers join, so
            # poll for it rather than asserting immediately.
            assert _wait_until(lambda: len(save_calls) == 2, timeout=10.0)

            # Snapshot lengths are asserted order-independently: queue delivery
            # order is not deterministic and the 500-boundary snapshot is taken
            # after add_result released the session lock, so it can exceed 500.
            lengths = [length for length, _ in save_calls]
            assert min(lengths) >= 500
            assert max(lengths) == 1000

            state = _checkpoint_writers.get(session)
            assert state is not None
            assert state['errors'] == []
            assert state['thread'].name == 'checkpoint-writer'
            assert len(factory.created) == 1
            assert _get_or_create_checkpoint_writer(session) is state
    finally:
        _shutdown_checkpoint_writer(session)


# ---------------------------------------------------------------------------
# record_error (new — issue #89)
# ---------------------------------------------------------------------------

def test_record_error_default_model_name(tmp_path):
    """record_error default model_name is MODEL_NUDENET."""
    session = ScanSession()
    file_path = str(tmp_path / "test.jpg")
    record_error(file_path, "some error", 60.0, session)
    results = session.get_results()
    assert len(results) == 1
    assert results[0].model_name == constants.MODEL_NUDENET
    assert results[0].detected_classes.startswith("ERROR:")


def test_record_error_explicit_helloz_model_name(tmp_path):
    """record_error with MODEL_HELLOZ_NSFW produces entry with correct model_name."""
    session = ScanSession()
    file_path = str(tmp_path / "test.jpg")
    record_error(file_path, "some error", 60.0, session, model_name=constants.MODEL_HELLOZ_NSFW)
    results = session.get_results()
    assert len(results) == 1
    assert results[0].model_name == constants.MODEL_HELLOZ_NSFW
    assert results[0].detected_classes.startswith("ERROR:")

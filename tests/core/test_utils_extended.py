"""Extended tests for src/core/utils.py — coverage for uncovered utility
functions: file operations, classify_files_in_folder, detect_with_timeout,
process_file, count_supported_files, handle_results edge cases, etc."""
import os
import sys
import tempfile
import threading
from unittest.mock import MagicMock, patch
import pytest

sys.modules.setdefault("nudenet", MagicMock())

from src.core.utils import (
    normalize_threshold,
    make_scan_config,
    create_session_state,
    get_detected_results,
    get_report_path,
    get_session_path,
    save_nudity_report,
    load_scan_session,
    load_existing_report,
    load_report_entries,
    validate_report_dir,
    open_file,
    open_file_location,
    delete_file_safely,
    process_file,
    count_supported_files,
    classify_files_in_folder,
    handle_results,
    detect_with_timeout,
    detect_media_type_utils,
    get_thumbnail,
    generate_image_thumbnail,
    generate_video_thumbnail,
)
from src.core.scan_session import ScanSession
from src.core.models import ReportEntry, ScanConfig, SessionState
from src.reporting.report_manager import ReportManager


# ---------------------------------------------------------------------------
# get_session_path
# ---------------------------------------------------------------------------

def test_get_session_path_returns_json():
    p = get_session_path("/reports/run/nudity_report.xlsx")
    assert p.endswith("_session.json")


# ---------------------------------------------------------------------------
# save_nudity_report / load_scan_session / load_existing_report
# ---------------------------------------------------------------------------

def test_save_nudity_report_and_load_session(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    entry = ReportEntry(
        file="/a/b.jpg",
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )
    save_nudity_report([entry], report_path)
    session = load_scan_session(report_path)
    assert isinstance(session, dict)


def test_save_nudity_report_with_session_state(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    config = ScanConfig(source_folder="/imgs", model_name="nudenet", threshold_percent=60.0)
    state = SessionState(scan_config=config, results=[])
    save_nudity_report([], report_path, session_state=state.to_dict())
    session = load_scan_session(report_path)
    assert session.get("scan_config", {}).get("source_folder") == "/imgs"


def test_load_existing_report_empty(tmp_path):
    report_path = str(tmp_path / "empty_report.xlsx")
    result = load_existing_report(report_path)
    assert result == set()


def test_load_existing_report_with_entries(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    entry = ReportEntry(
        file="/my/file.jpg",
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )
    ReportManager.save_entries([entry], report_path)
    result = load_existing_report(report_path)
    assert "/my/file.jpg" in result


def test_load_report_entries_roundtrip(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    entry = ReportEntry(
        file="/c/d.jpg",
        media_type="image",
        model_name="nudenet",
        threshold_percent=60.0,
        confidence_percent=0.8,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )
    ReportManager.save_entries([entry], report_path)
    entries = load_report_entries(report_path)
    assert len(entries) == 1
    assert entries[0]["file"] == "/c/d.jpg"


# ---------------------------------------------------------------------------
# validate_report_dir
# ---------------------------------------------------------------------------

def test_validate_report_dir_writable(tmp_path):
    ok, msg = validate_report_dir(str(tmp_path))
    assert ok is True
    assert msg == ""


def test_validate_report_dir_empty():
    ok, msg = validate_report_dir("")
    assert ok is False


# ---------------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------------

def test_open_file_nonexistent_returns_false():
    ok, msg = open_file("/nonexistent/path/file.jpg")
    assert ok is False
    assert "does not exist" in msg


def test_open_file_exists_calls_subprocess(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    with patch("subprocess.run") as mock_run, \
         patch("sys.platform", "linux"):
        mock_run.return_value = MagicMock()
        ok, msg = open_file(str(f))
    assert ok is True


# ---------------------------------------------------------------------------
# open_file_location
# ---------------------------------------------------------------------------

def test_open_file_location_directory(tmp_path):
    with patch("subprocess.run") as mock_run, \
         patch("sys.platform", "linux"):
        mock_run.return_value = MagicMock()
        ok, msg = open_file_location(str(tmp_path))
    assert ok is True


def test_open_file_location_file_path(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hi")
    with patch("subprocess.run") as mock_run, \
         patch("sys.platform", "linux"):
        mock_run.return_value = MagicMock()
        ok, msg = open_file_location(str(f))
    assert ok is True


# ---------------------------------------------------------------------------
# delete_file_safely
# ---------------------------------------------------------------------------

def test_delete_file_safely_nonexistent():
    ok, msg = delete_file_safely("/nonexistent/file.jpg")
    assert ok is False


def test_delete_file_safely_existing(tmp_path):
    f = tmp_path / "to_delete.txt"
    f.write_text("bye")
    ok, msg = delete_file_safely(str(f))
    assert ok is True
    assert not f.exists()


def test_delete_file_safely_directory(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    (d / "file.txt").write_text("content")
    ok, msg = delete_file_safely(str(d))
    assert ok is True


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------

def test_process_file_image_calls_classify_image(tmp_path):
    f = tmp_path / "img.jpg"
    f.write_text("fake")
    calls = []
    process_file(str(f), lambda p: calls.append(("img", p)), lambda p: calls.append(("vid", p)))
    assert len(calls) == 1
    assert calls[0][0] == "img"


def test_process_file_video_calls_classify_video(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_text("fake")
    calls = []
    process_file(str(f), lambda p: calls.append(("img", p)), lambda p: calls.append(("vid", p)))
    assert len(calls) == 1
    assert calls[0][0] == "vid"


def test_process_file_unsupported_skipped(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_text("fake")
    calls = []
    process_file(str(f), lambda p: calls.append("img"), lambda p: calls.append("vid"))
    assert calls == []


# ---------------------------------------------------------------------------
# count_supported_files
# ---------------------------------------------------------------------------

def test_count_supported_files(tmp_path):
    (tmp_path / "a.jpg").write_text("x")
    (tmp_path / "b.mp4").write_text("x")
    (tmp_path / "c.txt").write_text("x")
    count = count_supported_files(str(tmp_path))
    assert count == 2


def test_count_supported_files_empty_dir(tmp_path):
    assert count_supported_files(str(tmp_path)) == 0


# ---------------------------------------------------------------------------
# classify_files_in_folder
# ---------------------------------------------------------------------------

def test_classify_files_in_folder_processes_files(tmp_path):
    (tmp_path / "a.jpg").write_text("x")
    (tmp_path / "b.jpg").write_text("x")
    processed = []
    classify_files_in_folder(
        str(tmp_path),
        lambda p: processed.append(p),
        lambda p: processed.append(p),
        worker_count=2,
    )
    assert len(processed) == 2


def test_classify_files_in_folder_invalid_worker_count(tmp_path):
    with pytest.raises(ValueError, match="worker_count"):
        classify_files_in_folder(str(tmp_path), lambda p: None, lambda p: None, worker_count=0)


def test_classify_files_in_folder_empty_dir(tmp_path):
    processed = []
    classify_files_in_folder(
        str(tmp_path),
        lambda p: processed.append(p),
        lambda p: processed.append(p),
    )
    assert processed == []


# ---------------------------------------------------------------------------
# detect_with_timeout
# ---------------------------------------------------------------------------

def test_detect_with_timeout_success():
    detector = MagicMock()
    detector.detect.return_value = [{"label": "test"}]
    result = detect_with_timeout(detector, "/fake/file.jpg", timeout_seconds=5)
    assert result == [{"label": "test"}]


def test_detect_with_timeout_raises_on_timeout():
    import time

    def slow_detect(file_path):
        time.sleep(10)
        return []

    detector = MagicMock()
    detector.detect.side_effect = slow_detect
    with pytest.raises(TimeoutError):
        detect_with_timeout(detector, "/fake/file.jpg", timeout_seconds=1)


def test_detect_with_timeout_propagates_exception():
    detector = MagicMock()
    detector.detect.side_effect = ValueError("bad file")
    with pytest.raises(ValueError, match="bad file"):
        detect_with_timeout(detector, "/fake/file.jpg", timeout_seconds=5)


# ---------------------------------------------------------------------------
# detect_media_type_utils
# ---------------------------------------------------------------------------

def test_detect_media_type_utils_image():
    assert detect_media_type_utils("photo.png") == "image"


def test_detect_media_type_utils_video():
    assert detect_media_type_utils("clip.avi") == "video"


# ---------------------------------------------------------------------------
# generate_image_thumbnail / generate_video_thumbnail / get_thumbnail
# ---------------------------------------------------------------------------

def test_generate_image_thumbnail_nonexistent():
    result = generate_image_thumbnail("/nonexistent.jpg")
    assert result is None


def test_generate_video_thumbnail_nonexistent():
    result = generate_video_thumbnail("/nonexistent.mp4")
    assert result is None


def test_get_thumbnail_nonexistent():
    result = get_thumbnail("/nonexistent.jpg")
    assert result is None


# ---------------------------------------------------------------------------
# handle_results — edge cases
# ---------------------------------------------------------------------------

def test_handle_results_with_nudity_detected_false(tmp_path):
    session = ScanSession()
    handle_results(
        file_path=str(tmp_path / "clean.jpg"),
        nudity_detected=False,
        raw_result=[],
        session=session,
        report_dir=str(tmp_path),
    )
    results = session.get_results()
    assert len(results) == 1
    assert results[0].nudity_detected is False


def test_handle_results_string_raw_result(tmp_path):
    session = ScanSession()
    handle_results(
        file_path=str(tmp_path / "img.jpg"),
        nudity_detected=False,
        raw_result="some string result",
        session=session,
        report_dir=str(tmp_path),
    )
    results = session.get_results()
    assert results[0].detected_classes == "some string result"


def test_handle_results_with_model_name(tmp_path):
    session = ScanSession()
    handle_results(
        file_path=str(tmp_path / "img.jpg"),
        nudity_detected=False,
        raw_result=[],
        session=session,
        model_name="helloz_nsfw",
        confidence_score=0.75,
        threshold_percent=60.0,
        report_dir=str(tmp_path),
    )
    results = session.get_results()
    assert results[0].model_name == "helloz_nsfw"
    assert results[0].confidence_percent == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# create_session_state
# ---------------------------------------------------------------------------

def test_create_session_state_with_dict_config():
    state = create_session_state(
        scan_config={"source_folder": "/test", "model_name": "nudenet", "threshold_percent": 60.0},
        results=[],
    )
    assert state["scan_config"]["source_folder"] == "/test"


def test_create_session_state_empty():
    state = create_session_state()
    assert isinstance(state, dict)
    assert "scan_config" in state


# ---------------------------------------------------------------------------
# save_nudity_report — dict vs object items (line 117)
# ---------------------------------------------------------------------------

def test_save_nudity_report_with_dict_entries(tmp_path):
    """save_nudity_report handles dict entries (converts to ReportEntry)."""
    report_path = str(tmp_path / "report.xlsx")
    dict_entry = {
        "file": "/a/b.jpg",
        "media_type": "image",
        "model_name": "nudenet",
        "threshold_percent": 60.0,
        "confidence_percent": 0.8,
        "nudity_detected": True,
        "detected_classes": "[]",
        "thumbnail": "",
        "date_classified": "2025-01-01",
    }
    save_nudity_report([dict_entry], report_path)
    assert os.path.exists(report_path)


def test_save_nudity_report_with_report_entry_objects(tmp_path):
    """save_nudity_report handles ReportEntry objects directly."""
    report_path = str(tmp_path / "report.xlsx")
    entry = ReportEntry(
        file="/c/d.jpg",
        media_type="image",
        model_name="nudenet",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )
    save_nudity_report([entry], report_path)
    assert os.path.exists(report_path)


# ---------------------------------------------------------------------------
# open_file — win32 and darwin branches (lines 222, 224)
# ---------------------------------------------------------------------------

def test_open_file_win32(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hi")
    import os as _os
    with patch("sys.platform", "win32"), \
         patch.dict("os.__dict__", {"startfile": MagicMock()}) as mock_dict:
        ok, _ = open_file(str(f))
    assert ok is True


def test_open_file_darwin(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hi")
    with patch("sys.platform", "darwin"), \
         patch("subprocess.run") as mock_run:
        ok, _ = open_file(str(f))
    assert ok is True
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# open_file — exception path (lines 228-231)
# ---------------------------------------------------------------------------

def test_open_file_exception_returns_false(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hi")
    with patch("sys.platform", "linux"), \
         patch("subprocess.run", side_effect=OSError("no xdg")):
        ok, msg = open_file(str(f))
    assert ok is False
    assert "Could not open" in msg


# ---------------------------------------------------------------------------
# delete_file_safely — send2trash path (lines 248-249)
# ---------------------------------------------------------------------------

def test_delete_file_safely_uses_send2trash(tmp_path):
    f = tmp_path / "trash_me.txt"
    f.write_text("content")
    import src.core.utils as utils_module
    mock_trash = MagicMock()
    original = utils_module.send2trash
    utils_module.send2trash = mock_trash
    try:
        ok, msg = delete_file_safely(str(f))
    finally:
        utils_module.send2trash = original
    assert ok is True
    mock_trash.assert_called_once_with(str(f))


# ---------------------------------------------------------------------------
# delete_file_safely — exception path (lines 257-259)
# ---------------------------------------------------------------------------

def test_delete_file_safely_exception_returns_false(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    import src.core.utils as utils_module
    original = utils_module.send2trash
    utils_module.send2trash = None
    try:
        with patch("os.remove", side_effect=OSError("permission denied")):
            ok, msg = delete_file_safely(str(f))
    finally:
        utils_module.send2trash = original
    assert ok is False


# ---------------------------------------------------------------------------
# open_file_location — win32/darwin/exception paths (lines 273-285)
# ---------------------------------------------------------------------------

def test_open_file_location_empty_dirname(tmp_path):
    """open_file_location with a bare filename (no dir) uses '.'."""
    with patch("sys.platform", "linux"), \
         patch("subprocess.run"):
        ok, _ = open_file_location("just_a_filename.jpg")
    assert ok is True


def test_open_file_location_win32(tmp_path):
    d = tmp_path
    import os as _os
    with patch("sys.platform", "win32"), \
         patch.dict("os.__dict__", {"startfile": MagicMock()}):
        ok, _ = open_file_location(str(d))
    assert ok is True


def test_open_file_location_darwin(tmp_path):
    d = tmp_path
    with patch("sys.platform", "darwin"), \
         patch("subprocess.run") as mock_run:
        ok, _ = open_file_location(str(d))
    assert ok is True
    mock_run.assert_called_once()


def test_open_file_location_exception(tmp_path):
    d = tmp_path
    with patch("sys.platform", "linux"), \
         patch("subprocess.run", side_effect=OSError("error")):
        ok, msg = open_file_location(str(d))
    assert ok is False


# ---------------------------------------------------------------------------
# classify_files_in_folder — worker error handling (lines 362-363)
# ---------------------------------------------------------------------------

def test_classify_files_in_folder_exception_in_worker(tmp_path):
    """Worker exception does not crash classify_files_in_folder."""
    (tmp_path / "a.jpg").write_text("x")

    def bad_classifier(p):
        raise RuntimeError("classifier failed")

    classify_files_in_folder(str(tmp_path), bad_classifier, bad_classifier, worker_count=1)
    # Should complete without raising


# ---------------------------------------------------------------------------
# handle_results — periodic save (line 471)
# ---------------------------------------------------------------------------

def test_handle_results_periodic_save_at_500(tmp_path):
    """handle_results calls save_entries when count is multiple of 500."""
    session = ScanSession()
    with patch("src.core.utils.ReportManager.save_entries") as mock_save:
        # Add 499 entries first (won't trigger)
        for i in range(499):
            session.add_result(ReportEntry(
                file=f"/img{i}.jpg", media_type="image", model_name="test",
                threshold_percent=60.0, confidence_percent=0.0,
                nudity_detected=False, detected_classes="[]",
            ))
        # The 500th call (count == 500) should trigger save
        handle_results(
            file_path=str(tmp_path / "img500.jpg"),
            nudity_detected=False,
            raw_result=[],
            session=session,
            report_dir=str(tmp_path),
        )
    mock_save.assert_called()


# ---------------------------------------------------------------------------
# count_supported_files — walked subdirectories (lines 395-396)
# ---------------------------------------------------------------------------

def test_count_supported_files_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.jpg").write_text("x")
    (sub / "b.mp4").write_text("x")
    (sub / "c.txt").write_text("x")
    count = count_supported_files(str(tmp_path))
    assert count == 2


# ---------------------------------------------------------------------------
# classify_files_in_folder — worker timeout warning (line 407)
# ---------------------------------------------------------------------------

def test_classify_files_in_folder_hung_worker(tmp_path, monkeypatch):
    """classify_files_in_folder logs warning when a worker stays alive past timeout."""
    import src.core.utils as utils_module
    monkeypatch.setattr(utils_module.constants, "WORKER_THREAD_TIMEOUT", 1)

    (tmp_path / "a.jpg").write_text("x")

    import time
    def slow_classifier(p):
        time.sleep(5)  # longer than 1s timeout

    # Should complete (not hang forever) because join(timeout=1) is used
    classify_files_in_folder(str(tmp_path), slow_classifier, slow_classifier,
                             worker_count=1, worker_timeout=1)
    # Test just verifies it doesn't deadlock


# ---------------------------------------------------------------------------
# handle_results — nudity_detected=True generates thumbnail + creates dir (lines 446-451)
# ---------------------------------------------------------------------------

def test_handle_results_nudity_detected_creates_report_dir(tmp_path):
    report_dir = str(tmp_path / "reports")
    session = ScanSession()
    # Create a fake image file
    img_path = tmp_path / "nude.jpg"
    img_path.write_bytes(b"fake")
    handle_results(
        file_path=str(img_path),
        nudity_detected=True,
        raw_result=[],
        session=session,
        media_type="image",
        report_dir=report_dir,
    )
    assert os.path.isdir(report_dir)


# ---------------------------------------------------------------------------
# handle_results — auto-detect media type when not provided (line 446)
# ---------------------------------------------------------------------------

def test_handle_results_auto_detects_media_type(tmp_path):
    session = ScanSession()
    img_path = tmp_path / "img.jpg"
    img_path.write_bytes(b"fake")
    entry = handle_results(
        file_path=str(img_path),
        nudity_detected=False,
        raw_result=[],
        session=session,
        media_type=None,
        report_dir=str(tmp_path),
    )
    assert entry["media_type"] == "image"

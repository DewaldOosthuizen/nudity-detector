"""Extended tests for src/core/utils.py to boost coverage."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy optional deps before importing source modules
sys.modules.setdefault("nudenet", MagicMock())

from src.core.scan_session import ScanSession
from src.core.utils import (
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
    save_nudity_report,
    validate_report_dir,
)

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

def test_detect_media_type_utils_image():
    assert detect_media_type_utils("photo.jpg") == "image"


def test_detect_media_type_utils_video():
    assert detect_media_type_utils("clip.mp4") == "video"


def test_detect_media_type_utils_unknown():
    assert detect_media_type_utils("file.pdf") == "unknown"


# ---------------------------------------------------------------------------
# detect_with_timeout
# ---------------------------------------------------------------------------

def test_detect_with_timeout_success():
    class FakeDetector:
        def detect(self, path):
            return [{"label": "EXPOSED_BREAST_F", "score": 0.9}]

    result = detect_with_timeout(FakeDetector(), "dummy.jpg", timeout_seconds=5)
    assert result == [{"label": "EXPOSED_BREAST_F", "score": 0.9}]


def test_detect_with_timeout_raises_on_detector_error():
    class ErrorDetector:
        def detect(self, path):
            raise ValueError("bad file")

    with pytest.raises(ValueError, match="bad file"):
        detect_with_timeout(ErrorDetector(), "dummy.jpg", timeout_seconds=5)


def test_detect_with_timeout_raises_timeout():
    import time

    class SlowDetector:
        def detect(self, path):
            time.sleep(10)
            return []

    with pytest.raises(TimeoutError):
        detect_with_timeout(SlowDetector(), "dummy.jpg", timeout_seconds=1)


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
    with patch("subprocess.run"):
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
    with patch("subprocess.run"):
        ok, msg = open_file_location(str(tmp_path))
    assert ok is True


def test_open_file_location_existing_file(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    with patch("subprocess.run"):
        ok, msg = open_file_location(str(f))
    assert ok is True


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------

def test_process_file_image(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_bytes(b"data")
    image_cb = MagicMock()
    video_cb = MagicMock()
    process_file(str(f), image_cb, video_cb)
    image_cb.assert_called_once_with(str(f))
    video_cb.assert_not_called()


def test_process_file_video(tmp_path):
    f = tmp_path / "test.mp4"
    f.write_bytes(b"data")
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

def test_count_supported_files(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")
    count = count_supported_files(str(tmp_path))
    assert count == 2


def test_count_supported_files_empty(tmp_path):
    assert count_supported_files(str(tmp_path)) == 0


# ---------------------------------------------------------------------------
# classify_files_in_folder
# ---------------------------------------------------------------------------

def test_classify_files_in_folder_basic(tmp_path):
    from src.core.utils import classify_files_in_folder

    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "b.mp4").write_bytes(b"")
    (tmp_path / "c.txt").write_bytes(b"")

    image_cb = MagicMock()
    video_cb = MagicMock()
    classify_files_in_folder(str(tmp_path), image_cb, video_cb, worker_count=2)

    assert image_cb.call_count == 1
    assert video_cb.call_count == 1


def test_classify_files_in_folder_invalid_worker_count(tmp_path):
    from src.core.utils import classify_files_in_folder

    with pytest.raises(ValueError, match="worker_count must be at least 1"):
        classify_files_in_folder(str(tmp_path), MagicMock(), MagicMock(), worker_count=0)


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

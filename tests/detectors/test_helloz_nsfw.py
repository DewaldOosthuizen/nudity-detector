"""
Tests for src/detectors/helloz_nsfw.py
Targets: lines 96-97, 117-118, 125, 145-146, 162-164.
"""
import sys
import logging
import pytest
from unittest.mock import MagicMock, patch, call

sys.modules.setdefault("nudenet", MagicMock())
# Stub gi before any src import
def _ensure_gi_stubs():
    if "gi" in sys.modules:
        return
    gi_mock = MagicMock()
    sys.modules["gi"] = gi_mock
    sys.modules["gi.repository"] = gi_mock.repository
    class _GObjectBase:
        def __init__(self, **kwargs): pass
    gobject_mod = MagicMock()
    gobject_mod.Object = _GObjectBase
    sys.modules["gi.repository.GObject"] = gobject_mod
    for mod in ["gi.repository.Gtk","gi.repository.Gdk","gi.repository.Adw",
                "gi.repository.Gio","gi.repository.GLib","gi.repository.GdkPixbuf","gi.repository.Pango"]:
        sys.modules[mod] = MagicMock()

_ensure_gi_stubs()

import src.detectors.helloz_nsfw as helloz  # noqa: E402
from src.detectors.helloz_nsfw import (  # noqa: E402
    prompt_threshold_percent, extract_frames, _record_error, _post_with_retry
)
from src.core.scan_session import ScanSession  # noqa: E402


# ---------------------------------------------------------------------------
# extract_frames (lines 95-97)
# ---------------------------------------------------------------------------

def test_extract_frames_calls_extractor(tmp_path):
    """extract_frames delegates to FrameExtractor.extract."""
    fake_frames = [str(tmp_path / "frame_0.jpg")]
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = fake_frames

    with patch("src.detectors.helloz_nsfw.FrameExtractor", return_value=mock_extractor) as MockExt:
        result = extract_frames("/fake/video.mp4", frame_rate=5)

    MockExt.assert_called_once()
    mock_extractor.extract.assert_called_once_with("/fake/video.mp4")
    assert result == fake_frames


# ---------------------------------------------------------------------------
# prompt_threshold_percent edge cases
# ---------------------------------------------------------------------------

def test_prompt_threshold_percent_empty_input_returns_default():
    with patch("builtins.input", return_value=""):
        result = prompt_threshold_percent(60.0)
    assert result == 60.0


def test_prompt_threshold_percent_invalid_logs_warning(caplog):
    with caplog.at_level(logging.WARNING), patch("builtins.input", return_value="not_a_number"):
        result = prompt_threshold_percent(60.0)
    assert result == 60.0
    assert any("Invalid threshold" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _record_error
# ---------------------------------------------------------------------------

def test_record_error_adds_entry_to_session():
    session = ScanSession()
    _record_error("/tmp/bad.jpg", ValueError("network error"), "helloz", 60.0, session)
    results = session.get_results()
    assert len(results) == 1
    assert "ERROR" in results[0].detected_classes


# ---------------------------------------------------------------------------
# _post_with_retry
# ---------------------------------------------------------------------------

def test_post_with_retry_success_first_attempt():
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("requests.post", return_value=mock_response) as mock_post:
        result = _post_with_retry("http://fake", files={"file": MagicMock()}, timeout=5, retries=3)
    assert result is mock_response
    assert mock_post.call_count == 1


def test_post_with_retry_retries_on_5xx():
    mock_5xx = MagicMock()
    mock_5xx.status_code = 503
    mock_200 = MagicMock()
    mock_200.status_code = 200

    with patch("requests.post", side_effect=[mock_5xx, mock_200]), \
         patch("time.sleep"):
        result = _post_with_retry("http://fake", files={"file": MagicMock()}, timeout=5, retries=3, backoff=0.01)
    assert result is mock_200


def test_post_with_retry_exhausted_raises():
    import requests as req_mod
    with patch("requests.post", side_effect=req_mod.RequestException("timeout")), \
         patch("time.sleep"):
        with pytest.raises(req_mod.RequestException):
            _post_with_retry("http://fake", files={"file": MagicMock()}, timeout=5, retries=2, backoff=0.01)


# ---------------------------------------------------------------------------
# main() classify_image closure — lines 116-118 (skip already scanned)
# ---------------------------------------------------------------------------

def test_main_classify_image_skips_existing(tmp_path):
    """Verifies the 'already scanned' early-return branch (lines 116-118)."""
    existing_file = str(tmp_path / "existing.jpg")
    open(existing_file, "w").close()  # ensure it exists on disk

    inputs = iter([str(tmp_path), ""])  # folder path, empty threshold

    with patch("builtins.input", side_effect=inputs), \
         patch("src.detectors.helloz_nsfw.get_report_path", return_value=str(tmp_path / "r.xlsx")), \
         patch("src.detectors.helloz_nsfw.load_existing_report", return_value={existing_file}), \
         patch("src.detectors.helloz_nsfw.classify_files_in_folder", return_value=([existing_file], [])), \
         patch("src.detectors.helloz_nsfw.save_nudity_report"), \
         patch("src.detectors.helloz_nsfw.create_session_state", return_value={}), \
         patch("src.detectors.helloz_nsfw._post_with_retry") as mock_post:
        helloz.main()

    # _post_with_retry should NOT have been called for the skipped file
    mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# main() classify_video — lines 144-146 (skip already scanned video)
# ---------------------------------------------------------------------------

def test_main_classify_video_skips_existing(tmp_path):
    """Verifies the 'already scanned' early-return for video (lines 144-146)."""
    existing_video = str(tmp_path / "existing.mp4")
    open(existing_video, "w").close()

    inputs = iter([str(tmp_path), ""])

    with patch("builtins.input", side_effect=inputs), \
         patch("src.detectors.helloz_nsfw.get_report_path", return_value=str(tmp_path / "r.xlsx")), \
         patch("src.detectors.helloz_nsfw.load_existing_report", return_value={existing_video}), \
         patch("src.detectors.helloz_nsfw.classify_files_in_folder", return_value=([], [existing_video])), \
         patch("src.detectors.helloz_nsfw.save_nudity_report"), \
         patch("src.detectors.helloz_nsfw.create_session_state", return_value={}), \
         patch("src.detectors.helloz_nsfw._post_with_retry") as mock_post:
        helloz.main()

    mock_post.assert_not_called()

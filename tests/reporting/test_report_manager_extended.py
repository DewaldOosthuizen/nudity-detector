"""Extended tests for src/reporting/report_manager.py to boost coverage."""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.reporting.report_manager import ReportManager
from src.core.models import ReportEntry, SessionState, ScanConfig


def _make_entry(**kwargs):
    defaults = {
        "file": "/tmp/img.jpg",
        "media_type": "image",
        "model_name": "nudenet",
        "threshold_percent": 60.0,
        "confidence_percent": 0.0,
        "nudity_detected": False,
        "detected_classes": "[]",
        "thumbnail": "",
        "date_classified": "2024-01-01 00:00:00",
    }
    defaults.update(kwargs)
    return ReportEntry.from_dict(defaults)


# ---------------------------------------------------------------------------
# save_entries / load_entries round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_entries(tmp_path):
    report = str(tmp_path / "report.xlsx")
    entries = [_make_entry(file=str(tmp_path / "a.jpg"), nudity_detected=True)]
    result = ReportManager.save_entries(entries, report)
    assert result is True
    assert os.path.exists(report)

    loaded = ReportManager.load_entries(report)
    assert len(loaded) == 1
    assert loaded[0].file == str(tmp_path / "a.jpg")


def test_save_entries_overwrites(tmp_path):
    """Saving twice should overwrite, not append."""
    report = str(tmp_path / "report.xlsx")
    entries1 = [_make_entry(file="/tmp/a.jpg")]
    entries2 = [_make_entry(file="/tmp/b.jpg"), _make_entry(file="/tmp/c.jpg")]
    ReportManager.save_entries(entries1, report)
    ReportManager.save_entries(entries2, report)
    loaded = ReportManager.load_entries(report)
    assert len(loaded) == 2


def test_load_entries_returns_empty_for_empty_xlsx(tmp_path):
    """An xlsx with only a header row and no data returns empty list."""
    import openpyxl
    report = str(tmp_path / "empty.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nudity Report"
    ws.append(["File"])
    wb.save(report)
    loaded = ReportManager.load_entries(report)
    assert loaded == []


# ---------------------------------------------------------------------------
# save_session / load_session round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_session(tmp_path):
    report = str(tmp_path / "report.xlsx")
    session = SessionState(
        scan_config=ScanConfig(source_folder="/tmp"),
        results=[],
    )
    result = ReportManager.save_session(session, report)
    assert result is True

    loaded = ReportManager.load_session(report)
    assert isinstance(loaded, SessionState)
    assert loaded.scan_config.source_folder == "/tmp"


def test_load_session_missing_file():
    loaded = ReportManager.load_session("/nonexistent/report.xlsx")
    assert isinstance(loaded, SessionState)


def test_load_session_from_json(tmp_path):
    """Pass a .json path directly."""
    session = SessionState(scan_config=ScanConfig(source_folder="/data"))
    json_path = str(tmp_path / "sess.json")
    with open(json_path, "w") as f:
        json.dump(session.to_dict(), f)

    loaded = ReportManager.load_session(json_path)
    assert loaded.scan_config.source_folder == "/data"


def test_load_session_corrupt_json(tmp_path):
    """Corrupt JSON falls back to empty SessionState."""
    json_path = str(tmp_path / "corrupt_session.json")
    with open(json_path, "w") as f:
        f.write("{not valid json")

    loaded = ReportManager.load_session(json_path)
    assert isinstance(loaded, SessionState)


# ---------------------------------------------------------------------------
# create_demo_session
# ---------------------------------------------------------------------------

def test_create_demo_session_new_file(tmp_path):
    report = str(tmp_path / "report.xlsx")
    session = SessionState()
    result = ReportManager.create_demo_session(report, session)
    assert result is True
    assert os.path.exists(report)


def test_create_demo_session_existing_file(tmp_path):
    report = str(tmp_path / "report.xlsx")
    # First create
    ReportManager.save_entries([], report)
    session = SessionState(scan_config=ScanConfig(source_folder="/demo"))
    result = ReportManager.create_demo_session(report, session)
    assert result is True


# ---------------------------------------------------------------------------
# _embed_thumbnails — with actual base64 PNG thumbnail
# ---------------------------------------------------------------------------

def test_embed_thumbnails_with_valid_thumbnail(tmp_path):
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    # Generate a valid base64 thumbnail
    img = PILImage.new("RGB", (10, 10), color=(0, 0, 255))
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = __import__("base64").b64encode(buf.getvalue()).decode()

    report = str(tmp_path / "report.xlsx")
    entry = _make_entry(thumbnail=b64)
    result = ReportManager.save_entries([entry], report)
    assert result is True


# ---------------------------------------------------------------------------
# validate_report_dir — system protected
# ---------------------------------------------------------------------------

def test_validate_report_dir_system_protected():
    valid, msg = ReportManager.validate_report_dir("/")
    assert valid is False
    assert "system directory" in msg.lower()

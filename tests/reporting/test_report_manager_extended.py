"""Extended tests for src/reporting/report_manager.py — coverage for
save_entries, load_entries, save_session, load_session, _embed_thumbnails,
create_demo_session paths."""
import json
import os

import pytest

from src.reporting.report_manager import ReportManager
from src.core.models import ReportEntry, SessionState, ScanConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(file_path="test.jpg", nudity_detected=True):
    return ReportEntry(
        file=file_path,
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=nudity_detected,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )


def _make_session(source_folder="/images", entries=None):
    config = ScanConfig(source_folder=source_folder, model_name="helloz_nsfw", threshold_percent=60.0)
    return SessionState(scan_config=config, results=entries or [])


# ---------------------------------------------------------------------------
# save_entries / load_entries round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_entries_roundtrip(tmp_path):
    path = str(tmp_path / "nudity_report.xlsx")
    entries = [_make_entry("/a/b.jpg"), _make_entry("/c/d.mp4")]
    ReportManager.save_entries(entries, path)
    loaded = ReportManager.load_entries(path)
    assert len(loaded) == 2
    assert loaded[0].file == "/a/b.jpg"
    assert loaded[1].file == "/c/d.mp4"


def test_save_entries_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "sub" / "dir" / "nudity_report.xlsx")
    entries = [_make_entry()]
    result = ReportManager.save_entries(entries, path)
    assert result is True
    assert os.path.exists(path)


def test_save_entries_returns_true_on_success(tmp_path):
    path = str(tmp_path / "rep.xlsx")
    assert ReportManager.save_entries([], path) is True


def test_load_entries_empty_report(tmp_path):
    path = str(tmp_path / "empty.xlsx")
    ReportManager.save_entries([], path)
    loaded = ReportManager.load_entries(path)
    assert loaded == []


def test_load_entries_preserves_nudity_detected_flag(tmp_path):
    path = str(tmp_path / "rep.xlsx")
    entries = [
        _make_entry("/a.jpg", nudity_detected=True),
        _make_entry("/b.jpg", nudity_detected=False),
    ]
    ReportManager.save_entries(entries, path)
    loaded = ReportManager.load_entries(path)
    assert any(e.nudity_detected for e in loaded)


def test_save_and_overwrite_entries(tmp_path):
    path = str(tmp_path / "rep.xlsx")
    ReportManager.save_entries([_make_entry("/first.jpg")], path)
    ReportManager.save_entries([_make_entry("/second.jpg"), _make_entry("/third.jpg")], path)
    loaded = ReportManager.load_entries(path)
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# save_session / load_session round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_session_roundtrip(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    state = _make_session("/my/folder", [_make_entry()])
    ReportManager.save_session(state, report_path)
    loaded = ReportManager.load_session(report_path)
    assert loaded.scan_config.source_folder == "/my/folder"
    assert len(loaded.results) == 1


def test_load_session_missing_returns_empty(tmp_path):
    path = str(tmp_path / "nonexistent.json")
    loaded = ReportManager.load_session(path)
    assert isinstance(loaded, SessionState)
    assert loaded.results == []


def test_load_session_corrupt_json_returns_empty(tmp_path):
    session_path = str(tmp_path / "nudity_report_session.json")
    with open(session_path, "w") as f:
        f.write("{invalid json{{")
    loaded = ReportManager.load_session(session_path)
    assert isinstance(loaded, SessionState)


def test_load_session_directly_from_json_file(tmp_path):
    report_path = str(tmp_path / "nudity_report.xlsx")
    state = _make_session("/direct/json", [])
    ReportManager.save_session(state, report_path)
    session_path = ReportManager.get_session_path(report_path)
    loaded = ReportManager.load_session(session_path)
    assert loaded.scan_config.source_folder == "/direct/json"


def test_load_session_from_xlsx_with_embedded_session(tmp_path):
    """load_session falls back to Excel when no JSON is present."""
    report_path = str(tmp_path / "nudity_report.xlsx")
    # Create an xlsx with entries but no session JSON
    entries = [_make_entry()]
    ReportManager.save_entries(entries, report_path)
    # Do NOT call save_session so there is no _session.json
    state = ReportManager.load_session(report_path)
    assert isinstance(state, SessionState)


# ---------------------------------------------------------------------------
# create_demo_session
# ---------------------------------------------------------------------------

def test_create_demo_session_creates_session_sheet(tmp_path):
    import openpyxl
    report_path = str(tmp_path / "demo.xlsx")
    # Ensure xlsx exists first
    ReportManager.save_entries([], report_path)
    state = _make_session("/demo", [])
    result = ReportManager.create_demo_session(report_path, state)
    assert result is True
    wb = openpyxl.load_workbook(report_path)
    assert "Session" in wb.sheetnames


def test_create_demo_session_missing_xlsx(tmp_path):
    report_path = str(tmp_path / "new_demo.xlsx")
    state = _make_session("/demo", [])
    result = ReportManager.create_demo_session(report_path, state)
    assert result is True
    assert os.path.exists(report_path)


# ---------------------------------------------------------------------------
# _embed_thumbnails (indirectly via save_entries with thumbnail data)
# ---------------------------------------------------------------------------

def test_save_entries_with_thumbnail(tmp_path):
    """save_entries handles entries with a thumbnail without crashing."""
    import base64
    from io import BytesIO
    try:
        from PIL import Image as PILImage
        buf = BytesIO()
        img = PILImage.new("RGB", (10, 10), color=(255, 0, 0))
        img.save(buf, format="PNG")
        thumb = base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        thumb = ""

    entry = ReportEntry(
        file="thumb_test.jpg",
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail=thumb,
        date_classified="2025-01-01",
    )
    path = str(tmp_path / "thumb_report.xlsx")
    result = ReportManager.save_entries([entry], path)
    assert result is True


# ---------------------------------------------------------------------------
# get_report_path / get_session_path
# ---------------------------------------------------------------------------

def test_get_report_path_custom_dir(tmp_path):
    path = ReportManager.get_report_path(str(tmp_path))
    assert path.startswith(str(tmp_path))
    assert path.endswith(".xlsx")


def test_get_session_path_naming():
    path = ReportManager.get_session_path("/reports/2025-01-01/nudity_report.xlsx")
    assert "_session.json" in path
    assert ".xlsx" not in path


# ---------------------------------------------------------------------------
# validate_report_dir — additional paths (lines 81-82)
# ---------------------------------------------------------------------------

def test_validate_report_dir_protected_dir():
    """validate_report_dir rejects system-protected directories."""
    from src.core import constants
    if not constants.SYSTEM_PROTECTED_DIRS:
        import pytest
        pytest.skip("No protected dirs configured")
    protected = next(iter(constants.SYSTEM_PROTECTED_DIRS))
    ok, msg = ReportManager.validate_report_dir(protected)
    assert ok is False
    assert "system directory" in msg


def test_validate_report_dir_unwritable(tmp_path, monkeypatch):
    """validate_report_dir returns False when directory is not writable."""
    import builtins
    real_open = builtins.open

    def mock_open(path, *args, **kwargs):
        if ".test" in str(path):
            raise OSError("Permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", mock_open)
    ok, msg = ReportManager.validate_report_dir(str(tmp_path))
    assert ok is False
    assert "not writable" in msg


# ---------------------------------------------------------------------------
# load_entries — error paths (lines 131-133, 136-138)
# ---------------------------------------------------------------------------

def test_load_entries_skips_malformed_rows(tmp_path):
    """load_entries skips rows with bad data gracefully."""
    import openpyxl
    path = str(tmp_path / "bad.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["File", "Media Type", "Model", "Threshold Percent", "Confidence Percent",
                "Nudity Detected", "Detected Classes", "Thumbnail", "Date Classified"])
    # Row with None in file column - should be skipped
    ws.append([None, None, None, None, None, None, None, None, None])
    wb.save(path)
    loaded = ReportManager.load_entries(path)
    assert loaded == []


def test_load_entries_corrupt_file_returns_empty(tmp_path):
    """load_entries returns [] for non-xlsx files."""
    path = str(tmp_path / "corrupt.xlsx")
    with open(path, "w") as f:
        f.write("this is not a valid xlsx")
    loaded = ReportManager.load_entries(path)
    assert loaded == []


# ---------------------------------------------------------------------------
# save_entries — existing file overwrite (lines 176-178)
# ---------------------------------------------------------------------------

def test_save_entries_overwrites_existing(tmp_path):
    """save_entries replaces existing data."""
    path = str(tmp_path / "report.xlsx")
    ReportManager.save_entries([_make_entry("/first.jpg")], path)
    ReportManager.save_entries([_make_entry("/second.jpg"), _make_entry("/third.jpg")], path)
    loaded = ReportManager.load_entries(path)
    files = [e.file for e in loaded]
    assert "/second.jpg" in files
    assert "/third.jpg" in files
    assert "/first.jpg" not in files


def test_save_entries_exception_returns_false(tmp_path, monkeypatch):
    """save_entries returns False when an exception occurs."""
    import openpyxl
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))
    # Create the file first so load_workbook path is taken
    path = str(tmp_path / "report.xlsx")
    open(path, "wb").close()
    result = ReportManager.save_entries([_make_entry()], path)
    assert result is False


# ---------------------------------------------------------------------------
# save_session — exception path (lines 248-250)
# ---------------------------------------------------------------------------

def test_save_session_exception_returns_false(tmp_path, monkeypatch):
    """save_session returns False on I/O error."""
    import builtins
    real_open = builtins.open

    def fail_open(path, *args, **kwargs):
        if str(path).endswith(".json"):
            raise OSError("no space")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_open)
    state = _make_session()
    result = ReportManager.save_session(state, str(tmp_path / "report.xlsx"))
    assert result is False


# ---------------------------------------------------------------------------
# load_session — embedded session in xlsx (lines 278-284)
# ---------------------------------------------------------------------------

def test_load_session_from_xlsx_with_session_sheet(tmp_path):
    """load_session reads embedded session JSON from 'Session' sheet."""
    import openpyxl, json
    path = str(tmp_path / "report.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nudity Report"
    session_data = {
        "version": 1,
        "saved_at": "2025-01-01T00:00:00",
        "scan_config": {"source_folder": "/embedded", "model_name": "nudenet", "threshold_percent": 60.0, "theme_mode": "system"},
        "results": [],
    }
    sess_ws = wb.create_sheet("Session")
    sess_ws["A1"] = json.dumps(session_data)
    wb.save(path)
    state = ReportManager.load_session(path)
    assert state.scan_config.source_folder == "/embedded"


def test_load_session_from_xlsx_invalid_session_json(tmp_path):
    """load_session falls back when embedded session JSON is invalid."""
    import openpyxl
    path = str(tmp_path / "report.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nudity Report"
    sess_ws = wb.create_sheet("Session")
    sess_ws["A1"] = "{not valid json{{{"
    wb.save(path)
    state = ReportManager.load_session(path)
    assert isinstance(state, SessionState)


# ---------------------------------------------------------------------------
# create_demo_session — exception path (lines 318-320)
# ---------------------------------------------------------------------------

def test_create_demo_session_exception_returns_false(tmp_path, monkeypatch):
    """create_demo_session returns False on exception."""
    import openpyxl
    monkeypatch.setattr(openpyxl, "load_workbook", lambda *a, **kw: (_ for _ in ()).throw(OSError("broken")))
    path = str(tmp_path / "report.xlsx")
    open(path, "wb").close()
    result = ReportManager.create_demo_session(path, _make_session())
    assert result is False


# ---------------------------------------------------------------------------
# load_entries — line 115: skip empty rows
# ---------------------------------------------------------------------------

def test_load_entries_skips_empty_rows(tmp_path):
    """load_entries skips rows where first cell is None."""
    import openpyxl
    path = str(tmp_path / "sparse.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["File", "Media Type", "Model", "Threshold Percent", "Confidence Percent",
                "Nudity Detected", "Detected Classes", "Thumbnail", "Date Classified"])
    ws.append(["/valid.jpg", "image", "model", 60.0, 0.8, True, "[]", "", "2025-01-01"])
    ws.append([None, None, None, None, None, None, None, None, None])  # empty
    ws.append(["/another.jpg", "image", "model", 60.0, 0.5, False, "[]", "", "2025-01-01"])
    wb.save(path)
    loaded = ReportManager.load_entries(path)
    assert len(loaded) == 2

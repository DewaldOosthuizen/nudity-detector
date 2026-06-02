"""
Tests for SessionMixin (src/gui/session.py) — covers load_initial_session,
load_session_from_path, open_reports_folder, open_report.
Uses full gi stubs.
"""
import json
import sys
from unittest.mock import MagicMock, patch


# GI stubs
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
sys.modules.setdefault("nudenet", MagicMock())

from src.gui.session import SessionMixin  # noqa: E402


class FakeSessionWindow(SessionMixin):
    """Minimal concrete mix-in host."""
    def __init__(self):
        self.last_report_path = "/tmp/test.xlsx"
        self.folder_entry = MagicMock()
        self.nudenet_radio = MagicMock()
        self.helloz_nsfw_radio = MagicMock()
        self.theme_dropdown = MagicMock()
        self.threshold_spin = MagicMock()
        self.open_report_button = MagicMock()
        self.detected_results = []
        self._scan_session = None
        self.view_stack = MagicMock()

    def populate_results(self, results): pass
    def log_message(self, *a, **kw): pass
    def _show_error(self, *a, **kw): pass
    def _show_warning(self, *a, **kw): pass
    def _apply_theme(self, theme): pass
    def build_session_state(self): return {}
    def _find_latest_report_path(self): return None


# -----------------------------------------------------------------------
# load_initial_session
# -----------------------------------------------------------------------

def test_load_initial_session_no_latest():
    win = FakeSessionWindow()
    win._find_latest_report_path = lambda: None
    win.load_initial_session()  # should not raise


def test_load_initial_session_path_not_exists():
    win = FakeSessionWindow()
    win._find_latest_report_path = lambda: "/nonexistent.xlsx"
    win.load_initial_session()  # os.path.exists returns False, no-op


def test_load_initial_session_success():
    win = FakeSessionWindow()
    win._find_latest_report_path = lambda: "/tmp/report.xlsx"
    logs = []
    win.log_message = lambda msg, *a, **kw: logs.append(msg)

    with patch("os.path.exists", return_value=True), \
         patch.object(win, "load_session_from_path") as mock_load:
        win.load_initial_session()

    mock_load.assert_called_once_with("/tmp/report.xlsx", show_feedback=False)


def test_load_initial_session_error_logged():
    win = FakeSessionWindow()
    win._find_latest_report_path = lambda: "/tmp/report.xlsx"
    logs = []
    win.log_message = lambda msg, *a, **kw: logs.append((msg, kw))

    def boom(*a, **kw):
        raise json.JSONDecodeError("bad", "", 0)

    with patch("os.path.exists", return_value=True), \
         patch.object(win, "load_session_from_path", side_effect=boom):
        win.load_initial_session()

    assert any("No previous session" in m for m, _ in logs)


# -----------------------------------------------------------------------
# load_session_from_path
# -----------------------------------------------------------------------

def test_load_session_from_path_xlsx():
    win = FakeSessionWindow()
    session_state = {"scan_config": {"source_folder": "/scans", "model_name": "helloz"}, "results": []}

    with patch("src.gui.session.load_scan_session", return_value=session_state), \
         patch("src.gui.session.load_report_entries", return_value=[]), \
         patch("src.gui.session.get_detected_results", return_value=[]), \
         patch("os.path.exists", return_value=True), \
         patch("src.core.constants.SUPPORTED_THEMES", ["system", "light", "dark"]), \
         patch("src.core.constants.MODEL_NUDENET", "nudenet"), \
         patch("src.core.constants.XLSX_EXTENSION", ".xlsx"):
        win.load_session_from_path("/tmp/report.xlsx", show_feedback=True)

    assert win.last_report_path == "/tmp/report.xlsx"


def test_load_session_from_path_session_json():
    win = FakeSessionWindow()
    session_state = {"scan_config": {}, "results": []}

    with patch("src.gui.session.load_scan_session", return_value=session_state), \
         patch("src.gui.session.load_report_entries", return_value=[]), \
         patch("src.gui.session.get_detected_results", return_value=[]), \
         patch("os.path.exists", return_value=False), \
         patch("src.core.constants.SUPPORTED_THEMES", ["system", "light", "dark"]), \
         patch("src.core.constants.MODEL_NUDENET", "nudenet"), \
         patch("src.core.constants.XLSX_EXTENSION", ".xlsx"):
        win.load_session_from_path("/tmp/report_session.json", show_feedback=False)


# -----------------------------------------------------------------------
# open_reports_folder
# -----------------------------------------------------------------------

def test_open_reports_folder_success():
    win = FakeSessionWindow()
    with patch("src.core.utils.open_file_location", return_value=(True, "")):
        win.open_reports_folder()  # no error


def test_open_reports_folder_error():
    win = FakeSessionWindow()
    errors = []
    win._show_error = lambda t, m: errors.append(m)
    with patch("src.core.utils.open_file_location", return_value=(False, "not found")):
        win.open_reports_folder()
    assert any("not found" in e for e in errors)


# -----------------------------------------------------------------------
# open_report
# -----------------------------------------------------------------------

def test_open_report_file_missing():
    win = FakeSessionWindow()
    win.last_report_path = "/nonexistent/report.xlsx"
    warnings = []
    win._show_warning = lambda t, m: warnings.append(m)
    win.open_report()
    assert len(warnings) == 1


def test_open_report_success():
    win = FakeSessionWindow()
    win.last_report_path = "/tmp/report.xlsx"
    with patch("os.path.exists", return_value=True), \
         patch("src.core.utils.open_file", return_value=(True, "")):
        win.open_report()  # no error


def test_open_report_open_fails():
    win = FakeSessionWindow()
    win.last_report_path = "/tmp/report.xlsx"
    errors = []
    win._show_error = lambda t, m: errors.append(m)
    with patch("os.path.exists", return_value=True), \
         patch("src.core.utils.open_file", return_value=(False, "xdg-open failed")):
        win.open_report()
    assert any("xdg-open failed" in e for e in errors)

"""
Tests for ResultsMixin (src/gui/results.py).
Uses full gi stubs — no real GTK display needed.
"""
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# GI stubs — must be set BEFORE any src import
# ---------------------------------------------------------------------------

class _GObjectBase:
    """Minimal GObject.Object stand-in used across gi stubs."""
    def __init__(self, **kwargs):
        pass

    @classmethod
    def connect(cls, *a, **kw):
        pass


def _ensure_gi_stubs():
    # Always ensure GObject.Object is a real class, even if gi is already loaded
    # by another test module. Without this, ScanRunItem (which subclasses it) will
    # inherit from a MagicMock and attribute access returns new mocks instead of
    # the stored values, causing cross-file test-order failures.
    if "gi" in sys.modules:
        gobject_mod = sys.modules.get("gi.repository.GObject")
        if gobject_mod is not None:
            gobject_mod.Object = _GObjectBase
        return

    gi_mock = MagicMock()
    sys.modules["gi"] = gi_mock
    sys.modules["gi.repository"] = gi_mock.repository

    gobject_mod = MagicMock()
    gobject_mod.Object = _GObjectBase
    sys.modules["gi.repository.GObject"] = gobject_mod

    for mod in [
        "gi.repository.Gtk",
        "gi.repository.Gdk",
        "gi.repository.Adw",
        "gi.repository.Gio",
        "gi.repository.GLib",
        "gi.repository.GdkPixbuf",
        "gi.repository.Pango",
    ]:
        sys.modules[mod] = MagicMock()


_ensure_gi_stubs()
sys.modules.setdefault("nudenet", MagicMock())

# Patch the Gtk.SingleSelection at runtime so isinstance checks work
import src.gui.results as results_mod  # noqa: E402
from src.gui.results import ResultsMixin  # noqa: E402

# ---------------------------------------------------------------------------
# Fake concrete class mixing in ResultsMixin
# ---------------------------------------------------------------------------

class _FakeSingleSelection:
    """Stand-in for Gtk.SingleSelection."""
    INVALID = 4294967295  # GTK_INVALID_LIST_POSITION

    def __init__(self, selected=INVALID):
        self._selected = selected

    def get_selected(self):
        return self._selected


# Make Gtk.SingleSelection a real class so isinstance() works
class _FakeGtkSingleSelection:
    INVALID = 4294967295  # GTK_INVALID_LIST_POSITION

    def __init__(self, selected=4294967295):
        self._selected = selected

    def get_selected(self):
        return self._selected


# Patch Gtk.SingleSelection after import so runtime isinstance checks use our class
results_mod.Gtk.SingleSelection = _FakeGtkSingleSelection
results_mod.Gtk.INVALID_LIST_POSITION = _FakeGtkSingleSelection.INVALID


class _FakeResultItem:
    """Minimal stub for ResultItem so it doesn't hit the GObject mock."""
    def __init__(self, *, index, name, media_type, confidence, model_name, path):
        self.index = index
        self.name = name
        self.media_type = media_type
        self.confidence = confidence
        self.model_name = model_name
        self.path = path


# Patch ResultItem in the results module
results_mod.ResultItem = _FakeResultItem


class FakeResultsWindow(ResultsMixin):
    def __init__(self):
        self._list_store = MagicMock()
        self.summary_label = MagicMock()
        self.column_view = MagicMock()
        self.is_processing = False
        self.open_file_button = MagicMock()
        self.open_location_button = MagicMock()
        self.delete_button = MagicMock()
        self.detected_results = []
        self.last_report_path = "/tmp/test_report.json"
        self._scan_session = None
        self.folder_entry = MagicMock()
        self.folder_entry.get_text.return_value = ""

    def update_thumbnail_preview(self):
        pass

    def clear_thumbnail_preview(self):
        pass

    def log_message(self, *a, **kw):
        pass

    def _show_error(self, *a, **kw):
        pass

    def _ask_yes_no(self, title, msg, cb):
        cb()

    def build_session_state(self):
        return {}


# ---------------------------------------------------------------------------
# Tests: append_results
# ---------------------------------------------------------------------------

def test_append_results_appends_to_store():
    win = FakeResultsWindow()
    entries = [
        {"file": "/tmp/a.jpg", "media_type": "image", "confidence_percent": 75.0,
         "model_name": "helloz"},
        {"file": "/tmp/b.jpg", "media_type": "image", "confidence_percent": 90.0,
         "model_name": "helloz"},
    ]
    win.append_results(entries, start_index=0)
    assert win._list_store.append.call_count == 2


def test_append_results_uses_start_index():
    win = FakeResultsWindow()
    entries = [{"file": "/tmp/c.jpg", "media_type": "image", "confidence_percent": 50.0, "model_name": "m"}]
    win.append_results(entries, start_index=5)
    appended_item = win._list_store.append.call_args[0][0]
    assert appended_item.index == 5


def test_append_results_empty_list():
    win = FakeResultsWindow()
    win.append_results([], start_index=0)
    win._list_store.append.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: _on_result_selection_changed
# ---------------------------------------------------------------------------

def test_on_result_selection_changed_calls_actions():
    win = FakeResultsWindow()
    # set up column_view.get_model to return a non-SingleSelection mock
    win.column_view.get_model.return_value = MagicMock()
    win._on_result_selection_changed(None, None, None)
    # No assertion needed — just ensure no exception


# ---------------------------------------------------------------------------
# Tests: update_result_action_state / get_selected_entry
# ---------------------------------------------------------------------------

def test_update_result_action_state_no_selection():
    """When model is not a SingleSelection, buttons are insensitive."""
    win = FakeResultsWindow()
    plain_mock = MagicMock(spec=[])  # not a Gtk.SingleSelection
    win.column_view.get_model.return_value = plain_mock

    # Patch isinstance to return False for SingleSelection check
    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection):
        win.update_result_action_state()

    win.open_file_button.set_sensitive.assert_called_with(False)
    win.open_location_button.set_sensitive.assert_called_with(False)
    win.delete_button.set_sensitive.assert_called_with(False)


def test_update_result_action_state_valid_selection():
    """When model is SingleSelection with valid index, buttons are sensitive."""
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/x.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        win.update_result_action_state()

    win.open_file_button.set_sensitive.assert_called_with(True)


def test_get_selected_entry_no_single_selection():
    win = FakeResultsWindow()
    win.column_view.get_model.return_value = MagicMock(spec=[])
    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection):
        result = win.get_selected_entry()
    assert result is None


def test_get_selected_entry_invalid_position():
    win = FakeResultsWindow()
    sel = _FakeSingleSelection(selected=_FakeSingleSelection.INVALID)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        result = win.get_selected_entry()

    assert result is None


def test_get_selected_entry_valid():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/found.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        result = win.get_selected_entry()

    assert result == {"file": "/tmp/found.jpg"}


def test_get_selected_entry_out_of_range():
    win = FakeResultsWindow()
    win.detected_results = []  # empty — index 0 would be out of range
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        result = win.get_selected_entry()

    assert result is None


# ---------------------------------------------------------------------------
# Tests: open_selected_file
# ---------------------------------------------------------------------------

def test_open_selected_file_no_entry():
    win = FakeResultsWindow()
    win.column_view.get_model.return_value = MagicMock(spec=[])
    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection):
        win.open_selected_file()  # should not raise


def test_open_selected_file_missing_on_disk():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/nonexistent/path.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    errors = []
    win._show_error = lambda t, m: errors.append(m)

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        win.open_selected_file()

    assert any("no longer exists" in e for e in errors)


def test_open_selected_file_open_fails():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/exists.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    errors = []
    win._show_error = lambda t, m: errors.append(m)

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID), \
         patch("os.path.exists", return_value=True), \
         patch("src.gui.results.open_file", return_value=(False, "permission denied")):
        win.open_selected_file()

    assert any("permission denied" in e for e in errors)


def test_open_selected_file_success():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/exists.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    logs = []
    win.log_message = lambda msg, *a, **kw: logs.append(msg)

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID), \
         patch("os.path.exists", return_value=True), \
         patch("src.gui.results.open_file", return_value=(True, "")):
        win.open_selected_file()

    assert any("Opened" in line for line in logs)


# ---------------------------------------------------------------------------
# Tests: open_selected_location
# ---------------------------------------------------------------------------

def test_open_selected_location_no_entry():
    win = FakeResultsWindow()
    win.column_view.get_model.return_value = MagicMock(spec=[])
    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection):
        win.open_selected_location()  # no raise


def test_open_selected_location_fails():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/x.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    errors = []
    win._show_error = lambda t, m: errors.append(m)

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID), \
         patch("src.gui.results.open_file_location", return_value=(False, "no xdg-open")):
        win.open_selected_location()

    assert any("no xdg-open" in e for e in errors)


def test_open_selected_location_success():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/x.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID), \
         patch("src.gui.results.open_file_location", return_value=(True, "")):
        win.open_selected_location()  # no error


# ---------------------------------------------------------------------------
# Tests: delete_selected_result
# ---------------------------------------------------------------------------

def test_delete_selected_result_not_single_selection():
    win = FakeResultsWindow()
    win.column_view.get_model.return_value = MagicMock(spec=[])
    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection):
        win.delete_selected_result()  # returns early


def test_delete_selected_result_no_entry():
    win = FakeResultsWindow()
    sel = _FakeSingleSelection(selected=_FakeSingleSelection.INVALID)
    win.column_view.get_model.return_value = sel

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        win.delete_selected_result()  # returns early (no entry)


def test_delete_selected_result_invokes_ask():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/del.jpg"}]
    sel = _FakeSingleSelection(selected=0)
    win.column_view.get_model.return_value = sel

    asked = []
    win._ask_yes_no = lambda t, m, cb: asked.append((t, m))

    with patch.object(results_mod.Gtk, "SingleSelection", _FakeSingleSelection), \
         patch.object(results_mod.Gtk, "INVALID_LIST_POSITION", _FakeSingleSelection.INVALID):
        win.delete_selected_result()

    assert len(asked) == 1


# ---------------------------------------------------------------------------
# Tests: _do_delete
# ---------------------------------------------------------------------------

def test_do_delete_failure_shows_error():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/gone.jpg"}]

    errors = []
    win._show_error = lambda t, m: errors.append(m)
    win.populate_results = MagicMock()

    with patch("src.gui.results.delete_file_safely", return_value=(False, "locked")):
        win._do_delete(0, {"file": "/tmp/gone.jpg"})

    assert "locked" in errors[0]
    win.populate_results.assert_not_called()


def test_do_delete_success_no_scan_session():
    win = FakeResultsWindow()
    win.detected_results = [{"file": "/tmp/gone.jpg"}]
    win.populate_results = MagicMock()

    with patch("src.gui.results.delete_file_safely", return_value=(True, "moved to trash")), \
         patch("src.gui.results.save_nudity_report"):
        win._do_delete(0, {"file": "/tmp/gone.jpg"})

    win.populate_results.assert_called_once()
    assert len(win.detected_results) == 0


def test_do_delete_success_with_scan_session():
    win = FakeResultsWindow()

    mock_entry = MagicMock()
    mock_entry.file = "/tmp/gone.jpg"
    mock_session = MagicMock()
    mock_session.get_results.return_value = [mock_entry]
    win._scan_session = mock_session
    win.detected_results = [{"file": "/tmp/gone.jpg"}]
    win.populate_results = MagicMock()

    with patch("src.gui.results.delete_file_safely", return_value=(True, "ok")), \
         patch("src.gui.results.save_nudity_report"):
        win._do_delete(0, {"file": "/tmp/gone.jpg"})

    mock_session.reset.assert_called_once()
    win.populate_results.assert_called_once()

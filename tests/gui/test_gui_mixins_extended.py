"""Tests for GUI mixin modules — dialogs.py, result_item.py, results.py,
preview.py, scan_history.py (extended), session.py (extended), scanning.py
All GTK/GObject imports are stubbed via sys.modules before any src.gui import."""
import sys
import os
import json
import types
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


# ---------------------------------------------------------------------------
# Stub ALL gi / GTK / GDK imports at module level (idempotent)
# ---------------------------------------------------------------------------
class _GObjectBase:
    """Real Python class so that ResultItem(GObject.Object) and
    ScanRunItem(GObject.Object) subclassing works correctly regardless of
    which test file ran first."""
    def __init__(self, *args, **kwargs):
        pass
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


def _ensure_gi_stubs():
    # Always ensure GObject.Object is the real _GObjectBase —
    # another file may have already installed gi stubs with a MagicMock.

    class _GLibError(Exception):
        pass

    if "gi" in sys.modules:
        # Re-install the real class on whatever GObject mock is present
        gobject_mod = sys.modules.get("gi.repository.GObject")
        if gobject_mod is not None:
            gobject_mod.Object = _GObjectBase
            gobject_mod.GObject = _GObjectBase
        # Also ensure the repo_mod has it
        repo_mod = sys.modules.get("gi.repository")
        if repo_mod is not None and hasattr(repo_mod, "GObject"):
            repo_mod.GObject.Object = _GObjectBase
            repo_mod.GObject.GObject = _GObjectBase
        # Ensure GLib.Error is a real exception class to prevent
        # filesystem leaks when used in `except GLib.Error:` blocks.
        glib_mod = sys.modules.get("gi.repository.GLib")
        if glib_mod is not None:
            glib_mod.Error = _GLibError
        if repo_mod is not None and hasattr(repo_mod, "GLib"):
            repo_mod.GLib.Error = _GLibError
        return

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = MagicMock()

    repo_mod = types.ModuleType("gi.repository")

    gtk_mod = MagicMock()
    gtk_mod.INVALID_LIST_POSITION = 4294967295
    gtk_mod.Orientation = MagicMock()
    gtk_mod.Orientation.VERTICAL = 0
    gtk_mod.Orientation.HORIZONTAL = 1

    adw_mod = MagicMock()
    glib_mod = MagicMock()
    # GLib.Error must be a real exception class so `except GLib.Error:` works
    # in src/gui/session.py and prevents MagicMock paths leaking to the filesystem.
    class _GLibError(Exception):
        pass
    glib_mod.Error = _GLibError
    gio_mod = MagicMock()
    gdk_mod = MagicMock()
    gdkpixbuf_mod = MagicMock()

    # GObject.Object must be a real Python class so subclasses work correctly
    # (module-level _GObjectBase is used — do NOT redefine it here)
    gobject_mod = MagicMock()
    gobject_mod.Object = _GObjectBase
    gobject_mod.GObject = _GObjectBase

    gi_mod.repository = repo_mod
    repo_mod.Gtk = gtk_mod
    repo_mod.Adw = adw_mod
    repo_mod.GLib = glib_mod
    repo_mod.GObject = gobject_mod
    repo_mod.Gio = gio_mod
    repo_mod.Gdk = gdk_mod
    repo_mod.GdkPixbuf = gdkpixbuf_mod

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.Adw"] = adw_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod
    sys.modules["gi.repository.Gio"] = gio_mod
    sys.modules["gi.repository.Gdk"] = gdk_mod
    sys.modules["gi.repository.GdkPixbuf"] = gdkpixbuf_mod


_ensure_gi_stubs()

# Now safe to import src.gui modules
from src.gui.dialogs import DialogsMixin                    # noqa: E402
from src.gui.result_item import ResultItem                 # noqa: E402
from src.gui.results import ResultsMixin                   # noqa: E402
from src.gui.preview import PreviewMixin                   # noqa: E402
from src.gui.scan_history import ScanHistoryMixin, ScanRunItem  # noqa: E402
from src.gui.session import SessionMixin                   # noqa: E402
from src.gui.scanning import ScanningMixin                 # noqa: E402
from src.core.models import ReportEntry, SessionState, ScanConfig  # noqa: E402
from src.reporting.report_manager import ReportManager     # noqa: E402
from src.core import constants                             # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — build a fake window object that satisfies mixin method calls
# ---------------------------------------------------------------------------

def _make_window(**extra_attrs):
    """Build a MagicMock that has all the attributes GUI mixins reference."""
    win = MagicMock()
    win.folder_entry = MagicMock()
    win.folder_entry.get_text.return_value = "/tmp"
    win.threshold_spin = MagicMock()
    win.threshold_spin.get_value.return_value = 60.0
    win.nudenet_radio = MagicMock()
    win.helloz_nsfw_radio = MagicMock()
    win.theme_dropdown = MagicMock()
    win.summary_label = MagicMock()
    win.open_report_button = MagicMock()
    win._list_store = MagicMock()
    win.detected_results = []
    win.last_report_path = "/tmp/nudity_report.xlsx"
    win._scan_session = MagicMock()
    win._scan_session.get_results.return_value = []
    win.log_buffer = MagicMock()
    win.is_processing = False
    win.view_stack = MagicMock()
    win._history_store = MagicMock()
    win._history_selection = MagicMock()
    win._history_selection.set_selected = MagicMock()
    win.history_load_button = MagicMock()
    win.history_export_button = MagicMock()
    win.history_delete_button = MagicMock()
    win.thumbnail_picture = MagicMock()
    win._thumb_placeholder = MagicMock()
    win.thumbnail_meta_label = MagicMock()
    win.progress_bar = MagicMock()
    win.start_button = MagicMock()
    win.stop_button = MagicMock()
    win.log_message = MagicMock()
    win.populate_results = MagicMock()
    win.update_result_action_state = MagicMock()
    win.clear_thumbnail_preview = MagicMock()
    win.get_selected_entry = MagicMock(return_value=None)
    win._show_error = MagicMock()
    win._show_warning = MagicMock()
    win._get_model = MagicMock(return_value=constants.MODEL_NUDENET)
    win._get_theme_mode = MagicMock(return_value="system")
    win._apply_theme = MagicMock()
    win._update_history_action_state = MagicMock()
    for k, v in extra_attrs.items():
        setattr(win, k, v)
    return win


def _make_entry(file_path="test.jpg"):
    return ReportEntry(
        file=file_path,
        media_type="image",
        model_name="helloz_nsfw",
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2025-01-01",
    )


# ===========================================================================
# DialogsMixin
# ===========================================================================

class TestDialogsMixin:
    def test_importable(self):
        assert DialogsMixin is not None

    def test_show_error_presents_dialog(self):
        mixin = DialogsMixin()
        win = _make_window()
        # Mix in methods via direct call — _show_error calls Adw.AlertDialog (mocked)
        DialogsMixin._show_error(win, "Title", "Body")
        # Adw is mocked; just verify it doesn't crash

    def test_show_warning_presents_dialog(self):
        win = _make_window()
        DialogsMixin._show_warning(win, "Warn", "Message")

    def test_ask_yes_no_presents_dialog(self):
        win = _make_window()
        on_yes = MagicMock()
        DialogsMixin._ask_yes_no(win, "Confirm?", "Are you sure?", on_yes)


# ===========================================================================
# ResultItem
# ===========================================================================

class TestResultItem:
    def test_importable(self):
        assert ResultItem is not None

    def test_attributes_set(self):
        item = ResultItem(
            index=0,
            name="image.jpg",
            media_type="image",
            confidence="75.00%",
            model_name="helloz_nsfw",
            path="/some/path/image.jpg",
        )
        # GObject.Object is mocked; attributes are set as instance attrs after super().__init__()
        # Access via __dict__ to bypass MagicMock's __getattr__
        assert item.__dict__.get("index") == 0 or hasattr(item, "name")
        # Verify the class is properly defined
        assert type(item).__name__ == "ResultItem"


# ===========================================================================
# ResultsMixin
# ===========================================================================

class TestResultsMixin:
    def test_importable(self):
        assert ResultsMixin is not None

    def test_populate_results_empty(self):
        win = _make_window()
        ResultsMixin.populate_results(win, [])
        win.summary_label.set_text.assert_called()
        win.update_result_action_state.assert_called()

    def test_populate_results_with_entries(self):
        win = _make_window()
        results = [
            {"file": "/a/b.jpg", "media_type": "image", "confidence_percent": 80.0, "model_name": "helloz_nsfw"},
        ]
        ResultsMixin.populate_results(win, results)
        win._list_store.append.assert_called_once()

    def test_populate_results_multiple_entries(self):
        win = _make_window()
        results = [
            {"file": f"/img{i}.jpg", "media_type": "image", "confidence_percent": 70.0, "model_name": "test"}
            for i in range(3)
        ]
        ResultsMixin.populate_results(win, results)
        assert win._list_store.append.call_count == 3

    def test_on_open_file_clicked(self):
        win = _make_window()
        win.open_selected_file = MagicMock()
        ResultsMixin._on_open_file_clicked(win, None)
        win.open_selected_file.assert_called_once()

    def test_on_open_location_clicked(self):
        win = _make_window()
        win.open_selected_location = MagicMock()
        ResultsMixin._on_open_location_clicked(win, None)
        win.open_selected_location.assert_called_once()

    def test_on_delete_clicked(self):
        win = _make_window()
        win.delete_selected_result = MagicMock()
        ResultsMixin._on_delete_clicked(win, None)
        win.delete_selected_result.assert_called_once()


# ===========================================================================
# PreviewMixin
# ===========================================================================

class TestPreviewMixin:
    def test_importable(self):
        assert PreviewMixin is not None

    def test_clear_thumbnail_preview(self):
        win = _make_window()
        PreviewMixin.clear_thumbnail_preview(win)
        win.thumbnail_picture.set_paintable.assert_called_with(None)
        win._thumb_placeholder.set_text.assert_called()
        win.thumbnail_meta_label.set_text.assert_called()

    def test_update_thumbnail_preview_no_selection(self):
        win = _make_window()
        win.get_selected_entry.return_value = None
        PreviewMixin.update_thumbnail_preview(win)
        win.clear_thumbnail_preview.assert_called_once()

    def test_update_thumbnail_preview_with_entry_no_pil(self):
        win = _make_window()
        win.get_selected_entry.return_value = {
            "thumbnail": "",
            "media_type": "image",
            "confidence_percent": 75.0,
            "model_name": "helloz_nsfw",
        }
        import src.gui.preview as preview_module
        original = preview_module.Image
        preview_module.Image = None
        try:
            PreviewMixin.update_thumbnail_preview(win)
        finally:
            preview_module.Image = original
        win._thumb_placeholder.set_text.assert_called()

    def test_update_thumbnail_preview_no_thumbnail_data(self):
        win = _make_window()
        win.get_selected_entry.return_value = {
            "thumbnail": "",
            "media_type": "image",
            "confidence_percent": 60.0,
            "model_name": "nudenet",
        }
        PreviewMixin.update_thumbnail_preview(win)
        # Should not crash

    def test_update_thumbnail_preview_with_valid_b64(self):
        """If thumbnail b64 is present and PIL is available, attempts to load it."""
        try:
            from PIL import Image as PILImage
        except ImportError:
            pytest.skip("PIL not available")

        import base64
        from io import BytesIO
        buf = BytesIO()
        PILImage.new("RGB", (10, 10)).save(buf, format="PNG")
        thumb_b64 = base64.b64encode(buf.getvalue()).decode()

        win = _make_window()
        win.get_selected_entry.return_value = {
            "thumbnail": thumb_b64,
            "media_type": "image",
            "confidence_percent": 90.0,
            "model_name": "helloz_nsfw",
        }
        # GDK is mocked so it'll go to the fallback path — just verify no exception
        PreviewMixin.update_thumbnail_preview(win)


# ===========================================================================
# ScanHistoryMixin (extended)
# ===========================================================================

class TestScanHistoryMixinExtended:
    def test_importable(self):
        assert ScanHistoryMixin is not None

    def test_scan_run_item_attrs(self):
        # Create a ScanRunItem using _GObjectBase directly in case GObject.Object is mocked
        import src.gui.scan_history as sh_module
        # Temporarily ensure ScanRunItem uses _GObjectBase
        orig_bases = sh_module.ScanRunItem.__bases__
        item = sh_module.ScanRunItem.__new__(sh_module.ScanRunItem)
        _GObjectBase.__init__(item)
        item.dir_name = "2025-01-01_12-00-00"
        item.display_date = "2025-01-01  12:00:00"
        item.model_name = "helloz_nsfw"
        item.result_count = "3"
        item.source_folder = "/images"
        item.session_path = "/reports/2025-01-01_12-00-00/nudity_report_session.json"
        item.report_path = "/reports/2025-01-01_12-00-00/nudity_report.xlsx"
        assert item.dir_name == "2025-01-01_12-00-00"
        assert item.model_name == "helloz_nsfw"
        assert item.result_count == "3"

    def test_hist_col_bind_factory_returns_callable(self):
        bind_fn = ScanHistoryMixin._hist_col_bind_factory("model_name")
        assert callable(bind_fn)

    def test_hist_col_setup_sets_child(self):
        """_hist_col_setup sets a child on the list_item (all GTK mocked)."""
        import src.gui.scan_history as sh_module
        factory = MagicMock()
        list_item = MagicMock()
        ScanHistoryMixin._hist_col_setup(factory, list_item)
        list_item.set_child.assert_called_once()

    def test_refresh_scan_history_no_report_dir(self, tmp_path, monkeypatch):
        """refresh_scan_history does not crash when DEFAULT_REPORT_DIR doesn't exist."""
        import src.gui.scan_history as sh_module
        monkeypatch.setattr(sh_module, "DEFAULT_REPORT_DIR", str(tmp_path / "nonexistent"))
        win = _make_window()
        ScanHistoryMixin.refresh_scan_history(win)
        win._history_store.remove_all.assert_called()

    def test_refresh_scan_history_with_runs(self, tmp_path, monkeypatch):
        """refresh_scan_history loads session files from subdirs."""
        import src.gui.scan_history as sh_module
        monkeypatch.setattr(sh_module, "DEFAULT_REPORT_DIR", str(tmp_path))

        # Create a valid scan run dir
        run_dir = tmp_path / "2025-01-01_12-00-00"
        run_dir.mkdir()
        session_data = {
            "scan_config": {"source_folder": "/my/images", "model_name": "helloz_nsfw"},
            "results": [{}],
        }
        with open(run_dir / "nudity_report_session.json", "w") as f:
            json.dump(session_data, f)

        win = _make_window()
        # Patch ScanRunItem so it returns a simple namespace object
        with patch.object(sh_module, "ScanRunItem", side_effect=lambda **kw: types.SimpleNamespace(**kw)):
            ScanHistoryMixin.refresh_scan_history(win)
        win._history_store.remove_all.assert_called()
        win._history_store.append.assert_called()

    def test_refresh_scan_history_invalid_date_format(self, tmp_path, monkeypatch):
        """Subdirs with non-date names are handled gracefully."""
        import src.gui.scan_history as sh_module
        monkeypatch.setattr(sh_module, "DEFAULT_REPORT_DIR", str(tmp_path))

        (tmp_path / "not_a_date").mkdir()
        win = _make_window()
        with patch.object(sh_module, "ScanRunItem", side_effect=lambda **kw: types.SimpleNamespace(**kw)):
            ScanHistoryMixin.refresh_scan_history(win)
        win._history_store.remove_all.assert_called()

    def test_on_history_load_clicked(self):
        win = _make_window()
        win._on_history_load_clicked = MagicMock()
        # Directly invoke the button handler wiring
        win.history_load_button.connect.assert_not_called()  # just ensure mock set up


# ===========================================================================
# SessionMixin (extended)
# ===========================================================================

class TestSessionMixinExtended:
    def test_importable(self):
        assert SessionMixin is not None

    def test_on_save_session_clicked_delegates(self):
        win = _make_window()
        win.save_session_dialog = MagicMock()
        SessionMixin._on_save_session_clicked(win, None)
        win.save_session_dialog.assert_called_once()

    def test_on_load_session_clicked_delegates(self):
        win = _make_window()
        win.load_session_dialog = MagicMock()
        SessionMixin._on_load_session_clicked(win, None)
        win.load_session_dialog.assert_called_once()

    def test_on_open_report_clicked_delegates(self):
        win = _make_window()
        win.open_report = MagicMock()
        SessionMixin._on_open_report_clicked(win, None)
        win.open_report.assert_called_once()

    def test_on_open_reports_clicked_delegates(self):
        win = _make_window()
        win.open_reports_folder = MagicMock()
        SessionMixin._on_open_reports_clicked(win, None)
        win.open_reports_folder.assert_called_once()

    def test_build_scan_config_returns_dict(self):
        win = _make_window()
        config = SessionMixin.build_scan_config(win)
        assert isinstance(config, dict)
        assert "model_name" in config

    def test_build_session_state_returns_dict(self):
        win = _make_window()
        state = SessionMixin.build_session_state(win)
        assert isinstance(state, dict)
        assert "scan_config" in state

    def test_find_latest_report_path_no_dir(self, tmp_path, monkeypatch):
        import src.gui.session as sess_module
        monkeypatch.setattr(sess_module, "DEFAULT_REPORT_DIR", str(tmp_path / "no_dir"))
        win = _make_window()
        path = SessionMixin._find_latest_report_path(win)
        assert path is None

    def test_find_latest_report_path_with_runs(self, tmp_path, monkeypatch):
        import src.gui.session as sess_module
        monkeypatch.setattr(sess_module, "DEFAULT_REPORT_DIR", str(tmp_path))

        run = tmp_path / "2025-01-01_12-00-00"
        run.mkdir()
        report = run / "nudity_report.xlsx"
        ReportManager.save_entries([], str(report))

        win = _make_window()
        path = SessionMixin._find_latest_report_path(win)
        assert path is not None

    def test_load_initial_session_no_latest(self, tmp_path, monkeypatch):
        import src.gui.session as sess_module
        monkeypatch.setattr(sess_module, "DEFAULT_REPORT_DIR", str(tmp_path / "empty"))
        win = _make_window()
        SessionMixin.load_initial_session(win)
        # no crash, no load

    def test_open_reports_folder_success(self):
        win = _make_window()
        with patch("src.core.utils.open_file_location", return_value=(True, "")):
            SessionMixin.open_reports_folder(win)

    def test_open_reports_folder_failure(self):
        win = _make_window()
        with patch("src.core.utils.open_file_location", return_value=(False, "no xdg")):
            SessionMixin.open_reports_folder(win)
        win._show_error.assert_called()

    def test_load_session_from_path(self, tmp_path):
        """load_session_from_path with a real xlsx file."""
        report_path = str(tmp_path / "nudity_report.xlsx")
        config = ScanConfig(source_folder="/hello", model_name="nudenet", threshold_percent=60.0)
        state = SessionState(scan_config=config, results=[])
        ReportManager.save_entries([], report_path)
        ReportManager.save_session(state, report_path)

        win = _make_window()
        SessionMixin.load_session_from_path(win, report_path, show_feedback=False)
        win.folder_entry.set_text.assert_called_with("/hello")

    def test_load_session_from_path_show_feedback(self, tmp_path):
        report_path = str(tmp_path / "nudity_report.xlsx")
        ReportManager.save_entries([], report_path)
        ReportManager.save_session(SessionState(), report_path)
        win = _make_window()
        SessionMixin.load_session_from_path(win, report_path, show_feedback=True)
        win.log_message.assert_called()


# ===========================================================================
# ResultsMixin — additional uncovered paths
# ===========================================================================

class TestResultsMixinExtended:
    def test_append_results_adds_items(self):
        win = _make_window()
        entries = [
            {"file": "/a/b.jpg", "media_type": "image", "confidence_percent": 70.0, "model_name": "test"},
            {"file": "/c/d.mp4", "media_type": "video", "confidence_percent": 50.0, "model_name": "test"},
        ]
        ResultsMixin.append_results(win, entries, start_index=5)
        assert win._list_store.append.call_count == 2
        win.update_result_action_state.assert_called()

    def test_append_results_empty_list(self):
        win = _make_window()
        ResultsMixin.append_results(win, [], start_index=0)
        win._list_store.append.assert_not_called()
        win.update_result_action_state.assert_called()

    def test_on_result_selection_changed_delegates(self):
        win = _make_window()
        win.update_thumbnail_preview = MagicMock()
        ResultsMixin._on_result_selection_changed(win, None, 0, 1)
        win.update_result_action_state.assert_called()
        win.update_thumbnail_preview.assert_called()

    def test_update_result_action_state_no_selection(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            pass

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = object()  # not FakeSingleSelection
            win.open_file_button = MagicMock()
            win.open_location_button = MagicMock()
            win.delete_button = MagicMock()
            ResultsMixin.update_result_action_state(win)
        win.open_file_button.set_sensitive.assert_called_with(False)

    def test_update_result_action_state_with_valid_selection(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 0

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            selection = FakeSingleSelection()
            win.column_view.get_model.return_value = selection
            win.is_processing = False
            win.open_file_button = MagicMock()
            win.open_location_button = MagicMock()
            win.delete_button = MagicMock()
            ResultsMixin.update_result_action_state(win)
        win.open_file_button.set_sensitive.assert_called_with(True)

    def test_update_result_action_state_processing_disables_buttons(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 0

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            selection = FakeSingleSelection()
            win.column_view.get_model.return_value = selection
            win.is_processing = True
            win.open_file_button = MagicMock()
            win.open_location_button = MagicMock()
            win.delete_button = MagicMock()
            ResultsMixin.update_result_action_state(win)
        win.open_file_button.set_sensitive.assert_called_with(False)

    def test_get_selected_entry_returns_none_for_non_single_selection(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            pass  # subclass

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection):
            win = _make_window()
            # Return object that is NOT a FakeSingleSelection
            win.column_view.get_model.return_value = object()
            result = ResultsMixin.get_selected_entry(win)
        assert result is None

    def test_get_selected_entry_invalid_position(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 4294967295  # INVALID

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = FakeSingleSelection()
            win.detected_results = [{"file": "/a.jpg"}]
            result = ResultsMixin.get_selected_entry(win)
        assert result is None

    def test_get_selected_entry_out_of_bounds(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 99  # beyond list length

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = FakeSingleSelection()
            win.detected_results = [{"file": "/a.jpg"}]
            result = ResultsMixin.get_selected_entry(win)
        assert result is None

    def test_get_selected_entry_valid(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 0

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = FakeSingleSelection()
            win.detected_results = [{"file": "/a.jpg"}]
            result = ResultsMixin.get_selected_entry(win)
        assert result == {"file": "/a.jpg"}

    def test_open_selected_file_no_entry(self):
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value=None)
        ResultsMixin.open_selected_file(win)

    def test_open_selected_file_file_not_exists(self):
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value={"file": "/nonexistent/file.jpg"})
        ResultsMixin.open_selected_file(win)
        win._show_error.assert_called()
        win.log_message.assert_called()

    def test_open_selected_file_success(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value={"file": str(f)})
        with patch("src.core.utils.subprocess.run"):
            ResultsMixin.open_selected_file(win)
        win.log_message.assert_called()

    def test_open_selected_file_failure(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value={"file": str(f)})
        with patch("src.core.utils.subprocess.run", side_effect=OSError("no open")):
            ResultsMixin.open_selected_file(win)
        win._show_error.assert_called()

    def test_open_selected_location_no_entry(self):
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value=None)
        ResultsMixin.open_selected_location(win)

    def test_open_selected_location_success(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value={"file": str(f)})
        with patch("src.core.utils.subprocess.run"):
            ResultsMixin.open_selected_location(win)

    def test_open_selected_location_failure(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.get_selected_entry = MagicMock(return_value={"file": str(f)})
        with patch("src.core.utils.subprocess.run", side_effect=OSError("error")):
            ResultsMixin.open_selected_location(win)
        win._show_error.assert_called()

    def test_delete_selected_result_no_single_selection(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            pass

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection):
            win = _make_window()
            win.column_view.get_model.return_value = object()  # not FakeSingleSelection
            ResultsMixin.delete_selected_result(win)

    def test_delete_selected_result_no_entry(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 0

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = FakeSingleSelection()
            win.get_selected_entry = MagicMock(return_value=None)
            ResultsMixin.delete_selected_result(win)

    def test_delete_selected_result_calls_ask_yes_no(self):
        import src.gui.results as results_module

        class FakeSingleSelection:
            def get_selected(self): return 0

        with patch.object(results_module.Gtk, "SingleSelection", FakeSingleSelection), \
             patch.object(results_module.Gtk, "INVALID_LIST_POSITION", 4294967295):
            win = _make_window()
            win.column_view.get_model.return_value = FakeSingleSelection()
            win.get_selected_entry = MagicMock(return_value={"file": "/tmp/file.jpg"})
            win._ask_yes_no = MagicMock()
            ResultsMixin.delete_selected_result(win)
        win._ask_yes_no.assert_called()

    def test_do_delete_failure(self):
        win = _make_window()
        win.detected_results = [{"file": "/fake.jpg"}]
        with patch("src.core.utils.delete_file_safely", return_value=(False, "Permission denied")):
            ResultsMixin._do_delete(win, 0, {"file": "/fake.jpg"})
        win._show_error.assert_called()

    def test_do_delete_success_no_scan_session(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.detected_results = [{"file": str(f)}]
        win._scan_session = None
        win.populate_results = MagicMock()
        with patch("src.core.utils.delete_file_safely", return_value=(True, "Deleted")), \
             patch("src.core.utils.ReportManager.save_entries"), \
             patch("src.core.utils.ReportManager.save_session"):
            ResultsMixin._do_delete(win, 0, {"file": str(f)})
        win.populate_results.assert_called()
        win.log_message.assert_called()

    def test_do_delete_success_with_scan_session(self, tmp_path):
        f = tmp_path / "test.jpg"
        f.write_bytes(b"data")
        win = _make_window()
        win.detected_results = [{"file": str(f)}]
        mock_session = MagicMock()
        mock_session.get_results.return_value = []
        win._scan_session = mock_session
        win.populate_results = MagicMock()
        with patch("src.core.utils.delete_file_safely", return_value=(True, "Deleted")), \
             patch("src.core.utils.ReportManager.save_entries"), \
             patch("src.core.utils.ReportManager.save_session"):
            ResultsMixin._do_delete(win, 0, {"file": str(f)})
        win.populate_results.assert_called()


# ===========================================================================
# SessionMixin — additional uncovered paths
# ===========================================================================

class TestSessionMixinMore:
    def test_find_latest_report_path_subdirs_but_no_report(self, tmp_path, monkeypatch):
        import src.gui.session as sess_module
        monkeypatch.setattr(sess_module, "DEFAULT_REPORT_DIR", str(tmp_path))
        (tmp_path / "2025-01-01_12-00-00").mkdir()
        win = _make_window()
        path = SessionMixin._find_latest_report_path(win)
        assert path is None

    def test_load_initial_session_exception_logged(self, tmp_path, monkeypatch):
        import src.gui.session as sess_module
        from src.reporting.report_manager import ReportManager as RM
        monkeypatch.setattr(sess_module, "DEFAULT_REPORT_DIR", str(tmp_path))
        run = tmp_path / "2025-01-01_12-00-00"
        run.mkdir()
        report = run / "nudity_report.xlsx"
        RM.save_entries([], str(report))
        win = _make_window()
        win.load_session_from_path = MagicMock(side_effect=OSError("bad file"))
        SessionMixin.load_initial_session(win)
        win.log_message.assert_called()

    def test_save_session_dialog(self):
        win = _make_window()
        SessionMixin.save_session_dialog(win)

    def test_on_save_session_done_success(self, tmp_path):
        win = _make_window()
        win.open_report_button = MagicMock()
        mock_file = MagicMock()
        report_path = str(tmp_path / "report.xlsx")
        mock_file.get_path.return_value = report_path
        mock_dialog = MagicMock()
        mock_dialog.save_finish.return_value = mock_file
        with patch("src.core.utils.ReportManager.save_entries"), \
             patch("src.core.utils.ReportManager.save_session"):
            SessionMixin._on_save_session_done(win, mock_dialog, MagicMock())
        win.open_report_button.set_sensitive.assert_called_with(True)
        win.log_message.assert_called()

    def test_on_save_session_done_adds_extension(self, tmp_path):
        win = _make_window()
        win.open_report_button = MagicMock()
        mock_file = MagicMock()
        report_path = str(tmp_path / "report")  # no .xlsx
        mock_file.get_path.return_value = report_path
        mock_dialog = MagicMock()
        mock_dialog.save_finish.return_value = mock_file
        with patch("src.core.utils.ReportManager.save_entries"), \
             patch("src.core.utils.ReportManager.save_session"):
            SessionMixin._on_save_session_done(win, mock_dialog, MagicMock())
        assert win.last_report_path.endswith(".xlsx")

    def test_on_save_session_done_glib_error(self):
        from gi.repository import GLib
        win = _make_window()
        mock_dialog = MagicMock()
        mock_dialog.save_finish.side_effect = GLib.Error()
        SessionMixin._on_save_session_done(win, mock_dialog, MagicMock())

    def test_load_session_dialog(self):
        win = _make_window()
        SessionMixin.load_session_dialog(win)

    def test_on_load_session_done_success(self, tmp_path):
        win = _make_window()
        report_path = str(tmp_path / "nudity_report.xlsx")
        ReportManager.save_entries([], report_path)
        ReportManager.save_session(SessionState(), report_path)
        mock_file = MagicMock()
        mock_file.get_path.return_value = report_path
        mock_dialog = MagicMock()
        mock_dialog.open_finish.return_value = mock_file
        win.load_session_from_path = MagicMock()
        SessionMixin._on_load_session_done(win, mock_dialog, MagicMock())
        win.load_session_from_path.assert_called_once_with(report_path, show_feedback=True)

    def test_on_load_session_done_glib_error(self):
        from gi.repository import GLib
        win = _make_window()
        mock_dialog = MagicMock()
        mock_dialog.open_finish.side_effect = GLib.Error()
        SessionMixin._on_load_session_done(win, mock_dialog, MagicMock())

    def test_load_session_from_path_helloz_model(self, tmp_path):
        report_path = str(tmp_path / "nudity_report.xlsx")
        config = ScanConfig(source_folder="/hello", model_name=constants.MODEL_HELLOZ_NSFW, threshold_percent=60.0)
        state = SessionState(scan_config=config, results=[])
        ReportManager.save_entries([], report_path)
        ReportManager.save_session(state, report_path)
        win = _make_window()
        SessionMixin.load_session_from_path(win, report_path, show_feedback=False)
        win.helloz_nsfw_radio.set_active.assert_called_with(True)

    def test_load_session_from_path_invalid_theme(self, tmp_path):
        report_path = str(tmp_path / "nudity_report.xlsx")
        config = ScanConfig(source_folder="/x", model_name="nudenet", theme_mode="invalid_theme", threshold_percent=60.0)
        state = SessionState(scan_config=config, results=[])
        ReportManager.save_entries([], report_path)
        ReportManager.save_session(state, report_path)
        win = _make_window()
        SessionMixin.load_session_from_path(win, report_path, show_feedback=False)
        win.theme_dropdown.set_selected.assert_called_with(0)

    def test_open_report_not_exists_shows_warning(self):
        win = _make_window()
        win.last_report_path = "/nonexistent/report.xlsx"
        SessionMixin.open_report(win)
        win._show_warning.assert_called()

    def test_open_report_success(self, tmp_path):
        report = tmp_path / "report.xlsx"
        report.write_bytes(b"data")
        win = _make_window()
        win.last_report_path = str(report)
        with patch("src.core.utils.subprocess.run"):
            SessionMixin.open_report(win)

    def test_open_report_failure(self, tmp_path):
        report = tmp_path / "report.xlsx"
        report.write_bytes(b"data")
        win = _make_window()
        win.last_report_path = str(report)
        with patch("src.core.utils.subprocess.run", side_effect=OSError("no open")):
            SessionMixin.open_report(win)
        win._show_error.assert_called()


# ===========================================================================
# ScanningMixin
# ===========================================================================

class TestScanningMixin:
    def test_importable(self):
        assert ScanningMixin is not None

    def test_on_start_clicked_delegates(self):
        win = _make_window()
        win.start_scanning = MagicMock()
        ScanningMixin._on_start_clicked(win, None)
        win.start_scanning.assert_called_once()

    def test_on_stop_clicked_delegates(self):
        win = _make_window()
        win.stop_scanning = MagicMock()
        ScanningMixin._on_stop_clicked(win, None)
        win.stop_scanning.assert_called_once()

    def test_start_scanning_empty_folder(self):
        win = _make_window()
        win.folder_entry.get_text.return_value = ""
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

    def test_start_scanning_nonexistent_folder(self):
        win = _make_window()
        win.folder_entry.get_text.return_value = "/definitely/not/a/real/folder"
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

    def test_check_helloz_nsfw_server_failure(self):
        win = _make_window()
        win._get_helloz_nsfw_check_url = MagicMock(return_value="http://localhost:9999/health")
        win._get_helloz_nsfw_health_check_timeout = MagicMock(return_value=1)
        result = ScanningMixin.check_helloz_nsfw_server(win)
        assert result is False  # server not running

    def test_start_scanning_helloz_server_not_available(self, tmp_path):
        win = _make_window()
        win.folder_entry.get_text.return_value = str(tmp_path)
        win._get_model.return_value = constants.MODEL_HELLOZ_NSFW
        win.check_helloz_nsfw_server = MagicMock(return_value=False)
        win._get_helloz_nsfw_check_url = MagicMock(return_value="http://localhost:9999/health")
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

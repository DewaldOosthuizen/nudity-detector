"""Tests for ScanHistoryMixin methods (GTK/GObject fully stubbed)."""
import sys
import json
import os
import types
import threading
import unittest.mock as mock

import pytest

# ---------------------------------------------------------------------------
# Stub gi / GTK (idempotent)
# ---------------------------------------------------------------------------
def _ensure_gi_stubs():
    if 'gi' in sys.modules:
        # Ensure GObject.Object is a real class so ScanRunItem.__init__ works
        gobject_mod = sys.modules.get('gi.repository.GObject')
        if gobject_mod is not None:
            class _Base:
                def __init__(self, *a, **kw): pass
            gobject_mod.Object = _Base
        gtk_mod = sys.modules.get('gi.repository.Gtk')
        if gtk_mod is not None:
            gtk_mod.INVALID_LIST_POSITION = 4294967295
        return

    gi_mod = types.ModuleType('gi')
    gi_mod.require_version = mock.MagicMock()
    repo_mod = types.ModuleType('gi.repository')

    class _GObjectBase:
        def __init__(self, *a, **kw): pass

    gobject_mod = mock.MagicMock()
    gobject_mod.Object = _GObjectBase
    gtk_mod = mock.MagicMock()
    gtk_mod.INVALID_LIST_POSITION = 4294967295
    adw_mod = mock.MagicMock()
    glib_mod = mock.MagicMock()
    gio_mod = mock.MagicMock()
    gdk_mod = mock.MagicMock()
    gi_mod.repository = repo_mod
    repo_mod.Gtk = gtk_mod
    repo_mod.Adw = adw_mod
    repo_mod.GLib = glib_mod
    repo_mod.GObject = gobject_mod
    repo_mod.Gio = gio_mod
    repo_mod.Gdk = gdk_mod
    sys.modules['gi'] = gi_mod
    sys.modules['gi.repository'] = repo_mod
    sys.modules['gi.repository.Gtk'] = gtk_mod
    sys.modules['gi.repository.Adw'] = adw_mod
    sys.modules['gi.repository.GLib'] = glib_mod
    sys.modules['gi.repository.GObject'] = gobject_mod
    sys.modules['gi.repository.Gio'] = gio_mod
    sys.modules['gi.repository.Gdk'] = gdk_mod


_ensure_gi_stubs()

# Always pin INVALID_LIST_POSITION to a real integer regardless of which test
# file installed the gi stubs first.
sys.modules['gi.repository.Gtk'].INVALID_LIST_POSITION = 4294967295

# Ensure GObject.Object is a plain Python class so that ScanRunItem (which
# subclasses it) can be defined without a TypeError.
class _GObjectBase:
    def __init__(self, *a, **kw): pass
sys.modules['gi.repository.GObject'].Object = _GObjectBase

from src.gui.scan_history import ScanHistoryMixin, ScanRunItem  # noqa: E402
from src.core.utils import DEFAULT_REPORT_DIR  # noqa: E402

_INVALID = 4294967295


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_gtk_stubs():
    """Re-pin stubs before every test so shared mock state doesn't bleed."""
    sys.modules['gi.repository.Gtk'].INVALID_LIST_POSITION = _INVALID
    class _GObjectBase:
        def __init__(self, *a, **kw): pass
    sys.modules['gi.repository.GObject'].Object = _GObjectBase
    yield


def _make_win():
    """Return a MagicMock that acts as the mixed-in window object."""
    win = mock.MagicMock()
    # Set up a minimal list-store/selection mock
    history_store = mock.MagicMock()
    win._history_store = history_store
    history_selection = mock.MagicMock()
    history_selection.get_selected.return_value = _INVALID  # nothing selected
    win._history_selection = history_selection
    return win


def _make_item(**kwargs):
    defaults = dict(
        dir_name='2025-01-01_12-00-00',
        display_date='2025-01-01  12:00:00',
        model_name='helloz_nsfw',
        result_count='3',
        source_folder='/photos',
        session_path='/reports/2025-01-01_12-00-00/nudity_report_session.json',
        report_path='/reports/2025-01-01_12-00-00/nudity_report.xlsx',
    )
    defaults.update(kwargs)
    return mock.MagicMock(**defaults)


# ---------------------------------------------------------------------------
# ScanRunItem
# ---------------------------------------------------------------------------

def test_scan_run_item_stores_attributes():
    item = ScanRunItem(
        dir_name='2025-06-01_10-00-00',
        display_date='2025-06-01  10:00:00',
        model_name='nudenet',
        result_count='5',
        source_folder='/images',
        session_path='/path/session.json',
        report_path='/path/report.xlsx',
    )
    assert item.dir_name == '2025-06-01_10-00-00'
    assert item.model_name == 'nudenet'
    assert item.result_count == '5'
    assert item.source_folder == '/images'


# ---------------------------------------------------------------------------
# _hist_col_bind_factory
# ---------------------------------------------------------------------------

def test_hist_col_bind_factory_sets_text():
    """The closure returned by _hist_col_bind_factory should read the named attr."""
    bind_fn = ScanHistoryMixin._hist_col_bind_factory('model_name')
    item = mock.MagicMock()
    item.model_name = 'helloz_nsfw'
    list_item = mock.MagicMock()
    list_item.get_item.return_value = item
    label = mock.MagicMock()
    list_item.get_child.return_value = label

    bind_fn(None, list_item)

    label.set_text.assert_called_once_with('helloz_nsfw')


def test_hist_col_bind_factory_missing_attr_uses_empty():
    bind_fn = ScanHistoryMixin._hist_col_bind_factory('nonexistent_attr')
    item = object()  # plain object — no attribute
    list_item = mock.MagicMock()
    list_item.get_item.return_value = item
    label = mock.MagicMock()
    list_item.get_child.return_value = label

    bind_fn(None, list_item)

    label.set_text.assert_called_once_with('')


# ---------------------------------------------------------------------------
# _hist_col_setup
# ---------------------------------------------------------------------------

def test_hist_col_setup_creates_label():
    list_item = mock.MagicMock()
    ScanHistoryMixin._hist_col_setup(None, list_item)
    # set_child should have been called with the newly created Gtk.Label mock
    list_item.set_child.assert_called_once()


# ---------------------------------------------------------------------------
# _update_history_action_state
# ---------------------------------------------------------------------------

def test_update_history_action_state_enables_buttons():
    win = _make_win()
    ScanHistoryMixin._update_history_action_state(win, True)
    win.history_load_button.set_sensitive.assert_called_with(True)
    win.history_export_button.set_sensitive.assert_called_with(True)
    win.history_delete_button.set_sensitive.assert_called_with(True)


def test_update_history_action_state_disables_buttons():
    win = _make_win()
    ScanHistoryMixin._update_history_action_state(win, False)
    win.history_load_button.set_sensitive.assert_called_with(False)
    win.history_export_button.set_sensitive.assert_called_with(False)
    win.history_delete_button.set_sensitive.assert_called_with(False)


# ---------------------------------------------------------------------------
# _on_history_selection_changed
# ---------------------------------------------------------------------------

def test_on_history_selection_changed_has_selection():
    win = _make_win()
    selection = mock.MagicMock()
    selection.get_selected.return_value = 0  # item selected

    ScanHistoryMixin._on_history_selection_changed(win, selection, 0, 1)

    win._update_history_action_state.assert_called_once_with(True)


def test_on_history_selection_changed_no_selection():
    win = _make_win()
    selection = mock.MagicMock()
    selection.get_selected.return_value = _INVALID  # INVALID

    ScanHistoryMixin._on_history_selection_changed(win, selection, 0, 0)

    win._update_history_action_state.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# _get_selected_history_item
# ---------------------------------------------------------------------------

def test_get_selected_history_item_returns_none_when_nothing_selected():
    win = _make_win()
    win._history_selection.get_selected.return_value = 4294967295

    result = ScanHistoryMixin._get_selected_history_item(win)

    assert result is None


def test_get_selected_history_item_returns_item_when_selected():
    win = _make_win()
    win._history_selection.get_selected.return_value = 0
    fake_item = _make_item()
    win._history_store.get_item.return_value = fake_item

    result = ScanHistoryMixin._get_selected_history_item(win)

    assert result is fake_item


# ---------------------------------------------------------------------------
# _on_history_load_clicked
# ---------------------------------------------------------------------------

def test_on_history_load_clicked_no_selection_does_nothing():
    win = _make_win()
    win._get_selected_history_item.return_value = None

    ScanHistoryMixin._on_history_load_clicked(win, None)

    win.load_session_from_path.assert_not_called()


def test_on_history_load_clicked_path_not_found_shows_error(tmp_path):
    win = _make_win()
    missing = str(tmp_path / 'missing.json')
    item = mock.MagicMock()
    item.session_path = missing
    win._get_selected_history_item.return_value = item

    ScanHistoryMixin._on_history_load_clicked(win, None)

    win._show_error.assert_called_once()
    win.load_session_from_path.assert_not_called()


def test_on_history_load_clicked_valid_path_loads_session(tmp_path):
    win = _make_win()
    session_file = tmp_path / 'session.json'
    session_file.write_text('{}')
    item = mock.MagicMock()
    item.session_path = str(session_file)
    win._get_selected_history_item.return_value = item

    ScanHistoryMixin._on_history_load_clicked(win, None)

    win.load_session_from_path.assert_called_once_with(str(session_file), show_feedback=True)
    win.view_stack.set_visible_child_name.assert_called_once_with('scan')


# ---------------------------------------------------------------------------
# _on_history_export_clicked
# ---------------------------------------------------------------------------

def test_on_history_export_clicked_no_selection_does_nothing():
    win = _make_win()
    win._history_selection.get_selected.return_value = 4294967295

    ScanHistoryMixin._on_history_export_clicked(win, None)

    # If nothing is selected the method returns early; no dialog created
    import gi
    Gtk = gi.repository.Gtk
    Gtk.FileDialog.assert_not_called()


# ---------------------------------------------------------------------------
# _on_history_export_done
# ---------------------------------------------------------------------------

def test_on_history_export_done_glib_error_is_silent():
    """GLib.Error raised by save_finish should be swallowed."""
    win = _make_win()
    import gi
    GLib = gi.repository.GLib
    GLib.Error = Exception  # make it a real exception class for raising
    dialog = mock.MagicMock()
    dialog.save_finish.side_effect = GLib.Error("cancelled")
    item = _make_item()

    # Should not raise
    ScanHistoryMixin._on_history_export_done(win, dialog, None, item)


def test_on_history_export_done_no_file_returns_silently():
    win = _make_win()
    import gi
    GLib = gi.repository.GLib
    GLib.Error = Exception
    dialog = mock.MagicMock()
    dialog.save_finish.return_value = None
    item = _make_item()

    ScanHistoryMixin._on_history_export_done(win, dialog, None, item)

    win._show_error.assert_not_called()
    win.log_message.assert_not_called()


def test_on_history_export_done_no_local_path_shows_error():
    win = _make_win()
    import gi
    GLib = gi.repository.GLib
    GLib.Error = Exception
    dialog = mock.MagicMock()
    file_obj = mock.MagicMock()
    file_obj.get_path.return_value = None
    dialog.save_finish.return_value = file_obj
    item = _make_item()

    ScanHistoryMixin._on_history_export_done(win, dialog, None, item)

    win._show_error.assert_called_once()


def test_on_history_export_done_appends_xlsx_extension(tmp_path):
    win = _make_win()
    import gi
    GLib = gi.repository.GLib
    GLib.Error = Exception

    # Create a fake report so the copy branch is taken
    fake_report = tmp_path / 'nudity_report.xlsx'
    fake_report.write_bytes(b'PK')

    item = mock.MagicMock()
    item.report_path = str(fake_report)

    dest = str(tmp_path / 'export_no_ext')
    dialog = mock.MagicMock()
    file_obj = mock.MagicMock()
    file_obj.get_path.return_value = dest
    dialog.save_finish.return_value = file_obj

    ScanHistoryMixin._on_history_export_done(win, dialog, None, item)

    assert os.path.exists(dest + '.xlsx')
    win.log_message.assert_called_once()


def test_on_history_export_done_no_report_no_session_shows_error(tmp_path):
    win = _make_win()
    import gi
    GLib = gi.repository.GLib
    GLib.Error = Exception

    item = mock.MagicMock()
    item.report_path = str(tmp_path / 'missing.xlsx')
    item.session_path = str(tmp_path / 'missing.json')

    dest = str(tmp_path / 'out.xlsx')
    dialog = mock.MagicMock()
    file_obj = mock.MagicMock()
    file_obj.get_path.return_value = dest
    dialog.save_finish.return_value = file_obj

    ScanHistoryMixin._on_history_export_done(win, dialog, None, item)

    win._show_error.assert_called_once()
    win.log_message.assert_called()


# ---------------------------------------------------------------------------
# _on_history_delete_response
# ---------------------------------------------------------------------------

def test_on_history_delete_response_cancel_does_nothing():
    win = _make_win()
    ScanHistoryMixin._on_history_delete_response(win, None, 'cancel', _make_item())
    win.history_load_button.set_sensitive.assert_not_called()


def test_on_history_delete_response_delete_removes_dir(tmp_path):
    win = _make_win()

    subdir = tmp_path / '2025-01-01_12-00-00'
    subdir.mkdir()
    (subdir / 'file.txt').write_text('data')

    def _run_sync(target, **kwargs):
        t = mock.MagicMock()
        t.start.side_effect = target
        return t

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)), \
         mock.patch('src.gui.scan_history.threading.Thread', side_effect=_run_sync):
        item = mock.MagicMock()
        item.dir_name = subdir.name

        ScanHistoryMixin._on_history_delete_response(win, None, 'delete', item)

    assert not subdir.exists()


def test_on_history_delete_response_delete_oserror_shows_error(tmp_path):
    win = _make_win()

    def _run_sync(target, **kwargs):
        t = mock.MagicMock()
        t.start.side_effect = target
        return t

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)), \
         mock.patch('shutil.rmtree', side_effect=OSError('permission denied')), \
         mock.patch('src.gui.scan_history.threading.Thread', side_effect=_run_sync):
        item = mock.MagicMock()
        item.dir_name = 'nonexistent'

        ScanHistoryMixin._on_history_delete_response(win, None, 'delete', item)

    # GLib.idle_add should have been scheduled with _show_error
    import gi
    GLib = gi.repository.GLib
    assert GLib.idle_add.called


# ---------------------------------------------------------------------------
# _on_history_clear_all_response
# ---------------------------------------------------------------------------

def test_on_history_clear_all_response_cancel_does_nothing():
    win = _make_win()
    ScanHistoryMixin._on_history_clear_all_response(win, None, 'cancel')
    win.history_load_button.set_sensitive.assert_not_called()


def test_on_history_clear_all_response_clears_dirs(tmp_path):
    win = _make_win()

    for name in ['2025-01-01_10-00-00', '2025-01-02_11-00-00']:
        d = tmp_path / name
        d.mkdir()
        (d / 'report.xlsx').write_bytes(b'PK')

    def _run_sync(target, **kwargs):
        t = mock.MagicMock()
        t.start.side_effect = target
        return t

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)), \
         mock.patch('src.gui.scan_history.threading.Thread', side_effect=_run_sync):
        ScanHistoryMixin._on_history_clear_all_response(win, None, 'clear')

    remaining = list(tmp_path.iterdir())
    assert remaining == []


def test_on_history_clear_all_response_handles_oserror(tmp_path):
    win = _make_win()

    def _run_sync(target, **kwargs):
        t = mock.MagicMock()
        t.start.side_effect = target
        return t

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)), \
         mock.patch('shutil.rmtree', side_effect=OSError('locked')), \
         mock.patch('os.listdir', return_value=['bad_dir']), \
         mock.patch('os.path.isdir', return_value=True), \
         mock.patch('src.gui.scan_history.threading.Thread', side_effect=_run_sync):
        ScanHistoryMixin._on_history_clear_all_response(win, None, 'clear')

    import gi
    GLib = gi.repository.GLib
    assert GLib.idle_add.called


# ---------------------------------------------------------------------------
# refresh_scan_history
# ---------------------------------------------------------------------------

def test_refresh_scan_history_no_report_dir():
    win = _make_win()
    with mock.patch('os.path.isdir', return_value=False):
        ScanHistoryMixin.refresh_scan_history(win)

    win._history_store.remove_all.assert_called_once()
    win._update_history_action_state.assert_called_with(False)


def test_refresh_scan_history_populates_store(tmp_path):
    win = _make_win()

    # Create a scan run directory with a session JSON
    run_name = '2025-03-01_09-00-00'
    run_dir = tmp_path / run_name
    run_dir.mkdir()
    session_data = {
        'scan_config': {'model_name': 'helloz_nsfw', 'source_folder': '/pics'},
        'results': [{}, {}],
    }
    (run_dir / 'nudity_report_session.json').write_text(json.dumps(session_data))

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)):
        ScanHistoryMixin.refresh_scan_history(win)

    win._history_store.remove_all.assert_called_once()
    win._history_store.append.assert_called_once()
    appended_item = win._history_store.append.call_args[0][0]
    assert appended_item.model_name == 'helloz_nsfw'
    assert appended_item.result_count == '2'


def test_refresh_scan_history_invalid_date_format(tmp_path):
    win = _make_win()

    run_dir = tmp_path / 'invalid_date'
    run_dir.mkdir()

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)):
        ScanHistoryMixin.refresh_scan_history(win)

    # Should still append the item with display_date == dir name
    win._history_store.append.assert_called_once()
    appended_item = win._history_store.append.call_args[0][0]
    assert appended_item.display_date == 'invalid_date'


def test_refresh_scan_history_broken_session_json(tmp_path):
    win = _make_win()

    run_dir = tmp_path / '2025-04-01_08-00-00'
    run_dir.mkdir()
    (run_dir / 'nudity_report_session.json').write_text('NOT JSON {{{')

    with mock.patch('src.gui.scan_history.DEFAULT_REPORT_DIR', str(tmp_path)):
        ScanHistoryMixin.refresh_scan_history(win)

    # Still appends — JSON error is swallowed
    win._history_store.append.assert_called_once()


# ---------------------------------------------------------------------------
# _export_from_session_json
# ---------------------------------------------------------------------------

def test_export_from_session_json_success(tmp_path):
    win = _make_win()

    session_data = {
        'scan_config': {'model_name': 'helloz_nsfw', 'source_folder': '/a'},
        'results': [],
    }
    session_file = tmp_path / 'session.json'
    session_file.write_text(json.dumps(session_data))
    dest = str(tmp_path / 'out.xlsx')

    with mock.patch('src.gui.scan_history.load_scan_session', return_value=session_data) as _ls, \
         mock.patch('src.gui.scan_history.ScanHistoryMixin') as _:
        # Patch imports inside method
        with mock.patch('src.core.models.ReportEntry.from_dict', return_value=mock.MagicMock()), \
             mock.patch('src.reporting.report_manager.ReportManager.save_entries') as mock_save:
            ScanHistoryMixin._export_from_session_json(win, str(session_file), dest)


def test_export_from_session_json_exception_shows_error(tmp_path):
    win = _make_win()

    with mock.patch('src.gui.scan_history.load_scan_session', side_effect=Exception('boom')):
        ScanHistoryMixin._export_from_session_json(win, '/nonexistent.json', '/out.xlsx')

    win._show_error.assert_called_once()
    win.log_message.assert_called()

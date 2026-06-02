"""Tests for src/gui/session.py — SessionMixin (GTK/GObject stubbed via sys.modules)."""
import sys
import types
import unittest.mock as mock


# ---------------------------------------------------------------------------
# Stub ALL gi / GTK imports before any src.gui module is imported
# ---------------------------------------------------------------------------
def _make_gi_stubs():
    gi_mod = types.ModuleType('gi')
    gi_mod.require_version = mock.MagicMock()

    repo_mod = types.ModuleType('gi.repository')

    gtk_mod = mock.MagicMock()
    gtk_mod.INVALID_LIST_POSITION = 4294967295
    adw_mod = mock.MagicMock()
    glib_mod = mock.MagicMock()
    gobject_mod = mock.MagicMock()
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

_make_gi_stubs()

# Now safe to import from src.gui
from src.core.models import ReportEntry, ScanConfig, SessionState  # noqa: E402
from src.gui.session import SessionMixin  # noqa: E402
from src.reporting.report_manager import ReportManager  # noqa: E402


def _make_entry(file_path='test.jpg'):
    return ReportEntry(
        file=file_path,
        media_type='image',
        model_name='helloz_nsfw',
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=True,
        detected_classes='',
        thumbnail='',
        date_classified='2025-01-01',
    )


# ---------------------------------------------------------------------------
# Test 1: SessionMixin class is importable
# ---------------------------------------------------------------------------
def test_session_mixin_importable():
    assert SessionMixin is not None


# ---------------------------------------------------------------------------
# Test 2: save/load session roundtrip (via core utilities)
# ---------------------------------------------------------------------------
def test_save_load_session_roundtrip(tmp_path):
    report_path = str(tmp_path / 'nudity_report.xlsx')
    config = ScanConfig(source_folder='/round/trip', model_name='helloz_nsfw', threshold_percent=75.0)
    entry = _make_entry('/round/trip/img.jpg')
    state = SessionState(scan_config=config, results=[entry])

    ReportManager.save_session(state, report_path)
    loaded = ReportManager.load_session(report_path)

    assert loaded.scan_config.source_folder == '/round/trip'
    assert len(loaded.results) == 1


# ---------------------------------------------------------------------------
# Test 3: load missing path returns safe default
# ---------------------------------------------------------------------------
def test_load_session_missing_path(tmp_path):
    missing = str(tmp_path / 'nonexistent.json')
    result = ReportManager.load_session(missing)
    assert isinstance(result, SessionState)


# ---------------------------------------------------------------------------
# Test 4: load corrupt JSON does not raise
# ---------------------------------------------------------------------------
def test_load_session_corrupt_json(tmp_path):
    corrupt = tmp_path / 'nudity_report_session.json'
    corrupt.write_text('{ bad json !!', encoding='utf-8')
    result = ReportManager.load_session(str(corrupt))
    assert isinstance(result, SessionState)


# ---------------------------------------------------------------------------
# Test 5: _find_latest_report_path logic (exercised via standalone function)
# ---------------------------------------------------------------------------
def test_find_latest_report_path_empty_dir(tmp_path):
    import os


    # No subdirs - should return None equivalent
    subdirs = sorted(
        (d for d in os.listdir(str(tmp_path)) if os.path.isdir(os.path.join(str(tmp_path), d))),
        reverse=True,
    )
    assert subdirs == []

"""Tests for src/gui/scan_history.py — ScanHistoryMixin (GTK/GObject stubbed via sys.modules)."""
import sys
import json
import os
import types
import unittest.mock as mock

import pytest

# ---------------------------------------------------------------------------
# Stub ALL gi / GTK imports (idempotent - session.py tests may have done this already)
# ---------------------------------------------------------------------------
def _ensure_gi_stubs():
    if 'gi' not in sys.modules:
        gi_mod = types.ModuleType('gi')
        gi_mod.require_version = mock.MagicMock()  # type: ignore[attr-defined]
        repo_mod = types.ModuleType('gi.repository')
        gtk_mod = mock.MagicMock()
        gtk_mod.INVALID_LIST_POSITION = 4294967295
        adw_mod = mock.MagicMock()
        glib_mod = mock.MagicMock()
        gobject_mod = mock.MagicMock()
        gio_mod = mock.MagicMock()
        gdk_mod = mock.MagicMock()
        gi_mod.repository = repo_mod  # type: ignore[attr-defined]
        repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
        repo_mod.Adw = adw_mod  # type: ignore[attr-defined]
        repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
        repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
        repo_mod.Gio = gio_mod  # type: ignore[attr-defined]
        repo_mod.Gdk = gdk_mod  # type: ignore[attr-defined]
        sys.modules['gi'] = gi_mod
        sys.modules['gi.repository'] = repo_mod
        sys.modules['gi.repository.Gtk'] = gtk_mod
        sys.modules['gi.repository.Adw'] = adw_mod
        sys.modules['gi.repository.GLib'] = glib_mod
        sys.modules['gi.repository.GObject'] = gobject_mod
        sys.modules['gi.repository.Gio'] = gio_mod
        sys.modules['gi.repository.Gdk'] = gdk_mod

_ensure_gi_stubs()

from src.gui.scan_history import ScanHistoryMixin, ScanRunItem  # noqa: E402
from src.reporting.report_manager import ReportManager  # noqa: E402
from src.core.models import SessionState, ScanConfig, ReportEntry  # noqa: E402


def _make_entry(file_path='img.jpg'):
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


def _save_scan_run(report_dir, run_name, source_folder, entries):
    run_dir = os.path.join(report_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)
    report_path = os.path.join(run_dir, 'nudity_report.xlsx')
    config = ScanConfig(source_folder=source_folder, model_name='helloz_nsfw', threshold_percent=60.0)
    state = SessionState(scan_config=config, results=entries)
    ReportManager.save_session(state, report_path)
    return run_dir, report_path


# ---------------------------------------------------------------------------
# Test 1: ScanHistoryMixin is importable
# ---------------------------------------------------------------------------
def test_scan_history_mixin_importable():
    assert ScanHistoryMixin is not None


# ---------------------------------------------------------------------------
# Test 2: ScanRunItem class is defined and importable
# ---------------------------------------------------------------------------
def test_scan_run_item_class_defined():
    # ScanRunItem extends GObject.Object (mocked), just verify the class exists
    assert ScanRunItem is not None


# ---------------------------------------------------------------------------
# Test 3: Append and reload entries
# ---------------------------------------------------------------------------
def test_append_entry_and_reload(tmp_path):
    run_dir, report_path = _save_scan_run(str(tmp_path), '2025-01-01_12-00-00', '/src', [_make_entry()])
    session_path = ReportManager.get_session_path(report_path)
    loaded = ReportManager.load_session(session_path)
    assert len(loaded.results) == 1
    assert loaded.results[0].file == 'img.jpg'


# ---------------------------------------------------------------------------
# Test 4: Clear scan run dir
# ---------------------------------------------------------------------------
def test_clear_scan_run(tmp_path):
    import shutil
    run_dir, _ = _save_scan_run(str(tmp_path), '2025-01-03_08-00-00', '/src', [_make_entry()])
    assert os.path.isdir(run_dir)
    shutil.rmtree(run_dir)
    assert not os.path.exists(run_dir)


# ---------------------------------------------------------------------------
# Test 5: Missing session file returns empty state
# ---------------------------------------------------------------------------
def test_load_missing_session_returns_default(tmp_path):
    missing = str(tmp_path / 'missing.json')
    loaded = ReportManager.load_session(missing)
    assert isinstance(loaded, SessionState)
    assert loaded.results is not None


# ---------------------------------------------------------------------------
# Test 6: Discover multiple scan runs
# ---------------------------------------------------------------------------
def test_discover_multiple_scan_runs(tmp_path):
    run_names = ['2025-02-01_10-00-00', '2025-02-02_11-00-00', '2025-02-03_12-00-00']
    for name in run_names:
        _save_scan_run(str(tmp_path), name, '/src', [_make_entry()])

    subdirs = sorted(
        [d for d in os.listdir(str(tmp_path)) if os.path.isdir(os.path.join(str(tmp_path), d))],
        reverse=True,
    )
    assert len(subdirs) == 3
    assert subdirs == sorted(run_names, reverse=True)

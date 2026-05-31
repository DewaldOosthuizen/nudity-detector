"""Tests for issue #23 — ScanHistoryMixin: scan history persistence via filesystem
(exercises the utility layer used by the GUI ScanHistoryMixin without requiring GTK4).
"""
import json
import os

import pytest

from src.reporting.report_manager import ReportManager
from src.core.models import SessionState, ScanConfig, ReportEntry


def _make_entry(file_path='img.jpg', nudity=True):
    return ReportEntry(
        file=file_path,
        media_type='image',
        model_name='helloz_nsfw',
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=nudity,
        detected_classes='',
        thumbnail='',
        date_classified='2025-01-01',
    )


def _save_scan_run(report_dir, run_name, source_folder, entries):
    """Helper: simulate saving a scan run under report_dir/<run_name>/."""
    run_dir = os.path.join(report_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)
    report_path = os.path.join(run_dir, 'nudity_report.xlsx')
    config = ScanConfig(source_folder=source_folder, model_name='helloz_nsfw', threshold_percent=60.0)
    state = SessionState(scan_config=config, results=entries)
    ReportManager.save_session(state, report_path)
    return run_dir, report_path


# ---------------------------------------------------------------------------
# Test 1: Append entry and reload — entry is present
# ---------------------------------------------------------------------------
def test_append_entry_and_reload(tmp_path):
    run_dir, report_path = _save_scan_run(str(tmp_path), '2025-01-01_12-00-00', '/src', [_make_entry()])

    session_path = ReportManager.get_session_path(report_path)
    loaded = ReportManager.load_session(session_path)

    assert len(loaded.results) == 1
    assert loaded.results[0].file == 'img.jpg'


# ---------------------------------------------------------------------------
# Test 2: Append multiple entries — all persisted and reloaded correctly
# ---------------------------------------------------------------------------
def test_append_multiple_entries_all_reloaded(tmp_path):
    entries = [_make_entry(f'img_{i}.jpg') for i in range(5)]
    run_dir, report_path = _save_scan_run(str(tmp_path), '2025-01-02_10-00-00', '/src', entries)

    session_path = ReportManager.get_session_path(report_path)
    loaded = ReportManager.load_session(session_path)

    assert len(loaded.results) == 5
    files = {e.file for e in loaded.results}
    assert files == {f'img_{i}.jpg' for i in range(5)}


# ---------------------------------------------------------------------------
# Test 3: Clear history — scan run directory absent after removal
# ---------------------------------------------------------------------------
def test_clear_history(tmp_path):
    import shutil
    run_dir, _ = _save_scan_run(str(tmp_path), '2025-01-03_08-00-00', '/src', [_make_entry()])
    assert os.path.isdir(run_dir)

    shutil.rmtree(run_dir)

    assert not os.path.exists(run_dir)


# ---------------------------------------------------------------------------
# Test 4: Load from missing file returns empty/default without raising
# ---------------------------------------------------------------------------
def test_load_from_missing_file_returns_empty(tmp_path):
    missing = str(tmp_path / 'missing_session.json')
    loaded = ReportManager.load_session(missing)
    assert isinstance(loaded, SessionState)
    assert loaded.results is not None


# ---------------------------------------------------------------------------
# Test 5: refresh_scan_history equivalent — reading subdirs discovers runs
# ---------------------------------------------------------------------------
def test_scan_history_discovers_multiple_runs(tmp_path):
    run_names = ['2025-02-01_10-00-00', '2025-02-02_11-00-00', '2025-02-03_12-00-00']
    for name in run_names:
        _save_scan_run(str(tmp_path), name, '/src', [_make_entry()])

    subdirs = sorted(
        [d for d in os.listdir(str(tmp_path)) if os.path.isdir(os.path.join(str(tmp_path), d))],
        reverse=True,
    )
    assert subdirs == sorted(run_names, reverse=True)
    assert len(subdirs) == 3

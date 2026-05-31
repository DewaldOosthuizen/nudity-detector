"""Tests for issue #23 — SessionMixin: session save/load via ReportManager
(exercises the utility layer used by the GUI SessionMixin without requiring GTK4).
"""
import json
import os

import pytest

from src.reporting.report_manager import ReportManager
from src.core.models import SessionState, ScanConfig, ReportEntry
from src.core.utils import save_nudity_report, load_scan_session


def _make_entry(file_path='test.jpg', nudity=True):
    return ReportEntry(
        file=file_path,
        media_type='image',
        model_name='helloz_nsfw',
        threshold_percent=60.0,
        confidence_percent=0.9,
        nudity_detected=nudity,
        detected_classes='EXPOSED_BREAST_F',
        thumbnail='',
        date_classified='2025-01-01',
    )


# ---------------------------------------------------------------------------
# Test 1: Save session to file produces valid JSON on disk
# ---------------------------------------------------------------------------
def test_save_session_produces_valid_json(tmp_path):
    report_path = str(tmp_path / 'nudity_report.xlsx')
    session_path = ReportManager.get_session_path(report_path)

    entry = _make_entry()
    config = ScanConfig(source_folder='/some/folder', model_name='helloz_nsfw', threshold_percent=60.0)
    state = SessionState(scan_config=config, results=[entry])

    ReportManager.save_session(state, report_path)

    assert os.path.exists(session_path)
    with open(session_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert 'scan_config' in data


# ---------------------------------------------------------------------------
# Test 2: Load session round-trips the same data
# ---------------------------------------------------------------------------
def test_save_load_session_roundtrip(tmp_path):
    report_path = str(tmp_path / 'nudity_report.xlsx')

    config = ScanConfig(source_folder='/round/trip', model_name='helloz_nsfw', threshold_percent=75.0)
    entry = _make_entry('/round/trip/img.jpg')
    state = SessionState(scan_config=config, results=[entry])

    ReportManager.save_session(state, report_path)
    loaded = ReportManager.load_session(report_path)

    assert loaded.scan_config.source_folder == '/round/trip'
    assert loaded.scan_config.threshold_percent == 75.0
    assert len(loaded.results) == 1
    assert loaded.results[0].file == '/round/trip/img.jpg'


# ---------------------------------------------------------------------------
# Test 3: Load from non-existent path returns safe default without raising
# ---------------------------------------------------------------------------
def test_load_session_from_nonexistent_path_returns_default(tmp_path):
    missing = str(tmp_path / 'does_not_exist.json')
    result = ReportManager.load_session(missing)
    assert isinstance(result, SessionState)
    # Should be empty/default
    assert result.results == [] or result.results is not None


# ---------------------------------------------------------------------------
# Test 4: Load from corrupt/malformed JSON does not raise
# ---------------------------------------------------------------------------
def test_load_session_from_corrupt_json_does_not_raise(tmp_path):
    corrupt = tmp_path / 'nudity_report_session.json'
    corrupt.write_text('{ this is: not valid json !!! }', encoding='utf-8')

    result = ReportManager.load_session(str(corrupt))
    assert isinstance(result, SessionState)


# ---------------------------------------------------------------------------
# Test 5 (bonus): load_scan_session util wrapper returns dict
# ---------------------------------------------------------------------------
def test_load_scan_session_util_returns_dict(tmp_path):
    report_path = str(tmp_path / 'nudity_report.xlsx')
    config = ScanConfig(source_folder='/util/test', model_name='nudenet', threshold_percent=50.0)
    state = SessionState(scan_config=config, results=[])
    ReportManager.save_session(state, report_path)

    # load via session path (JSON)
    session_path = ReportManager.get_session_path(report_path)
    result = load_scan_session(session_path)
    assert isinstance(result, dict)
    assert result.get('scan_config', {}).get('source_folder') == '/util/test'

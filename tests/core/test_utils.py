"""Tests for src/core/utils.py"""
import sys
import pytest

# Stub heavy optional deps before importing source modules
from unittest.mock import MagicMock
sys.modules["nudenet"] = MagicMock()

from src.core.utils import (
    normalize_threshold,
    threshold_to_percent,
    make_scan_config,
    get_detected_results,
)


@pytest.mark.parametrize("value,expected", [
    (60, 0.6),
    (0.6, 0.6),
    (0, 0.0),
    (100, 1.0),
    (150, 1.0),
    (-10, 0.0),
    (None, 0.6),
])
def test_normalize_threshold(value, expected):
    assert normalize_threshold(value) == pytest.approx(expected)


def test_threshold_to_percent_roundtrip():
    pct = threshold_to_percent(0.75)
    assert pct == pytest.approx(75.0)
    pct2 = threshold_to_percent(75)
    assert pct2 == pytest.approx(75.0)


def test_make_scan_config_defaults():
    config = make_scan_config()
    assert config["model_name"] == "nudenet"
    assert config["threshold_percent"] == pytest.approx(60.0)


def test_make_scan_config_custom():
    config = make_scan_config(source_folder="/tmp/images", threshold_percent=80)
    assert config["source_folder"] == "/tmp/images"
    assert config["threshold_percent"] == pytest.approx(80.0)


def test_get_detected_results_filters_by_nudity_detected():
    data = [
        {"nudity_detected": True, "file": "a.jpg"},
        {"nudity_detected": False, "file": "b.jpg"},
        {"nudity_detected": True, "file": "c.jpg"},
    ]
    results = get_detected_results(data)
    assert len(results) == 2
    assert all(r["nudity_detected"] for r in results)


def test_handle_results_uses_session(tmp_path):
    """handle_results appends entry to the provided ScanSession."""
    from src.core.scan_session import ScanSession
    from src.core.utils import handle_results

    session = ScanSession()
    entry = handle_results(
        file_path=str(tmp_path / "test.jpg"),
        nudity_detected=False,
        raw_result=[],
        session=session,
        report_dir=str(tmp_path),
    )
    results = session.get_results()
    assert len(results) == 1
    assert results[0].file == str(tmp_path / "test.jpg")

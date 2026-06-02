"""Tests for src/core/models.py — focused on missed lines 95, 134-137, 145."""
import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("nudenet", MagicMock())

from src.core.models import DetectionResult, ReportEntry, ScanConfig, SessionState

# ---------------------------------------------------------------------------
# SessionState.__post_init__ — scan_config dict conversion (line 95)
# ---------------------------------------------------------------------------

def test_session_state_converts_dict_scan_config():
    """SessionState.__post_init__ converts dict scan_config to ScanConfig."""
    state = SessionState(
        scan_config={"source_folder": "/test", "model_name": "nudenet",
                     "threshold_percent": 60.0, "theme_mode": "system"}
    )
    assert isinstance(state.scan_config, ScanConfig)
    assert state.scan_config.source_folder == "/test"


def test_session_state_keeps_scan_config_object():
    """SessionState keeps ScanConfig as-is when already a ScanConfig."""
    cfg = ScanConfig(source_folder="/data", model_name="helloz_nsfw")
    state = SessionState(scan_config=cfg)
    assert state.scan_config is cfg


# ---------------------------------------------------------------------------
# DetectionResult._serialize_classes (lines 134-137)
# ---------------------------------------------------------------------------

def test_serialize_classes_list_to_json():
    """_serialize_classes serializes a list to a JSON string."""
    result = DetectionResult(
        file_path="/a.jpg",
        media_type="image",
        model_name="test",
        raw_data={},
        detected_classes=["NSFW", "explicit"],
    )
    serialized = result._serialize_classes()
    assert '"NSFW"' in serialized
    assert '"explicit"' in serialized


def test_serialize_classes_non_serializable_falls_back():
    """_serialize_classes falls back to str() on TypeError."""
    result = DetectionResult(
        file_path="/a.jpg",
        media_type="image",
        model_name="test",
        raw_data={},
        detected_classes=[object()],  # not JSON serializable
    )
    serialized = result._serialize_classes()
    assert isinstance(serialized, str)
    assert len(serialized) > 0


def test_serialize_classes_empty_list():
    """_serialize_classes returns '[]' for empty list."""
    result = DetectionResult(
        file_path="/a.jpg",
        media_type="image",
        model_name="test",
        raw_data={},
    )
    serialized = result._serialize_classes()
    assert serialized == "[]"


# ---------------------------------------------------------------------------
# DetectionResult.to_report_entry (line 145)
# ---------------------------------------------------------------------------

def test_to_report_entry_creates_report_entry():
    """to_report_entry returns a ReportEntry with correct values."""
    result = DetectionResult(
        file_path="/nude.jpg",
        media_type="image",
        model_name="nudenet",
        raw_data=[],
        max_confidence=0.85,
        nudity_detected=True,
        detected_classes=["NUDE"],
    )
    entry = result.to_report_entry(threshold_percent=60.0, thumbnail="b64data")
    assert isinstance(entry, ReportEntry)
    assert entry.file == "/nude.jpg"
    assert entry.confidence_percent == pytest.approx(85.0, abs=0.1)
    assert entry.nudity_detected is True
    assert entry.thumbnail == "b64data"
    assert entry.model_name == "nudenet"


def test_to_report_entry_clamps_confidence():
    """to_report_entry clamps confidence to [0, 100]."""
    result = DetectionResult(
        file_path="/a.jpg",
        media_type="image",
        model_name="test",
        raw_data={},
        max_confidence=1.5,  # > 1.0, should be clamped
    )
    entry = result.to_report_entry()
    assert entry.confidence_percent == 100.0


def test_to_report_entry_negative_confidence():
    """to_report_entry clamps negative confidence to 0."""
    result = DetectionResult(
        file_path="/a.jpg",
        media_type="image",
        model_name="test",
        raw_data={},
        max_confidence=-0.5,
    )
    entry = result.to_report_entry()
    assert entry.confidence_percent == 0.0

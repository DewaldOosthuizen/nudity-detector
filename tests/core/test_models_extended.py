"""
Additional tests for src/core/models.py — covering DetectionResult,
SessionState.__post_init__, and DetectionResult._serialize_classes.
"""
import json
import sys
from unittest.mock import MagicMock

import pytest


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

from src.core.models import DetectionResult, ReportEntry, ScanConfig, SessionState  # noqa: E402

# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

def test_session_state_post_init_converts_dict_scan_config():
    # Pass a dict — __post_init__ should convert it to ScanConfig
    state = SessionState.__new__(SessionState)
    state.version = "1.0"
    state.saved_at = ""
    state.scan_config = {"source_folder": "/tmp", "model_name": "helloz"}
    state.results = []
    state.__post_init__()
    assert isinstance(state.scan_config, ScanConfig)


def test_session_state_post_init_sets_saved_at():
    state = SessionState()
    assert state.saved_at != ""


def test_session_state_from_dict_roundtrip():
    original = SessionState()
    d = original.to_dict()
    restored = SessionState.from_dict(d)
    assert restored.version == original.version


# ---------------------------------------------------------------------------
# DetectionResult
# ---------------------------------------------------------------------------

def test_detection_result_serialize_classes_valid():
    dr = DetectionResult(
        file_path="/tmp/x.jpg",
        media_type="image",
        model_name="helloz",
        raw_data={},
        detected_classes=["EXPOSED_BREAST_F", "EXPOSED_BELLY"],
    )
    serialized = dr._serialize_classes()
    loaded = json.loads(serialized)
    assert loaded == ["EXPOSED_BREAST_F", "EXPOSED_BELLY"]


def test_detection_result_to_report_entry():
    dr = DetectionResult(
        file_path="/tmp/img.jpg",
        media_type="image",
        model_name="helloz",
        raw_data={"data": {"nsfw": 0.85}},
        max_confidence=0.85,
        nudity_detected=True,
        detected_classes=["EXPOSED_BREAST_F"],
    )
    entry = dr.to_report_entry(threshold_percent=60.0)
    assert isinstance(entry, ReportEntry)
    assert entry.file == "/tmp/img.jpg"
    assert entry.nudity_detected is True
    assert entry.confidence_percent == pytest.approx(85.0, abs=0.1)


def test_detection_result_clamps_confidence():
    dr = DetectionResult(
        file_path="/tmp/img.jpg",
        media_type="image",
        model_name="helloz",
        raw_data={},
        max_confidence=1.5,  # over 1.0 — should clamp to 100%
        nudity_detected=True,
    )
    entry = dr.to_report_entry()
    assert entry.confidence_percent == pytest.approx(100.0, abs=0.1)

"""Tests for src/detectors/nudenet.py"""
import sys
from unittest.mock import MagicMock

import pytest

# MUST stub nudenet before any import of src.detectors.nudenet
sys.modules["nudenet"] = MagicMock()

from src.detectors.nudenet import get_nudenet_confidence, simplify_nudenet_results


def test_simplify_nudenet_results_strips_box():
    raw = [{"label": "BELLY_EXPOSED", "score": 0.9, "box": [0, 0, 100, 100]}]
    result = simplify_nudenet_results(raw)
    assert result == [{"class": "BELLY_EXPOSED", "score": 0.9}]
    assert "box" not in result[0]


def test_simplify_nudenet_results_empty_input():
    assert simplify_nudenet_results([]) == []


def test_get_nudenet_confidence_picks_nudity_class_only():
    """FACE_F is not in NUDITY_CLASSES_STRICT; nudity classes should be picked up."""
    from src.core import constants
    # Build a nudity class label from the strict set
    nudity_label = next(iter(constants.NUDITY_CLASSES_STRICT))
    raw = [
        {"label": "FACE_F", "score": 0.99},
        {"label": nudity_label, "score": 0.85},
        {"label": nudity_label, "score": 0.70},
    ]
    confidence = get_nudenet_confidence(raw)
    assert confidence == pytest.approx(0.85)


def test_get_nudenet_confidence_empty():
    assert get_nudenet_confidence([]) == 0.0


"""Tests for issue #91 — timeout unit normalization (ms→s conversion)."""
import json
import os

from src.core import constants


def test_milliseconds_to_seconds_converts():
    """250 ms → 0.25 s."""
    assert constants.milliseconds_to_seconds(250) == 0.25


def test_normalize_timeout_seconds_passes_through_seconds():
    """Values already in seconds pass through unchanged."""
    assert constants.normalize_timeout_seconds(5, 5) == 5
    assert constants.normalize_timeout_seconds(60, 60) == 60


def test_normalize_timeout_seconds_converts_legacy_milliseconds():
    """Values >= LEGACY_TIMEOUT_MS_THRESHOLD are converted from ms to s."""
    assert constants.normalize_timeout_seconds(2500, 5) == 3  # round-half-up: 2.5 → 3
    assert constants.normalize_timeout_seconds(1500, 5) == 2  # round-half-up: 1.5 → 2


def test_normalize_timeout_seconds_none_returns_default():
    """None falls back to default."""
    assert constants.normalize_timeout_seconds(None, 5) == 5


def test_normalize_timeout_seconds_invalid_returns_default():
    """Invalid values (string) fall back to default."""
    assert constants.normalize_timeout_seconds("abc", 5) == 5


def test_normalize_timeout_seconds_zero_clamps_to_one():
    """Zero is clamped to 1."""
    assert constants.normalize_timeout_seconds(0, 5) == 1


def test_normalize_timeout_seconds_negative_clamps_to_one():
    """Negative values are clamped to 1."""
    assert constants.normalize_timeout_seconds(-3, 5) == 1


def test_config_defaults_match_constants():
    """Config defaults use seconds matching the constants."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "app_config.json",
    )
    with open(config_path) as f:
        cfg = json.load(f)
    assert cfg["worker_thread_timeout"] == constants.WORKER_THREAD_TIMEOUT
    assert cfg["detect_timeout"] == constants.DETECT_TIMEOUT
    # Both must be below the legacy-ms threshold (genuinely seconds, not leftover ms)
    assert cfg["worker_thread_timeout"] < constants.LEGACY_TIMEOUT_MS_THRESHOLD
    assert cfg["detect_timeout"] < constants.LEGACY_TIMEOUT_MS_THRESHOLD


def test_constants_are_seconds_scale():
    """Guard against re-introduction of ms defaults."""
    assert constants.WORKER_THREAD_TIMEOUT == 5
    assert constants.DETECT_TIMEOUT == 60
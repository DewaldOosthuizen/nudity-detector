"""Tests for issue #91 — timeout unit normalization (ms→s conversion)."""
import json
import os

from src.core import constants


def _default_config_path():
    """Return the path to the committed default-config fixture.

    The runtime ``config/app_config.json`` is deliberately NOT committed: the app
    writes user state (theme, model, last_source_folder) into it, so tracking it
    would leave every working tree permanently dirty. Defaults are therefore
    asserted against the immutable fixture copy.

    Returns:
        Absolute path to ``tests/fixtures/app_config.default.json``.
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "fixtures", "app_config.default.json",
    )


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


def test_normalize_timeout_seconds_non_finite_returns_default():
    """Non-finite floats (inf/nan) raise OverflowError/ValueError in ``int()``.

    The defensive boundary must fall back to the default, not propagate.
    """
    assert constants.normalize_timeout_seconds(float("inf"), 5) == 5
    assert constants.normalize_timeout_seconds(float("nan"), 5) == 5


def test_normalize_timeout_seconds_threshold_boundary():
    """The legacy-ms threshold boundary is pinned: 999 stays seconds, 1000 converts."""
    assert constants.normalize_timeout_seconds(999, 5) == 999
    assert constants.normalize_timeout_seconds(1000, 5) == 1
    assert constants.normalize_timeout_seconds(1001, 5) == 1
    # 1499 ms -> 1.499 s rounds down to 1; 1500 ms -> 1.5 s rounds half-up to 2.
    assert constants.normalize_timeout_seconds(1499, 5) == 1
    assert constants.normalize_timeout_seconds(1500, 5) == 2
    assert constants.normalize_timeout_seconds(1999, 5) == 2
    assert constants.normalize_timeout_seconds(2000, 5) == 2


def test_normalize_timeout_seconds_truncates_fractional_seconds():
    """Fractional seconds truncate toward zero (int()), then clamp to >= 1."""
    assert constants.normalize_timeout_seconds(2.7, 5) == 2
    assert constants.normalize_timeout_seconds(59.9, 5) == 59
    assert constants.normalize_timeout_seconds(0.5, 5) == 1


def test_normalize_timeout_seconds_accepts_numeric_strings():
    """Numeric strings from a hand-edited config are accepted."""
    assert constants.normalize_timeout_seconds("30", 5) == 30
    assert constants.normalize_timeout_seconds(" 45 ", 5) == 45


def test_normalize_timeout_seconds_bool_is_accepted_as_int():
    """``bool`` is an ``int`` subclass, so it is coerced rather than rejected.

    Documented-by-design: ``True`` yields 1 s and ``False`` clamps to 1 s. A
    boolean in the config is a user error, but the boundary never raises.
    """
    assert constants.normalize_timeout_seconds(True, 5) == 1
    assert constants.normalize_timeout_seconds(False, 5) == 1


def test_normalize_timeout_seconds_logs_when_converting_legacy_ms(caplog):
    """A legacy-ms conversion emits a warning naming the setting.

    The heuristic guess about units must be visible in the log, otherwise a
    legitimate seconds value >= 1000 would be silently divided by 1000.
    """
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_timeout_seconds(3600, 60, name="detect_timeout")
    assert result == 4
    assert "detect_timeout" in caplog.text
    assert "milliseconds" in caplog.text


def test_normalize_timeout_seconds_logs_on_invalid_value(caplog):
    """An unparseable value emits a warning rather than presenting silently."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_timeout_seconds("abc", 60, name="detect_timeout_spin")
    assert result == 60
    assert "detect_timeout_spin" in caplog.text


def test_normalize_timeout_seconds_does_not_warn_when_unset(caplog):
    """An absent key is normal on a fresh install — it must not warn."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_timeout_seconds(None, 60, name="detect_timeout")
    assert result == 60
    assert caplog.text == ""


def test_normalize_timeout_seconds_accepts_no_name_argument():
    """The optional ``name`` argument stays optional for existing call sites."""
    assert constants.normalize_timeout_seconds(7, 5) == 7


def test_config_defaults_match_constants():
    """Default config values use seconds matching the constants."""
    with open(_default_config_path()) as f:
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

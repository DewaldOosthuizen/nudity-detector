"""Tests for issue #91 — timeout units: normalization and one-time migration.

Two layers are covered:

* ``constants.normalize_positive_int`` / ``normalize_timeout_seconds`` — the read
  boundary. It assumes seconds; no unit is inferred from a value's magnitude.
* ``config_migration.migrate_config`` — the one-time, deterministic conversion of a
  pre-ADD-007 millisecond config, including the shipped ``250`` value.
"""
import json
import os
from unittest.mock import patch

import pytest

from src.core import config_migration, constants


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


def _load_default_config():
    """Return the default-config fixture as a dict.

    Returns:
        The parsed fixture mapping.
    """
    with open(_default_config_path()) as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# normalize_positive_int — the shared config-scalar coercion
# ---------------------------------------------------------------------------

def test_normalize_positive_int_passes_through():
    """Values already above the minimum pass through unchanged."""
    assert constants.normalize_positive_int(5, 10) == 5
    assert constants.normalize_positive_int(60, 10) == 60


def test_normalize_positive_int_none_returns_default():
    """An absent key falls back to the default (logged at DEBUG, not WARNING)."""
    assert constants.normalize_positive_int(None, 10) == 10


def test_normalize_positive_int_invalid_returns_default():
    """An unparseable value falls back to the default."""
    assert constants.normalize_positive_int("abc", 10) == 10


def test_normalize_positive_int_non_finite_returns_default():
    """Non-finite floats raise OverflowError/ValueError in ``int()``.

    The defensive boundary must fall back to the default, not propagate.
    """
    assert constants.normalize_positive_int(float("inf"), 10) == 10
    assert constants.normalize_positive_int(float("nan"), 10) == 10


def test_normalize_positive_int_accepts_numeric_strings():
    """Numeric strings from a hand-edited config are accepted."""
    assert constants.normalize_positive_int("30", 10) == 30
    assert constants.normalize_positive_int(" 45 ", 10) == 45


def test_normalize_positive_int_truncates_fractions():
    """Fractional values truncate toward zero, then clamp to the minimum."""
    assert constants.normalize_positive_int(2.7, 10) == 2
    assert constants.normalize_positive_int(0.5, 10) == 1


def test_normalize_positive_int_clamps_zero_and_negative():
    """Zero and negative values clamp up to the minimum."""
    assert constants.normalize_positive_int(0, 10) == 1
    assert constants.normalize_positive_int(-3, 10) == 1


def test_normalize_positive_int_honours_custom_minimum():
    """A caller-supplied minimum is respected."""
    assert constants.normalize_positive_int(0, 10, min_value=300) == 300
    assert constants.normalize_positive_int(300, 10, min_value=300) == 300


def test_normalize_positive_int_rejects_bool(caplog):
    """``bool`` is rejected explicitly: a JSON ``true`` is a user error, not 1."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_positive_int(True, 60, name="detect_timeout_seconds") == 60
        assert constants.normalize_positive_int(False, 60, name="detect_timeout_seconds") == 60
    assert "detect_timeout_seconds" in caplog.text
    assert "boolean" in caplog.text


def test_normalize_positive_int_clamps_default_too():
    """The documented lower bound holds even when a zero default is supplied.

    Regression guard: the docstring promises ``>= min_value``; an unclamped fallback
    would violate that contract the first time a default became 0.
    """
    assert constants.normalize_positive_int(None, 0) == 1
    assert constants.normalize_positive_int("abc", 0) == 1


def test_normalize_positive_int_does_not_warn_when_unset(caplog):
    """An absent key is normal on a fresh install — it must not warn."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_positive_int(None, 60, name="detect_timeout_seconds")
    assert result == 60
    assert caplog.text == ""


# ---------------------------------------------------------------------------
# normalize_timeout_seconds — the timeout unit boundary
# ---------------------------------------------------------------------------

def test_normalize_timeout_seconds_passes_through_seconds():
    """Values already in seconds pass through unchanged."""
    assert constants.normalize_timeout_seconds(5, 5) == 5
    assert constants.normalize_timeout_seconds(60, 60) == 60


def test_normalize_timeout_seconds_does_not_guess_units():
    """A large seconds value is honoured — there is no millisecond heuristic.

    Regression guard for the ADD-007 defect: the previous implementation treated any
    value ``>= 1000`` as milliseconds, silently rewriting a legitimate
    ``detect_timeout: 3600`` down to 4 seconds.
    """
    assert constants.normalize_timeout_seconds(3600, 60) == 3600
    assert constants.normalize_timeout_seconds(1000, 60) == 1000
    assert constants.normalize_timeout_seconds(250, 60) == 250


def test_normalize_timeout_seconds_none_returns_default():
    """None falls back to default."""
    assert constants.normalize_timeout_seconds(None, 5) == 5


def test_normalize_timeout_seconds_invalid_returns_default(caplog):
    """An unparseable value falls back to the default and warns, naming the setting."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_timeout_seconds("abc", 60, name="detect_timeout_seconds")
    assert result == 60
    assert "detect_timeout_seconds" in caplog.text


def test_normalize_timeout_seconds_zero_clamps_to_one(caplog):
    """Zero clamps to 1 and the clamp is logged."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_timeout_seconds(0, 5, name="worker_thread_timeout_seconds") == 1
    assert "worker_thread_timeout_seconds" in caplog.text


def test_normalize_timeout_seconds_negative_clamps_to_one(caplog):
    """Negative values clamp to 1 and the clamp is logged.

    A negative timeout is a config error; surfacing it prevents an unexplained
    1-second join timeout later.
    """
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_timeout_seconds(-3, 5, name="worker_thread_timeout_seconds") == 1
    assert "worker_thread_timeout_seconds" in caplog.text


def test_normalize_timeout_seconds_non_finite_returns_default():
    """Non-finite floats (inf/nan) fall back to the default, not propagate."""
    assert constants.normalize_timeout_seconds(float("inf"), 5) == 5
    assert constants.normalize_timeout_seconds(float("nan"), 5) == 5


def test_normalize_timeout_seconds_always_at_least_one():
    """The ``>= 1`` guarantee holds on every path, including the default fallback."""
    for value in (None, "abc", 0, -1, float("inf"), True):
        assert constants.normalize_timeout_seconds(value, 0) >= 1


def test_normalize_timeout_seconds_accepts_no_name_argument():
    """The optional ``name`` argument stays optional for existing call sites."""
    assert constants.normalize_timeout_seconds(7, 5) == 7


# ---------------------------------------------------------------------------
# migrate_config — the one-time, deterministic ms -> s conversion
# ---------------------------------------------------------------------------

def test_migrate_config_converts_shipped_250_defaults():
    """The exact defect of issue #91: ``250`` must not survive as 250 seconds.

    ``250`` was the shipped millisecond value for both timeouts. It is sub-second
    once converted, so it migrates to the code defaults (5 s / 60 s) rather than to
    a 250-second freeze or a 1-second guaranteed timeout.
    """
    migrated, changes = config_migration.migrate_config({'worker_thread_timeout': 250, 'detect_timeout': 250})
    assert migrated['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT
    assert migrated['detect_timeout_seconds'] == constants.DETECT_TIMEOUT
    assert 'worker_thread_timeout' not in migrated
    assert 'detect_timeout' not in migrated
    assert len(changes) == 2


def test_migrate_config_converts_unambiguous_millisecond_values():
    """A legacy millisecond value above one second converts faithfully."""
    migrated, _ = config_migration.migrate_config({'detect_timeout': 2500})
    assert migrated['detect_timeout_seconds'] == 3  # 2.5 s rounds half-up to 3
    migrated, _ = config_migration.migrate_config({'detect_timeout': 1500})
    assert migrated['detect_timeout_seconds'] == 2  # 1.5 s rounds half-up to 2


@pytest.mark.parametrize("legacy_ms, expected", [(1499, 1), (1500, 2), (1999, 2), (2000, 2)])
def test_migrate_config_rounds_half_up(legacy_ms, expected):
    """Millisecond-to-second conversion rounds half-up, boundary pinned."""
    migrated, _ = config_migration.migrate_config({'detect_timeout': legacy_ms})
    assert migrated['detect_timeout_seconds'] == expected


def test_migrate_config_stamps_current_version():
    """A migrated config is stamped so the legacy branch never runs again."""
    migrated, _ = config_migration.migrate_config({'detect_timeout': 250})
    assert migrated[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION


def test_migrate_config_is_idempotent():
    """Re-running the migration on a migrated config changes nothing."""
    once, _ = config_migration.migrate_config({'worker_thread_timeout': 250, 'detect_timeout': 60000})
    twice, changes = config_migration.migrate_config(once)
    assert twice == once
    assert changes == []


def test_migrate_config_preserves_unrelated_keys():
    """Migration touches only the timeout keys; other user state survives."""
    migrated, _ = config_migration.migrate_config({
        'theme': 'dark', 'model': 'nudenet', 'last_source_folder': '/videos', 'detect_timeout': 250,
    })
    assert migrated['theme'] == 'dark'
    assert migrated['model'] == 'nudenet'
    assert migrated['last_source_folder'] == '/videos'


def test_migrate_config_handles_missing_keys():
    """A config omitting a legacy key leaves the constant default in force."""
    migrated, changes = config_migration.migrate_config({'theme': 'dark'})
    assert 'detect_timeout_seconds' not in migrated
    assert changes == []
    assert migrated[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION


@pytest.mark.parametrize("bad_value", ["abc", None, True, float("inf"), float("nan"), -5, 0])
def test_migrate_config_unusable_legacy_values_use_defaults(bad_value):
    """An unusable legacy value falls back to the key's constant default."""
    migrated, _ = config_migration.migrate_config({'worker_thread_timeout': bad_value})
    assert migrated['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT


def test_migrate_config_logs_the_rewrite(caplog):
    """Every migration is logged at WARNING, naming the key and both values."""
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        config_migration.migrate_config({'detect_timeout': 250})
    assert "detect_timeout" in caplog.text
    assert "250" in caplog.text
    assert str(constants.DETECT_TIMEOUT) in caplog.text


def test_needs_migration_detects_missing_version():
    """A config without ``config_version`` predates the seconds contract."""
    assert config_migration.needs_migration({}) is True
    assert config_migration.needs_migration({'detect_timeout': 250}) is True
    assert config_migration.needs_migration({constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION}) is False


def test_config_version_defaults_to_one_and_warns_on_garbage(caplog):
    """A missing or unparseable version is treated as legacy and warned about."""
    assert config_migration.config_version({}) == 1
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        assert config_migration.config_version({constants.CONFIG_VERSION_KEY: "x"}) == 1
    assert constants.CONFIG_VERSION_KEY in caplog.text


def test_migrate_config_file_rewrites_disk_and_is_one_time(tmp_path):
    """The file migration persists once; a second call is a no-op."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'worker_thread_timeout': 250, 'detect_timeout': 250}))

    changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert len(changes) == 2
    persisted = json.loads(config_path.read_text())
    assert persisted['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT
    assert persisted['detect_timeout_seconds'] == constants.DETECT_TIMEOUT
    assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION

    # Second run: the file is already stamped, so nothing is rewritten.
    before = config_path.read_text()
    assert config_migration.migrate_config_file(str(tmp_path), "app_config.json") == []
    assert config_path.read_text() == before


def test_migrate_config_file_tolerates_missing_and_invalid_files(tmp_path):
    """A missing or malformed config must not stop the app from starting."""
    assert config_migration.migrate_config_file(str(tmp_path), "absent.json") == []

    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert config_migration.migrate_config_file(str(tmp_path), "bad.json") == []

    not_object = tmp_path / "list.json"
    not_object.write_text("[1, 2, 3]")
    assert config_migration.migrate_config_file(str(tmp_path), "list.json") == []


def test_migrate_config_file_stamps_version_when_no_keys_to_convert(tmp_path):
    """A legacy config with no timeout keys is still stamped, so the legacy branch
    is never evaluated again for this file."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'theme': 'dark'}))

    assert config_migration.migrate_config_file(str(tmp_path), "app_config.json") == []
    persisted = json.loads(config_path.read_text())
    assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION
    assert persisted['theme'] == 'dark'


def test_migrate_config_file_survives_unwritable_file(tmp_path, caplog):
    """A config that cannot be rewritten must not prevent the app from starting.

    The in-memory defaults still apply, so a permissions problem degrades to a
    warning rather than an exception.
    """
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'detect_timeout': 250}))

    with patch("src.core.config_migration._write_config", side_effect=OSError("read-only")):
        with caplog.at_level("WARNING", logger="src.core.config_migration"):
            changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")

    assert len(changes) == 1  # the migration still ran in memory
    assert "Could not persist migrated config" in caplog.text


def test_migrate_config_file_survives_unstampable_file(tmp_path, caplog):
    """A key-less legacy config that cannot be stamped warns instead of raising."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'theme': 'dark'}))

    with patch("src.core.config_migration._write_config", side_effect=OSError("read-only")):
        with caplog.at_level("WARNING", logger="src.core.config_migration"):
            assert config_migration.migrate_config_file(str(tmp_path), "app_config.json") == []
    assert "Could not stamp config version" in caplog.text


# ---------------------------------------------------------------------------
# Golden fixture / constants consistency
# ---------------------------------------------------------------------------

# Every constant-backed key in the fixture. Parametrised so a key added to the
# fixture without a matching constant (or vice versa) fails loudly, and so a value
# that drifts from its constant fails instead of silently diverging.
FIXTURE_CONSTANT_KEYS = [
    ("theme", constants.THEME_DARK),
    ("threshold_percent", constants.DEFAULT_THRESHOLD_PERCENT),
    ("progress_update_interval", constants.SCAN_PROGRESS_UPDATE_INTERVAL),
    ("worker_thread_count", constants.WORKER_THREAD_COUNT),
    ("worker_thread_timeout_seconds", constants.WORKER_THREAD_TIMEOUT),
    ("detect_timeout_seconds", constants.DETECT_TIMEOUT),
    ("helloz_nsfw_host", constants.HELLOZ_NSFW_HOST),
    ("helloz_nsfw_port", constants.HELLOZ_NSFW_PORT),
    ("helloz_nsfw_api_endpoint", constants.HELLOZ_NSFW_API_ENDPOINT),
]

# Keys present in the fixture that are not backed by a constant.
FIXTURE_NON_CONSTANT_KEYS = {
    "config_version", "model", "last_source_folder",
    # Dead keys retained as reference only; removal tracked in issue #104.
    "video_frame_rate", "nudenet_worker_thread_count", "nudenet_worker_thread_timeout",
    "helloz_nsfw_worker_thread_count", "helloz_nsfw_worker_thread_timeout",
    "helloz_nsfw_request_timeout", "helloz_nsfw_health_check_timeout",
}


@pytest.mark.parametrize("key, expected", FIXTURE_CONSTANT_KEYS)
def test_fixture_matches_constant(key, expected):
    """Each constant-backed fixture key equals its constant default."""
    assert _load_default_config()[key] == expected, f"fixture key {key} drifted from constants.py"


def test_fixture_declares_current_config_version():
    """The documented default config is stamped with the current schema version."""
    assert _load_default_config()[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION


def test_fixture_migrates_cleanly():
    """The shipped defaults are already in the seconds contract — nothing to migrate.

    Guards against a future edit reintroducing millisecond key names or values.
    """
    cfg = _load_default_config()
    assert config_migration.needs_migration(cfg) is False
    migrated, changes = config_migration.migrate_config(cfg)
    assert changes == []
    assert migrated == cfg


def test_legacy_millisecond_key_names_are_absent_from_fixture():
    """The fixture must not ship the pre-migration key names."""
    cfg = _load_default_config()
    for legacy_key in constants.LEGACY_MILLISECOND_TIMEOUT_KEYS:
        assert legacy_key not in cfg


def test_fixture_only_contains_known_keys():
    """Every fixture key is either constant-backed, dead, or plain user state."""
    expected_keys = {key for key, _ in FIXTURE_CONSTANT_KEYS} | FIXTURE_NON_CONSTANT_KEYS
    assert set(_load_default_config()) == expected_keys


def test_constants_are_seconds_scale():
    """Guard against re-introduction of ms defaults."""
    assert constants.WORKER_THREAD_TIMEOUT == 5
    assert constants.DETECT_TIMEOUT == 60
    assert constants.HELLOZ_NSFW_REQUEST_TIMEOUT == 30
    assert constants.HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT == 5
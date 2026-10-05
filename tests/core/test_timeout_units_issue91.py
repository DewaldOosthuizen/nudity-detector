"""Tests for issue #91 — timeout units: normalization and one-time migration.

Two layers are covered:

* ``constants.normalize_positive_int`` / ``normalize_timeout_seconds`` — the read
  boundary. It assumes seconds; no unit is inferred from a value's magnitude.
* ``config_migration.migrate_config`` — the one-time, deterministic conversion of a
  pre-ADD-007 millisecond config, including the shipped ``250`` value.
"""
import json
import os
import re
import stat
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


def test_normalize_timeout_seconds_warns_when_no_bound_is_passed(caplog):
    """Omitting the supported bound is a defect and says so.

    The bound used to be inferred from ``name``. A widget accessor passes a display
    name (``detect_timeout_spin``), never a config key, so the lookup silently
    failed and the clamp was inert on the save path. Inference is gone; this
    warning makes a missing bound loud instead of invisible.
    """
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_timeout_seconds(999999, 60, name="detect_timeout_spin") == 999999
    assert "detect_timeout_spin" in caplog.text
    assert "maximum" in caplog.text


def test_normalize_timeout_seconds_bound_is_not_inferred_from_the_name():
    """A config-key name alone no longer supplies the documented maximum.

    Regression guard for the stringly-typed coupling: with the inference in place a
    renamed widget or a typo in a log label silently removed the clamp.
    """
    assert constants.normalize_timeout_seconds(
        999999, 60, name="detect_timeout_seconds",
        max_seconds=constants.DETECT_TIMEOUT_MAX_SECONDS,
    ) == constants.DETECT_TIMEOUT_MAX_SECONDS


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


@pytest.mark.parametrize("legacy_ms", [1, 250, 499, 500, 700, 999, 0, -5])
def test_migrate_config_sub_second_band_uses_constant_default(legacy_ms):
    """The whole 0-999 ms band falls back to the constant default.

    Regression guard for the documented rule ("a legacy value below one second
    becomes the code default"). The first implementation branched only on whether
    the *rounded* result was 0, so ``700``/``999`` became a 1-second timeout —
    which times out on essentially every file, the exact failure the fallback
    exists to prevent — while every document said otherwise.
    """
    migrated, changes = config_migration.migrate_config({'detect_timeout': legacy_ms})
    assert migrated['detect_timeout_seconds'] == constants.DETECT_TIMEOUT
    assert str(constants.DETECT_TIMEOUT) in changes[0]

    migrated, _ = config_migration.migrate_config({'worker_thread_timeout': legacy_ms})
    assert migrated['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT


def test_migrate_config_one_second_legacy_value_converts():
    """Exactly 1000 ms is one second and converts, not falls back."""
    migrated, _ = config_migration.migrate_config({'detect_timeout': 1000})
    assert migrated['detect_timeout_seconds'] == 1


def test_conversion_never_emits_below_the_migratable_floor():
    """Every converted value honours ``MIN_MIGRATABLE_SECONDS``.

    The sub-second branch handles everything below one second, so the rounding
    branch cannot yield 0. This test pins that invariant rather than leaving a
    defensive branch no test could reach.
    """
    for legacy_ms in range(1000, 1000 + 5000):
        seconds, _ = config_migration._convert_milliseconds_to_seconds(
            legacy_ms, constants.DETECT_TIMEOUT, "detect_timeout",
        )
        assert seconds >= constants.MIN_MIGRATABLE_SECONDS


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

    _, changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert len(changes) == 2
    persisted = json.loads(config_path.read_text())
    assert persisted['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT
    assert persisted['detect_timeout_seconds'] == constants.DETECT_TIMEOUT
    assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION

    # Second run: the file is already stamped, so nothing is rewritten.
    before = config_path.read_text()
    migrated, changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert changes == []
    assert migrated == persisted
    assert config_path.read_text() == before


def test_migrate_config_file_tolerates_missing_file(tmp_path):
    """A missing config must not stop the app from starting (normal first run)."""
    migrated, notes = config_migration.migrate_config_file(str(tmp_path), "absent.json")
    assert migrated == {}
    assert notes == []


def test_migrate_config_file_tolerates_invalid_files(tmp_path, caplog):
    """A malformed config degrades to a note, never an exception.

    The app falls back to built-in defaults; the note tells the user why.
    """
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        migrated, notes = config_migration.migrate_config_file(str(tmp_path), "bad.json")
    assert migrated == {}
    assert notes and "could not be read" in notes[0]
    assert "Could not read" in caplog.text

    not_object = tmp_path / "list.json"
    not_object.write_text("[1, 2, 3]")
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        migrated, notes = config_migration.migrate_config_file(str(tmp_path), "list.json")
    assert migrated == {}
    assert notes and "not a JSON object" in notes[0]


def test_migrate_config_file_stamps_version_when_no_keys_to_convert(tmp_path):
    """A legacy config with no timeout keys is still stamped, so the legacy branch
    is never evaluated again for this file."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'theme': 'dark'}))

    migrated, changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert changes == []
    persisted = json.loads(config_path.read_text())
    assert migrated == persisted
    assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION
    assert persisted['theme'] == 'dark'


def test_migrate_config_file_survives_unwritable_file(tmp_path, caplog):
    """A config that cannot be rewritten must not prevent the app from starting.

    The in-memory defaults still apply, so a permissions problem degrades to a
    warning rather than an exception. The failure is also *returned* as a note so
    the GUI can announce that the on-disk file is stale.
    """
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'detect_timeout': 250}))

    with patch("src.core.config_migration.write_config", side_effect=OSError("read-only")):
        with caplog.at_level("WARNING", logger="src.core.config_migration"):
            _, changes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")

    assert len(changes) == 2  # the rewrite itself, plus the persistence-failure note
    assert "could not be rewritten" in changes[-1]
    assert "Could not persist migrated config" in caplog.text


def test_migrate_config_file_reports_unreadable_file(tmp_path):
    """An unreadable config returns a note, so the user learns the file is stale."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")

    _, notes = config_migration.migrate_config_file(str(tmp_path), "bad.json")
    assert notes, "an unreadable config must produce a user-visible note"
    assert "could not be read" in notes[0]


def test_migrate_config_file_reports_non_object_config(tmp_path):
    """A non-object JSON config is reported rather than silently ignored."""
    not_object = tmp_path / "list.json"
    not_object.write_text("[1, 2, 3]")

    _, notes = config_migration.migrate_config_file(str(tmp_path), "list.json")
    assert notes and "not a JSON object" in notes[0]


# ---------------------------------------------------------------------------
# Migration must never silently discard an explicit *_seconds value
# ---------------------------------------------------------------------------

def test_migrate_config_keeps_existing_seconds_value_when_both_keys_present():
    """A hand-added ``*_seconds`` value wins over the legacy millisecond key.

    A partially applied upgrade or a restored backup can hold both spellings. The
    ``*_seconds`` key is the one that states its unit, so overwriting it with a
    converted legacy value would be an unrecoverable loss.
    """
    migrated, changes = config_migration.migrate_config({
        'detect_timeout': 250, 'detect_timeout_seconds': 120,
    })
    assert migrated['detect_timeout_seconds'] == 120
    assert 'detect_timeout' not in migrated
    assert len(changes) == 1
    assert "kept the existing detect_timeout_seconds=120" in changes[0]


def test_migrate_config_keeps_existing_seconds_value_on_disk(tmp_path):
    """The on-disk path keeps the explicit seconds value too, and stays stamped."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'detect_timeout': 250, 'detect_timeout_seconds': 120}))

    _, _ = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    persisted = json.loads(config_path.read_text())
    assert persisted['detect_timeout_seconds'] == 120
    assert 'detect_timeout' not in persisted
    assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION


# ---------------------------------------------------------------------------
# Rename-only keys: the unit was already seconds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("legacy_key", sorted(constants.RENAMED_TIMEOUT_KEYS))
def test_migrate_config_renames_timeout_keys_without_converting(legacy_key):
    """A key that already held seconds is renamed, never converted.

    Converting these would silently turn a 300 s request timeout into 0.3 s.
    """
    seconds_key = constants.RENAMED_TIMEOUT_KEYS[legacy_key]
    migrated, changes = config_migration.migrate_config({legacy_key: 300})
    assert migrated[seconds_key] == 300
    assert legacy_key not in migrated
    assert len(changes) == 1
    assert "renamed to" in changes[0]


def test_migrate_config_keeps_existing_seconds_value_on_rename():
    """When both spellings of a renamed key exist, the suffixed one is kept."""
    migrated, changes = config_migration.migrate_config({
        'helloz_nsfw_request_timeout': 300,
        'helloz_nsfw_request_timeout_seconds': 45,
    })
    assert migrated['helloz_nsfw_request_timeout_seconds'] == 45
    assert 'helloz_nsfw_request_timeout' not in migrated
    assert "kept the existing" in changes[0]


def test_migrate_config_file_renames_on_disk(tmp_path):
    """The on-disk rewrite performs the rename too."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({'helloz_nsfw_request_timeout': 300}))

    _, _ = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    persisted = json.loads(config_path.read_text())
    assert persisted['helloz_nsfw_request_timeout_seconds'] == 300
    assert 'helloz_nsfw_request_timeout' not in persisted


# ---------------------------------------------------------------------------
# Logging policy and atomic persistence
# ---------------------------------------------------------------------------

def test_migrate_config_does_not_warn_when_nothing_to_migrate(caplog):
    """A config with no legacy keys must not emit a misleading migration WARNING.

    Regression guard: the summary warning fired unconditionally, so every first
    run of a clean install told the user to review keys that were never present.
    """
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        config_migration.migrate_config({'theme': 'dark'})
    assert caplog.text == ""


def test_migrate_config_warns_summary_only_on_real_change(caplog):
    """The summary warning still fires when something was actually rewritten."""
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        config_migration.migrate_config({'detect_timeout': 250})
    assert "Config migrated to version" in caplog.text


def test_write_config_is_atomic_and_ends_with_newline(tmp_path):
    """The rewrite must not truncate the user's only config file, and must end
    with a newline for POSIX tooling."""
    target = tmp_path / "app_config.json"
    target.write_text('{"theme": "dark"}')

    config_migration.write_config(str(target), {'theme': 'light'})

    assert target.read_text().endswith('\n')
    assert json.loads(target.read_text()) == {'theme': 'light'}
    # No temp files left behind.
    assert [p.name for p in tmp_path.iterdir()] == ['app_config.json']


def test_write_config_leaves_no_temp_file_on_failure(tmp_path):
    """A failed write leaves the original file intact and no debris behind."""
    target = tmp_path / "app_config.json"
    target.write_text('{"theme": "dark"}')

    with patch("src.core.config_migration.json.dump", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            config_migration.write_config(str(target), {'theme': 'light'})

    assert target.read_text() == '{"theme": "dark"}'
    assert [p.name for p in tmp_path.iterdir()] == ['app_config.json']


def test_write_config_raises_when_the_temp_file_cannot_be_removed(tmp_path):
    """An unremovable temp file does not mask the original write failure.

    The unlink in the cleanup path is best-effort: a failure there must not
    replace the OSError the caller needs to see.
    """
    target = tmp_path / "app_config.json"
    target.write_text('{"theme": "dark"}')

    with patch("src.core.config_migration.json.dump", side_effect=OSError("disk full")), \
         patch("src.core.config_migration.os.unlink", side_effect=OSError("permission")):
        with pytest.raises(OSError, match="disk full"):
            config_migration.write_config(str(target), {'theme': 'light'})

    assert target.read_text() == '{"theme": "dark"}'


def test_migrate_config_file_defaults_to_constants_paths():
    """The default arguments come from constants.py, not a duplicated literal."""
    assert config_migration.CONFIG_DIR == constants.CONFIG_DIR
    assert config_migration.CONFIG_FILE_NAME == constants.CONFIG_FILE_NAME


def test_legacy_key_rename_and_default_are_one_mapping():
    """The rename and its fallback default cannot drift apart.

    AGENTS.md §C: the mapping and its defaults live together in constants.py, so a
    new legacy key cannot be added with a rename but no fallback (or vice versa).
    """
    for legacy_key, entry in constants.LEGACY_MILLISECOND_TIMEOUT_KEYS.items():
        seconds_key, fallback = entry
        assert seconds_key.endswith('_seconds')
        assert fallback >= constants.MIN_MIGRATABLE_SECONDS


def test_migration_floors_a_mapping_fallback_below_the_minimum(caplog):
    """``MIN_MIGRATABLE_SECONDS`` is enforced, not merely documented.

    The constant claimed a mapping entry could not declare a fallback below the
    floor, but nothing checked: ``_convert_milliseconds_to_seconds`` returned
    ``default_seconds`` verbatim, so a new entry such as
    ``('some_timeout', ('some_timeout_seconds', 0))`` would emit a 0-second timeout,
    contradicting the constant's own docstring and the ``>= 1`` contract of
    ``normalize_timeout_seconds``.
    """
    bad_mapping = {'detect_timeout': ('detect_timeout_seconds', 0)}
    with patch.dict(config_migration.LEGACY_MILLISECOND_TIMEOUT_KEYS, bad_mapping, clear=True), \
         caplog.at_level("WARNING", logger="src.core.config_migration"):
        migrated, changes = config_migration.migrate_config({'detect_timeout': 250})
    assert migrated["detect_timeout_seconds"] == constants.MIN_MIGRATABLE_SECONDS
    assert migrated["detect_timeout_seconds"] >= constants.MIN_MIGRATABLE_SECONDS
    assert any(f"replaced with {constants.MIN_MIGRATABLE_SECONDS} s" in change for change in changes)
    assert "below the" in caplog.text


def test_migration_never_emits_a_zero_second_timeout_for_any_fallback():
    """Whatever fallback a mapping declares, the emitted value honours the floor."""
    for fallback in (0, -5, -1):
        bad_mapping = {'detect_timeout': ('detect_timeout_seconds', fallback)}
        with patch.dict(config_migration.LEGACY_MILLISECOND_TIMEOUT_KEYS, bad_mapping, clear=True):
            migrated, _ = config_migration.migrate_config({'detect_timeout': 250})
            assert migrated["detect_timeout_seconds"] >= constants.MIN_MIGRATABLE_SECONDS


# ---------------------------------------------------------------------------
# Config/constant default divergence
# ---------------------------------------------------------------------------

def test_shipped_defaults_equal_constants():
    """Every constant-backed shipped default equals its constant.

    Guards the ``helloz_nsfw_request_timeout: 300`` / ``video_frame_rate: 10``
    mismatches against 30 s and 5: config and code must agree on day one.
    """
    cfg = _load_default_config()
    for key, default in constants.CONFIG_DEFAULT_ALIGNMENT.items():
        assert cfg[key] == default, f"shipped default for {key} diverges from constants.py"


def test_log_config_default_divergences_reports_mismatch(caplog):
    """A right-unit / wrong-magnitude value is reported, never rewritten."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        divergences = constants.log_config_default_divergences({
            'helloz_nsfw_request_timeout_seconds': 300,
        })
    assert len(divergences) == 1
    assert "helloz_nsfw_request_timeout_seconds" in divergences[0]
    assert "300" in divergences[0]
    assert "Config value divergence" in caplog.text


def test_log_config_default_divergences_is_quiet_when_aligned(caplog):
    """An aligned config produces no divergence note."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        divergences = constants.log_config_default_divergences({
            'helloz_nsfw_request_timeout_seconds': constants.HELLOZ_NSFW_REQUEST_TIMEOUT,
        })
    assert divergences == []
    assert caplog.text == ""


def test_log_config_default_divergences_ignores_absent_keys():
    """A key the config does not set is not a divergence."""
    assert constants.log_config_default_divergences({}) == []


def test_log_config_default_divergences_does_not_double_log(caplog):
    """An unparseable value yields one coercion WARNING, not two.

    The divergence pass runs before the real read, so a coercing call inside it
    produced a second WARNING for the same key and made one bad value look like
    two separate problems.
    """
    with caplog.at_level("WARNING", logger="src.core.constants"):
        constants.log_config_default_divergences({'video_frame_rate': "abc"})
    assert caplog.text == ""


def test_normalize_positive_int_quiet_suppresses_logging(caplog):
    """``quiet=True`` coerces without reporting, for callers that only want a value."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_positive_int("abc", 5, name="some_key", quiet=True) == 5
        assert constants.normalize_positive_int(-1, 5, name="some_key", quiet=True) == 1
    assert caplog.text == ""


# ---------------------------------------------------------------------------
# Bounded ranges — the GUI must not silently truncate a legal value
# ---------------------------------------------------------------------------

def test_normalize_timeout_seconds_clamps_above_the_supported_maximum(caplog):
    """A value beyond the documented maximum is clamped and the clamp is logged."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_positive_int(
            999999, 60, name="detect_timeout_seconds",
            max_value=constants.DETECT_TIMEOUT_MAX_SECONDS,
        )
    assert result == constants.DETECT_TIMEOUT_MAX_SECONDS
    assert "detect_timeout_seconds" in caplog.text
    assert "999999" in caplog.text
    assert str(constants.DETECT_TIMEOUT_MAX_SECONDS) in caplog.text


def test_normalize_timeout_seconds_honours_3600_within_the_bound():
    """The README's headline example survives: 3600 s is inside the bound."""
    assert constants.normalize_timeout_seconds(3600, 60, name="detect_timeout_seconds") == 3600
    assert constants.normalize_timeout_seconds(3600, 60, name="worker_thread_timeout_seconds") == 3600


def test_timeout_maxima_cover_every_suffixed_timeout_key():
    """Every ``*_seconds`` key the GUI reads has a declared maximum."""
    for key in ("worker_thread_timeout_seconds", "detect_timeout_seconds",
                "helloz_nsfw_request_timeout_seconds", "helloz_nsfw_health_check_timeout_seconds"):
        assert key in constants.TIMEOUT_MAX_SECONDS
        assert constants.TIMEOUT_MAX_SECONDS[key] >= constants.MIN_MIGRATABLE_SECONDS


def test_log_timeout_truncations_reports_an_out_of_range_value(caplog):
    """A value past the bound is reported with the key and both values."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        notes = constants.log_timeout_truncations({
            'detect_timeout_seconds': constants.DETECT_TIMEOUT_MAX_SECONDS + 1,
        })
    assert len(notes) == 1
    assert "detect_timeout_seconds" in notes[0]
    assert str(constants.DETECT_TIMEOUT_MAX_SECONDS + 1) in notes[0]
    assert "Config timeout truncation" in caplog.text


def test_log_timeout_truncations_is_quiet_for_supported_values(caplog):
    """A value inside the supported range is not reported as truncated."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        notes = constants.log_timeout_truncations({
            'detect_timeout_seconds': 3600,
            'worker_thread_timeout_seconds': constants.WORKER_THREAD_TIMEOUT_MAX_SECONDS,
        })
    assert notes == []
    assert caplog.text == ""


def test_log_timeout_truncations_ignores_absent_and_unparseable_keys(caplog):
    """Absent keys, booleans and garbage are the read path's business, not this pass."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.log_timeout_truncations({}) == []
        assert constants.log_timeout_truncations({'detect_timeout_seconds': True}) == []
        assert constants.log_timeout_truncations({'detect_timeout_seconds': "abc"}) == []
        assert constants.log_timeout_truncations({'detect_timeout_seconds': float("inf")}) == []
    assert caplog.text == ""


def test_normalize_positive_int_clamps_to_the_port_bound(caplog):
    """The port accessor bound is enforced and logged, not silently substituted."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_positive_int(
            70000, 6086, name="helloz_nsfw_port", min_value=1, max_value=constants.MAX_PORT,
        ) == constants.MAX_PORT
        assert constants.normalize_positive_int(
            0, 6086, name="helloz_nsfw_port", min_value=1, max_value=constants.MAX_PORT,
        ) == 1
    assert "helloz_nsfw_port" in caplog.text


def test_max_port_is_the_highest_legal_tcp_port():
    """The bound constant is the real TCP limit, not a duplicated literal."""
    assert constants.MAX_PORT == 65535


# ---------------------------------------------------------------------------
# Live vs dead key classification must match what src/ actually reads
# ---------------------------------------------------------------------------

def _src_sources(subdir="src"):
    """Return the concatenated text of every Python module under a source directory.

    Args:
        subdir: Directory to walk, relative to the repository root.

    Returns:
        A single string containing the contents of every ``*.py`` file found.
    """
    root_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), subdir,
    )
    chunks = []
    for root, _dirs, files in os.walk(root_dir):
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    chunks.append(handle.read())
    return "\n".join(chunks)


def _has_config_read_access(sources, key):
    """Return whether ``sources`` reads ``key`` out of a config mapping.

    A reader looks like ``cfg.get('key')`` or ``cfg['key']`` — an actual access.
    Merely naming the key (as ``constants.DEAD_CONFIG_KEYS`` or the migration
    rename tables do) is not a reader.

    A key referenced through a constant (``CONFIG_VERSION_KEY`` for
    ``config_version``) is also a reader: the alias map supplies the constant name
    as a second accepted spelling — quoted (it indexes a table of key names) or
    bare (``cfg.get(CONFIG_VERSION_KEY, 1)``) — so indirection through
    ``constants.py`` does not read as "no reader".

    Args:
        sources: Concatenated source text.
        key: Config key name.

    Returns:
        True if the key is read from a mapping somewhere in the text.
    """
    spellings = [key] + list(_READER_ALIASES.get(key, ()))
    patterns = [
        rf"\.get\(\s*['\"]{re.escape(spelling)}['\"]" for spelling in spellings
    ] + [
        rf"\[\s*['\"]{re.escape(spelling)}['\"]\s*\]" for spelling in spellings
    ] + [
        rf"\.get\(\s*{re.escape(alias)}\b" for alias in _READER_ALIASES.get(key, ())
    ]
    return any(re.search(pattern, sources) for pattern in patterns)


# Config keys whose reader goes through a named constant rather than a literal.
# The value is the *name* of that constant, since the read is ``.get(NAME)``.
_READER_ALIASES = {
    'config_version': ('CONFIG_VERSION_KEY',),
}


@pytest.mark.parametrize("key", sorted(_load_default_config()))
def test_shipped_live_config_keys_have_a_reader(key):
    """Every non-dead shipped key is actually read somewhere under ``src/``.

    Guards the documentation: a key described as "read directly from config at
    runtime" with no reader is a defect (issue #104's scope is derived from that
    classification), and this is what proves it either way.
    """
    if key in constants.DEAD_CONFIG_KEYS:
        pytest.skip(f"{key} is documented as dead (issue #104)")
    assert _has_config_read_access(_src_sources(), key), (
        f"shipped config key {key} is documented as read at runtime but has no src/ reader"
    )


@pytest.mark.parametrize("key", sorted(constants.DEAD_CONFIG_KEYS))
def test_dead_config_keys_are_documented_as_dead(key):
    """A key in ``DEAD_CONFIG_KEYS`` must ship in the fixture and be documented."""
    assert key in _load_default_config()
    assert key in constants.DEAD_CONFIG_KEYS


def test_dead_config_keys_are_not_read_by_src():
    """A key classified as dead is never read from a config mapping under ``src/``."""
    sources = _src_sources()
    for key in constants.DEAD_CONFIG_KEYS:
        assert not _has_config_read_access(sources, key), (
            f"{key} is classified as dead but src/ reads it"
        )


def test_dead_classification_is_not_vacuous_for_its_own_declaration():
    """The dead-key declaration in ``src/`` does not make the check self-fulfilling.

    ``DEAD_CONFIG_KEYS`` lives in ``src/core/constants.py`` and necessarily *names*
    each of its own keys, so a naive "does the string appear under src/" search
    would find all four and classify them as live. The classification test looks
    for a mapping read instead, which a declaration is not — this test pins that
    distinction, so replacing the read-based matcher with a substring search fails
    here rather than quietly inverting the whole dead/live split.
    """
    sources = _src_sources()
    for key in constants.DEAD_CONFIG_KEYS:
        assert key in sources, (
            f"{key} is declared in DEAD_CONFIG_KEYS, so it must appear in src/; if this "
            "fails the declaration and the classification test have diverged"
        )
        assert not _has_config_read_access(sources, key), (
            f"{key} appears in src/ but only as a declaration, which is not a reader"
        )
    # The live direction of the same matcher must still be capable of finding a
    # reader, otherwise "no reader" would be trivially true for every key.
    assert _has_config_read_access(sources, "helloz_nsfw_port") is True
    assert _has_config_read_access(sources, "config_version") is True


def test_no_shipped_key_is_silently_unclassified():
    """Every shipped fixture key is either explicitly dead or proven to have a reader.

    The complementary direction the documentation leans on: a key cannot be promoted
    to "live" (i.e. left out of ``DEAD_CONFIG_KEYS``) without a reader existing under
    ``src/``.
    """
    sources = _src_sources()
    for key in _load_default_config():
        if key in constants.DEAD_CONFIG_KEYS:
            continue
        assert _has_config_read_access(sources, key), (
            f"{key} ships in the default config, is not classified dead, and has no "
            "src/ reader — either it is dead or it is missing a reader"
        )


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
    ("video_frame_rate", constants.VIDEO_FRAME_RATE),
    ("worker_thread_count", constants.WORKER_THREAD_COUNT),
    ("worker_thread_timeout_seconds", constants.WORKER_THREAD_TIMEOUT),
    ("detect_timeout_seconds", constants.DETECT_TIMEOUT),
    ("helloz_nsfw_host", constants.HELLOZ_NSFW_HOST),
    ("helloz_nsfw_port", constants.HELLOZ_NSFW_PORT),
    ("helloz_nsfw_api_endpoint", constants.HELLOZ_NSFW_API_ENDPOINT),
    ("helloz_nsfw_request_timeout_seconds", constants.HELLOZ_NSFW_REQUEST_TIMEOUT),
    ("helloz_nsfw_health_check_timeout_seconds", constants.HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT),
]

# Keys present in the fixture that are not backed by a constant.
FIXTURE_NON_CONSTANT_KEYS = {
    "config_version", "model", "last_source_folder",
    # Dead keys retained as reference only; removal tracked in issue #104.
    "nudenet_worker_thread_count",
    "helloz_nsfw_worker_thread_count",
    "nudenet_worker_thread_timeout_seconds",
    "helloz_nsfw_worker_thread_timeout_seconds",
}


FIXTURE_CONSTANT_KEYS_DICT = dict(FIXTURE_CONSTANT_KEYS)


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
    """The fixture must not ship any pre-migration key name."""
    cfg = _load_default_config()
    for legacy_key in constants.LEGACY_MILLISECOND_TIMEOUT_KEYS:
        assert legacy_key not in cfg
    for legacy_key in constants.RENAMED_TIMEOUT_KEYS:
        assert legacy_key not in cfg


def test_fixture_timeout_keys_all_declare_their_unit():
    """Every fixture key whose name ends in ``_timeout`` must state its unit.

    The whole premise of ADD-007 is that the suffix is the unit declaration; a
    bare ``*_timeout`` key would make the suffix an unreliable marker again.
    """
    for key in _load_default_config():
        if key.endswith('_timeout'):
            pytest.fail(f"fixture key {key} does not state its unit; expected a *_timeout_seconds name")


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


# ---------------------------------------------------------------------------
# threshold_percent — the float config key must not be able to abort startup
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_value", ["abc", True, {}, [], float("nan"), float("inf"), float("-inf")])
def test_normalize_threshold_percent_falls_back_for_unusable_values(bad_value, caplog):
    """An unusable threshold never raises; it falls back and is named in the log.

    Regression guard: ``float(cfg.get('threshold_percent', ...))`` in the window
    constructor raised for every one of these, so the app never started.
    """
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_threshold_percent(bad_value)
    assert result == constants.DEFAULT_THRESHOLD_PERCENT
    assert "threshold_percent" in caplog.text


def test_normalize_threshold_percent_uses_default_when_absent(caplog):
    """A missing key is normal, not a defect: DEBUG at most, never WARNING."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_threshold_percent(None) == constants.DEFAULT_THRESHOLD_PERCENT
    assert caplog.text == ""


@pytest.mark.parametrize(
    "raw, expected",
    [(150.0, constants.MAX_THRESHOLD_PERCENT), (-5.0, constants.MIN_THRESHOLD_PERCENT)],
)
def test_normalize_threshold_percent_clamps_out_of_range(raw, expected, caplog):
    """An out-of-range percentage is clamped into the supported band and logged."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants.normalize_threshold_percent(raw) == expected
    assert "threshold_percent" in caplog.text
    assert str(raw) in caplog.text


def test_normalize_threshold_percent_passes_valid_values_through():
    """A valid value, including a numeric string, is honoured as written."""
    assert constants.normalize_threshold_percent(42.5) == 42.5
    assert constants.normalize_threshold_percent("42.5") == 42.5
    assert constants.normalize_threshold_percent(0) == 0.0
    assert constants.normalize_threshold_percent(100) == 100.0


def test_normalize_threshold_percent_clamps_an_out_of_range_default(caplog):
    """Even the fallback is clamped, so the bound holds by code, not by convention."""
    with caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants.normalize_threshold_percent("abc", 500.0)
    assert result == constants.MAX_THRESHOLD_PERCENT
    assert "threshold_percent" in caplog.text


# ---------------------------------------------------------------------------
# write_config — an atomic write must change contents, never the file's mode
# ---------------------------------------------------------------------------

def test_write_config_preserves_existing_file_permissions(tmp_path):
    """Replacing an existing config must not narrow it to the mkstemp 0600.

    Regression guard: ``tempfile.mkstemp`` always creates 0600, so ``os.replace``
    silently downgraded a group- or world-readable config to owner-only.
    """
    config_path = tmp_path / "app_config.json"
    config_path.write_text('{"theme": "dark"}\n', encoding="utf-8")
    os.chmod(config_path, 0o644)

    config_migration.write_config(str(config_path), {"theme": "light"})

    assert stat.S_IMODE(os.stat(config_path).st_mode) == 0o644
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"theme": "light"}


def test_write_config_new_file_respects_the_process_umask(tmp_path):
    """A brand-new config gets the umask-derived mode, not a hardcoded 0600."""
    previous = os.umask(0o022)
    try:
        config_migration.write_config(str(tmp_path / "new.json"), {"theme": "dark"})
    finally:
        os.umask(previous)
    assert stat.S_IMODE(os.stat(tmp_path / "new.json").st_mode) == 0o644


def test_migration_on_disk_preserves_file_permissions(tmp_path):
    """The startup rewrite keeps the user's file mode end to end."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps({"worker_thread_timeout": 250}), encoding="utf-8")
    os.chmod(config_path, 0o640)

    config_migration.migrate_config_file(str(tmp_path), "app_config.json")

    assert stat.S_IMODE(os.stat(config_path).st_mode) == 0o640
    assert json.loads(config_path.read_text(encoding="utf-8"))["worker_thread_timeout_seconds"] == 5


# ---------------------------------------------------------------------------
# The dead per-detector timeout keys are not renamed by the migration
# ---------------------------------------------------------------------------

def _read_src_file(relative_path):
    """Return the text of a file under ``src/``.

    Args:
        relative_path: Path relative to the ``src/`` root, e.g. ``gui/app.py``.

    Returns:
        The file's contents as a single string.
    """
    src_root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src",
    )
    with open(os.path.join(src_root, relative_path), encoding="utf-8") as handle:
        return handle.read()


@pytest.mark.parametrize(
    "legacy_key",
    ["nudenet_worker_thread_timeout", "helloz_nsfw_worker_thread_timeout"],
)
def test_migration_leaves_dead_timeout_keys_untouched(legacy_key):
    """Renaming a key nothing reads has no reader to benefit and no unit to preserve.

    These two keys are classified dead by ``DEAD_CONFIG_KEYS``; issue #104 deletes
    them. The migration must not spend a schema-version bump and a user-facing
    change note rewriting them.
    """
    assert legacy_key not in constants.RENAMED_TIMEOUT_KEYS
    assert legacy_key not in constants.DEAD_CONFIG_KEYS  # dead under the *new* name
    cfg = {legacy_key: 10, "worker_thread_timeout": 2500}
    migrated, changes = config_migration.migrate_config(cfg)
    assert legacy_key in migrated, "a dead key must survive untouched, not be renamed"
    assert migrated["worker_thread_timeout_seconds"] == 3
    assert not any(legacy_key in change for change in changes)


# ---------------------------------------------------------------------------
# Wiring guards — the normalizers must actually be the read path
# ---------------------------------------------------------------------------

def test_window_constructor_cannot_raise_on_a_threshold_value():
    """``NudityDetectorWindow.__init__`` must not call ``float()`` on the threshold.

    The regression this guards: ``float(cfg.get('threshold_percent', ...))`` raised
    out of the constructor for ``"abc"``, ``true`` or ``{}``, so the app never
    started. Asserted on the source because constructing the real GTK window is not
    possible in a headless test run.
    """
    app_source = _read_src_file(os.path.join("gui", "app.py"))
    raw_reads = re.findall(r"float\(\s*cfg\.get\(\s*['\"]threshold_percent['\"]", app_source)
    assert raw_reads == [], (
        "threshold_percent must be read via constants.normalize_threshold_percent, "
        "not a bare float(): an unparseable value would abort window construction"
    )
    assert "normalize_threshold_percent" in app_source

# ---------------------------------------------------------------------------
# _load_helloz_config — the detection read path must use the same coercion
# ---------------------------------------------------------------------------

def _write_config(tmp_path, cfg):
    """Write ``cfg`` to a temp app_config.json and point constants at it."""
    config_path = tmp_path / "app_config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    return patch("src.core.constants._config_path", return_value=str(config_path))


@pytest.mark.parametrize("bad_port", ["abc", True, None, 0, -1, 70000, float("inf")])
def test_load_helloz_config_never_interpolates_an_unusable_port(tmp_path, caplog, bad_port):
    """The port is coerced, not interpolated raw into the request URL.

    Regression guard: ``cfg.get('helloz_nsfw_port', ...)`` put the configured value
    straight into the URL, so a boolean or non-numeric port yielded
    ``http://localhost:True:6086/...`` with no warning anywhere. One read policy:
    the detection path coerces exactly as the GUI path does.
    """
    with _write_config(tmp_path, {"helloz_nsfw_port": bad_port}), \
         caplog.at_level("WARNING", logger="src.core.constants"):
        host, port, _endpoint, scheme = constants._load_helloz_config()
    if bad_port is None:
        assert port == constants.HELLOZ_NSFW_PORT
        assert caplog.text == ""
        return
    assert 1 <= port <= constants.MAX_PORT
    assert isinstance(port, int)
    assert "helloz_nsfw_port" in caplog.text
    assert f"{scheme}://{host}:{port}" != "http://localhost:True:6086"


@pytest.mark.parametrize(
    "bad_value, expected",
    [(42, constants.HELLOZ_NSFW_HOST), ("", constants.HELLOZ_NSFW_HOST), ({}, constants.HELLOZ_NSFW_HOST)],
)
def test_load_helloz_config_coerces_string_keys(tmp_path, caplog, bad_value, expected):
    """A non-string or blank host falls back to the constant default, loudly."""
    with _write_config(tmp_path, {"helloz_nsfw_host": bad_value}), \
         caplog.at_level("WARNING", logger="src.core.constants"):
        host, _port, _endpoint, _scheme = constants._load_helloz_config()
    assert host == expected
    assert "helloz_nsfw_host" in caplog.text


def test_load_helloz_config_coerces_the_api_endpoint(tmp_path, caplog):
    """A blank endpoint falls back to the documented default, loudly."""
    with _write_config(tmp_path, {"helloz_nsfw_api_endpoint": "   "}), \
         caplog.at_level("WARNING", logger="src.core.constants"):
        _host, _port, endpoint, _scheme = constants._load_helloz_config()
    assert endpoint == constants.HELLOZ_NSFW_API_ENDPOINT
    assert "helloz_nsfw_api_endpoint" in caplog.text


def test_load_helloz_config_absent_keys_are_not_warned(tmp_path, caplog):
    """An absent key is normal on a fresh install, not a defect.

    Written against a present-but-empty config file so the only possible warning is
    the "not found or invalid file" one, which is not what is under test here.
    """
    with _write_config(tmp_path, {}), caplog.at_level("WARNING", logger="src.core.constants"):
        assert constants._load_helloz_config() == (
            constants.HELLOZ_NSFW_HOST, constants.HELLOZ_NSFW_PORT,
            constants.HELLOZ_NSFW_API_ENDPOINT, 'http',
        )
    assert caplog.text == ""


def test_load_helloz_config_scheme_still_guards_remote_hosts(tmp_path):
    """The explicit-``http``-for-a-remote-host rejection is unchanged."""
    with _write_config(tmp_path, {"helloz_nsfw_scheme": "http", "helloz_nsfw_host": "myserver"}):
        with pytest.raises(ValueError, match="'http' is not allowed for non-loopback host"):
            constants.get_helloz_nsfw_url()


def test_resolve_scheme_is_the_single_scheme_rule():
    """``resolve_scheme`` is shared by the GUI and the detection read path."""
    assert constants.resolve_scheme("localhost") == "http"
    assert constants.resolve_scheme("127.0.0.1") == "http"
    assert constants.resolve_scheme("myserver") == "https"
    assert constants.resolve_scheme("myserver", "https") == "https"
    with pytest.raises(ValueError, match="'http' is not allowed for non-loopback host"):
        constants.resolve_scheme("myserver", "http")
    # An unusable configured scheme falls back to the default rule, never to http.
    assert constants.resolve_scheme("myserver", 42) == "https"


# ---------------------------------------------------------------------------
# PR #102 review — hardening of the shared read path
# ---------------------------------------------------------------------------

def test_load_helloz_config_uses_the_single_scheme_rule(tmp_path, monkeypatch):
    """``_load_helloz_config`` routes through ``resolve_scheme``, not its own copy.

    Regression guard: the PR added ``resolve_scheme`` as the single scheme rule and
    then inlined the same http-for-loopback / https-for-remote default twice more in
    ``_load_helloz_config``, so the security-relevant half of the rule existed in two
    places and only one was canonical.
    """
    calls = []
    original = constants.resolve_scheme
    monkeypatch.setattr(
        constants, "resolve_scheme",
        lambda host, scheme=None: calls.append((host, scheme)) or original(host, scheme),
    )
    with _write_config(tmp_path, {"helloz_nsfw_host": "localhost"}):
        _host, _port, _endpoint, scheme = constants._load_helloz_config()
    assert scheme == "http"
    assert calls == [("localhost", None)], "detection read path bypassed resolve_scheme"
    # The default expression itself must exist in exactly one function.
    source = open(constants.__file__, encoding="utf-8").read()
    assert source.count("'http' if host in _LOOPBACK_HOSTS else 'https'") == 1


@pytest.mark.parametrize("payload", ["[1, 2]", '"dark"', "null", "42"])
def test_load_helloz_config_rejects_a_non_object_document(tmp_path, caplog, payload):
    """Valid JSON of the wrong shape must not raise out of the detection path.

    Regression guard: ``json.load`` succeeded, so the ``try/except`` never fired and
    ``cfg.get(...)`` raised AttributeError/TypeError on every detection call —
    the opposite of the function's stated "return defaults on error" contract.
    """
    config_path = tmp_path / "app_config.json"
    config_path.write_text(payload, encoding="utf-8")
    with patch("src.core.constants._config_path", return_value=str(config_path)), \
         caplog.at_level("WARNING", logger="src.core.constants"):
        result = constants._load_helloz_config()
    assert result == (
        constants.HELLOZ_NSFW_HOST, constants.HELLOZ_NSFW_PORT,
        constants.HELLOZ_NSFW_API_ENDPOINT, 'http',
    )
    assert "not an object" in caplog.text


def test_absurdly_large_legacy_value_never_raises(tmp_path):
    """A ~400-digit legacy integer must not escape the migration.

    Regression guard: ``ms / 1000.0`` raised OverflowError for an integer beyond
    the float range, escaping ``migrate_config`` and therefore the window
    constructor — from the function whose job is to be defensive about junk. The
    integer-only conversion is exact, so the absurd magnitude is carried forward
    and bounded downstream by the read path, which is where the bound lives.
    """
    huge = int("9" * 400)
    migrated, changes = config_migration.migrate_config({"detect_timeout": huge})
    assert isinstance(migrated["detect_timeout_seconds"], int)
    assert migrated["detect_timeout_seconds"] == (huge + 500) // 1000
    assert changes and "detect_timeout" in changes[0]
    # Bounded on read, never on write — the value is honoured, not silently capped.
    assert constants.normalize_timeout_seconds(
        migrated["detect_timeout_seconds"], constants.DETECT_TIMEOUT,
        name="detect_timeout_seconds", max_seconds=constants.DETECT_TIMEOUT_MAX_SECONDS,
    ) == constants.DETECT_TIMEOUT_MAX_SECONDS
    # And the file-level entry point stays exception-free.
    (tmp_path / "app_config.json").write_text(
        json.dumps({"detect_timeout": huge}), encoding="utf-8",
    )
    persisted, notes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert isinstance(persisted["detect_timeout_seconds"], int)
    assert notes


def test_config_from_a_newer_schema_version_warns_and_is_not_migrated(caplog):
    """A downgrade is reported, never silently accepted."""
    cfg = {constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION + 1, "detect_timeout": 250}
    with caplog.at_level("WARNING", logger="src.core.config_migration"):
        assert config_migration.needs_migration(cfg) is False
        note = config_migration.downgrade_note(cfg)
    assert note and str(constants.CONFIG_VERSION + 1) in note
    assert str(constants.CONFIG_VERSION) in note
    assert "newer than the supported version" in caplog.text
    # Nothing was rewritten: this build cannot know the newer schema.
    assert config_migration.migrate_config(cfg) == (cfg, [])
    assert config_migration.downgrade_note({}) is None


def test_downgrade_reaches_the_activity_log(tmp_path):
    """``migrate_config_file`` returns the downgrade note so the GUI can show it."""
    (tmp_path / "app_config.json").write_text(
        json.dumps({constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION + 1, "theme": "dark"}),
        encoding="utf-8",
    )
    migrated, notes = config_migration.migrate_config_file(str(tmp_path), "app_config.json")
    assert migrated == {constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION + 1, "theme": "dark"}
    assert any("newer than the supported version" in note for note in notes)


def test_dead_config_keys_agree_with_the_shipped_fixture():
    """The dead-key set and the fixture's non-constant set describe the same split.

    ``DEAD_CONFIG_KEYS`` is documentation-and-test data that lives in
    ``src/core/constants.py`` deliberately, so the drift risk it carries is pinned
    here: the four dead keys plus the three genuinely non-constant live keys must be
    exactly the fixture's constant-less entries.
    """
    non_constant_live = {"config_version", "model", "last_source_folder"}
    assert set(_load_default_config()) - set(FIXTURE_CONSTANT_KEYS_DICT) == (
        set(constants.DEAD_CONFIG_KEYS) | non_constant_live
    )
    assert constants.DEAD_CONFIG_KEYS <= set(FIXTURE_NON_CONSTANT_KEYS)

"""Deterministic, one-time migration of ``config/app_config.json`` (ADD-007).

Before this module existed the app guessed whether a configured timeout was in
milliseconds or seconds from the magnitude of the value (``>= 1000`` meant
"milliseconds"). That heuristic had two defects:

* it could not repair the value the project actually shipped — ``250`` — so every
  existing install kept the 250-second worker/detection timeouts that issue #91 was
  filed against; and
* it rewrote legitimate large seconds values such as ``detect_timeout: 3600`` down
  to 4 seconds.

The unit is now *stated* instead of guessed. The config carries a
``config_version`` field; a config without it (or below
:data:`src.core.constants.CONFIG_VERSION`) predates the seconds contract, so its
legacy timeout keys are converted once, deterministically, and the file is
rewritten with the current key names and version. Subsequent loads take the
seconds branch and no value is ever re-interpreted.

Two entry points:

* :func:`migrate_config` — pure; migrates a loaded dict and returns the new dict
  plus human-readable change descriptions.
* :func:`migrate_config_file` — reads the on-disk config, migrates it and persists
  the rewrite atomically, so the conversion is recorded on disk once and never
  depends on the user happening to change a setting in the GUI.
"""
import json
import logging
import os
import tempfile

from .constants import (
    CONFIG_DIR,
    CONFIG_FILE_NAME,
    CONFIG_VERSION,
    CONFIG_VERSION_KEY,
    LEGACY_MILLISECOND_TIMEOUT_KEYS,
    MILLISECONDS_PER_SECOND,
    MIN_MIGRATABLE_SECONDS,
    RENAMED_TIMEOUT_KEYS,
)

logger = logging.getLogger(__name__)


def config_version(cfg):
    """Return the declared config schema version of a loaded config dict.

    A config that has no ``config_version`` key is version 1 — the millisecond
    contract that shipped before ADD-007 — because that is what its keys mean.

    Args:
        cfg: Loaded config mapping (may be empty).

    Returns:
        The declared version as an int, or 1 when absent/unparseable.
    """
    try:
        return int(cfg.get(CONFIG_VERSION_KEY, 1))
    except (TypeError, ValueError, OverflowError):
        logger.warning(
            "%s value %r is not a valid version; treating this config as version 1 "
            "(legacy millisecond timeouts)",
            CONFIG_VERSION_KEY, cfg.get(CONFIG_VERSION_KEY),
        )
        return 1


def needs_migration(cfg):
    """Return whether ``cfg`` predates the seconds timeout contract.

    Args:
        cfg: Loaded config mapping.

    Returns:
        True if the config must be migrated from millisecond to second timeouts.
    """
    return config_version(cfg) < CONFIG_VERSION


def _convert_milliseconds_to_seconds(raw_value, default_seconds, key):
    """Convert one legacy millisecond timeout to whole seconds.

    A value that cannot be honoured as seconds — unparseable, non-positive, or
    sub-second once converted — falls back to ``default_seconds``. The shipped
    ``250`` is exactly such a value: 250 ms is 0.25 s, which no whole-second
    timeout can express and which would make every detection time out at once, so
    it migrates to the code default (5 s / 60 s) rather than to 0 s or 1 s.

    Args:
        raw_value: The legacy millisecond value read from the config.
        default_seconds: Seconds value to use when conversion is not faithful.
        key: Legacy key name, used for the change description and log message.

    Returns:
        Tuple of (seconds_value, change_description).
    """
    if isinstance(raw_value, bool):
        return default_seconds, f"{key}: boolean {raw_value!r} replaced with {default_seconds} s"
    try:
        milliseconds = int(raw_value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError covers non-finite floats such as float('inf').
        return default_seconds, f"{key}: unusable value {raw_value!r} replaced with {default_seconds} s"
    seconds = int(milliseconds / MILLISECONDS_PER_SECOND + 0.5)  # round-half-up
    if seconds < MIN_MIGRATABLE_SECONDS:
        return (
            default_seconds,
            f"{key}: legacy {milliseconds} ms is sub-second, replaced with {default_seconds} s",
        )
    return seconds, f"{key}: legacy {milliseconds} ms migrated to {seconds} s"


def _migrate_millisecond_keys(migrated, changes):
    """Convert every legacy millisecond timeout key in ``migrated`` to seconds.

    A hand-edited or partially-updated config can carry both spellings of a key.
    The ``*_seconds`` key is then authoritative — it is the one that states its
    unit — so the legacy key is dropped and the existing value kept rather than
    silently overwritten.

    Args:
        migrated: Config mapping being built; mutated in place.
        changes: List of change descriptions appended to in place.
    """
    for legacy_key, (seconds_key, default_seconds) in LEGACY_MILLISECOND_TIMEOUT_KEYS.items():
        if legacy_key not in migrated:
            # A config may legitimately omit the key; the constant default applies.
            continue
        raw_value = migrated.pop(legacy_key)
        if seconds_key in migrated:
            changes.append(
                f"{legacy_key}: legacy millisecond key dropped; kept the existing "
                f"{seconds_key}={migrated[seconds_key]} s"
            )
            continue
        seconds, description = _convert_milliseconds_to_seconds(raw_value, default_seconds, legacy_key)
        migrated[seconds_key] = seconds
        changes.append(description)


def _rename_timeout_keys(migrated, changes):
    """Rename timeout keys that already held seconds but lacked the unit suffix.

    These keys were read as seconds before ADD-007 (and still are), so this is a
    pure rename: no value is converted, only the key name changes to state the
    unit that was always true.

    Args:
        migrated: Config mapping being built; mutated in place.
        changes: List of change descriptions appended to in place.
    """
    for legacy_key, seconds_key in RENAMED_TIMEOUT_KEYS.items():
        if legacy_key not in migrated:
            continue
        value = migrated.pop(legacy_key)
        if seconds_key in migrated:
            changes.append(
                f"{legacy_key}: dropped; kept the existing {seconds_key}={migrated[seconds_key]} s"
            )
            continue
        migrated[seconds_key] = value
        changes.append(f"{legacy_key}: renamed to {seconds_key} (value unchanged, already in seconds)")


def migrate_config(cfg):
    """Migrate a legacy millisecond config to the seconds contract.

    Pure function: the input mapping is not modified. Migration is idempotent —
    running it on an already-migrated config returns it unchanged with no change
    descriptions.

    Args:
        cfg: Loaded config mapping (may be empty or missing keys).

    Returns:
        Tuple of ``(migrated_cfg, changes)`` where ``migrated_cfg`` is a new dict
        and ``changes`` is a list of human-readable descriptions of every rewrite
        performed (empty when nothing changed).
    """
    if not needs_migration(cfg):
        return dict(cfg), []

    migrated = {key: value for key, value in cfg.items() if key != CONFIG_VERSION_KEY}
    changes = []

    _migrate_millisecond_keys(migrated, changes)
    _rename_timeout_keys(migrated, changes)

    migrated[CONFIG_VERSION_KEY] = CONFIG_VERSION
    for description in changes:
        logger.warning("Config migration: %s", description)
    if changes:
        # WARNING only when something was actually rewritten: the whole argument
        # of ADD-007 is that a rewrite the user cannot see is a rewrite they
        # cannot correct. A fresh install has nothing to rewrite.
        logger.warning(
            "Config migrated to version %s (timeout keys now state their unit in "
            "seconds). Review them in %s before relying on the migrated values.",
            CONFIG_VERSION, os.path.join(CONFIG_DIR, CONFIG_FILE_NAME),
        )
    else:
        logger.debug(
            "Config contains no legacy timeout keys; stamped with version %s", CONFIG_VERSION,
        )
    return migrated, changes


def _write_config(config_path, data):
    """Write ``data`` as formatted JSON to ``config_path``, atomically.

    The config file is the user's only copy of their settings (theme, model, last
    source folder as well as timeouts), so it is never truncated in place: the
    JSON is streamed to a sibling temp file in the same directory and then moved
    over the target with :func:`os.replace`, which is atomic on POSIX and stays
    on the same filesystem.

    Args:
        config_path: Destination path.
        data: Mapping to serialise.

    Raises:
        OSError: If the file cannot be written.
    """
    directory = os.path.dirname(config_path) or '.'
    descriptor, temp_path = tempfile.mkstemp(dir=directory, prefix='.app_config.', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(temp_path, config_path)
    except BaseException:
        # Never leave a partial temp file behind on failure.
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def migrate_config_file(config_dir=None, config_file_name=None, cfg=None):
    """Migrate the on-disk config file in place, if it needs migration.

    Called on GUI startup so the conversion is persisted once, rather than being
    re-derived on every launch and only reaching disk when the user next saves a
    setting. Failures are logged *and* returned as note strings so the caller can
    surface them in the activity log: a config that cannot be read or rewritten is
    exactly the state where the user most needs to be told the file is stale.

    Args:
        config_dir: Directory holding the config file. Defaults to
            :data:`src.core.constants.CONFIG_DIR`.
        config_file_name: File name of the config file. Defaults to
            :data:`src.core.constants.CONFIG_FILE_NAME`.
        cfg: Already-loaded config mapping, when the caller has read the file
            itself. Passing it avoids a second read of the same file and keeps the
            migrated result consistent with what the caller is about to use. When
            None the file is read from disk.

    Returns:
        Tuple of ``(migrated_cfg, notes)``. ``migrated_cfg`` is the dict the caller
        should read settings from; it is empty when the file could not be read.
        ``notes`` holds one entry per rewrite plus an entry naming the file
        whenever it could not be read, migrated or persisted. Both are empty when
        the file is absent and empty when it is already at the current version.
    """
    config_path = os.path.join(config_dir or CONFIG_DIR, config_file_name or CONFIG_FILE_NAME)
    if cfg is None:
        try:
            with open(config_path, 'r', encoding='utf-8') as handle:
                cfg = json.load(handle)
        except FileNotFoundError:
            # A fresh install has no config yet; the app writes one on first save.
            return {}, []
        except (OSError, ValueError) as exc:
            logger.warning("Could not read %s for migration (%s); using defaults", config_path, exc)
            return {}, [f"{config_path} could not be read for migration ({exc}); the file is left as-is"]
    if not isinstance(cfg, dict):
        logger.warning("%s is not a JSON object; skipping config migration", config_path)
        return {}, [f"{config_path} is not a JSON object; it is ignored and will be retried on every start"]

    migrated, changes = migrate_config(cfg)
    if not changes and config_version(cfg) >= CONFIG_VERSION:
        return dict(cfg), []

    try:
        _write_config(config_path, migrated)
    except OSError as exc:
        # Note is returned, not just logged: the on-disk and in-memory views now
        # diverge and the user must be told (ADD-007 section 3).
        logger.warning("Could not persist migrated config to %s (%s)", config_path, exc)
        return migrated, changes + [
            f"{config_path} could not be rewritten ({exc}); the migration will be re-applied on every start"
        ]
    return migrated, changes

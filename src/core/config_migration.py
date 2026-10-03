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
legacy millisecond timeout keys are converted once, deterministically, on load and
the file is stamped with the current version. Subsequent loads take the seconds
branch and no value is ever re-interpreted.

This module is pure: it takes a dict and returns a new dict plus a list of
human-readable change descriptions. The caller decides whether to persist.
"""
import json
import logging
import os

from .constants import (
    CONFIG_VERSION,
    CONFIG_VERSION_KEY,
    DETECT_TIMEOUT,
    LEGACY_MILLISECOND_TIMEOUT_KEYS,
    MILLISECONDS_PER_SECOND,
    MIN_MIGRATABLE_SECONDS,
    WORKER_THREAD_TIMEOUT,
)

logger = logging.getLogger(__name__)

# The seconds default each legacy millisecond key migrates to when it cannot be
# converted faithfully (sub-second value, or unparseable value).
LEGACY_KEY_DEFAULTS = {
    'worker_thread_timeout': WORKER_THREAD_TIMEOUT,
    'detect_timeout': DETECT_TIMEOUT,
}


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
        Tuple of (seconds_value, change_description_or_None).
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

    for legacy_key, seconds_key in LEGACY_MILLISECOND_TIMEOUT_KEYS.items():
        if legacy_key not in migrated:
            # A config may legitimately omit the key; the constant default applies.
            continue
        raw_value = migrated.pop(legacy_key)
        seconds, description = _convert_milliseconds_to_seconds(
            raw_value, LEGACY_KEY_DEFAULTS[legacy_key], legacy_key,
        )
        migrated[seconds_key] = seconds
        changes.append(description)

    migrated[CONFIG_VERSION_KEY] = CONFIG_VERSION
    for description in changes:
        logger.warning("Config migration: %s", description)
    logger.warning(
        "Config migrated to version %s (timeouts are now in seconds). Review %s in "
        "config/%s before relying on the migrated values.",
        CONFIG_VERSION, ' and '.join(LEGACY_MILLISECOND_TIMEOUT_KEYS.values()), 'app_config.json',
    )
    return migrated, changes


def migrate_config_file(config_dir, config_file_name):
    """Migrate the on-disk config file in place, if it needs migration.

    Used by the GUI on startup so the conversion happens once rather than on every
    read. Failures (missing file, unreadable, unwritable directory) are logged and
    swallowed: a config that cannot be persisted must still start the application,
    which will fall back to the in-memory defaults.

    Args:
        config_dir: Directory holding the config file.
        config_file_name: File name of the config file.

    Returns:
        List of change descriptions performed; empty when nothing was migrated or
        the file could not be read.
    """
    config_path = os.path.join(config_dir, config_file_name)
    if not os.path.exists(config_path):
        return []
    try:
        with open(config_path, 'r', encoding='utf-8') as handle:
            cfg = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.warning("Could not read %s for migration (%s); using defaults", config_path, exc)
        return []
    if not isinstance(cfg, dict):
        logger.warning("%s is not a JSON object; skipping config migration", config_path)
        return []

    migrated, changes = migrate_config(cfg)
    if not changes:
        # Nothing was rewritten, but stamp the version so the legacy branch is
        # never evaluated again for this file.
        if config_version(cfg) >= CONFIG_VERSION:
            return []
        try:
            _write_config(config_path, migrated)
        except OSError as exc:
            logger.warning("Could not stamp config version in %s (%s)", config_path, exc)
        return []

    try:
        _write_config(config_path, migrated)
    except OSError as exc:
        logger.warning("Could not persist migrated config to %s (%s)", config_path, exc)
    return changes


def _write_config(config_path, data):
    """Write ``data`` as formatted JSON to ``config_path``.

    Args:
        config_path: Destination path.
        data: Mapping to serialise.

    Raises:
        OSError: If the file cannot be written.
    """
    with open(config_path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
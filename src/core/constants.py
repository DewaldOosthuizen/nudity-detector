"""
Centralized constants for the Nudity Detector application.
Provides single source of truth for configuration values, avoiding magic numbers.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# ============================================================================
# Media Type Configuration
# ============================================================================
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'})
VIDEO_EXTENSIONS = frozenset({'.mp4', '.avi', '.mkv', '.mov', '.vob', '.wmv', '.flv', '.3gp', '.webm'})
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

MIME_IMAGE_TYPES = frozenset({
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/tiff', 'image/bmp',
})
# NOTE: 'application/octet-stream' is deliberately NOT included here. libmagic reports
# that generic MIME type as a fallback for a huge range of unrecognized/malformed
# binary content, so admitting it would let any file renamed to a trusted video
# extension (e.g. payload.mp4) sail through the extension+MIME cross-check unchanged,
# defeating the purpose of the magic-byte verification.
MIME_VIDEO_TYPES = frozenset({
    'video/mp4', 'video/x-msvideo', 'video/x-matroska', 'video/quicktime',
    'video/x-ms-wmv', 'video/x-flv', 'video/3gpp', 'video/webm',
})

MEDIA_TYPE_IMAGE = 'image'
MEDIA_TYPE_VIDEO = 'video'
MEDIA_TYPE_UNKNOWN = 'unknown'

# ============================================================================
# Nudity Detection - Model Classes
# ============================================================================
# NudeNet detector class labels for nudity
NUDITY_CLASSES = frozenset({
    'EXPOSED_ANUS',
    'EXPOSED_BREAST_F',
    'EXPOSED_GENITALIA_F',
    'EXPOSED_GENITALIA_M',
    'EXPOSED_BUTTOCKS',
})
# Optional exposed classes that can increase recall, but may also raise false positives.
NUDITY_CLASSES_EXTENDED = frozenset({
    'EXPOSED_ARMPITS',
    'EXPOSED_BELLY',
    'EXPOSED_BREAST_M',
    'EXPOSED_FEET',
})

NUDITY_CLASSES_BROAD = frozenset(NUDITY_CLASSES | NUDITY_CLASSES_EXTENDED)

MODEL_NUDENET = 'nudenet'
MODEL_HELLOZ_NSFW = 'helloz_nsfw'
SUPPORTED_MODELS = (MODEL_NUDENET, MODEL_HELLOZ_NSFW)

# ============================================================================
# Nudity Detection - Thresholds
# ============================================================================
DEFAULT_THRESHOLD_PERCENT = 60.0
MIN_THRESHOLD_PERCENT = 0.0
MAX_THRESHOLD_PERCENT = 100.0
THRESHOLD_TOLERANCE = 0.001  # For normalize_threshold equality checks

# ============================================================================
# App Configuration
# ============================================================================
CONFIG_DIR = 'config'
CONFIG_FILE_NAME = 'app_config.json'

# ============================================================================
# Report Configuration
# ============================================================================
DEFAULT_REPORT_DIR = 'reports'
REPORT_FILE_NAME = 'nudity_report.xlsx'
XLSX_EXTENSION = '.xlsx'
SESSION_FILE_SUFFIX = '_session.json'
SESSION_VERSION = 1
SCAN_RUN_DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'

REPORT_HEADERS = (
    'File',
    'Media Type',
    'Model',
    'Threshold Percent',
    'Confidence Percent',
    'Nudity Detected',
    'Detected Classes',
    'Thumbnail',
    'Date Classified',
)

# ============================================================================
# Thumbnail Configuration
# ============================================================================
THUMBNAIL_SIZE_REPORT = (100, 100)  # Size for Excel embedding
THUMBNAIL_SIZE_PREVIEW = (320, 320)  # Size for GUI preview container
THUMBNAIL_SIZE_PREVIEW_IMAGE = (
    int(THUMBNAIL_SIZE_PREVIEW[0] * 0.70),
    int(THUMBNAIL_SIZE_PREVIEW[1] * 0.70),
)  # Actual rendered image size within the preview container (70% of container)
THUMBNAIL_FORMAT = 'PNG'
THUMBNAIL_IMAGE_INDEX = 0.25  # Video frame at 25% progress
NO_THUMBNAIL_TEXT = 'No thumbnail available'

# ============================================================================
# Video Frame Extraction
# ============================================================================
VIDEO_FRAME_RATE = 5  # Extract every Nth frame
FRAME_TEMP_DIR_PREFIX_GUI_NUDENET = 'gui_nudenet_frames_'
FRAME_TEMP_DIR_PREFIX_GUI_HELLOZ_NSFW = 'gui_helloz_nsfw_frames_'
FRAME_TEMP_DIR_PREFIX_CLI_NUDENET = 'nudenet_frames_'
FRAME_TEMP_DIR_PREFIX_CLI_HELLOZ_NSFW = 'helloz_nsfw_frames_'
FRAME_FILE_NAME_PATTERN = 'frame_{}.jpg'

# ============================================================================
# Helloz NSFW API
# ============================================================================
HELLOZ_NSFW_HOST = 'localhost'
HELLOZ_NSFW_PORT = 6086
HELLOZ_NSFW_API_ENDPOINT = '/api/upload_check'
HELLOZ_NSFW_REQUEST_TIMEOUT = 30  # seconds
HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT = 5  # seconds
HELLOZ_NSFW_MAX_RETRIES = 3
HELLOZ_NSFW_RETRY_BACKOFF = 1.0  # seconds; doubles on each attempt


_LOOPBACK_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})


def _config_path():
    """Return the path to app_config.json relative to the current working directory."""
    return os.path.join(CONFIG_DIR, CONFIG_FILE_NAME)


def _load_helloz_config():
    """Load helloz NSFW config from app_config.json; return defaults on error."""
    try:
        with open(_config_path(), 'r') as f:
            cfg = json.load(f)
        host = cfg.get('helloz_nsfw_host', HELLOZ_NSFW_HOST)
        port = cfg.get('helloz_nsfw_port', HELLOZ_NSFW_PORT)
        endpoint = cfg.get('helloz_nsfw_api_endpoint', HELLOZ_NSFW_API_ENDPOINT)
        # Use configured scheme when provided; otherwise default to http for loopback
        # and https for any remote host.
        if 'helloz_nsfw_scheme' in cfg:
            scheme = cfg['helloz_nsfw_scheme']
        else:
            scheme = 'http' if host in _LOOPBACK_HOSTS else 'https'
        return host, port, endpoint, scheme
    except (OSError, json.JSONDecodeError):
        logger.warning(
            "app_config.json not found or invalid at %s; using built-in defaults",
            _config_path(),
        )
        return HELLOZ_NSFW_HOST, HELLOZ_NSFW_PORT, HELLOZ_NSFW_API_ENDPOINT, 'http'


def _validate_scheme(scheme, host):
    """Raise ValueError when HTTP is used with a non-loopback host."""
    if scheme == 'http' and host not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Insecure scheme 'http' is not allowed for non-loopback host '{host}'. "
            "Set 'helloz_nsfw_scheme' to 'https' in config/app_config.json."
        )


def get_helloz_nsfw_url():
    """Return the full Helloz NSFW API upload URL, read from config each call."""
    host, port, endpoint, scheme = _load_helloz_config()
    _validate_scheme(scheme, host)
    return f'{scheme}://{host}:{port}{endpoint}'


def get_helloz_nsfw_connection_check_url():
    """Return the base Helloz NSFW connection-check URL, read from config each call."""
    host, port, _endpoint, scheme = _load_helloz_config()
    _validate_scheme(scheme, host)
    return f'{scheme}://{host}:{port}'




# ============================================================================
# GUI Configuration - UI Constants
# ============================================================================
GUI_WINDOW_TITLE = 'Nudity Detector'
GUI_WINDOW_GEOMETRY = '1080x950'
GUI_WINDOW_MIN_WIDTH = 900
GUI_WINDOW_MIN_HEIGHT = 700
GUI_FRAME_PADDING = 16
GUI_CONTROLS_PADDING = 12
GUI_PREVIEW_PANEL_WIDTH = 30  # Character width

# GUI Theme Options
THEME_SYSTEM = 'system'
THEME_LIGHT = 'light'
THEME_DARK = 'dark'
SUPPORTED_THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

# ============================================================================
# GUI Configuration - Tree View
# ============================================================================
TREE_COLUMNS = ('name', 'media_type', 'confidence', 'model', 'path')
TREE_HEIGHT = 12
TREE_COLUMN_WIDTHS = {
    'name': 220,
    'media_type': 90,
    'confidence': 110,
    'model': 100,
    'path': 430,
}
TREE_COLUMN_ANCHORS = {
    'name': 'w',
    'media_type': 'center',
    'confidence': 'center',
    'model': 'center',
    'path': 'w',
}

# ============================================================================
# GUI Configuration - Button Padding
# ============================================================================
BUTTON_PADX_DEFAULT = (0, 8)
BUTTON_PADX_LAST = (0, 0)

# ============================================================================
# Threading
# ============================================================================
WORKER_THREAD_COUNT = 10
WORKER_THREAD_TIMEOUT = 5  # seconds
DETECT_TIMEOUT = 60  # seconds for individual detections

# ============================================================================
# Threading — Timeout Units
# ============================================================================
# Conversion factor used ONLY by the one-time config migration in
# src/core/config_migration.py. It is a plain conversion factor, deliberately
# unrelated to any unit-detection bound: since ADD-007 the unit is never guessed
# from the magnitude of a value, it is stated by the config schema version.
MILLISECONDS_PER_SECOND = 1000

# Bumped whenever the meaning (not merely the value) of a config key changes.
# Version 1: timeout keys were milliseconds (the defect in issue #91).
# Version 2: all timeout keys are seconds. ``migrate_config`` converts 1 -> 2 once.
CONFIG_VERSION = 2
CONFIG_VERSION_KEY = 'config_version'

# Keys whose unit changed in CONFIG_VERSION 2, mapping
# legacy_key -> (seconds_key, fallback_seconds). The rename and the fallback live
# in one mapping so they cannot drift apart. ``fallback_seconds`` is used when the
# legacy millisecond value cannot be honoured as whole seconds.
LEGACY_MILLISECOND_TIMEOUT_KEYS = {
    'worker_thread_timeout': ('worker_thread_timeout_seconds', WORKER_THREAD_TIMEOUT),
    'detect_timeout': ('detect_timeout_seconds', DETECT_TIMEOUT),
}

# Timeout keys renamed in CONFIG_VERSION 2 purely so their key name states the
# unit. These already held seconds before ADD-007 and still do, so the migration
# renames them without converting the value — leaving them unsuffixed would keep
# the suffix an unreliable unit marker, which is the ambiguity ADD-007 removes.
#
# Only keys with a reader belong here: the rename exists so the *value the app
# uses* states its unit, and a key nothing reads has no established unit to
# preserve. ``nudenet_worker_thread_timeout`` and
# ``helloz_nsfw_worker_thread_timeout`` are deliberately NOT listed even though
# they would fit mechanically — this PR's own tests classify them as dead (see
# :data:`DEAD_CONFIG_KEYS`), so migrating them would spend a schema-version bump
# and a user-facing change note to rewrite a value nothing consumes, on the
# unverifiable premise that their pre-rename unit "was always seconds". They are
# removed by issue #104 rather than renamed forward here.
RENAMED_TIMEOUT_KEYS = {
    'helloz_nsfw_request_timeout': 'helloz_nsfw_request_timeout_seconds',
    'helloz_nsfw_health_check_timeout': 'helloz_nsfw_health_check_timeout_seconds',
}

# Constant-backed config keys whose *shipped* default must equal the constant, so
# config and code agree on day one. A configured value is honoured as written
# (only its type is coerced); a divergence between the shipped default and the
# constant is what silently handed users a 300 s request timeout where the code
# default is 30 s, so it is logged at WARNING on startup.
CONFIG_DEFAULT_ALIGNMENT = {
    'video_frame_rate': VIDEO_FRAME_RATE,
    'worker_thread_count': WORKER_THREAD_COUNT,
    'worker_thread_timeout_seconds': WORKER_THREAD_TIMEOUT,
    'detect_timeout_seconds': DETECT_TIMEOUT,
    'helloz_nsfw_request_timeout_seconds': HELLOZ_NSFW_REQUEST_TIMEOUT,
    'helloz_nsfw_health_check_timeout_seconds': HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT,
}


# Smallest whole-second timeout the migration will ever emit. A legacy millisecond
# value below one second (``MILLISECONDS_PER_SECOND``) is not migrated by arithmetic
# at all — it is replaced by the key's constant default, because 0.25 s expressed
# in whole seconds is not a usable timeout. ``MIN_MIGRATABLE_SECONDS`` documents
# that floor so a mapping entry cannot declare a fallback below it.
MIN_MIGRATABLE_SECONDS = 1

# Upper bounds accepted for timeout settings, in seconds. They are the documented
# supported range: the GUI spin buttons are built with these as their ``upper`` so
# a value the config path accepts is never silently truncated by Gtk, and a
# configured value beyond the bound is clamped with a WARNING that names the key,
# the configured value and the applied maximum (ADD-007).
WORKER_THREAD_TIMEOUT_MAX_SECONDS = 86400  # 24 hours
DETECT_TIMEOUT_MAX_SECONDS = 86400  # 24 hours
HELLOZ_NSFW_REQUEST_TIMEOUT_MAX_SECONDS = 3600  # 1 hour
HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT_MAX_SECONDS = 3600  # 1 hour

TIMEOUT_MAX_SECONDS = {
    'worker_thread_timeout_seconds': WORKER_THREAD_TIMEOUT_MAX_SECONDS,
    'detect_timeout_seconds': DETECT_TIMEOUT_MAX_SECONDS,
    'helloz_nsfw_request_timeout_seconds': HELLOZ_NSFW_REQUEST_TIMEOUT_MAX_SECONDS,
    'helloz_nsfw_health_check_timeout_seconds': HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT_MAX_SECONDS,
}

# Highest legal TCP port, used as the upper bound of the port accessor.
MAX_PORT = 65535

# Config keys that no code under ``src/`` reads. They are retained in the shipped
# defaults as a reference table only; their removal is tracked in issue #104.
# Kept here so the documentation, the reference fixture and the test that greps
# ``src/`` for a reader cannot disagree about which keys are dead.
DEAD_CONFIG_KEYS = frozenset({
    'nudenet_worker_thread_count',
    'helloz_nsfw_worker_thread_count',
    'nudenet_worker_thread_timeout_seconds',
    'helloz_nsfw_worker_thread_timeout_seconds',
})


def normalize_positive_int(value, default, name=None, min_value=1, max_value=None, quiet=False):
    """Coerce a possibly-invalid configured scalar to an integer at or above a bound.

    The single implementation of "config scalar -> safe positive int" used by every
    numeric config read (ADD-007). Previously each call site hand-rolled its own
    ``try: max(1, int(...)) except (ValueError, TypeError)`` block, so the same
    coercion had several implementations with inconsistent logging policies.

    Args:
        value: Raw configured value; may be None, a numeric string, a bool, or garbage.
        default: Fallback used when the value is absent or unparseable. It is
            itself clamped to ``min_value`` so the documented lower bound holds.
        name: Optional setting name, used only to make log messages actionable.
        min_value: Lower bound applied to the parsed value (inclusive).
        max_value: Optional upper bound applied to the parsed value (inclusive).
            A value above it is clamped down and the clamp is logged, naming the key,
            the configured value and the applied maximum, so a truncation is never
            silent.
        quiet: Suppress the value-coercion log records. Used by callers that only
            want the coerced value (such as the divergence pass) and delegate the
            reporting to a single read path.

    Returns:
        An int within ``[min_value, max_value]`` (``max_value`` when given).

    Raises:
        Nothing. ``bool`` is rejected explicitly (a JSON ``true`` in a numeric key
        is a user error, not the value 1) and ``None`` is treated as "not configured"
        at DEBUG level, because a missing key is normal on a fresh install. Every
        other rewrite is logged at WARNING level so no config error is silent.
    """
    label = name or 'value'

    def _warn(message, *args):
        if not quiet:
            logger.warning(message, *args)

    def _debug(message, *args):
        if not quiet:
            logger.debug(message, *args)

    def _fallback():
        return max(min_value, int(default))

    if value is None:
        # Absent key is normal on a fresh install, not a defect — do not warn.
        _debug("%s is not configured; using default of %s", label, default)
        return _fallback()
    if isinstance(value, bool):
        _warn(
            "%s value %r is a boolean, not a number; using default of %s",
            label, value, default,
        )
        return _fallback()
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: int(float('inf')) / int(float('nan')) raise it.
        _warn(
            "%s value %r is not a valid number; using default of %s",
            label, value, default,
        )
        return _fallback()
    if numeric < min_value:
        _warn(
            "%s value %s is below the minimum of %s; using %s",
            label, numeric, min_value, min_value,
        )
        return min_value
    if max_value is not None and numeric > max_value:
        _warn(
            "%s value %s is above the supported maximum of %s; using %s",
            label, numeric, max_value, max_value,
        )
        return max_value
    return numeric


def normalize_timeout_seconds(value, default_seconds, name=None, max_seconds=None):
    """Normalize a configured timeout value to whole seconds for the threading API.

    This is the single unit boundary for timeout values (ADD-007). The value is
    *already in seconds*: legacy millisecond configs are converted once,
    deterministically, by :func:`src.core.config_migration.migrate_config` at load
    time. No unit is guessed from the magnitude of the value, so a legitimate large
    timeout such as ``detect_timeout_seconds: 3600`` is honoured as 3600 seconds.

    Args:
        value: Raw timeout value in seconds (post-migration).
        default_seconds: Fallback value in seconds when value is missing or invalid.
        name: Optional name of the setting, used only to make log messages
            actionable. Purely diagnostic.
        max_seconds: Optional supported upper bound, in seconds. A configured value
            above it is clamped down and logged, naming the key, the configured
            value and the applied maximum, so the truncation is visible rather than
            silent. Defaults to the per-key bound in :data:`TIMEOUT_MAX_SECONDS`
            when ``name`` names a known timeout key.

    Returns:
        Timeout in whole seconds, always >= 1 — including when ``default_seconds``
        is returned, so the documented guarantee is enforced by the code and not
        merely by today's constant values.

    Raises:
        Nothing — invalid values (non-finite floats, booleans, non-numeric strings)
        fall back to ``default_seconds``, and every fallback and clamp is logged at
        WARNING level so an unparseable or out-of-range value is visible in the log
        rather than silently presenting as a default.
    """
    if max_seconds is None and name in TIMEOUT_MAX_SECONDS:
        max_seconds = TIMEOUT_MAX_SECONDS[name]
    return normalize_positive_int(
        value, default_seconds, name=name, min_value=1, max_value=max_seconds,
    )


def normalize_threshold_percent(value, default=None, name=None):
    """Coerce a possibly-invalid ``threshold_percent`` to a float percentage.

    The sibling of :func:`normalize_positive_int` for the one numeric config key
    that is a float rather than a count. It closes the same hole for the same
    reason (ADD-007): a raw ``float(cfg.get('threshold_percent', ...))`` lets a
    hand-edited ``"abc"``, ``true`` or ``{}`` raise out of the window constructor,
    so the application never starts — a config error that is not merely applied
    silently but fatal.

    Args:
        value: Raw configured value; may be None, a numeric string, a bool, or garbage.
        default: Fallback in percent when the value is absent or unparseable.
            Defaults to :data:`DEFAULT_THRESHOLD_PERCENT`.
        name: Optional setting name, used only to make log messages actionable.

    Returns:
        A float within ``[MIN_THRESHOLD_PERCENT, MAX_THRESHOLD_PERCENT]``.

    Raises:
        Nothing. ``bool`` is rejected explicitly (a JSON ``true`` in a numeric key
        is a user error, not the value 1.0), ``None`` is treated as "not configured"
        at DEBUG level, and every other rewrite is logged at WARNING so no config
        error is silent.
    """
    label = name or 'threshold_percent'
    fallback = DEFAULT_THRESHOLD_PERCENT if default is None else default
    if value is None:
        logger.debug("%s is not configured; using default of %s", label, fallback)
        return _clamp_threshold(fallback, fallback, label)
    if isinstance(value, bool):
        logger.warning(
            "%s value %r is a boolean, not a number; using default of %s",
            label, value, fallback,
        )
        return _clamp_threshold(fallback, fallback, label)
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: float of a huge Decimal/int can raise it.
        logger.warning(
            "%s value %r is not a valid number; using default of %s",
            label, value, fallback,
        )
        return _clamp_threshold(fallback, fallback, label)
    if numeric != numeric or numeric in (float('inf'), float('-inf')):
        # NaN fails every comparison below, so it must be rejected explicitly.
        logger.warning("%s value %r is not finite; using default of %s", label, value, fallback)
        return _clamp_threshold(fallback, fallback, label)
    if numeric < MIN_THRESHOLD_PERCENT or numeric > MAX_THRESHOLD_PERCENT:
        clamped = min(MAX_THRESHOLD_PERCENT, max(MIN_THRESHOLD_PERCENT, numeric))
        logger.warning(
            "%s value %s is outside the supported range %s-%s; using %s",
            label, numeric, MIN_THRESHOLD_PERCENT, MAX_THRESHOLD_PERCENT, clamped,
        )
        return clamped
    return numeric


def _clamp_threshold(value, fallback, label):
    """Clamp ``value`` into the threshold range, falling back when out of range.

    Args:
        value: Candidate percentage.
        fallback: Value to use when ``value`` is itself out of range.
        label: Setting name, used only for the WARNING message.

    Returns:
        A float within ``[MIN_THRESHOLD_PERCENT, MAX_THRESHOLD_PERCENT]``.
    """
    if MIN_THRESHOLD_PERCENT <= value <= MAX_THRESHOLD_PERCENT:
        return float(value)
    clamped_fallback = min(MAX_THRESHOLD_PERCENT, max(MIN_THRESHOLD_PERCENT, fallback))
    logger.warning(
        "%s default of %s is itself outside the supported range %s-%s; using %s",
        label, value, MIN_THRESHOLD_PERCENT, MAX_THRESHOLD_PERCENT, clamped_fallback,
    )
    return clamped_fallback


def log_config_default_divergences(cfg, expectations=None):
    """Warn about config keys whose configured value differs from its constant default.

    ADD-007 removed the *unit* mismatch, but it cannot detect a value that is the
    right unit and the wrong magnitude relative to the constant — the constant is
    not consulted once the key is present. A divergent value is legitimate for a
    hand-tuned setting, so it is never rewritten; the user is only told, per
    ADD-007's own argument that a change the user never sees is a change they
    cannot correct.

    Args:
        cfg: Loaded config mapping.
        expectations: Mapping of key -> constant default. Defaults to
            :data:`CONFIG_DEFAULT_ALIGNMENT`.

    Returns:
        List of human-readable descriptions of every divergence found.
    """
    expected_defaults = CONFIG_DEFAULT_ALIGNMENT if expectations is None else expectations
    divergences = []
    for key, default in expected_defaults.items():
        if key not in cfg:
            continue
        # quiet=True: this pass reports *divergences* only. Value-coercion
        # warnings are the single read path's job, so an unparseable value yields
        # one WARNING naming the key, not two that look like separate problems.
        configured = normalize_positive_int(cfg.get(key), default, name=key, quiet=True)
        if configured != default:
            description = (
                f"{key}: configured value {configured} differs from the code default of "
                f"{default}; the configured value is used"
            )
            logger.warning("Config value divergence: %s", description)
            divergences.append(description)
    return divergences


def log_timeout_truncations(cfg, maxima=None):
    """Report configured timeout values that exceed the supported maximum.

    The GUI spin buttons are bounded by :data:`TIMEOUT_MAX_SECONDS`, so a larger
    configured value cannot be represented in the UI and would otherwise be
    silently rewritten to the bound on the next save — the same class of
    unrecoverable, invisible value loss ADD-007 rejects. The value is clamped (see
    :func:`normalize_positive_int`) and this note names the key, the configured
    value and the applied maximum so the user can correct it.

    Args:
        cfg: Loaded config mapping.
        maxima: Mapping of timeout key -> supported upper bound in seconds.
            Defaults to :data:`TIMEOUT_MAX_SECONDS`.

    Returns:
        List of human-readable descriptions of every clamped timeout.
    """
    expected_maxima = TIMEOUT_MAX_SECONDS if maxima is None else maxima
    notes = []
    for key, maximum in expected_maxima.items():
        if key not in cfg:
            continue
        raw = cfg.get(key)
        try:
            # bool is a user error, not a magnitude: leave it to the read path.
            if isinstance(raw, bool):
                continue
            exceeds = int(raw) > maximum
        except (TypeError, ValueError, OverflowError):
            # Unparseable or non-finite: the read path already warns about the
            # coercion; this pass reports magnitude truncation only.
            continue
        if not exceeds:
            continue
        description = (
            f"{key}: configured value {raw} s exceeds the supported maximum of "
            f"{maximum} s; the value is clamped and saved back as {maximum} s"
        )
        logger.warning("Config timeout truncation: %s", description)
        notes.append(description)
    return notes


# ============================================================================
# System Directories (Safety)
# ============================================================================
SYSTEM_PROTECTED_DIRS = ('/', '/etc', '/sys', '/dev', '/proc', '/root')

# ============================================================================
# Detection Result Fields
# ============================================================================
RESULT_FIELD_FILE = 'file'
RESULT_FIELD_MEDIA_TYPE = 'media_type'
RESULT_FIELD_MODEL = 'model_name'
RESULT_FIELD_THRESHOLD = 'threshold_percent'
RESULT_FIELD_CONFIDENCE = 'confidence_percent'
RESULT_FIELD_NUDITY = 'nudity_detected'
RESULT_FIELD_CLASSES = 'detected_classes'
RESULT_FIELD_THUMBNAIL = 'thumbnail'
RESULT_FIELD_DATE = 'date_classified'

# ============================================================================
# GUI Styles
# ============================================================================
TREEVIEW_Heading_BACKGROUND = 'accent'
TREEVIEW_Heading_FOREGROUND = 'panel'
TREEVIEW_SELECTED_BACKGROUND = 'accent'
TREEVIEW_SELECTED_FOREGROUND = 'panel'

# ============================================================================
# Scan Progress
# ============================================================================
SCAN_PROGRESS_UPDATE_INTERVAL = 100  # Flush UI results every N files processed

"""
Centralized constants for the Nudity Detector application.
Provides single source of truth for configuration values, avoiding magic numbers.
"""
import json
import os

# ============================================================================
# Media Type Configuration
# ============================================================================
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'})
VIDEO_EXTENSIONS = frozenset({'.mp4', '.avi', '.mkv', '.mov', '.vob', '.wmv', '.flv', '.3gp', '.webm'})
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

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

NUDITY_CLASSES_STRICT = frozenset(NUDITY_CLASSES | NUDITY_CLASSES_EXTENDED)

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


# Backward-compatible module-level aliases (resolved at import time)
HELLOZ_NSFW_URL = get_helloz_nsfw_url()
HELLOZ_NSFW_CONNECTION_CHECK_URL = get_helloz_nsfw_connection_check_url()

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

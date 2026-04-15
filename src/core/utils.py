"""Nudity detection utilities and coordinator.

This module provides:
- High-level detection orchestration
- Thread-safe batch processing with worker pools
- File system operations (deletion, opening files)
- Integration layer between detection models and storage

Thread Safety:
- nudity_report list is protected by report_lock
- Worker threads are non-daemon to ensure proper cleanup
- All thread operations have explicit join() with timeout
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from queue import Queue
from threading import Lock, Thread
from typing import Optional, Tuple

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

from . import constants
from .models import ReportEntry, SessionState, ScanConfig
from ..processing.media_processor import detect_media_type, is_supported_file, ThumbnailGenerator
from ..reporting.report_manager import ReportManager


# ============================================================================
# Global State Management
# ============================================================================
nudity_report = []
report_lock = Lock()


# ============================================================================
# Public API (maintained for compatibility)
# ============================================================================
DEFAULT_REPORT_DIR = constants.DEFAULT_REPORT_DIR


def normalize_threshold(threshold_value) -> float:
    """Normalize threshold to 0-1 range.

    Args:
        threshold_value: Threshold as percentage (>1) or decimal (0-1)

    Returns:
        Normalized threshold in range [0, 1]
    """
    if threshold_value is None:
        return 0.6

    threshold = float(threshold_value)
    if threshold > 1:
        threshold /= 100.0
    return max(0.0, min(threshold, 1.0))


def threshold_to_percent(threshold_value) -> float:
    """Convert normalized threshold to percentage."""
    return round(normalize_threshold(threshold_value) * 100, 2)


def make_scan_config(source_folder='', model_name='nudenet', threshold_percent=60, theme_mode='system') -> dict:
    """Create scan config dictionary."""
    config = ScanConfig(
        source_folder=source_folder,
        model_name=model_name,
        threshold_percent=threshold_to_percent(threshold_percent),
        theme_mode=theme_mode,
    )
    return config.to_dict()


def create_session_state(scan_config=None, results=None) -> dict:
    """Create session state dictionary."""
    config = ScanConfig.from_dict(scan_config) if isinstance(scan_config, dict) else (scan_config or ScanConfig())
    result_entries = [ReportEntry.from_dict(r) if isinstance(r, dict) else r for r in (results or [])]
    state = SessionState(scan_config=config, results=result_entries)
    return state.to_dict()


def reset_nudity_report() -> None:
    """Clear the global nudity report list."""
    with report_lock:
        nudity_report.clear()


def replace_nudity_report(entries: list) -> None:
    """Replace nudity report contents."""
    with report_lock:
        nudity_report.clear()
        nudity_report.extend(entries)


def get_detected_results(report_data=None) -> list:
    """Get results where nudity was detected."""
    data = report_data if report_data is not None else nudity_report
    return [entry for entry in data if (entry.get('nudity_detected') if isinstance(entry, dict) else entry.nudity_detected)]


# ============================================================================
# Report Management Delegation
# ============================================================================
def get_report_path(report_dir=DEFAULT_REPORT_DIR) -> str:
    """Get standard report file path."""
    return ReportManager.get_report_path(report_dir)


def get_session_path(report_file_path: str) -> str:
    """Get session file path for report file."""
    return ReportManager.get_session_path(report_file_path)


def load_report_entries(file_path: str) -> list:
    """Load report entries from file."""
    entries = ReportManager.load_entries(file_path)
    return [e.to_dict() for e in entries]


def save_nudity_report(report_data, file_path, session_state=None) -> None:
    """Save report to Excel with session."""
    if session_state is None:
        session_state = create_session_state(results=get_detected_results(report_data))

    # Convert to ReportEntry objects
    entries = []
    for item in report_data:
        if isinstance(item, dict):
            entries.append(ReportEntry.from_dict(item))
        else:
            entries.append(item)

    # Save report
    ReportManager.save_entries(entries, file_path)

    # Save session
    session_obj = SessionState.from_dict(session_state) if isinstance(session_state, dict) else session_state
    ReportManager.save_session(session_obj, file_path)


def load_scan_session(file_path: str) -> dict:
    """Load session from file."""
    session = ReportManager.load_session(file_path)
    return session.to_dict()


def load_existing_report(file_path: str) -> set:
    """Get set of files already in report."""
    entries = ReportManager.load_entries(file_path)
    return {e.file for e in entries}


# ============================================================================
# File Operations
# ============================================================================
def validate_report_dir(report_dir: str) -> Tuple[bool, str]:
    """Validate report directory is writable."""
    return ReportManager.validate_report_dir(report_dir)


def generate_image_thumbnail(file_path: str, size: Tuple[int, int] = constants.THUMBNAIL_SIZE_REPORT) -> Optional[str]:
    """Generate thumbnail from image file."""
    return ThumbnailGenerator.generate_from_image(file_path, size)


def generate_video_thumbnail(file_path: str, size: Tuple[int, int] = constants.THUMBNAIL_SIZE_REPORT) -> Optional[str]:
    """Generate thumbnail from video file."""
    return ThumbnailGenerator.generate_from_video(file_path, size)


def get_thumbnail(file_path: str, media_type: Optional[str] = None) -> Optional[str]:
    """Get thumbnail for media file."""
    return ThumbnailGenerator.generate(file_path, media_type)


def detect_media_type_utils(file_path: str) -> str:
    """Detect media type from file extension."""
    return detect_media_type(file_path)


def detect_with_timeout(detector, file_path: str, timeout_seconds: int = constants.DETECT_TIMEOUT) -> Optional[list]:
    """Wrap detection with timeout.

    Args:
        detector: Detection instance (NudeNet)
        file_path: Path to file
        timeout_seconds: Timeout in seconds

    Returns:
        Detection results

    Raises:
        TimeoutError: If detection exceeds timeout
    """
    result_container = [None]
    exception_container = [None]

    def run_detection():
        try:
            result_container[0] = detector.detect(file_path)
        except Exception as e:
            exception_container[0] = e

    thread = Thread(target=run_detection, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        logging.error('Detection timeout for file: %s after %d seconds', file_path, timeout_seconds)
        raise TimeoutError(f'Detection timeout for {file_path}')

    if exception_container[0]:
        raise exception_container[0]

    return result_container[0]


def open_file(file_path: str) -> Tuple[bool, str]:
    """Open file directly (not parent directory).

    Args:
        file_path: Path to file to open

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    if not os.path.exists(file_path):
        error_msg = f'File does not exist: {file_path}'
        logging.warning(error_msg)
        return False, error_msg

    try:
        if sys.platform == 'win32':
            os.startfile(file_path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', file_path], check=False)
        else:
            subprocess.run(['xdg-open', file_path], check=False)
        return True, ''
    except Exception as error:
        error_msg = f'Could not open file {file_path}: {error}'
        logging.error(error_msg)
        return False, error_msg


def delete_file_safely(file_path: str) -> Tuple[bool, str]:
    """Safely delete file using trash first.

    Args:
        file_path: Path to file to delete

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not os.path.exists(file_path):
        return False, 'File does not exist.'

    try:
        if send2trash is not None:
            send2trash(file_path)
            return True, 'Moved to trash.'

        import shutil
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        return True, 'Deleted permanently because trash support is unavailable.'
    except Exception as error:
        logging.error('Could not delete %s: %s', file_path, error)
        return False, str(error)


def open_file_location(file_path: str) -> Tuple[bool, str]:
    """Open file location (parent folder).

    Args:
        file_path: Path to file or folder

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    target_path = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
    if not target_path:
        target_path = '.'

    try:
        if sys.platform == 'win32':
            os.startfile(target_path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', target_path], check=False)
        else:
            subprocess.run(['xdg-open', target_path], check=False)
        return True, ''
    except Exception as error:
        logging.error('Could not open path %s: %s', target_path, error)
        return False, str(error)


# ============================================================================
# File Classification & Processing
# ============================================================================
def process_file(file_path: str, classify_image, classify_video) -> None:
    """Process single file with appropriate classification function."""
    if not is_supported_file(file_path):
        logging.info('Skipping unsupported file: %s', file_path)
        return

    media_type = detect_media_type(file_path)
    if media_type == constants.MEDIA_TYPE_IMAGE:
        classify_image(file_path)
    elif media_type == constants.MEDIA_TYPE_VIDEO:
        classify_video(file_path)


def classify_files_in_folder(
    folder_path: str,
    classify_image,
    classify_video,
    worker_count: int = constants.WORKER_THREAD_COUNT,
    worker_timeout: int = constants.WORKER_THREAD_TIMEOUT,
) -> None:
    """Classify all supported files in folder using worker threads.

    Workers are started before directory traversal so they begin processing
    immediately as files are discovered (streaming discovery).

    Args:
        folder_path: Root folder to scan
        classify_image: Image classification callable
        classify_video: Video classification callable
        worker_count: Number of concurrent worker threads
        worker_timeout: Seconds to wait for each worker to finish
    """
    logging.debug('Starting classification in folder: %s', folder_path)
    file_queue = Queue()
    os.makedirs(DEFAULT_REPORT_DIR, exist_ok=True)

    _SENTINEL = object()

    def _worker():
        while True:
            item = file_queue.get()
            if item is _SENTINEL:
                file_queue.task_done()
                break
            try:
                process_file(item, classify_image, classify_video)
            except Exception as e:
                logging.error('Error processing file %s: %s', item, e)
            finally:
                file_queue.task_done()

    # Start workers before queuing files so they can begin immediately.
    workers = []
    for _ in range(worker_count):
        worker = Thread(target=_worker, daemon=False)
        worker.start()
        workers.append(worker)

    try:
        # Stream files into the queue as they are discovered.
        for root, _, files in os.walk(folder_path):
            for file_name in files:
                file_queue.put(os.path.join(root, file_name))
    finally:
        # Send one sentinel per worker to signal completion, even if
        # directory traversal fails before all files are queued.
        for _ in workers:
            file_queue.put(_SENTINEL)

    # Block until all queued items (including sentinels) have been processed.
    file_queue.join()

    # Workers have exited their loops; collect threads.
    for worker in workers:
        worker.join()


# ============================================================================
# Detection Result Handling
# ============================================================================
def handle_results(
    file_path: str,
    nudity_detected: bool,
    raw_result,
    confidence_score: float = 0.0,
    media_type: Optional[str] = None,
    model_name: str = '',
    threshold_percent: float = constants.DEFAULT_THRESHOLD_PERCENT,
    report_dir: str = DEFAULT_REPORT_DIR,
) -> dict:
    """Handle detection results: create entry, generate thumbnail, and cache.

    Args:
        file_path: Original file path
        nudity_detected: Whether nudity was detected
        raw_result: Raw detection result
        confidence_score: Confidence score (0-1)
        media_type: Media type (auto-detected if None)
        model_name: Detection model name
        threshold_percent: Detection threshold percentage
        report_dir: Report directory path

    Returns:
        Report entry dictionary
    """
    # Generate thumbnail for detected items
    thumbnail = ''
    if nudity_detected:
        media_type = media_type or detect_media_type(file_path)
        thumbnail = ThumbnailGenerator.generate(file_path, media_type, constants.THUMBNAIL_SIZE_REPORT) or ''

    # Ensure report directory exists
    if nudity_detected:
        os.makedirs(report_dir, exist_ok=True)

    # Create and cache entry
    with report_lock:
        entry_data = {
            constants.RESULT_FIELD_FILE: file_path,
            constants.RESULT_FIELD_MEDIA_TYPE: media_type or detect_media_type(file_path),
            constants.RESULT_FIELD_MODEL: model_name,
            constants.RESULT_FIELD_THRESHOLD: threshold_to_percent(threshold_percent),
            constants.RESULT_FIELD_CONFIDENCE: round(max(0.0, min(float(confidence_score), 1.0)) * 100, 2),
            constants.RESULT_FIELD_NUDITY: bool(nudity_detected),
            constants.RESULT_FIELD_CLASSES: json.dumps(raw_result, ensure_ascii=False) if not isinstance(raw_result, str) else raw_result,
            constants.RESULT_FIELD_THUMBNAIL: thumbnail,
            constants.RESULT_FIELD_DATE: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        nudity_report.append(entry_data)

        # Periodically save report
        if len(nudity_report) % 500 == 0:
            entries = [ReportEntry.from_dict(e) for e in nudity_report]
            ReportManager.save_entries(entries, get_report_path(report_dir))

        return entry_data

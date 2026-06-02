import logging
import os
import time

import requests

from ..core import constants
from ..core.models import ReportEntry
from ..core.scan_session import ScanSession
from ..core.utils import (
    classify_files_in_folder,
    create_session_state,
    get_detected_results,
    get_report_path,
    handle_results,
    load_existing_report,
    make_scan_config,
    normalize_threshold,
    save_nudity_report,
)
from ..processing.media_processor import FrameExtractor, detect_media_type

logger = logging.getLogger(__name__)


def _post_with_retry(url, files, timeout,
                     retries=constants.HELLOZ_NSFW_MAX_RETRIES,
                     backoff=constants.HELLOZ_NSFW_RETRY_BACKOFF):
    """POST with exponential backoff; raises on retry exhaustion.

    Returns the first response whose status code is below 500.
    Retries on 5xx responses and on RequestException (network errors).
    Rewinds any file-like objects in `files` before each attempt so that
    repeated tries always send the full body.
    """
    last_exc = None
    for attempt in range(retries):
        # Rewind file handles before each attempt so retries send the full body.
        for _key, value in files.items():
            # Support plain file objects and (filename, fileobj[, content_type]) tuples.
            obj = value[1] if isinstance(value, tuple) else value
            if hasattr(obj, 'seek'):
                obj.seek(0)
        try:
            response = requests.post(url, files=files, timeout=timeout)
            if response.status_code < 500:
                return response
            logger.warning(
                'HTTP %s on attempt %d/%d, retrying\u2026',
                response.status_code, attempt + 1, retries,
            )
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            logger.warning(
                'Request failed on attempt %d/%d: %s',
                attempt + 1, retries, exc,
            )
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last_exc or RuntimeError(
        f'HTTP service unavailable after {retries} retries'
    )


def _record_error(file_path, error, model_name, threshold_percent, session):
    """Append an ERROR sentinel entry to *session* for a failed file."""
    media_type = detect_media_type(file_path)
    entry = ReportEntry(
        file=file_path,
        media_type=media_type,
        model_name=model_name,
        threshold_percent=threshold_percent,
        confidence_percent=0.0,
        nudity_detected=False,
        detected_classes=f'ERROR: {error}',
        thumbnail='',
        date_classified='',
    )
    session.add_result(entry)


def prompt_threshold_percent(default_percent=constants.DEFAULT_THRESHOLD_PERCENT):
    raw_value = input(f'Enter detection threshold percentage [{default_percent}]: ').strip()
    if not raw_value:
        return default_percent

    try:
        return max(constants.MIN_THRESHOLD_PERCENT, min(float(raw_value), constants.MAX_THRESHOLD_PERCENT))
    except ValueError:
        logger.warning('Invalid threshold value. Using default %.1f%%', default_percent)
        return default_percent


def extract_frames(file_path, frame_rate=constants.VIDEO_FRAME_RATE):
    """Legacy wrapper for backward compatibility."""
    extractor = FrameExtractor(frame_rate=frame_rate, temp_prefix=constants.FRAME_TEMP_DIR_PREFIX_CLI_HELLOZ_NSFW)
    return extractor.extract(file_path)


def make_classify_image(existing_files, threshold_value, threshold_percent, session):
    """Factory: return a classify_image function closed over the given parameters."""

    def classify_image(file_path):
        if file_path in existing_files:
            logger.info('Skipping already scanned file: %s', file_path)
            return

        try:
            with open(file_path, 'rb') as image_file:
                response = _post_with_retry(constants.get_helloz_nsfw_url(), files={'file': image_file}, timeout=constants.HELLOZ_NSFW_REQUEST_TIMEOUT)

            if response.status_code != 200:
                raise RuntimeError(f'Unexpected HTTP {response.status_code} for {file_path}')

            result = response.json()
            confidence_score = float(result.get('data', {}).get('nsfw', 0.0))
            handle_results(
                file_path,
                confidence_score >= threshold_value,
                result,
                session=session,
                confidence_score=confidence_score,
                media_type=constants.MEDIA_TYPE_IMAGE,
                model_name=constants.MODEL_HELLOZ_NSFW,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logger.error('Error classifying image %s: %s', file_path, error)
            _record_error(file_path, error, constants.MODEL_HELLOZ_NSFW, threshold_percent, session)

    return classify_image


def make_classify_video(existing_files, threshold_value, threshold_percent, session):
    """Factory: return a classify_video function closed over the given parameters."""

    def classify_video(file_path):
        if file_path in existing_files:
            logger.info('Skipping already scanned file: %s', file_path)
            return

        extractor = FrameExtractor(
            frame_rate=constants.VIDEO_FRAME_RATE,
            temp_prefix=constants.FRAME_TEMP_DIR_PREFIX_CLI_HELLOZ_NSFW,
        )
        frame_error_count = 0
        upload_url = constants.get_helloz_nsfw_url()
        try:
            frame_scores = []
            max_confidence = 0.0

            for frame_path in extractor.iter_frames(file_path):
                try:
                    with open(frame_path, 'rb') as image_file:
                        response = _post_with_retry(upload_url, files={'file': image_file}, timeout=constants.HELLOZ_NSFW_REQUEST_TIMEOUT)
                    if response.status_code != 200:
                        logger.error('Failed to classify frame %s. HTTP status: %s', frame_path, response.status_code)
                        frame_error_count += 1
                        continue

                    result = response.json()
                    confidence_score = float(result.get('data', {}).get('nsfw', 0.0))
                    max_confidence = max(max_confidence, confidence_score)
                    frame_scores.append({'frame': os.path.basename(frame_path), 'unsafe_score': confidence_score})
                    if max_confidence >= threshold_value:
                        break
                except Exception as frame_error:
                    logger.warning('Failed to classify frame %s: %s', frame_path, frame_error)
                    frame_error_count += 1

            if frame_error_count > 0 and not frame_scores:
                raise RuntimeError(f'All {frame_error_count} frame(s) failed classification')

            handle_results(
                file_path,
                max_confidence >= threshold_value,
                frame_scores,
                session=session,
                confidence_score=max_confidence,
                media_type=constants.MEDIA_TYPE_VIDEO,
                model_name=constants.MODEL_HELLOZ_NSFW,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logger.error('Error classifying video %s: %s', file_path, error)
            _record_error(file_path, error, constants.MODEL_HELLOZ_NSFW, threshold_percent, session)
        finally:
            extractor.cleanup()

    return classify_video


def main():
    report_path = get_report_path()
    existing_files = load_existing_report(report_path)
    session = ScanSession()

    folder_to_classify = input('Enter the path to the folder: ').strip()
    threshold_percent = prompt_threshold_percent()
    threshold_value = normalize_threshold(threshold_percent)
    scan_config = make_scan_config(
        source_folder=folder_to_classify,
        model_name=constants.MODEL_HELLOZ_NSFW,
        threshold_percent=threshold_percent,
        theme_mode=constants.THEME_SYSTEM,
    )

    classify_image = make_classify_image(existing_files, threshold_value, threshold_percent, session)
    classify_video = make_classify_video(existing_files, threshold_value, threshold_percent, session)

    logger.debug('User input folder: %s', folder_to_classify)
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)

    all_results = session.get_results()
    error_count = sum(
        1 for entry in all_results
        if isinstance(entry.detected_classes, str)
        and entry.detected_classes.startswith('ERROR:')
    )
    if error_count:
        logger.warning(
            '%d file(s) could not be classified due to service errors '
            '\u2014 check report for ERROR entries.',
            error_count,
        )

    session_state = create_session_state(scan_config=scan_config, results=get_detected_results(all_results))
    save_nudity_report(all_results, report_path, session_state=session_state)
    logger.info('Report saved to %s', report_path)


if __name__ == '__main__':
    main()

import logging
import os

import requests

from ..core import constants
from ..core.utils import (
    classify_files_in_folder,
    create_session_state,
    get_detected_results,
    get_report_path,
    handle_results,
    load_existing_report,
    make_scan_config,
    nudity_report,
    normalize_threshold,
    reset_nudity_report,
    save_nudity_report,
)
from ..processing.media_processor import FrameExtractor

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def prompt_threshold_percent(default_percent=constants.DEFAULT_THRESHOLD_PERCENT):
    raw_value = input(f'Enter detection threshold percentage [{default_percent}]: ').strip()
    if not raw_value:
        return default_percent

    try:
        return max(constants.MIN_THRESHOLD_PERCENT, min(float(raw_value), constants.MAX_THRESHOLD_PERCENT))
    except ValueError:
        logging.warning('Invalid threshold value. Using default %.1f%%', default_percent)
        return default_percent


def extract_frames(file_path, frame_rate=constants.VIDEO_FRAME_RATE):
    """Legacy wrapper for backward compatibility."""
    extractor = FrameExtractor(frame_rate=frame_rate, temp_prefix=constants.FRAME_TEMP_DIR_PREFIX_CLI_DEEPSTACK)
    return extractor.extract(file_path)


def main():
    report_path = get_report_path()
    existing_files = load_existing_report(report_path)

    folder_to_classify = input('Enter the path to the folder: ').strip()
    threshold_percent = prompt_threshold_percent()
    threshold_value = normalize_threshold(threshold_percent)
    scan_config = make_scan_config(
        source_folder=folder_to_classify,
        model_name=constants.MODEL_DEEPSTACK,
        threshold_percent=threshold_percent,
        theme_mode=constants.THEME_SYSTEM,
    )

    def classify_image(file_path):
        if file_path in existing_files:
            logging.info('Skipping already scanned file: %s', file_path)
            return

        try:
            with open(file_path, 'rb') as image_file:
                response = requests.post(constants.DEEPSTACK_URL, files={'image': image_file}, timeout=constants.DEEPSTACK_REQUEST_TIMEOUT)

            if response.status_code != 200:
                logging.error('Failed to classify image %s. HTTP status: %s', file_path, response.status_code)
                return

            result = response.json()
            confidence_score = 0.0
            predictions = result.get('predictions', [])
            for pred in predictions:
                if pred.get('label') == 'nsfw':
                    confidence_score = float(pred.get('confidence', 0.0))
                    break
            handle_results(
                file_path,
                confidence_score >= threshold_value,
                result,
                confidence_score=confidence_score,
                media_type=constants.MEDIA_TYPE_IMAGE,
                model_name=constants.MODEL_DEEPSTACK,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logging.error('Error classifying image %s: %s', file_path, error)

    def classify_video(file_path):
        if file_path in existing_files:
            logging.info('Skipping already scanned file: %s', file_path)
            return

        temp_dir = None
        try:
            extractor = FrameExtractor(
                frame_rate=constants.VIDEO_FRAME_RATE,
                temp_prefix=constants.FRAME_TEMP_DIR_PREFIX_CLI_DEEPSTACK,
            )
            temp_dir, frame_paths = extractor.extract(file_path)
            frame_scores = []
            max_confidence = 0.0

            for frame_path in frame_paths:
                with open(frame_path, 'rb') as image_file:
                    response = requests.post(constants.DEEPSTACK_URL, files={'image': image_file}, timeout=constants.DEEPSTACK_REQUEST_TIMEOUT)
                if response.status_code != 200:
                    logging.error('Failed to classify frame %s. HTTP status: %s', frame_path, response.status_code)
                    continue

                result = response.json()
                confidence_score = 0.0
                predictions = result.get('predictions', [])
                for pred in predictions:
                    if pred.get('label') == 'nsfw':
                        confidence_score = float(pred.get('confidence', 0.0))
                        break
                max_confidence = max(max_confidence, confidence_score)
                frame_scores.append({'frame': os.path.basename(frame_path), 'unsafe_score': confidence_score})
                if max_confidence >= threshold_value:
                    break

            handle_results(
                file_path,
                max_confidence >= threshold_value,
                frame_scores,
                confidence_score=max_confidence,
                media_type=constants.MEDIA_TYPE_VIDEO,
                model_name=constants.MODEL_DEEPSTACK,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logging.error('Error classifying video %s: %s', file_path, error)
        finally:
            if temp_dir:
                extractor.cleanup()

    logging.debug('User input folder: %s', folder_to_classify)
    reset_nudity_report()
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)

    session_state = create_session_state(scan_config=scan_config, results=get_detected_results(nudity_report))
    save_nudity_report(nudity_report, report_path, session_state=session_state)
    logging.info('Report saved to %s', report_path)


if __name__ == '__main__':
    main()

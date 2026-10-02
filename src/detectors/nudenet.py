import logging
import os

from nudenet import NudeDetector

from ..core import constants
from ..core.scan_session import ScanSession
from ..core.utils import (
    classify_files_in_folder,
    create_session_state,
    get_detected_results,
    get_nudenet_confidence,
    get_report_path,
    handle_results,
    load_existing_report,
    make_scan_config,
    normalize_threshold,
    prompt_threshold_percent,
    record_error,
    save_nudity_report,
    simplify_nudenet_results,
)
from ..processing.media_processor import FrameExtractor

logger = logging.getLogger(__name__)


def main():
    report_path = get_report_path()
    existing_files = load_existing_report(report_path)
    detector = NudeDetector()
    session = ScanSession()

    folder_to_classify = input('Enter the path to the folder: ').strip()
    threshold_percent = prompt_threshold_percent()
    threshold_value = normalize_threshold(threshold_percent)
    scan_config = make_scan_config(
        source_folder=folder_to_classify,
        model_name=constants.MODEL_NUDENET,
        threshold_percent=threshold_percent,
        theme_mode=constants.THEME_SYSTEM,
    )

    def classify_image(file_path):
        if file_path in existing_files:
            logger.info('Skipping already scanned file: %s', file_path)
            return

        try:
            detection_result = detector.detect(file_path)
            confidence_score = get_nudenet_confidence(detection_result)
            nudity_detected = confidence_score >= threshold_value
            simplified_results = simplify_nudenet_results(detection_result)
            handle_results(
                file_path,
                nudity_detected,
                simplified_results,
                session=session,
                confidence_score=confidence_score,
                media_type=constants.MEDIA_TYPE_IMAGE,
                model_name=constants.MODEL_NUDENET,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logger.error('Error classifying image %s: %s', file_path, error)
            record_error(file_path, error, threshold_percent, session, model_name=constants.MODEL_NUDENET)

    def classify_video(file_path):
        if file_path in existing_files:
            logger.info('Skipping already scanned file: %s', file_path)
            return

        extractor = FrameExtractor(
            frame_rate=constants.VIDEO_FRAME_RATE,
            temp_prefix=constants.FRAME_TEMP_DIR_PREFIX_CLI_NUDENET,
        )
        try:
            detection_results = []
            max_confidence = 0.0

            for frame_path in extractor.iter_frames(file_path):
                frame_result = detector.detect(frame_path)
                simplified_frame = simplify_nudenet_results(frame_result)
                detection_results.append({'frame': os.path.basename(frame_path), 'detections': simplified_frame})
                max_confidence = max(max_confidence, get_nudenet_confidence(frame_result))
                if max_confidence >= threshold_value:
                    break

            handle_results(
                file_path,
                max_confidence >= threshold_value,
                detection_results,
                session=session,
                confidence_score=max_confidence,
                media_type=constants.MEDIA_TYPE_VIDEO,
                model_name=constants.MODEL_NUDENET,
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logger.error('Error classifying video %s: %s', file_path, error)
            record_error(file_path, error, threshold_percent, session, model_name=constants.MODEL_NUDENET)
        finally:
            extractor.cleanup()

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
            '%d file(s) could not be classified — check report for ERROR entries.',
            error_count,
        )
    session_state = create_session_state(scan_config=scan_config, results=get_detected_results(all_results))
    save_nudity_report(all_results, report_path, session_state=session_state)
    logger.info('Report saved to %s', report_path)


if __name__ == '__main__':
    main()

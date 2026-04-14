import json
import logging
import os
import tempfile

import cv2
from nudenet import NudeDetector

import logging

from nudity_detector_utils import (
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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

NUDITY_CLASSES = {
    'EXPOSED_ANUS',
    'EXPOSED_BREAST_F',
    'EXPOSED_GENITALIA_F',
    'EXPOSED_GENITALIA_M',
    'EXPOSED_BUTTOCKS',
}


def prompt_threshold_percent(default_percent=60.0):
    raw_value = input(f'Enter detection threshold percentage [{default_percent}]: ').strip()
    if not raw_value:
        return default_percent

    try:
        return max(0.0, min(float(raw_value), 100.0))
    except ValueError:
        logging.warning('Invalid threshold value. Using default %.1f%%', default_percent)
        return default_percent


def simplify_nudenet_results(detection_result):
    return [
        {'class': record.get('label', ''), 'score': record.get('score', 0.0)}
        for record in detection_result
    ]


def get_nudenet_confidence(detection_result):
    class_scores = [
        record.get('score', 0.0)
        for record in detection_result
        if record.get('label') in NUDITY_CLASSES
    ]
    return max(class_scores, default=0.0)


def extract_frames(file_path, frame_rate=5):
    cap = cv2.VideoCapture(file_path)
    frame_paths = []
    frame_count = 0
    temp_dir = tempfile.mkdtemp(prefix='nudenet_frames_')

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_rate == 0:
                frame_path = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)
            frame_count += 1
    finally:
        cap.release()

    return temp_dir, frame_paths


def cleanup_frames(temp_dir):
    if os.path.isdir(temp_dir):
        for file_name in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(temp_dir)


if __name__ == '__main__':
    report_path = get_report_path()
    existing_files = load_existing_report(report_path)
    detector = NudeDetector()

    folder_to_classify = input('Enter the path to the folder: ').strip()
    threshold_percent = prompt_threshold_percent()
    threshold_value = normalize_threshold(threshold_percent)
    scan_config = make_scan_config(
        source_folder=folder_to_classify,
        model_name='nudenet',
        threshold_percent=threshold_percent,
        theme_mode='system',
    )

    def classify_image(file_path):
        if file_path in existing_files:
            logging.info('Skipping already scanned file: %s', file_path)
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
                confidence_score=confidence_score,
                media_type='image',
                model_name='nudenet',
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
            temp_dir, frame_paths = extract_frames(file_path, frame_rate=5)
            detection_results = []
            max_confidence = 0.0

            for frame_path in frame_paths:
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
                confidence_score=max_confidence,
                media_type='video',
                model_name='nudenet',
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logging.error('Error classifying video %s: %s', file_path, error)
        finally:
            if temp_dir:
                cleanup_frames(temp_dir)

    logging.debug('User input folder: %s', folder_to_classify)
    reset_nudity_report()
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)

    session_state = create_session_state(scan_config=scan_config, results=get_detected_results(nudity_report))
    save_nudity_report(nudity_report, report_path, session_state=session_state)
    logging.info('Report saved to %s', report_path)

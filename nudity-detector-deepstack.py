import logging
import os
import shutil
import tempfile

import cv2
import requests

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

DEEPSTACK_URL = 'http://localhost:5000/v1/vision/nsfw'


def prompt_threshold_percent(default_percent=60.0):
    raw_value = input(f'Enter detection threshold percentage [{default_percent}]: ').strip()
    if not raw_value:
        return default_percent

    try:
        return max(0.0, min(float(raw_value), 100.0))
    except ValueError:
        logging.warning('Invalid threshold value. Using default %.1f%%', default_percent)
        return default_percent


def extract_frames(file_path, frame_rate=5):
    cap = cv2.VideoCapture(file_path)
    frame_paths = []
    frame_count = 0
    temp_dir = tempfile.mkdtemp(prefix='deepstack_frames_')

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


if __name__ == '__main__':
    report_path = get_report_path()
    existing_files = load_existing_report(report_path)

    folder_to_classify = input('Enter the path to the folder: ').strip()
    threshold_percent = prompt_threshold_percent()
    threshold_value = normalize_threshold(threshold_percent)
    scan_config = make_scan_config(
        source_folder=folder_to_classify,
        model_name='deepstack',
        threshold_percent=threshold_percent,
        theme_mode='system',
    )

    def classify_image(file_path):
        if file_path in existing_files:
            logging.info('Skipping already scanned file: %s', file_path)
            return

        try:
            with open(file_path, 'rb') as image_file:
                response = requests.post(DEEPSTACK_URL, files={'image': image_file}, timeout=30)

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
                media_type='image',
                model_name='deepstack',
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
            frame_scores = []
            max_confidence = 0.0

            for frame_path in frame_paths:
                with open(frame_path, 'rb') as image_file:
                    response = requests.post(DEEPSTACK_URL, files={'image': image_file}, timeout=30)
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
                media_type='video',
                model_name='deepstack',
                threshold_percent=threshold_percent,
            )
        except Exception as error:
            logging.error('Error classifying video %s: %s', file_path, error)
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    logging.debug('User input folder: %s', folder_to_classify)
    reset_nudity_report()
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)

    session_state = create_session_state(scan_config=scan_config, results=get_detected_results(nudity_report))
    save_nudity_report(nudity_report, report_path, session_state=session_state)
    logging.info('Report saved to %s', report_path)

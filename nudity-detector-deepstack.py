from datetime import datetime
import os
import shutil
import logging
import requests
import cv2
import json
from nudity_detector_utils import classify_files_in_folder, save_nudity_report, nudity_report, report_lock, check_and_save_report, load_existing_report, handle_results

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# DeepStack server configuration
DEEPSTACK_URL = "http://localhost:5000/v1/vision/nsfw"

# Load existing report to avoid reprocessing files
existing_files = load_existing_report(os.path.join('exposed', 'nudity_report.xlsx'))

def classify_image(file_path):
    """Classify an image for nudity using DeepStack."""
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        # Open the image file
        with open(file_path, "rb") as image_file:
            # Send the image to DeepStack for classification
            response = requests.post(DEEPSTACK_URL, files={"image": image_file})
        
        if response.status_code == 200:
            # Parse the response from DeepStack
            result = response.json()
            logging.debug(f"DeepStack Result for {file_path}: {result}")
            
            # Check if nudity is detected
            nudity_detected = result.get("nudity", {}).get("unsafe", 0) > 0.6
            classifiers = ["unsafe"] if nudity_detected else []
            
            # Handle the results (e.g., save to report, copy file if nudity detected)
            handle_results(file_path, nudity_detected, classifiers)
        else:
            logging.error(f"Failed to classify image {file_path}. HTTP Status: {response.status_code}")
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

def extract_frames(file_path, frame_rate=5):
    """Extract frames from a video file at a specified frame rate."""
    cap = cv2.VideoCapture(file_path)
    frames = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_rate == 0:
            frame_path = f"temp_frame_{frame_count}.jpg"
            cv2.imwrite(frame_path, frame)
            frames.append(frame_path)
        frame_count += 1

    cap.release()
    return frames

def cleanup_frames(frames):
    """Remove temporary frames."""
    for frame in frames:
        try:
            os.remove(frame)
        except Exception as e:
            logging.error(f"Error removing frame {frame}: {e}")

def classify_video(file_path):
    """Classify a video for nudity using DeepStack by analyzing extracted frames."""
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        frames = extract_frames(file_path, frame_rate=5)  # Analyze every 5th frame

        nudity_detected = False
        detection_results = []

        for frame in frames:
            with open(frame, "rb") as image_file:
                response = requests.post(DEEPSTACK_URL, files={"image": image_file})
            if response.status_code == 200:
                result = response.json()
                unsafe_score = result.get("nudity", {}).get("unsafe", 0)
                detection_results.append({"frame": frame, "unsafe_score": unsafe_score})
                if unsafe_score > 0.6:
                    nudity_detected = True
            else:
                logging.error(f"Failed to classify frame {frame}. HTTP Status: {response.status_code}")

        json_result = json.dumps(detection_results, ensure_ascii=False, indent=4)
        handle_results(file_path, nudity_detected, json_result)
        cleanup_frames(frames)

    except Exception as e:
        logging.error(f"Error classifying video {file_path}: {e}")

if __name__ == "__main__":
    # Get the folder path from the user
    folder_to_classify = input("Enter the path to the folder: ").strip()
    logging.debug(f"User input folder: {folder_to_classify}")
    
    # Classify files in the specified folder
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)
    
    # Save the nudity report
    report_path = os.path.join('exposed', 'nudity_report.xlsx')
    save_nudity_report(nudity_report, report_path)
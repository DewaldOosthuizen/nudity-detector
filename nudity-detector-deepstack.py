from datetime import datetime
import os
import shutil
import logging
import requests
from nudity_detector_utils import classify_files_in_folder, save_nudity_report, nudity_report, report_lock, check_and_save_report, load_existing_report, handle_results

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# DeepStack server configuration
DEEPSTACK_URL = "http://localhost:5000/v1/vision/nudity"

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

def classify_video(file_path):
    """Classify a video for nudity using DeepStack."""
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        # Open the video file
        with open(file_path, "rb") as video_file:
            # Send the video to DeepStack for classification
            response = requests.post(DEEPSTACK_URL, files={"video": video_file})
        
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
            logging.error(f"Failed to classify video {file_path}. HTTP Status: {response.status_code}")
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
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

existing_files = load_existing_report(os.path.join('exposed', 'nudity_report.xlsx'))

def classify_image(file_path):
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        with open(file_path, "rb") as image_file:
            response = requests.post(DEEPSTACK_URL, files={"image": image_file})
        
        if response.status_code == 200:
            result = response.json()
            logging.debug(f"DeepStack Result for {file_path}: {result}")
            
            nudity_detected = result.get("nudity", {}).get("unsafe", 0) > 0.6
            classifiers = ["unsafe"] if nudity_detected else []
            
            handle_results(file_path, nudity_detected, classifiers)
        else:
            logging.error(f"Failed to classify image {file_path}. HTTP Status: {response.status_code}")
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

def classify_video(file_path):
    logging.warning(f"Video classification is not supported with DeepStack. Skipping {file_path}.")

if __name__ == "__main__":
    folder_to_classify = input("Enter the path to the folder: ").strip()
    logging.debug(f"User input folder: {folder_to_classify}")
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)
    
    report_path = os.path.join('exposed', 'nudity_report.xlsx')
    save_nudity_report(nudity_report, report_path)
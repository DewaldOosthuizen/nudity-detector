from datetime import datetime
import os
import shutil
import logging
from nudenet import NudeDetector

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Classes considered as nudity
nudity_classes = [
    'ANUS_EXPOSED',
    'FEMALE_BREAST_EXPOSED',
    'FEMALE_GENITALIA_EXPOSED',
    'MALE_GENITALIA_EXPOSED',
    'BUTTOCKS_EXPOSED'
]

# Function to classify an image file
def classify_image(file_path, detector):
    try:
        detection_result = detector.detect(file_path)
        logging.debug(f"Image Classification Result for {file_path}: {detection_result}")
        
        # Check for nudity
        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
        
        # Log and copy file if nudity detected
        if nudity_detected:
            classifiers = [result['class'] for result in detection_result if result['class'] in nudity_classes]
            shutil.copy(file_path, os.path.join('exposed', os.path.basename(file_path)))
            nudity_report.append({
                "file": file_path,
                "nudity_detected": True,
                "detected_classes": classifiers
            })
        else:
            nudity_report.append({
                "file": file_path,
                "nudity_detected": False,
                "detected_classes": []
            })
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

# Function to classify a video file
def classify_video(file_path, detector):
    try:
        detection_result = detector.detect(file_path)
        logging.debug(f"Video Classification Result for {file_path}: {detection_result}")
        
        # Check for nudity
        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
        
        # Log and copy file if nudity detected
        if nudity_detected:
            classifiers = [result['class'] for result in detection_result if result['class'] in nudity_classes]
            shutil.copy(file_path, os.path.join('exposed', os.path.basename(file_path)))
            nudity_report.append({
                "file": file_path,
                "nudity_detected": True,
                "detected_classes": classifiers
            })
        else:
            nudity_report.append({
                "file": file_path,
                "nudity_detected": False,
                "detected_classes": []
            })
    except Exception as e:
        logging.error(f"Error classifying video {file_path}: {e}")

# Function to classify all files in a given folder
def classify_files_in_folder(folder_path):
    logging.debug(f"Starting classification in folder: {folder_path}")
    detector = NudeDetector()
    os.makedirs('exposed', exist_ok=True)
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            logging.debug(f"Processing file: {file_path}")
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                classify_image(file_path, detector)
            elif file_name.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
                classify_video(file_path, detector)
            else:
                logging.info(f"Skipping unsupported file: {file_path}")

# Main entry point of the script
if __name__ == "__main__":
    nudity_report = []
    folder_to_classify = input("Enter the path to the folder: ")
    logging.debug(f"User input folder: {folder_to_classify}")
    classify_files_in_folder(folder_to_classify)
    
    # Write the report to a file
    report_file_path = os.path.join('exposed', 'nudity_detection_report.txt')
    with open(report_file_path, 'w') as report_file:
        report_file.write(f"Nudity Detection Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:\n")
        for report in nudity_report:
            report_file.write(f"File: {report['file']}, Nudity Detected: {report['nudity_detected']}, Classes: {report['detected_classes']}\n")

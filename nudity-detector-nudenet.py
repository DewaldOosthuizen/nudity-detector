from datetime import datetime
import os
import shutil
import logging
from nudenet import NudeDetector
from queue import Queue
from threading import Thread, Lock
import openpyxl

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
# Supported formats
image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}
video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.vob', '.wmv', '.flv', '.3gp', '.webm'}

# Global variables
nudity_report = []
report_lock = Lock()

# Function to classify an image file
def classify_image(file_path, detector):
    try:
        detection_result = detector.detect(file_path)
        classifiers = [result['class'] for result in detection_result if result['class'] in nudity_classes]
        logging.debug(f"Image Classification Result for {file_path}: {detection_result}")
        
        # Check for nudity
        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
        
        # Log and copy file if nudity detected
        with report_lock:
            if nudity_detected:
                shutil.copy(file_path, os.path.join('exposed', os.path.basename(file_path)))
                nudity_report.append({
                    "file": file_path,
                    "nudity_detected": True,
                    "detected_classes": classifiers
                })
            else:
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    nudity_report.append({
                        "file": file_path,
                        "nudity_detected": False,
                        "detected_classes": classifiers
                    })
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

# Function to classify a video file
def classify_video(file_path, detector):
    try:
        detection_result = detector.detect(file_path)
        classifiers = [result['class'] for result in detection_result if result['class'] in nudity_classes]
        logging.debug(f"Video Classification Result for {file_path}: {detection_result}")
        
        # Check for nudity
        with report_lock:
            nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
            
            if nudity_detected:
                shutil.copy(file_path, os.path.join('exposed', os.path.basename(file_path)))
                nudity_report.append({
                    "file": file_path,
                    "nudity_detected": True,
                    "detected_classes": classifiers
                })
            else:
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    nudity_report.append({
                        "file": file_path,
                        "nudity_detected": False,
                        "detected_classes": classifiers
                    })
    except Exception as e:
        logging.error(f"Error classifying video {file_path}: {e}")

def process_file(file_path, detector):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in image_extensions:
        classify_image(file_path, detector)
    elif ext in video_extensions:
        classify_video(file_path, detector)
    else:
        logging.info(f"Skipping unsupported file: {file_path}")

# Function to classify all files in a given folder
def process_file_queue(file_queue, detector):
    while not file_queue.empty():
        file_path = file_queue.get()
        process_file(file_path, detector)
        file_queue.task_done()

def classify_files_in_folder(folder_path):
    logging.debug(f"Starting classification in folder: {folder_path}")
    file_queue = Queue()
    detector = NudeDetector()
    os.makedirs('exposed', exist_ok=True)
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_queue.put(os.path.join(root, file_name))
    # Start a few worker threads
    for _ in range(10):  # Number of threads
        worker = Thread(target=process_file_queue, args=(file_queue, detector))
        worker.start()
    file_queue.join()
    
def save_nudity_report(report_data, file_path):
    if not report_data:
        logging.warning("No data available to save in the report.")
        return
    
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Nudity Report"

    # Write headers
    headers = ["File", "Nudity Detected", "Detected Classes"]
    sheet.append(headers)

    # Write data rows
    for data in report_data:
        sheet.append([data["file"], data["nudity_detected"], ", ".join(data["detected_classes"])])

    workbook.save(file_path)
    logging.info(f"Report saved to {file_path}")

# Main entry point of the script
if __name__ == "__main__":
    folder_to_classify = input("Enter the path to the folder: ").strip()
    logging.debug(f"User input folder: {folder_to_classify}")
    classify_files_in_folder(folder_to_classify)
    
    # Write the report to a file
    report_path = os.path.join('exposed', 'nudity_report.xlsx')
    save_nudity_report(nudity_report, report_path)
from datetime import datetime
import os
import shutil
import logging
import requests
from queue import Queue
from threading import Thread, Lock
import openpyxl

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# DeepStack server configuration
DEEPSTACK_URL = "http://localhost:5000/v1/vision/nudity"

# Supported formats
image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}
video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.vob', '.wmv', '.flv', '.3gp', '.webm'}

# Global variables
nudity_report = []
report_lock = Lock()

# Function to classify an image file using DeepStack
def classify_image(file_path):
    try:
        with open(file_path, "rb") as image_file:
            response = requests.post(DEEPSTACK_URL, files={"image": image_file})
        
        if response.status_code == 200:
            result = response.json()
            logging.debug(f"DeepStack Result for {file_path}: {result}")
            
            nudity_detected = result.get("nudity", {}).get("unsafe", 0) > 0.6
            classifiers = ["unsafe"] if nudity_detected else []
            
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
                    nudity_report.append({
                        "file": file_path,
                        "nudity_detected": False,
                        "detected_classes": classifiers
                    })
        else:
            logging.error(f"Failed to classify image {file_path}. HTTP Status: {response.status_code}")
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

# Function to classify a video file (placeholder, as DeepStack does not support videos directly)
def classify_video(file_path):
    logging.warning(f"Video classification is not supported with DeepStack. Skipping {file_path}.")

def process_file(file_path):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in image_extensions:
        classify_image(file_path)
    elif ext in video_extensions:
        classify_video(file_path)
    else:
        logging.info(f"Skipping unsupported file: {file_path}")

# Function to classify all files in a given folder
def process_file_queue(file_queue):
    while not file_queue.empty():
        file_path = file_queue.get()
        process_file(file_path)
        file_queue.task_done()

def classify_files_in_folder(folder_path):
    logging.debug(f"Starting classification in folder: {folder_path}")
    file_queue = Queue()
    os.makedirs('exposed', exist_ok=True)
    
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_queue.put(os.path.join(root, file_name))
    
    # Start a few worker threads
    for _ in range(10):  # Number of threads
        worker = Thread(target=process_file_queue, args=(file_queue,))
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

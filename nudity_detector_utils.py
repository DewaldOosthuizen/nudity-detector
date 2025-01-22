import os
import shutil
import logging
from queue import Queue
from threading import Thread, Lock
import openpyxl
from datetime import datetime

# Supported formats
image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}
video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.vob', '.wmv', '.flv', '.3gp', '.webm'}

# Global variables
nudity_report = []
report_lock = Lock()

def process_file(file_path, classify_image, classify_video):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in image_extensions:
        classify_image(file_path)
    elif ext in video_extensions:
        classify_video(file_path)
    else:
        logging.info(f"Skipping unsupported file: {file_path}")

def process_file_queue(file_queue, classify_image, classify_video):
    while not file_queue.empty():
        file_path = file_queue.get()
        process_file(file_path, classify_image, classify_video)
        file_queue.task_done()

def classify_files_in_folder(folder_path, classify_image, classify_video):
    logging.debug(f"Starting classification in folder: {folder_path}")
    file_queue = Queue()
    os.makedirs('exposed', exist_ok=True)
    
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_queue.put(os.path.join(root, file_name))
    
    # Start a few worker threads
    for _ in range(10):  # Number of threads
        worker = Thread(target=process_file_queue, args=(file_queue, classify_image, classify_video))
        worker.start()
    file_queue.join()

def save_nudity_report(report_data, file_path):
    if not report_data:
        logging.warning("No data available to save in the report.")
        return
    
    if os.path.exists(file_path):
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active
    else:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Nudity Report"
        headers = ["File", "Nudity Detected", "Detected Classes", "Date Classified"]
        sheet.append(headers)

    # Write data rows
    for data in report_data:
        sheet.append([data["file"], data["nudity_detected"], data["detected_classes"], data["date_classified"]])

    workbook.save(file_path)
    logging.info(f"Report saved to {file_path}")

def check_and_save_report(report_data, file_path, batch_size=500):
    if len(report_data) >= batch_size:
        save_nudity_report(report_data, file_path)
        report_data.clear()

def load_existing_report(file_path):
    existing_files = set()
    if os.path.exists(file_path):
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active
        for row in sheet.iter_rows(min_row=2, values_only=True):
            existing_files.add(row[0])
    return existing_files
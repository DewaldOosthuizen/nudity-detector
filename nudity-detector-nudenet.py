from datetime import datetime
import os
import shutil
import logging
import json
from nudenet import NudeDetector
from nudity_detector_utils import classify_files_in_folder, save_nudity_report, nudity_report, report_lock, check_and_save_report, load_existing_report

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

existing_files = load_existing_report(os.path.join('exposed', 'nudity_report.xlsx'))

def classify_image(file_path):
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        detector = NudeDetector()
        detection_result = detector.detect(file_path)
        logging.debug(f"Image Classification Result for {file_path}: {detection_result}")
        
        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
        
        # Remove the 'box' property from each record
        detection_result = [{'class': record['class'], 'score': record['score']} for record in detection_result]
        json_result = json.dumps(detection_result, ensure_ascii=False, indent=4)
        
        with report_lock:
            if nudity_detected:
                shutil.copy(file_path, os.path.join('exposed', os.path.basename(file_path)))
                nudity_report.append({
                    "file": file_path,
                    "nudity_detected": True,
                    "detected_classes": json_result,
                    "date_classified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    nudity_report.append({
                        "file": file_path,
                        "nudity_detected": False,
                        "detected_classes": json_result,
                        "date_classified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            check_and_save_report(nudity_report, os.path.join('exposed', 'nudity_report.xlsx'))
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

def classify_video(file_path):
    logging.warning(f"Video classification is not supported with Nudenet. Skipping {file_path}.")

if __name__ == "__main__":
    folder_to_classify = input("Enter the path to the folder: ").strip()
    logging.debug(f"User input folder: {folder_to_classify}")
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)
    
    report_path = os.path.join('exposed', 'nudity_report.xlsx')
    save_nudity_report(nudity_report, report_path)
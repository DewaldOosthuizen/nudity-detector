import os
import logging
import json
from nudenet import NudeDetector
import cv2
from nudity_detector_utils import classify_files_in_folder, save_nudity_report, nudity_report, load_existing_report, handle_results

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

# Load existing report to avoid reprocessing files
existing_files = load_existing_report(os.path.join('exposed', 'nudity_report.xlsx'))

# Initialize the NudeDetector
detector = NudeDetector()

def classify_image(file_path):
    """Classify an image for nudity."""
    if file_path in existing_files:
        logging.info(f"Skipping already scanned file: {file_path}")
        return

    try:
        
        # Detect nudity in the image
        detection_result = detector.detect(file_path)
        logging.debug(f"Image Classification Result for {file_path}: {detection_result}")
        
        # Check if any detected class is considered nudity
        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 for result in detection_result)
        
        # Remove the 'box' property from each record for simplicity
        detection_result = [{'class': record['class'], 'score': record['score']} for record in detection_result]
        json_result = json.dumps(detection_result, ensure_ascii=False, indent=4)
        logging.debug(f"Cleaned up image Classification Result for {file_path}: {json_result}")
        
        # Handle the results (e.g., save to report, copy file if nudity detected)
        handle_results(file_path, nudity_detected, json_result)
    except Exception as e:
        logging.error(f"Error classifying image {file_path}: {e}")

def extract_frames(file_path, frame_rate=1):
    """Extract frames from a video file at a specified frame rate."""
    cap = cv2.VideoCapture(file_path)
    frames = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        # Extract frame at specific intervals
        if frame_count % frame_rate == 0:
            frame_path = f"temp_frame_{frame_count}.jpg"
            cv2.imwrite(frame_path, frame)
            frames.append(frame_path)
        frame_count += 1

    cap.release()
    return frames

def classify_video(file_path):
    """Classify a video for nudity by analyzing extracted frames."""
    try:
        if file_path in existing_files:
            logging.info(f"Skipping already scanned file: {file_path}")
            return

        # Extract frames
        frames = extract_frames(file_path, frame_rate=5)  # Analyze every 5th frame

        detection_results = []
        nudity_detected = False

        # Analyze each frame
        for frame in frames:
            try:
                if frame is None:
                    logging.error("Extracted frame is None, skipping...")
                    continue
                
                # Detect nudity in the frame
                result = detector.detect(frame)
                detection_results.extend(result)

                # Check if any frame has nudity
                if any(r['class'] in nudity_classes and r['score'] > 0.6 for r in result):
                    nudity_detected = True
                    logging.info("Nudity detected in video frame, no need to continue checking other frames...")
                    break  # Exit the loop as we already detected nudity, no need to continue
            except Exception as e:
                if frame is None:
                    logging.error(f"Error classifying frame, due to type None: {e}")
                else:
                    logging.error(f"Error classifying frame {frame}: {e}")
                
            
        # Simplify results for the report
        simplified_results = [
            {'class': record['class'], 'score': record['score']}
            for record in detection_results
        ]
        json_result = json.dumps(simplified_results, ensure_ascii=False, indent=4)

        # Step 4: Handle results
        handle_results(file_path, nudity_detected, json_result)
            
        # Cleanup frames after saving the report
        cleanup_frames(frames)

    except Exception as e:
        logging.error(f"Error classifying video {file_path}: {e}")

def cleanup_frames(frames):
    """Remove temporary frames."""
    for frame in frames:
        try:
            if os.path.exists(frame):
                os.remove(frame)
        except Exception as e:
            logging.error(f"Error removing frame {frame}: {e}")

if __name__ == "__main__":
    # Get the folder path from the user
    folder_to_classify = input("Enter the path to the folder: ").strip()
    logging.debug(f"User input folder: {folder_to_classify}")
    
    # Classify files in the specified folder
    classify_files_in_folder(folder_to_classify, classify_image, classify_video)
    
    # Save the nudity report
    report_path = os.path.join('exposed', 'nudity_report.xlsx')
    save_nudity_report(nudity_report, report_path)
#!/usr/bin/env python3
"""
Nudity Detector GUI
A tkinter-based graphical user interface for the nudity detection system.
Supports both NudeNet and DeepStack models.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import subprocess
import sys
import webbrowser
import logging
from datetime import datetime

# Import existing functionality
from nudity_detector_utils import classify_files_in_folder, save_nudity_report, nudity_report, load_existing_report

# Configure logging for GUI
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NudityDetectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Nudity Detector")
        self.root.geometry("600x700")
        self.root.resizable(True, True)
        
        # Variables
        self.model_var = tk.StringVar(value="nudenet")
        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.is_processing = False
        self.processing_thread = None
        
        # Initialize GUI components
        self.create_widgets()
        
    def create_widgets(self):
        """Create and layout all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Nudity Detector", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Model selection
        model_frame = ttk.LabelFrame(main_frame, text="Detection Model", padding="10")
        model_frame.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 10))
        
        nudenet_radio = ttk.Radiobutton(model_frame, text="NudeNet (Fast, Local)", 
                                       variable=self.model_var, value="nudenet")
        nudenet_radio.grid(row=0, column=0, sticky=tk.W)
        
        deepstack_radio = ttk.Radiobutton(model_frame, text="DeepStack (Requires server)", 
                                         variable=self.model_var, value="deepstack")
        deepstack_radio.grid(row=1, column=0, sticky=tk.W)
        
        # Folder selection
        folder_frame = ttk.LabelFrame(main_frame, text="Folder to Scan", padding="10")
        folder_frame.grid(row=2, column=0, columnspan=3, sticky="we", pady=(0, 10))
        folder_frame.columnconfigure(0, weight=1)
        
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=50)
        self.folder_entry.grid(row=0, column=0, sticky="we", padx=(0, 10))
        
        browse_button = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        browse_button.grid(row=0, column=1)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, column=0, columnspan=3, pady=(0, 20))
        
        self.start_button = ttk.Button(control_frame, text="Start Scanning", command=self.start_scanning)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_scanning, state="disabled")
        self.stop_button.grid(row=0, column=1)
        
        # Progress bar
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=4, column=0, columnspan=3, sticky="we", pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=0, sticky="we", pady=(0, 5))
        
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0)
        
        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(0, 10))
        
        self.open_folder_button = ttk.Button(results_frame, text="Open Exposed Folder", 
                                           command=self.open_exposed_folder, state="disabled")
        self.open_folder_button.grid(row=0, column=0, padx=(0, 10))
        
        self.open_report_button = ttk.Button(results_frame, text="Open Report", 
                                           command=self.open_report, state="disabled")
        self.open_report_button.grid(row=0, column=1)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Create text widget with scrollbar
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
    def browse_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(title="Select folder to scan")
        if folder:
            self.folder_var.set(folder)
            
    def log_message(self, message):
        """Add message to log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def start_scanning(self):
        """Start the nudity detection process."""
        folder_path = self.folder_var.get().strip()
        
        if not folder_path:
            messagebox.showerror("Error", "Please select a folder to scan.")
            return
            
        if not os.path.exists(folder_path):
            messagebox.showerror("Error", "Selected folder does not exist.")
            return
            
        model = self.model_var.get()
        
        # Check DeepStack availability if selected
        if model == "deepstack":
            if not self.check_deepstack_server():
                messagebox.showerror("Error", 
                    "DeepStack server is not available at http://localhost:5000\n"
                    "Please start the DeepStack server using docker-compose up")
                return
        
        # Update UI state
        self.is_processing = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.open_folder_button.config(state="disabled")
        self.open_report_button.config(state="disabled")
        self.progress_bar.start(10)
        self.status_var.set("Initializing...")
        
        # Clear log
        self.log_text.delete(1.0, tk.END)
        self.log_message(f"Starting scan with {model.upper()} model")
        self.log_message(f"Scanning folder: {folder_path}")
        
        # Start processing in separate thread
        self.processing_thread = threading.Thread(target=self.process_files, args=(folder_path, model))
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def stop_scanning(self):
        """Stop the scanning process."""
        self.is_processing = False
        self.status_var.set("Stopping...")
        self.log_message("Stop requested by user")
        
    def check_deepstack_server(self):
        """Check if DeepStack server is running."""
        try:
            import requests
            response = requests.get("http://localhost:5000", timeout=5)
            return True
        except:
            return False
            
    def process_files(self, folder_path, model):
        """Process files in the background thread."""
        try:
            # Clear previous report data
            global nudity_report
            nudity_report.clear()
            
            self.status_var.set("Loading model...")
            
            # Import and initialize based on selected model
            if model == "nudenet":
                from nudenet import NudeDetector
                import json
                
                detector = NudeDetector()
                nudity_classes = [
                    'ANUS_EXPOSED', 'FEMALE_BREAST_EXPOSED', 'FEMALE_GENITALIA_EXPOSED',
                    'MALE_GENITALIA_EXPOSED', 'BUTTOCKS_EXPOSED'
                ]
                
                def classify_image(file_path):
                    if not self.is_processing:
                        return
                        
                    self.root.after(0, lambda: self.log_message(f"Processing: {os.path.basename(file_path)}"))
                    
                    try:
                        detection_result = detector.detect(file_path)
                        nudity_detected = any(result['class'] in nudity_classes and result['score'] > 0.6 
                                            for result in detection_result)
                        
                        detection_result = [{'class': record['class'], 'score': record['score']} 
                                          for record in detection_result]
                        json_result = json.dumps(detection_result, ensure_ascii=False, indent=4)
                        
                        # Handle results using existing utility
                        from nudity_detector_utils import handle_results
                        handle_results(file_path, nudity_detected, json_result)
                        
                    except Exception as e:
                        self.root.after(0, lambda: self.log_message(f"Error processing {file_path}: {e}"))
                
                def classify_video(file_path):
                    if not self.is_processing:
                        return
                        
                    self.root.after(0, lambda: self.log_message(f"Processing video: {os.path.basename(file_path)}"))
                    
                    try:
                        import cv2
                        
                        # Extract frames
                        cap = cv2.VideoCapture(file_path)
                        frames = []
                        frame_count = 0
                        
                        while cap.isOpened() and self.is_processing:
                            ret, frame = cap.read()
                            if not ret:
                                break
                            if frame_count % 5 == 0:  # Every 5th frame
                                frame_path = f"temp_frame_{frame_count}.jpg"
                                cv2.imwrite(frame_path, frame)
                                frames.append(frame_path)
                            frame_count += 1
                        
                        cap.release()
                        
                        detection_results = []
                        nudity_detected = False
                        
                        for frame in frames:
                            if not self.is_processing:
                                break
                                
                            try:
                                result = detector.detect(frame)
                                detection_results.extend(result)
                                
                                if any(r['class'] in nudity_classes and r['score'] > 0.6 for r in result):
                                    nudity_detected = True
                                    break
                            except Exception as e:
                                self.root.after(0, lambda: self.log_message(f"Error processing frame: {e}"))
                        
                        # Cleanup frames
                        for frame in frames:
                            try:
                                if os.path.exists(frame):
                                    os.remove(frame)
                            except:
                                pass
                        
                        simplified_results = [{'class': record['class'], 'score': record['score']}
                                            for record in detection_results]
                        json_result = json.dumps(simplified_results, ensure_ascii=False, indent=4)
                        
                        from nudity_detector_utils import handle_results
                        handle_results(file_path, nudity_detected, json_result)
                        
                    except Exception as e:
                        self.root.after(0, lambda: self.log_message(f"Error processing video {file_path}: {e}"))
                        
            else:  # deepstack
                import requests
                import cv2
                import json
                
                DEEPSTACK_URL = "http://localhost:5000/v1/vision/nsfw"
                
                def classify_image(file_path):
                    if not self.is_processing:
                        return
                        
                    self.root.after(0, lambda: self.log_message(f"Processing: {os.path.basename(file_path)}"))
                    
                    try:
                        with open(file_path, "rb") as image_file:
                            response = requests.post(DEEPSTACK_URL, files={"image": image_file})
                        
                        if response.status_code == 200:
                            result = response.json()
                            nudity_detected = result.get("nudity", {}).get("unsafe", 0) > 0.6
                            classifiers = ["unsafe"] if nudity_detected else []
                            
                            from nudity_detector_utils import handle_results
                            handle_results(file_path, nudity_detected, classifiers)
                        else:
                            self.root.after(0, lambda: self.log_message(f"Failed to classify {file_path}"))
                            
                    except Exception as e:
                        self.root.after(0, lambda: self.log_message(f"Error processing {file_path}: {e}"))
                
                def classify_video(file_path):
                    if not self.is_processing:
                        return
                        
                    self.root.after(0, lambda: self.log_message(f"Processing video: {os.path.basename(file_path)}"))
                    
                    try:
                        # Similar video processing as NudeNet but with DeepStack API
                        cap = cv2.VideoCapture(file_path)
                        frames = []
                        frame_count = 0
                        
                        while cap.isOpened() and self.is_processing:
                            ret, frame = cap.read()
                            if not ret:
                                break
                            if frame_count % 5 == 0:
                                frame_path = f"temp_frame_{frame_count}.jpg"
                                cv2.imwrite(frame_path, frame)
                                frames.append(frame_path)
                            frame_count += 1
                        
                        cap.release()
                        
                        nudity_detected = False
                        detection_results = []
                        
                        for frame in frames:
                            if not self.is_processing:
                                break
                                
                            try:
                                with open(frame, "rb") as image_file:
                                    response = requests.post(DEEPSTACK_URL, files={"image": image_file})
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    unsafe_score = result.get("nudity", {}).get("unsafe", 0)
                                    detection_results.append({"frame": frame, "unsafe_score": unsafe_score})
                                    
                                    if unsafe_score > 0.6:
                                        nudity_detected = True
                                        break
                            except Exception as e:
                                self.root.after(0, lambda: self.log_message(f"Error processing frame: {e}"))
                        
                        # Cleanup frames
                        for frame in frames:
                            try:
                                if os.path.exists(frame):
                                    os.remove(frame)
                            except:
                                pass
                        
                        json_result = json.dumps(detection_results, ensure_ascii=False, indent=4)
                        from nudity_detector_utils import handle_results
                        handle_results(file_path, nudity_detected, json_result)
                        
                    except Exception as e:
                        self.root.after(0, lambda: self.log_message(f"Error processing video {file_path}: {e}"))
            
            # Load existing report to avoid reprocessing
            existing_files = load_existing_report(os.path.join('exposed', 'nudity_report.xlsx'))
            
            self.status_var.set("Scanning files...")
            
            # Process all files
            classify_files_in_folder(folder_path, classify_image, classify_video)
            
            # Save final report
            if self.is_processing:
                self.status_var.set("Saving report...")
                report_path = os.path.join('exposed', 'nudity_report.xlsx')
                save_nudity_report(nudity_report, report_path)
                
                self.root.after(0, lambda: self.log_message(f"Scan completed! Report saved to: {report_path}"))
                self.root.after(0, lambda: self.log_message(f"Files processed: {len(nudity_report)}"))
                
                # Count detected files
                detected_count = sum(1 for entry in nudity_report if entry.get('nudity_detected', False))
                self.root.after(0, lambda: self.log_message(f"Nudity detected in: {detected_count} files"))
                
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"Error during processing: {e}"))
            
        finally:
            # Update UI state
            self.root.after(0, self.finish_processing)
            
    def finish_processing(self):
        """Clean up after processing is complete."""
        self.is_processing = False
        self.progress_bar.stop()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        
        # Enable result buttons if exposed folder exists
        if os.path.exists('exposed'):
            self.open_folder_button.config(state="normal")
            if os.path.exists(os.path.join('exposed', 'nudity_report.xlsx')):
                self.open_report_button.config(state="normal")
        
        self.status_var.set("Ready")
        
    def open_exposed_folder(self):
        """Open the exposed folder in file manager."""
        exposed_path = os.path.abspath('exposed')
        if os.path.exists(exposed_path):
            try:
                if sys.platform == "win32":
                    os.startfile(exposed_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", exposed_path])
                else:
                    subprocess.run(["xdg-open", exposed_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")
        else:
            messagebox.showwarning("Warning", "Exposed folder does not exist yet.")
            
    def open_report(self):
        """Open the nudity report."""
        report_path = os.path.abspath(os.path.join('exposed', 'nudity_report.xlsx'))
        if os.path.exists(report_path):
            try:
                if sys.platform == "win32":
                    os.startfile(report_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", report_path])
                else:
                    subprocess.run(["xdg-open", report_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open report: {e}")
        else:
            messagebox.showwarning("Warning", "Report file does not exist yet.")

def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = NudityDetectorGUI(root)
    
    # Handle window closing
    def on_closing():
        if app.is_processing:
            if messagebox.askokcancel("Quit", "Scanning is in progress. Do you want to quit?"):
                app.is_processing = False
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()
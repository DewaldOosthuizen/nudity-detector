#!/usr/bin/env python3
"""
Nudity Detector GUI
A tkinter-based graphical user interface for the nudity detection system.
Supports both NudeNet and DeepStack models with theme support and session persistence.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from functools import partial
from io import BytesIO
from tkinter import filedialog, messagebox, ttk

import darkdetect

import cv2

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from ..core import constants
from ..processing.media_processor import ThumbnailGenerator
from ..core.utils import (
    DEFAULT_REPORT_DIR,
    classify_files_in_folder,
    create_session_state,
    delete_file_safely,
    get_detected_results,
    get_report_path,
    handle_results,
    load_report_entries,
    load_scan_session,
    make_scan_config,
    nudity_report,
    normalize_threshold,
    open_file,
    open_file_location,
    replace_nudity_report,
    reset_nudity_report,
    save_nudity_report,
)


class NudityDetectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(constants.GUI_WINDOW_TITLE)
        self.root.geometry(constants.GUI_WINDOW_GEOMETRY)
        self.root.minsize(constants.GUI_WINDOW_MIN_WIDTH, constants.GUI_WINDOW_MIN_HEIGHT)

        self.style = ttk.Style()
        self.default_theme_name = self.style.theme_use()

        cfg = self._load_config()
        self.model_var = tk.StringVar(value=cfg.get('model', constants.MODEL_NUDENET))
        self.folder_var = tk.StringVar(value=cfg.get('last_source_folder', ''))
        self.theme_var = tk.StringVar(value=cfg.get('theme', constants.THEME_SYSTEM))
        self.threshold_var = tk.DoubleVar(value=cfg.get('threshold_percent', constants.DEFAULT_THRESHOLD_PERCENT))
        self.status_var = tk.StringVar(value='Ready')
        self.summary_var = tk.StringVar(value='No scan has been run yet.')

        self.is_processing = False
        self.processing_thread = None
        self.detected_results = []
        self.last_report_path = self._find_latest_report_path() or get_report_path()
        self.thumbnail_photo = None
        self.thumbnail_meta_var = tk.StringVar(value='Select a result to preview.')

        self.create_widgets()
        self.apply_theme(self.theme_var.get())
        self.load_initial_session()

    def create_widgets(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding=constants.GUI_FRAME_PADDING)
        main_frame.grid(row=0, column=0, sticky='nsew')
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=1)

        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text='Nudity Detector', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(
            header_frame,
            text='Modern scan workflow with saved sessions, theme control, and post-scan review.',
            style='Subtitle.TLabel',
        ).grid(row=1, column=0, sticky='w', pady=(4, 0))

        controls_frame = ttk.LabelFrame(main_frame, text='Scan Settings', padding=constants.GUI_CONTROLS_PADDING)
        controls_frame.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(3, weight=1)

        ttk.Label(controls_frame, text='Theme').grid(row=0, column=0, sticky='w')
        self.theme_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.theme_var,
            values=constants.SUPPORTED_THEMES,
            state='readonly',
        )
        self.theme_combo.grid(row=0, column=1, sticky='ew', padx=(8, 16), pady=(0, 8))
        self.theme_combo.bind('<<ComboboxSelected>>', self._on_theme_selected)

        ttk.Label(controls_frame, text='Model').grid(row=0, column=2, sticky='w')
        model_frame = ttk.Frame(controls_frame)
        model_frame.grid(row=0, column=3, sticky='w', pady=(0, 8))
        self.nudenet_radio = ttk.Radiobutton(model_frame, text='NudeNet', variable=self.model_var, value=constants.MODEL_NUDENET)
        self.deepstack_radio = ttk.Radiobutton(model_frame, text='DeepStack', variable=self.model_var, value=constants.MODEL_DEEPSTACK)
        self.nudenet_radio.grid(row=0, column=0, sticky='w')
        self.deepstack_radio.grid(row=0, column=1, sticky='w', padx=(12, 0))

        ttk.Label(controls_frame, text='Source Folder').grid(row=1, column=0, sticky='w')
        self.folder_entry = ttk.Entry(controls_frame, textvariable=self.folder_var)
        self.folder_entry.grid(row=1, column=1, columnspan=2, sticky='ew', padx=(8, 8), pady=(0, 8))
        self.browse_button = ttk.Button(controls_frame, text='Browse...', command=self.browse_folder)
        self.browse_button.grid(row=1, column=3, sticky='e', pady=(0, 8))

        ttk.Label(controls_frame, text='Threshold %').grid(row=2, column=0, sticky='w')
        self.threshold_spinbox = ttk.Spinbox(
            controls_frame,
            from_=0,
            to=100,
            increment=1,
            textvariable=self.threshold_var,
            width=8,
        )
        self.threshold_spinbox.grid(row=2, column=1, sticky='w', padx=(8, 16))
        ttk.Label(controls_frame, text='Only detections at or above this confidence are treated as explicit.').grid(
            row=2,
            column=2,
            columnspan=2,
            sticky='w',
        )

        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        for column in range(9):
            action_frame.columnconfigure(column, weight=1 if column == 8 else 0)

        self.start_button = ttk.Button(action_frame, text='Start Scan', command=self.start_scanning)
        self.stop_button = ttk.Button(action_frame, text='Stop', command=self.stop_scanning, state='disabled')
        self.save_session_button = ttk.Button(action_frame, text='Save Session', command=self.save_session_dialog)
        self.load_session_button = ttk.Button(action_frame, text='Load Session', command=self.load_session_dialog)
        self.open_report_button = ttk.Button(action_frame, text='Open Report', command=self.open_report, state='disabled')
        self.open_reports_button = ttk.Button(action_frame, text='Open Reports Folder', command=self.open_reports_folder)
        self.clear_all_button = ttk.Button(action_frame, text='Clear All Results', command=self.clear_all_scan_results)

        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        self.save_session_button.grid(row=0, column=2, padx=(0, 8))
        self.load_session_button.grid(row=0, column=3, padx=(0, 8))
        self.open_report_button.grid(row=0, column=4, padx=(0, 8))
        self.open_reports_button.grid(row=0, column=5, padx=(0, 8))
        self.clear_all_button.grid(row=0, column=6)

        results_frame = ttk.LabelFrame(main_frame, text='Detected Media Review', padding=12)
        results_frame.grid(row=3, column=0, sticky='nsew', pady=(0, 12))
        results_frame.columnconfigure(0, weight=1)
        results_frame.columnconfigure(2, weight=0)
        results_frame.rowconfigure(1, weight=1)

        ttk.Label(results_frame, textvariable=self.summary_var, style='Summary.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 8))

        self.results_tree = ttk.Treeview(results_frame, columns=constants.TREE_COLUMNS, show='headings', height=constants.TREE_HEIGHT)
        self.results_tree.heading('name', text='File')
        self.results_tree.heading('media_type', text='Type')
        self.results_tree.heading('confidence', text='Confidence')
        self.results_tree.heading('model', text='Model')
        self.results_tree.heading('path', text='Path')

        for col in constants.TREE_COLUMNS:
            width = constants.TREE_COLUMN_WIDTHS.get(col, 100)
            anchor = constants.TREE_COLUMN_ANCHORS.get(col, 'w')
            self.results_tree.column(col, width=width, anchor=anchor)
        self.results_tree.grid(row=1, column=0, sticky='nsew')

        tree_scroll = ttk.Scrollbar(results_frame, orient='vertical', command=self.results_tree.yview)
        tree_scroll.grid(row=1, column=1, sticky='ns')
        self.results_tree.configure(yscrollcommand=tree_scroll.set)
        self.results_tree.bind('<<TreeviewSelect>>', self.on_result_selected)

        preview_frame = ttk.Frame(results_frame)
        preview_frame.grid(row=1, column=2, rowspan=2, sticky='ns', padx=(12, 0))
        preview_frame.columnconfigure(0, weight=1)

        ttk.Label(preview_frame, text='Thumbnail Preview').grid(row=0, column=0, sticky='w', pady=(0, 8))
        self.thumbnail_image_label = ttk.Label(
            preview_frame,
            text=constants.NO_THUMBNAIL_TEXT,
            anchor='center',
            width=constants.GUI_PREVIEW_PANEL_WIDTH,
        )
        self.thumbnail_image_label.grid(row=1, column=0, sticky='n', pady=(0, 8))
        ttk.Label(preview_frame, textvariable=self.thumbnail_meta_var, wraplength=220, justify='left').grid(
            row=2,
            column=0,
            sticky='w',
        )

        result_action_frame = ttk.Frame(results_frame)
        result_action_frame.grid(row=2, column=0, sticky='w', pady=(10, 0))
        self.open_file_button = ttk.Button(
            result_action_frame,
            text='Open File',
            command=self.open_selected_file,
            state='disabled',
        )
        self.open_location_button = ttk.Button(
            result_action_frame,
            text='Open Location',
            command=self.open_selected_location,
            state='disabled',
        )
        self.delete_button = ttk.Button(
            result_action_frame,
            text='Delete Selected',
            command=self.delete_selected_result,
            state='disabled',
        )
        self.open_file_button.grid(row=0, column=0, padx=(0, 8))
        self.open_location_button.grid(row=0, column=1, padx=(0, 8))
        self.delete_button.grid(row=0, column=2)

        log_frame = ttk.LabelFrame(main_frame, text='Activity Log', padding=12)
        log_frame.grid(row=4, column=0, sticky='nsew')
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, relief='flat', borderwidth=0)
        self.log_text.grid(row=0, column=0, sticky='nsew')
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky='ns')
        self.log_text.configure(yscrollcommand=log_scroll.set)

        footer_frame = ttk.Frame(main_frame)
        footer_frame.grid(row=5, column=0, sticky='ew', pady=(12, 0))
        footer_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(footer_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=0, sticky='ew', padx=(0, 12))
        ttk.Label(footer_frame, textvariable=self.status_var).grid(row=0, column=1, sticky='e')

    def _load_config(self) -> dict:
        """Load persisted app settings from config/app_config.json."""
        config_path = os.path.join(constants.CONFIG_DIR, constants.CONFIG_FILE_NAME)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _save_config(self):
        """Persist current app settings to config/app_config.json."""
        config_path = os.path.join(constants.CONFIG_DIR, constants.CONFIG_FILE_NAME)
        try:
            os.makedirs(constants.CONFIG_DIR, exist_ok=True)
            data = {
                'theme': self.theme_var.get(),
                'model': self.model_var.get(),
                'threshold_percent': self.threshold_var.get(),
                'last_source_folder': self.folder_var.get().strip(),
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except (OSError, IOError):
            pass

    def _find_latest_report_path(self):
        """Return the report xlsx path from the most recent dated scan subfolder, or None."""
        report_dir = DEFAULT_REPORT_DIR
        if not os.path.isdir(report_dir):
            return None
        subdirs = sorted(
            (d for d in os.listdir(report_dir) if os.path.isdir(os.path.join(report_dir, d))),
            reverse=True,
        )
        for subdir in subdirs:
            candidate = get_report_path(os.path.join(report_dir, subdir))
            if os.path.exists(candidate):
                return candidate
        return None

    def load_initial_session(self):
        latest = self._find_latest_report_path()
        if latest and os.path.exists(latest):
            try:
                self.load_session_from_path(latest, show_feedback=False)
            except (OSError, IOError, json.JSONDecodeError):
                self.log_message('No previous session could be loaded.')

    def build_scan_config(self):
        return make_scan_config(
            source_folder=self.folder_var.get().strip(),
            model_name=self.model_var.get(),
            threshold_percent=int(round(self.threshold_var.get())),
            theme_mode=self.theme_var.get(),
        )

    def build_session_state(self):
        return create_session_state(scan_config=self.build_scan_config(), results=list(self.detected_results))

    def browse_folder(self):
        folder = filedialog.askdirectory(title='Select folder to scan')
        if folder:
            self.folder_var.set(folder)

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f'[{timestamp}] {message}\n')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def apply_theme(self, theme_mode):
        palette = {
            'system': {
                'frame': '#f4f1ea',
                'panel': '#ffffff',
                'text': '#1f2328',
                'muted': '#5c6670',
                'accent': '#1b6a63',
                'border': '#d7ddd7',
                'log': '#ffffff',
            },
            'light': {
                'frame': '#f8f3eb',
                'panel': '#fffdfa',
                'text': '#1c262b',
                'muted': '#51606a',
                'accent': '#0f766e',
                'border': '#d9dfd6',
                'log': '#fffdfa',
            },
            'dark': {
                'frame': '#182026',
                'panel': '#1f2a30',
                'text': '#f3f6f4',
                'muted': '#b6c4c5',
                'accent': '#7ed6cb',
                'border': '#334047',
                'log': '#11181d',
            },
        }
        resolved = theme_mode
        if theme_mode == constants.THEME_SYSTEM:
            detected = darkdetect.theme()
            if detected == 'Dark':
                resolved = 'dark'
            elif sys.platform.startswith('linux'):
                try:
                    r = subprocess.run(
                        ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                        capture_output=True, text=True, timeout=1,
                    )
                    resolved = 'dark' if 'dark' in r.stdout.lower() else 'light'
                except Exception:
                    resolved = 'light'
            else:
                resolved = 'light'
        colors = palette.get(resolved, palette['system'])

        self.style.theme_use(self.default_theme_name)
        self.root.configure(background=colors['frame'])
        self.style.configure('TFrame', background=colors['frame'])
        self.style.configure('TLabelframe', background=colors['panel'], bordercolor=colors['border'])
        self.style.configure('TLabelframe.Label', background=colors['panel'], foreground=colors['text'])
        self.style.configure('TLabel', background=colors['frame'], foreground=colors['text'])
        self.style.configure('Title.TLabel', font=('Georgia', 20, 'bold'), foreground=colors['text'])
        self.style.configure('Subtitle.TLabel', foreground=colors['muted'])
        self.style.configure('Summary.TLabel', background=colors['panel'], foreground=colors['muted'])
        self.style.configure('TButton', padding=8)
        self.style.configure('Treeview', background=colors['panel'], foreground=colors['text'], fieldbackground=colors['panel'])
        self.style.configure('Treeview.Heading', background=colors['accent'], foreground=colors['panel'])
        self.style.map('Treeview', background=[('selected', colors['accent'])], foreground=[('selected', colors['panel'])])
        self.log_text.configure(
            background=colors['log'],
            foreground=colors['text'],
            insertbackground=colors['text'],
            selectbackground=colors['accent'],
        )

    def _on_theme_selected(self, _event=None):
        self.apply_theme(self.theme_var.get())
        self._save_config()

    def set_controls_for_processing(self, processing):
        state = 'disabled' if processing else 'normal'
        self.start_button.config(state='disabled' if processing else 'normal')
        self.stop_button.config(state='normal' if processing else 'disabled')
        self.browse_button.config(state=state)
        self.folder_entry.config(state=state)
        self.theme_combo.config(state='disabled' if processing else 'readonly')
        self.threshold_spinbox.config(state=state)
        self.nudenet_radio.config(state=state)
        self.deepstack_radio.config(state=state)
        self.clear_all_button.config(state=state)

    def check_deepstack_server(self):
        try:
            import requests
            response = requests.get(constants.DEEPSTACK_CONNECTION_CHECK_URL, timeout=constants.DEEPSTACK_HEALTH_CHECK_TIMEOUT)
            return response.ok
        except requests.exceptions.RequestException:
            return False

    def start_scanning(self):
        folder_path = self.folder_var.get().strip()
        if not folder_path:
            messagebox.showerror('Error', 'Please select a folder to scan.')
            return
        if not os.path.isdir(folder_path):
            messagebox.showerror('Error', 'Selected folder does not exist.')
            return
        if self.model_var.get() == constants.MODEL_DEEPSTACK and not self.check_deepstack_server():
            messagebox.showerror(
                'Error',
                f'DeepStack server is not available at {constants.DEEPSTACK_CONNECTION_CHECK_URL}\nPlease start it before scanning.',
            )
            return

        self.is_processing = True
        self.detected_results = []
        self.populate_results([])
        reset_nudity_report()
        self.log_text.delete('1.0', tk.END)
        self.set_controls_for_processing(True)
        self.progress_bar.start(10)
        self.status_var.set('Scanning...')
        self.summary_var.set('Scan running...')
        scan_run_dir = os.path.join(DEFAULT_REPORT_DIR, datetime.now().strftime(constants.SCAN_RUN_DATE_FORMAT))
        self.log_message(f"Starting {self.model_var.get()} scan at {self.threshold_var.get():.0f}% threshold")
        self.log_message(f'Source folder: {folder_path}')
        self.log_message(f'Report folder: {scan_run_dir}')

        self.processing_thread = threading.Thread(target=self.process_files, args=(folder_path, scan_run_dir), daemon=True)
        self.processing_thread.start()

    def stop_scanning(self):
        self.is_processing = False
        self.status_var.set('Stopping...')
        self.log_message('Stop requested. Pending files will be skipped as workers drain.')

    def extract_video_frames(self, file_path, temp_prefix):
        temp_dir = tempfile.mkdtemp(prefix=temp_prefix)
        frame_paths = []
        cap = cv2.VideoCapture(file_path)
        frame_count = 0
        try:
            while cap.isOpened() and self.is_processing:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % 5 == 0:
                    frame_path = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
                    cv2.imwrite(frame_path, frame)
                    frame_paths.append(frame_path)
                frame_count += 1
        finally:
            cap.release()
        return temp_dir, frame_paths

    def cleanup_frame_dir(self, temp_dir, frame_paths):
        shutil.rmtree(temp_dir, ignore_errors=True)

    def create_nudenet_classifiers(self, existing_files, threshold_value, threshold_percent):
        from nudenet import NudeDetector

        detector = NudeDetector()

        def simplify_results(detection_result):
            return [
                {'class': record.get('label', ''), 'score': record.get('score', 0.0)}
                for record in detection_result
            ]

        def confidence_for_results(detection_result):
            class_scores = [
                record.get('score', 0.0)
                for record in detection_result
                if record.get('label') in constants.NUDITY_CLASSES
            ]
            return max(class_scores, default=0.0)

        def classify_image(file_path):
            if not self.is_processing or file_path in existing_files:
                return
            self.root.after(0, lambda: self.log_message(f'Processing image: {os.path.basename(file_path)}'))
            detection_result = detector.detect(file_path)
            confidence_score = confidence_for_results(detection_result)
            handle_results(
                file_path,
                confidence_score >= threshold_value,
                simplify_results(detection_result),
                confidence_score=confidence_score,
                media_type='image',
                model_name='nudenet',
                threshold_percent=threshold_percent,
            )

        def classify_video(file_path):
            if not self.is_processing or file_path in existing_files:
                return
            self.root.after(0, lambda: self.log_message(f'Processing video: {os.path.basename(file_path)}'))
            temp_dir, frame_paths = self.extract_video_frames(file_path, 'gui_nudenet_frames_')
            try:
                detection_results = []
                max_confidence = 0.0
                for frame_path in frame_paths:
                    if not self.is_processing:
                        break
                    frame_result = detector.detect(frame_path)
                    simplified_frame = simplify_results(frame_result)
                    detection_results.append({'frame': os.path.basename(frame_path), 'detections': simplified_frame})
                    max_confidence = max(max_confidence, confidence_for_results(frame_result))
                    if max_confidence >= threshold_value:
                        break

                handle_results(
                    file_path,
                    max_confidence >= threshold_value,
                    detection_results,
                    confidence_score=max_confidence,
                    media_type='video',
                    model_name='nudenet',
                    threshold_percent=threshold_percent,
                )
            finally:
                self.cleanup_frame_dir(temp_dir, frame_paths)

        return classify_image, classify_video

    def request_deepstack_score(self, image_path, requests_module, deepstack_url):
        with open(image_path, 'rb') as image_file:
            response = requests_module.post(deepstack_url, files={'image': image_file}, timeout=30)
        if response.status_code != 200:
            return None
        result = response.json()
        confidence_score = 0.0
        predictions = result.get('predictions', [])
        for pred in predictions:
            if pred.get('label') == 'nsfw':
                confidence_score = float(pred.get('confidence', 0.0))
                break
        return result, confidence_score

    def run_deepstack_image(self, file_path, existing_files, threshold_value, threshold_percent, requests_module, deepstack_url):
        if not self.is_processing or file_path in existing_files:
            return
        self.root.after(0, lambda: self.log_message(f'Processing image: {os.path.basename(file_path)}'))
        scored_result = self.request_deepstack_score(file_path, requests_module, deepstack_url)
        if scored_result is None:
            self.root.after(0, lambda: self.log_message(f'Failed to classify {file_path}'))
            return
        result, confidence_score = scored_result
        handle_results(
            file_path,
            confidence_score >= threshold_value,
            result,
            confidence_score=confidence_score,
            media_type='image',
            model_name='deepstack',
            threshold_percent=threshold_percent,
        )

    def run_deepstack_video(self, file_path, existing_files, threshold_value, threshold_percent, requests_module, deepstack_url):
        if not self.is_processing or file_path in existing_files:
            return
        self.root.after(0, lambda: self.log_message(f'Processing video: {os.path.basename(file_path)}'))
        temp_dir, frame_paths = self.extract_video_frames(file_path, 'gui_deepstack_frames_')
        try:
            frame_scores = []
            max_confidence = 0.0
            for frame_path in frame_paths:
                if not self.is_processing:
                    break
                scored_result = self.request_deepstack_score(frame_path, requests_module, deepstack_url)
                if scored_result is None:
                    continue
                _result, confidence_score = scored_result
                frame_scores.append({'frame': os.path.basename(frame_path), 'unsafe_score': confidence_score})
                max_confidence = max(max_confidence, confidence_score)
                if max_confidence >= threshold_value:
                    break

            handle_results(
                file_path,
                max_confidence >= threshold_value,
                frame_scores,
                confidence_score=max_confidence,
                media_type='video',
                model_name='deepstack',
                threshold_percent=threshold_percent,
            )
        finally:
            self.cleanup_frame_dir(temp_dir, frame_paths)

    def create_deepstack_classifiers(self, existing_files, threshold_value, threshold_percent):
        import requests

        deepstack_url = 'http://localhost:5000/v1/vision/nsfw'
        return (
            partial(self.run_deepstack_image, existing_files=existing_files, threshold_value=threshold_value, threshold_percent=threshold_percent, requests_module=requests, deepstack_url=deepstack_url),
            partial(self.run_deepstack_video, existing_files=existing_files, threshold_value=threshold_value, threshold_percent=threshold_percent, requests_module=requests, deepstack_url=deepstack_url),
        )

    def process_files(self, folder_path, scan_run_dir):
        model_name = self.model_var.get()
        threshold_percent = self.threshold_var.get()
        threshold_value = normalize_threshold(threshold_percent)
        report_path = get_report_path(scan_run_dir)
        existing_files = set()

        try:
            if model_name == constants.MODEL_NUDENET:
                classify_image, classify_video = self.create_nudenet_classifiers(
                    existing_files,
                    threshold_value,
                    threshold_percent,
                )
            else:
                classify_image, classify_video = self.create_deepstack_classifiers(
                    existing_files,
                    threshold_value,
                    threshold_percent,
                )

            classify_files_in_folder(folder_path, classify_image, classify_video)

            self.detected_results = get_detected_results(nudity_report)
            self.last_report_path = report_path
            session_state = self.build_session_state()
            save_nudity_report(nudity_report, report_path, session_state=session_state)
            self.root.after(0, lambda: self.populate_results(self.detected_results))
            self.root.after(0, lambda: self.log_message(f'Scan complete. {len(self.detected_results)} detections listed.'))
        except Exception as error:
            error_message = str(error)
            self.root.after(0, lambda: self.log_message(f'Error during processing: {error_message}'))
        finally:
            self.root.after(0, self.finish_processing)

    def clear_all_scan_results(self):
        if self.is_processing:
            messagebox.showwarning('Scan In Progress', 'Cannot clear results while a scan is running. Stop the scan first.')
            return
        if not messagebox.askyesno(
            'Clear All Results',
            'This will permanently delete all previous scan reports and cannot be undone.\n\nContinue?',
        ):
            return
        report_dir = DEFAULT_REPORT_DIR
        if os.path.isdir(report_dir):
            for name in os.listdir(report_dir):
                entry_path = os.path.join(report_dir, name)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path, ignore_errors=True)
                elif os.path.isfile(entry_path):
                    try:
                        os.remove(entry_path)
                    except OSError:
                        pass
        reset_nudity_report()
        self.detected_results = []
        self.last_report_path = get_report_path()
        self.populate_results([])
        self.open_report_button.config(state='disabled')
        self.log_message('All previous scan results have been cleared.')

    def finish_processing(self):
        self.is_processing = False
        self.progress_bar.stop()
        self.status_var.set('Ready')
        self.set_controls_for_processing(False)
        self.update_result_action_state()
        self.open_report_button.config(state='normal' if os.path.exists(self.last_report_path) else 'disabled')

    def populate_results(self, results):
        for item_id in self.results_tree.get_children():
            self.results_tree.delete(item_id)

        for index, entry in enumerate(results):
            self.results_tree.insert(
                '',
                'end',
                iid=str(index),
                values=(
                    os.path.basename(entry.get('file', '')),
                    entry.get('media_type', 'unknown'),
                    f"{float(entry.get('confidence_percent', 0)):.2f}%",
                    entry.get('model_name', ''),
                    entry.get('file', ''),
                ),
            )

        if results:
            self.summary_var.set(f'{len(results)} explicit item(s) detected. Review actions are available below.')
        else:
            self.summary_var.set('No explicit media detected in the current session.')
        self.update_result_action_state()
        self.clear_thumbnail_preview()

    def on_result_selected(self, _event=None):
        self.update_result_action_state()
        self.update_thumbnail_preview()

    def update_result_action_state(self):
        has_selection = bool(self.results_tree.selection())
        state = 'normal' if has_selection and not self.is_processing else 'disabled'
        self.open_file_button.config(state=state)
        self.open_location_button.config(state=state)
        self.delete_button.config(state=state)

    def clear_thumbnail_preview(self):
        self.thumbnail_photo = None
        self.thumbnail_image_label.config(image='', text=constants.NO_THUMBNAIL_TEXT)
        self.thumbnail_meta_var.set('Select a result to preview.')

    def _load_preview_from_file(self, file_path, media_type):
        """Try to load a full-quality PIL image from the original file."""
        resampler = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        if media_type == constants.MEDIA_TYPE_IMAGE:
            with Image.open(file_path) as im:
                img = im.copy()
            img.thumbnail(constants.THUMBNAIL_SIZE_PREVIEW_IMAGE, resampler)
            return img
        if media_type == constants.MEDIA_TYPE_VIDEO:
            b64 = ThumbnailGenerator.generate_from_video(file_path, constants.THUMBNAIL_SIZE_PREVIEW_IMAGE)
            if b64:
                return Image.open(BytesIO(base64.b64decode(b64)))
        return None

    def _load_preview_from_thumbnail(self, thumbnail_b64):
        """Decode and upscale the stored (small) base64 thumbnail as a fallback."""
        resampler = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        img = Image.open(BytesIO(base64.b64decode(thumbnail_b64)))
        if img.width < constants.THUMBNAIL_SIZE_PREVIEW_IMAGE[0] and img.height < constants.THUMBNAIL_SIZE_PREVIEW_IMAGE[1]:
            return img.resize(constants.THUMBNAIL_SIZE_PREVIEW_IMAGE, resampler)
        img.thumbnail(constants.THUMBNAIL_SIZE_PREVIEW_IMAGE, resampler)
        return img

    def update_thumbnail_preview(self):
        _index, entry = self.get_selected_entry()
        if entry is None:
            self.clear_thumbnail_preview()
            return

        thumbnail_b64 = entry.get('thumbnail', '') or ''
        meta_text = (
            f"Type: {entry.get('media_type', 'unknown')}\n"
            f"Confidence: {entry.get('confidence_percent', 0):.2f}%\n"
            f"Model: {entry.get('model_name', '')}"
        )

        if Image is None or ImageTk is None:
            self.thumbnail_image_label.config(image='', text=constants.NO_THUMBNAIL_TEXT)
            self.thumbnail_meta_var.set(meta_text)
            return

        pil_image = self._load_preview_image(entry, thumbnail_b64)
        if pil_image is not None:
            try:
                self.thumbnail_photo = ImageTk.PhotoImage(pil_image)
                self.thumbnail_image_label.config(image=self.thumbnail_photo, text='')
                self.thumbnail_meta_var.set(meta_text)
                return
            except Exception:
                pass

        self.thumbnail_photo = None
        fallback_text = constants.NO_THUMBNAIL_TEXT if not thumbnail_b64 else 'Thumbnail unavailable'
        self.thumbnail_image_label.config(image='', text=fallback_text)
        self.thumbnail_meta_var.set(meta_text)

    def _load_preview_image(self, entry, thumbnail_b64):
        """Return a PIL image for preview, sourcing from the original file when available."""
        file_path = entry.get('file', '')
        media_type = entry.get('media_type', '')
        if file_path and os.path.exists(file_path):
            try:
                return self._load_preview_from_file(file_path, media_type)
            except Exception:
                pass
        if thumbnail_b64:
            try:
                return self._load_preview_from_thumbnail(thumbnail_b64)
            except Exception:
                pass
        return None

    def get_selected_entry(self):
        selection = self.results_tree.selection()
        if not selection:
            return None, None
        index = int(selection[0])
        if index >= len(self.detected_results):
            return None, None
        return index, self.detected_results[index]

    def open_selected_file(self):
        """Open the selected detected file directly."""
        _index, entry = self.get_selected_entry()
        if entry is None:
            return
        file_path = entry.get('file', '')
        if not os.path.exists(file_path):
            messagebox.showerror('Error', f'File no longer exists: {file_path}')
            return
        success, error_message = open_file(file_path)
        if not success:
            messagebox.showerror('Error', f'Could not open file: {error_message}')

    def open_selected_location(self):
        _index, entry = self.get_selected_entry()
        if entry is None:
            return
        success, error_message = open_file_location(entry.get('file', ''))
        if not success:
            messagebox.showerror('Error', f'Could not open location: {error_message}')

    def delete_selected_result(self):
        index, entry = self.get_selected_entry()
        if entry is None or index is None:
            return

        confirm = messagebox.askyesno(
            'Delete detected file',
            f"Move this file to trash if possible?\n\n{entry.get('file', '')}",
        )
        if not confirm:
            return

        success, message = delete_file_safely(entry.get('file', ''))
        if not success:
            messagebox.showerror('Delete failed', message)
            return

        del self.detected_results[index]
        remaining_entries = [item for item in nudity_report if item.get('file') != entry.get('file')]
        replace_nudity_report(remaining_entries)
        save_nudity_report(nudity_report, self.last_report_path, session_state=self.build_session_state())
        self.populate_results(self.detected_results)
        self.log_message(f"Deleted {entry.get('file', '')}. {message}")

    def save_session_dialog(self):
        report_path = filedialog.asksaveasfilename(
            title='Save scan report',
            defaultextension=constants.XLSX_EXTENSION,
            filetypes=[('Excel Report', f'*{constants.XLSX_EXTENSION}')],
            initialfile=os.path.basename(self.last_report_path),
        )
        if not report_path:
            return

        self.last_report_path = report_path
        save_nudity_report(nudity_report, report_path, session_state=self.build_session_state())
        self.open_report_button.config(state='normal')
        self.log_message(f'Saved session report to {report_path}')

    def load_session_dialog(self):
        file_path = filedialog.askopenfilename(
            title='Load saved session',
            filetypes=[('Report or Session', f'*{constants.XLSX_EXTENSION} *.json'), ('Excel Report', f'*{constants.XLSX_EXTENSION}'), ('JSON Session', '*.json')],
        )
        if file_path:
            self.load_session_from_path(file_path, show_feedback=True)

    def load_session_from_path(self, file_path, show_feedback):
        session_state = load_scan_session(file_path)
        report_path = file_path if file_path.endswith(constants.XLSX_EXTENSION) else file_path.replace('_session.json', constants.XLSX_EXTENSION)
        report_entries = load_report_entries(report_path) if os.path.exists(report_path) else []
        detected_results = session_state.get('results') or get_detected_results(report_entries)
        scan_config = session_state.get('scan_config', {})

        self.folder_var.set(scan_config.get('source_folder', ''))
        self.model_var.set(scan_config.get('model_name', 'nudenet'))
        self.theme_var.set(scan_config.get('theme_mode', 'system'))
        self.threshold_var.set(float(scan_config.get('threshold_percent', 60)))
        self.apply_theme(self.theme_var.get())

        self.detected_results = detected_results
        replace_nudity_report(report_entries or detected_results)
        self.populate_results(self.detected_results)
        self.last_report_path = report_path
        self.open_report_button.config(state='normal' if os.path.exists(report_path) else 'disabled')

        if show_feedback:
            self.log_message(f'Loaded session from {file_path}')

    def open_reports_folder(self):
        success, error_message = open_file_location(DEFAULT_REPORT_DIR)
        if not success:
            messagebox.showerror('Error', f'Could not open folder: {error_message}')

    def open_report(self):
        if not os.path.exists(self.last_report_path):
            messagebox.showwarning('Warning', 'No report has been saved yet.')
            return
        try:
            if os.name == 'nt':
                os.startfile(self.last_report_path)
            elif os.uname().sysname == 'Darwin':
                subprocess.run(['open', self.last_report_path], check=False)
            else:
                subprocess.run(['xdg-open', self.last_report_path], check=False)
        except Exception as error:
            messagebox.showerror('Error', f'Could not open report: {error}')


def main():
    root = tk.Tk()
    app = NudityDetectorGUI(root)

    def on_closing():
        if app.is_processing:
            if not messagebox.askokcancel('Quit', 'Scanning is in progress. Do you want to quit?'):
                return
            app.is_processing = False
        app._save_config()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()

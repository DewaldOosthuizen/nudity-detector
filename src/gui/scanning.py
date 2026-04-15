import os
import shutil
import tempfile
import threading
from datetime import datetime
from functools import partial

import cv2

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib

from ..core import constants
from ..core.utils import (
    DEFAULT_REPORT_DIR,
    classify_files_in_folder,
    create_session_state,
    get_detected_results,
    get_report_path,
    handle_results,
    make_scan_config,
    nudity_report,
    normalize_threshold,
    reset_nudity_report,
    save_nudity_report,
)


class ScanningMixin:
    """Scan lifecycle, threading, classifier creation, and progress pulse.
    Mixed into NudityDetectorWindow."""

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start_clicked(self, _button):
        self.start_scanning()

    def _on_stop_clicked(self, _button):
        self.stop_scanning()

    def _on_clear_all_clicked(self, _button):
        self.clear_all_scan_results()

    # ------------------------------------------------------------------
    # Scan control
    # ------------------------------------------------------------------

    def check_deepstack_server(self):
        try:
            import requests
            response = requests.get(
                constants.DEEPSTACK_CONNECTION_CHECK_URL,
                timeout=constants.DEEPSTACK_HEALTH_CHECK_TIMEOUT,
            )
            return response.ok
        except Exception:
            return False

    def start_scanning(self):
        folder_path = self.folder_entry.get_text().strip()
        if not folder_path:
            self._show_error('Error', 'Please select a folder to scan.')
            return
        if not os.path.isdir(folder_path):
            self._show_error('Error', 'Selected folder does not exist.')
            return
        if self._get_model() == constants.MODEL_DEEPSTACK and not self.check_deepstack_server():
            self._show_error(
                'Error',
                f'DeepStack server is not available at {constants.DEEPSTACK_CONNECTION_CHECK_URL}\n'
                'Please start it before scanning.',
            )
            return

        self.is_processing = True
        self.detected_results = []
        self.populate_results([])
        reset_nudity_report()
        self.log_buffer.set_text('')
        self.set_controls_for_processing(True)
        self._start_progress_pulse()
        self.status_label.set_text('Scanning...')
        self.summary_label.set_text('Scan running...')
        scan_run_dir = os.path.join(DEFAULT_REPORT_DIR, datetime.now().strftime(constants.SCAN_RUN_DATE_FORMAT))
        self.log_message(f"Starting {self._get_model()} scan at {self.threshold_spin.get_value():.0f}% threshold")
        self.log_message(f'Source folder: {folder_path}')
        self.log_message(f'Report folder: {scan_run_dir}')

        # Create the report folder and write an initial empty session immediately
        # so the run appears in history before any files are processed.
        try:
            os.makedirs(scan_run_dir, exist_ok=True)
            initial_report_path = get_report_path(scan_run_dir)
            initial_session = create_session_state(
                scan_config=make_scan_config(
                    source_folder=folder_path,
                    model_name=self._get_model(),
                    threshold_percent=int(self.threshold_spin.get_value()),
                    theme_mode=self._get_theme_mode(),
                ),
                results=[],
            )
            save_nudity_report([], initial_report_path, session_state=initial_session)
            self.last_report_path = initial_report_path
            self.refresh_scan_history()
        except Exception:
            pass

        self.processing_thread = threading.Thread(
            target=self.process_files,
            args=(folder_path, scan_run_dir),
            daemon=True,
        )
        self.processing_thread.start()

    def stop_scanning(self):
        self.is_processing = False
        self.status_label.set_text('Stopping...')
        self.log_message('Stop requested. Pending files will be skipped as workers drain.')

    # ------------------------------------------------------------------
    # Video frame extraction
    # ------------------------------------------------------------------

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
                if frame_count % constants.VIDEO_FRAME_RATE == 0:
                    frame_path = os.path.join(temp_dir, constants.FRAME_FILE_NAME_PATTERN.format(frame_count))
                    cv2.imwrite(frame_path, frame)
                    frame_paths.append(frame_path)
                frame_count += 1
        finally:
            cap.release()
        return temp_dir, frame_paths

    def cleanup_frame_dir(self, temp_dir, _frame_paths):
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # NudeNet classifiers
    # ------------------------------------------------------------------

    def create_nudenet_classifiers(self, existing_files, threshold_value, threshold_percent):
        from nudenet import NudeDetector

        detector = NudeDetector()

        def simplify_results(detection_result):
            return [
                {'class': record.get('label', ''), 'score': record.get('score', 0.0)}
                for record in detection_result
            ]

        def confidence_for_results(detection_result):
            scores = [
                record.get('score', 0.0)
                for record in detection_result
                if record.get('label') in constants.NUDITY_CLASSES
            ]
            return max(scores, default=0.0)

        def classify_image(file_path):
            if not self.is_processing or file_path in existing_files:
                return
            GLib.idle_add(self.log_message, f'Processing image: {os.path.basename(file_path)}')
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
            GLib.idle_add(self.log_message, f'Processing video: {os.path.basename(file_path)}')
            temp_dir, frame_paths = self.extract_video_frames(file_path, constants.FRAME_TEMP_DIR_PREFIX_GUI_NUDENET)
            try:
                detection_results = []
                max_confidence = 0.0
                for frame_path in frame_paths:
                    if not self.is_processing:
                        break
                    frame_result = detector.detect(frame_path)
                    simplified_frame = simplify_results(frame_result)
                    detection_results.append(
                        {'frame': os.path.basename(frame_path), 'detections': simplified_frame}
                    )
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

    # ------------------------------------------------------------------
    # DeepStack classifiers
    # ------------------------------------------------------------------

    def request_deepstack_score(self, image_path, requests_module, deepstack_url):
        request_url = deepstack_url or constants.DEEPSTACK_URL
        with open(image_path, 'rb') as image_file:
            response = requests_module.post(
                request_url,
                files={'image': image_file},
                timeout=constants.DEEPSTACK_REQUEST_TIMEOUT,
            )
        if response.status_code != 200:
            return None
        result = response.json()
        confidence_score = 0.0
        for pred in result.get('predictions', []):
            if pred.get('label') == 'nsfw':
                confidence_score = float(pred.get('confidence', 0.0))
                break
        return result, confidence_score

    def run_deepstack_image(self, file_path, existing_files, threshold_value, threshold_percent, requests_module, deepstack_url):
        if not self.is_processing or file_path in existing_files:
            return
        GLib.idle_add(self.log_message, f'Processing image: {os.path.basename(file_path)}')
        scored_result = self.request_deepstack_score(file_path, requests_module, deepstack_url)
        if scored_result is None:
            GLib.idle_add(self.log_message, f'Failed to classify {file_path}')
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
        GLib.idle_add(self.log_message, f'Processing video: {os.path.basename(file_path)}')
        temp_dir, frame_paths = self.extract_video_frames(file_path, constants.FRAME_TEMP_DIR_PREFIX_GUI_DEEPSTACK)
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

        deepstack_url = constants.DEEPSTACK_URL
        return (
            partial(
                self.run_deepstack_image,
                existing_files=existing_files,
                threshold_value=threshold_value,
                threshold_percent=threshold_percent,
                requests_module=requests,
                deepstack_url=deepstack_url,
            ),
            partial(
                self.run_deepstack_video,
                existing_files=existing_files,
                threshold_value=threshold_value,
                threshold_percent=threshold_percent,
                requests_module=requests,
                deepstack_url=deepstack_url,
            ),
        )

    # ------------------------------------------------------------------
    # Main worker thread
    # ------------------------------------------------------------------

    def process_files(self, folder_path, scan_run_dir):
        model_name = self._get_model()
        threshold_percent = self.threshold_spin.get_value()
        threshold_value = normalize_threshold(threshold_percent)
        theme_mode = self._get_theme_mode()
        report_path = get_report_path(scan_run_dir)
        existing_files = set()
        update_interval = self._get_progress_interval()
        files_processed = [0]
        count_lock = threading.Lock()

        def _flush_intermediate():
            """Save a partial report snapshot and push results to the UI (worker thread)."""
            try:
                snapshot = list(nudity_report)
                intermediate_session = create_session_state(
                    scan_config=make_scan_config(
                        source_folder=folder_path,
                        model_name=model_name,
                        threshold_percent=threshold_percent,
                        theme_mode=theme_mode,
                    ),
                    results=snapshot,
                )
                save_nudity_report(snapshot, report_path, session_state=intermediate_session)
            except Exception:
                pass
            current_results = get_detected_results(nudity_report)
            GLib.idle_add(self._apply_intermediate_results, list(current_results))

        def _with_progress(fn):
            """Wrap a classifier to count processed files and flush every N."""
            def wrapper(file_path):
                fn(file_path)
                with count_lock:
                    files_processed[0] += 1
                    count = files_processed[0]
                if count % update_interval == 0:
                    _flush_intermediate()
            return wrapper

        try:
            if model_name == constants.MODEL_NUDENET:
                classify_image, classify_video = self.create_nudenet_classifiers(
                    existing_files, threshold_value, threshold_percent,
                )
            else:
                classify_image, classify_video = self.create_deepstack_classifiers(
                    existing_files, threshold_value, threshold_percent,
                )

            classify_image = _with_progress(classify_image)
            classify_video = _with_progress(classify_video)

            classify_files_in_folder(folder_path, classify_image, classify_video)

            self.detected_results = get_detected_results(nudity_report)
            self.last_report_path = report_path
            session_state = self.build_session_state()
            save_nudity_report(nudity_report, report_path, session_state=session_state)
            GLib.idle_add(self.populate_results, self.detected_results)
            GLib.idle_add(self.log_message, f'Scan complete. {len(self.detected_results)} detections listed.')
            GLib.idle_add(self.refresh_scan_history)
        except Exception as error:
            GLib.idle_add(self.log_message, f'Error during processing: {error}')
        finally:
            GLib.idle_add(self.finish_processing)

    # ------------------------------------------------------------------
    # Progress pulse
    # ------------------------------------------------------------------

    def _start_progress_pulse(self):
        if self._pulse_source_id is None:
            self._pulse_source_id = GLib.timeout_add(50, self._pulse_tick)

    def _pulse_tick(self):
        if self.is_processing:
            self.progress_bar.pulse()
            return True
        self._pulse_source_id = None
        self.progress_bar.set_fraction(0.0)
        return False

    def _apply_intermediate_results(self, results):
        """Update the results view with a mid-scan snapshot (called on the main thread)."""
        self.detected_results = results
        self.populate_results(results)
        count = len(results)
        if self.is_processing:
            self.summary_label.set_text(
                f'{count} explicit item(s) detected so far. Scan still running...'
                if count else 'Scan running... No detections yet.'
            )

    def finish_processing(self):
        self.is_processing = False
        self.status_label.set_text('Ready')
        self.set_controls_for_processing(False)
        self.update_result_action_state()
        self.open_report_button.set_sensitive(os.path.exists(self.last_report_path))

    # ------------------------------------------------------------------
    # Clear all
    # ------------------------------------------------------------------

    def clear_all_scan_results(self):
        if self.is_processing:
            self._show_warning('Scan In Progress', 'Cannot clear results while a scan is running. Stop the scan first.')
            return
        self._ask_yes_no(
            'Clear All Results',
            'This will permanently delete all previous scan reports and cannot be undone.\n\nContinue?',
            self._do_clear_all,
        )

    def _do_clear_all(self):
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
        self.open_report_button.set_sensitive(False)
        self.log_message('All previous scan results have been cleared.')
        self.refresh_scan_history()

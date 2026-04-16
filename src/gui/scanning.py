import logging
import os
import shutil
import sys
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
    count_supported_files,
    create_session_state,
    detect_with_timeout,
    get_detected_results,
    get_report_path,
    handle_results,
    make_scan_config,
    nudity_report,
    normalize_threshold,
    report_lock,
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

    # ------------------------------------------------------------------
    # Scan control
    # ------------------------------------------------------------------

    def check_helloz_nsfw_server(self):
        try:
            import requests
            response = requests.get(
                self._get_helloz_nsfw_check_url(),
                timeout=self._get_helloz_nsfw_health_check_timeout(),
            )
            return response.status_code < 500
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
        if self._get_model() == constants.MODEL_HELLOZ_NSFW and not self.check_helloz_nsfw_server():
            self._show_error(
                'Error',
                f'Helloz NSFW server is not available at {self._get_helloz_nsfw_check_url()}\n'
                'Please start it before scanning.',
            )
            self.log_message(f'Helloz NSFW server not reachable at {self._get_helloz_nsfw_check_url()}', 'error')
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
        self._total_files = 0
        self._last_populated_count = 0
        self._progress_fraction = 0.0
        scan_run_dir = os.path.join(DEFAULT_REPORT_DIR, datetime.now().strftime(constants.SCAN_RUN_DATE_FORMAT))
        self.log_message(f"Starting {self._get_model()} scan at {self.threshold_spin.get_value():.0f}% threshold")
        self.log_message(f'Source folder: {folder_path}')
        self.log_message(f'Report folder: {scan_run_dir}')
        self.log_message(
            f'Workers: {self._get_worker_thread_count()}, '
            f'detect timeout: {self._get_detect_timeout()}s, '
            f'video frame rate: 1/{self._get_video_frame_rate()}'
        )

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
        except OSError as error:
            self.log_message(f'Warning: could not create initial report: {error}', 'warning')

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

    @staticmethod
    def _frame_temp_dir_base():
        """Return /dev/shm on Linux when available (RAM disk), otherwise None."""
        if sys.platform.startswith('linux') and os.path.isdir('/dev/shm'):
            return '/dev/shm'
        return None

    def extract_video_frames(self, file_path, temp_prefix):
        temp_dir = tempfile.mkdtemp(prefix=temp_prefix, dir=self._frame_temp_dir_base())
        frame_paths = []
        cap = cv2.VideoCapture(file_path)
        frame_count = 0
        video_frame_rate = self._get_video_frame_rate()
        try:
            while cap.isOpened() and self.is_processing:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % video_frame_rate == 0:
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

        detect_timeout = self._get_detect_timeout()

        def classify_image(file_path):
            if not self.is_processing or file_path in existing_files:
                return
            if self._verbose_log:
                GLib.idle_add(self.log_message, f'Processing image: {os.path.basename(file_path)}')
            try:
                detection_result = detect_with_timeout(detector, file_path, detect_timeout)
            except TimeoutError:
                logging.debug(
                    'Detection timed out after %ds for %s; worker thread may continue in background',
                    detect_timeout, file_path,
                )
                GLib.idle_add(
                    self.log_message,
                    f'Detection timed out after {detect_timeout}s and was skipped: '
                    f'{os.path.basename(file_path)}',
                    'warning',
                )
                return
            except Exception as e:
                GLib.idle_add(self.log_message, f'Detection error for {os.path.basename(file_path)}: {e}', 'error')
                return
            if detection_result is None:
                GLib.idle_add(self.log_message, f'No result returned for {os.path.basename(file_path)}', 'warning')
                return
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
            if self._verbose_log:
                GLib.idle_add(self.log_message, f'Processing video: {os.path.basename(file_path)}')
            temp_dir, frame_paths = self.extract_video_frames(file_path, constants.FRAME_TEMP_DIR_PREFIX_GUI_NUDENET)
            try:
                detection_results = []
                max_confidence = 0.0
                for frame_path in frame_paths:
                    if not self.is_processing:
                        break
                    try:
                        frame_result = detect_with_timeout(detector, frame_path, detect_timeout)
                    except TimeoutError:
                        GLib.idle_add(
                            self.log_message,
                            f'Frame timed out after {detect_timeout}s — skipped: '
                            f'{os.path.basename(frame_path)} in {os.path.basename(file_path)}',
                            'warning',
                        )
                        continue
                    except Exception as e:
                        GLib.idle_add(self.log_message, f'Frame detection error for {os.path.basename(frame_path)}: {e}', 'error')
                        continue
                    if frame_result is None:
                        continue
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
    # Helloz NSFW classifiers
    # ------------------------------------------------------------------

    def request_helloz_nsfw_score(self, image_path, requests_module, helloz_nsfw_url, request_timeout):
        request_url = helloz_nsfw_url or constants.HELLOZ_NSFW_URL
        with open(image_path, 'rb') as image_file:
            response = requests_module.post(
                request_url,
                files={'file': image_file},
                timeout=request_timeout,
            )
        if response.status_code != 200:
            return None
        result = response.json()
        confidence_score = float(result.get('data', {}).get('nsfw', 0.0))
        return result, confidence_score

    def run_helloz_nsfw_image(self, file_path, existing_files, threshold_value, threshold_percent, requests_module, helloz_nsfw_url, request_timeout):
        if not self.is_processing or file_path in existing_files:
            return
        if self._verbose_log:
            GLib.idle_add(self.log_message, f'Processing image: {os.path.basename(file_path)}')
        scored_result = self.request_helloz_nsfw_score(file_path, requests_module, helloz_nsfw_url, request_timeout)
        if scored_result is None:
            GLib.idle_add(self.log_message, f'Failed to classify {os.path.basename(file_path)}', 'error')
            return
        result, confidence_score = scored_result
        handle_results(
            file_path,
            confidence_score >= threshold_value,
            result,
            confidence_score=confidence_score,
            media_type='image',
            model_name='helloz_nsfw',
            threshold_percent=threshold_percent,
        )

    def run_helloz_nsfw_video(self, file_path, existing_files, threshold_value, threshold_percent, requests_module, helloz_nsfw_url, request_timeout):
        if not self.is_processing or file_path in existing_files:
            return
        if self._verbose_log:
            GLib.idle_add(self.log_message, f'Processing video: {os.path.basename(file_path)}')
        temp_dir, frame_paths = self.extract_video_frames(file_path, constants.FRAME_TEMP_DIR_PREFIX_GUI_HELLOZ_NSFW)
        try:
            frame_scores = []
            max_confidence = 0.0
            for frame_path in frame_paths:
                if not self.is_processing:
                    break
                scored_result = self.request_helloz_nsfw_score(frame_path, requests_module, helloz_nsfw_url, request_timeout)
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
                model_name='helloz_nsfw',
                threshold_percent=threshold_percent,
            )
        finally:
            self.cleanup_frame_dir(temp_dir, frame_paths)

    def create_helloz_nsfw_classifiers(self, existing_files, threshold_value, threshold_percent):
        import requests

        helloz_nsfw_url = self._get_helloz_nsfw_url()
        request_timeout = self._get_helloz_nsfw_request_timeout()
        return (
            partial(
                self.run_helloz_nsfw_image,
                existing_files=existing_files,
                threshold_value=threshold_value,
                threshold_percent=threshold_percent,
                requests_module=requests,
                helloz_nsfw_url=helloz_nsfw_url,
                request_timeout=request_timeout,
            ),
            partial(
                self.run_helloz_nsfw_video,
                existing_files=existing_files,
                threshold_value=threshold_value,
                threshold_percent=threshold_percent,
                requests_module=requests,
                helloz_nsfw_url=helloz_nsfw_url,
                request_timeout=request_timeout,
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

        # ------------------------------------------------------------------
        # Step 1 — Count supported files before starting workers.
        # This lets us show a real progress fraction and verify completion.
        # ------------------------------------------------------------------
        scan_start_time = datetime.now()
        total_files = count_supported_files(folder_path)
        GLib.idle_add(self.log_message, f'Found {total_files} supported file(s) to scan.')
        if total_files == 0:
            GLib.idle_add(self.log_message, 'No supported media files found. Scan complete.', 'warning')
            GLib.idle_add(self.finish_processing)
            return

        # Publish total to the mixin so the progress bar can switch from pulse
        # to a real fraction (done on the main thread via idle_add).
        GLib.idle_add(self._set_scan_total, total_files)

        # ------------------------------------------------------------------
        # Async save thread — receives (snapshot, session, path) from worker
        # threads so Excel writes never block file-processing workers.
        # ------------------------------------------------------------------
        from queue import Queue as _Queue
        _save_queue = _Queue()

        def _save_worker():
            while True:
                item = _save_queue.get()
                if item is None:
                    break
                snap, sess, path = item
                try:
                    save_nudity_report(snap, path, session_state=sess)
                except Exception as exc:
                    logging.exception('Intermediate report save failed: %s', exc)
                    GLib.idle_add(self.log_message, f'Warning: could not save intermediate report: {exc}', 'warning')

        save_thread = threading.Thread(target=_save_worker, daemon=True)
        save_thread.start()

        def _flush_intermediate(count):
            """Queue a partial report snapshot for async save, then push new results to UI."""
            snapshot = []
            try:
                with report_lock:
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
                _save_queue.put((snapshot, intermediate_session, report_path))
            except Exception as exc:
                logging.exception(
                    'Failed to queue intermediate report snapshot at count=%s, report_path=%s, snapshot_size=%s',
                    count,
                    report_path,
                    len(snapshot),
                )

            current_results = get_detected_results(snapshot)
            detected_count = len(current_results)
            fraction = count / total_files if total_files > 0 else 0.0
            GLib.idle_add(
                self._apply_intermediate_results,
                list(current_results),
                count,
                total_files,
                fraction,
            )
            GLib.idle_add(
                self.log_message,
                f'Progress: {count}/{total_files} files scanned — {detected_count} detection(s) so far.',
            )

        def _with_progress(fn):
            """Wrap a classifier to count files attempted while scanning is active.

            The counter is incremented in a ``finally`` block so that exceptions
            inside ``fn`` still count toward attempted files and don't inflate
            the "skipped" total.
            """
            def wrapper(file_path):
                if not self.is_processing:
                    return
                try:
                    fn(file_path)
                finally:
                    with count_lock:
                        files_processed[0] += 1
                        count = files_processed[0]
                    if count % update_interval == 0:
                        _flush_intermediate(count)
            return wrapper

        try:
            if model_name == constants.MODEL_NUDENET:
                classify_image, classify_video = self.create_nudenet_classifiers(
                    existing_files, threshold_value, threshold_percent,
                )
            else:
                classify_image, classify_video = self.create_helloz_nsfw_classifiers(
                    existing_files, threshold_value, threshold_percent,
                )

            classify_image = _with_progress(classify_image)
            classify_video = _with_progress(classify_video)

            classify_files_in_folder(
                folder_path,
                classify_image,
                classify_video,
                worker_count=self._get_worker_thread_count(),
                worker_timeout=self._get_worker_thread_timeout(),
            )

            processed = files_processed[0]
            skipped = total_files - processed
            self.detected_results = get_detected_results(nudity_report)
            self.last_report_path = report_path
            session_state = self.build_session_state()

            # Write the final definitive report (save thread already drained via finally).
            save_nudity_report(nudity_report, report_path, session_state=session_state)
            elapsed = datetime.now() - scan_start_time
            total_seconds = int(elapsed.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            elapsed_str = f'{minutes}m {seconds}s' if minutes else f'{seconds}s'
            GLib.idle_add(self.populate_results, self.detected_results)
            # stop_scanning() sets is_processing=False on the UI thread; process_files()
            # runs on a worker thread and never sets is_processing back to True, so if
            # is_processing is False here the user must have clicked Stop.
            was_stopped = not self.is_processing
            if was_stopped:
                GLib.idle_add(
                    self.log_message,
                    f'Scan stopped: {processed}/{total_files} file(s) processed, '
                    f'{len(self.detected_results)} detection(s) — took {elapsed_str}.',
                    'warning',
                )
                if skipped > 0:
                    GLib.idle_add(
                        self.log_message,
                        f'{skipped} file(s) were not scanned (scan stopped early).',
                        'warning',
                    )
            else:
                GLib.idle_add(
                    self.log_message,
                    f'Scan complete: {processed}/{total_files} file(s) processed, '
                    f'{len(self.detected_results)} detection(s) — took {elapsed_str}.',
                    'success',
                )
                if skipped > 0:
                    GLib.idle_add(
                        self.log_message,
                        f'Warning: {skipped} file(s) were skipped, timed out, or encountered errors.',
                        'warning',
                    )
            GLib.idle_add(self.refresh_scan_history)
        except Exception as error:
            GLib.idle_add(self.log_message, f'Error during processing: {error}', 'error')
        finally:
            # Always drain and terminate the async save thread before finish_processing
            # so there is no background writer touching report files after the scan ends.
            _save_queue.put(None)
            save_thread.join()
            GLib.idle_add(self.finish_processing)

    # ------------------------------------------------------------------
    # Progress pulse / fraction
    # ------------------------------------------------------------------

    def _start_progress_pulse(self):
        if self._pulse_source_id is None:
            self._pulse_source_id = GLib.timeout_add(50, self._pulse_tick)

    def _set_scan_total(self, total):
        """Called on the main thread once total supported files is known.
        Switches the progress bar from indeterminate pulse to a real fraction."""
        self._total_files = total

    def _pulse_tick(self):
        if self.is_processing:
            if self._progress_fraction > 0.0:
                # Real fraction available — show determinate progress.
                self.progress_bar.set_fraction(min(self._progress_fraction, 1.0))
            else:
                # Total not yet known — show indeterminate activity.
                self.progress_bar.pulse()
            return True
        self._pulse_source_id = None
        self.progress_bar.set_fraction(0.0)
        return False

    def _apply_intermediate_results(self, results, files_count, total_files, fraction):
        """Update the results view with a mid-scan snapshot (called on the main thread)."""
        if not self.is_processing:
            return

        # Append only the new items to avoid O(n) full rebuild on every flush.
        new_items = results[self._last_populated_count:]
        if new_items:
            self.append_results(new_items, start_index=self._last_populated_count)
            self._last_populated_count = len(results)
            self.detected_results = results

        detected_count = len(results)
        # Update the shared fraction; _pulse_tick will render it on the next tick.
        self._progress_fraction = fraction
        self.summary_label.set_text(
            f'{detected_count} explicit item(s) detected so far — '
            f'{files_count}/{total_files} file(s) scanned. Scan still running...'
            if detected_count else
            f'Scan running... {files_count}/{total_files} file(s) scanned. No detections yet.'
        )

    def finish_processing(self):
        self.is_processing = False
        self.status_label.set_text('Ready')
        self.set_controls_for_processing(False)
        self.update_result_action_state()
        self.open_report_button.set_sensitive(os.path.exists(self.last_report_path))

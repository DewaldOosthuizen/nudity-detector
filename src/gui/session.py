import json
import os

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gio, GLib, Gtk

from ..core import constants
from ..core.utils import (
    DEFAULT_REPORT_DIR,
    create_session_state,
    get_detected_results,
    get_report_path,
    load_report_entries,
    load_scan_session,
    make_scan_config,
    nudity_report,
    replace_nudity_report,
    save_nudity_report,
)


class SessionMixin:
    """Session persistence, report access, and scan config helpers.
    Mixed into NudityDetectorWindow."""

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_save_session_clicked(self, _button):
        self.save_session_dialog()

    def _on_load_session_clicked(self, _button):
        self.load_session_dialog()

    def _on_open_report_clicked(self, _button):
        self.open_report()

    def _on_open_reports_clicked(self, _button):
        self.open_reports_folder()

    # ------------------------------------------------------------------
    # Scan config / session state builders
    # ------------------------------------------------------------------

    def build_scan_config(self):
        return make_scan_config(
            source_folder=self.folder_entry.get_text().strip(),
            model_name=self._get_model(),
            threshold_percent=int(round(self.threshold_spin.get_value())),
            theme_mode=self._get_theme_mode(),
        )

    def build_session_state(self):
        return create_session_state(
            scan_config=self.build_scan_config(),
            results=list(self.detected_results),
        )

    # ------------------------------------------------------------------
    # Startup auto-load
    # ------------------------------------------------------------------

    def _find_latest_report_path(self):
        """Return the xlsx path from the most recent dated scan subfolder, or None."""
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
                self.log_message(f'Loaded previous session from {latest}')
            except (OSError, IOError, json.JSONDecodeError):
                self.log_message('No previous session could be loaded.', 'warning')

    # ------------------------------------------------------------------
    # Save dialog
    # ------------------------------------------------------------------

    def save_session_dialog(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Save scan report')
        dialog.set_initial_name(os.path.basename(self.last_report_path))
        xlsx_filter = Gtk.FileFilter()
        xlsx_filter.set_name('Excel Report (*.xlsx)')
        xlsx_filter.add_pattern('*.xlsx')
        filters = Gio.ListStore(item_type=Gtk.FileFilter)
        filters.append(xlsx_filter)
        dialog.set_filters(filters)
        dialog.save(self, None, self._on_save_session_done)

    def _on_save_session_done(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file:
                report_path = file.get_path()
                if not report_path.endswith(constants.XLSX_EXTENSION):
                    report_path += constants.XLSX_EXTENSION
                self.last_report_path = report_path
                save_nudity_report(nudity_report, report_path, session_state=self.build_session_state())
                self.open_report_button.set_sensitive(True)
                self.log_message(f'Saved session report to {report_path}', 'success')
        except GLib.Error:
            pass

    # ------------------------------------------------------------------
    # Load dialog
    # ------------------------------------------------------------------

    def load_session_dialog(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Load saved session')
        all_filter = Gtk.FileFilter()
        all_filter.set_name('Report or Session (*.xlsx, *.json)')
        all_filter.add_pattern('*.xlsx')
        all_filter.add_pattern('*.json')
        filters = Gio.ListStore(item_type=Gtk.FileFilter)
        filters.append(all_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_load_session_done)

    def _on_load_session_done(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.load_session_from_path(file.get_path(), show_feedback=True)
        except GLib.Error:
            pass

    def load_session_from_path(self, file_path, show_feedback):
        session_state = load_scan_session(file_path)
        report_path = (
            file_path
            if file_path.endswith(constants.XLSX_EXTENSION)
            else file_path.replace('_session.json', constants.XLSX_EXTENSION)
        )
        report_entries = load_report_entries(report_path) if os.path.exists(report_path) else []
        detected_results = session_state.get('results') or get_detected_results(report_entries)
        scan_config = session_state.get('scan_config', {})

        self.folder_entry.set_text(scan_config.get('source_folder', ''))
        if scan_config.get('model_name', 'nudenet') == constants.MODEL_NUDENET:
            self.nudenet_radio.set_active(True)
        else:
            self.helloz_nsfw_radio.set_active(True)

        theme = scan_config.get('theme_mode', 'system')
        try:
            idx = list(constants.SUPPORTED_THEMES).index(theme)
        except ValueError:
            idx = 0
        self.theme_dropdown.set_selected(idx)
        self._apply_theme(theme)

        self.threshold_spin.set_value(float(scan_config.get('threshold_percent', 60)))

        self.detected_results = detected_results
        replace_nudity_report(report_entries or detected_results)
        self.populate_results(self.detected_results)
        self.last_report_path = report_path
        self.open_report_button.set_sensitive(os.path.exists(report_path))

        if show_feedback:
            self.log_message(f'Loaded session from {file_path}', 'success')

        # Ensure the Scan tab is visible after loading a session
        if hasattr(self, 'view_stack'):
            self.view_stack.set_visible_child_name('scan')

    # ------------------------------------------------------------------
    # Open report / reports folder
    # ------------------------------------------------------------------

    def open_reports_folder(self):
        from ..core.utils import open_file_location
        success, error_message = open_file_location(DEFAULT_REPORT_DIR)
        if not success:
            self._show_error('Error', f'Could not open folder: {error_message}')
            self.log_message(f'Could not open reports folder: {error_message}', 'error')

    def open_report(self):
        if not os.path.exists(self.last_report_path):
            self._show_warning('Warning', 'No report has been saved yet.')
            return
        from ..core.utils import open_file
        success, error_message = open_file(self.last_report_path)
        if not success:
            self._show_error('Error', f'Could not open report: {error_message}')
            self.log_message(f'Could not open report: {error_message}', 'error')

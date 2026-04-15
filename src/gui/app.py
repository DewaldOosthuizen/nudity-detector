#!/usr/bin/env python3
"""
Nudity Detector GUI
A GTK4 + libadwaita graphical user interface for the nudity detection system.
Supports both NudeNet and DeepStack models with theme support and session persistence.
"""

import json
import os
import sys
from datetime import datetime

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk

from ..core import constants
from ..core.utils import get_report_path

from .dialogs import DialogsMixin
from .preview import PreviewMixin
from .result_item import ResultItem
from .results import ResultsMixin
from .scan_history import ScanHistoryMixin
from .scanning import ScanningMixin
from .session import SessionMixin


class NudityDetectorWindow(
    ScanHistoryMixin,
    ScanningMixin,
    PreviewMixin,
    SessionMixin,
    ResultsMixin,
    DialogsMixin,
    Adw.ApplicationWindow,
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(constants.GUI_WINDOW_TITLE)
        self.set_default_size(
            int(constants.GUI_WINDOW_GEOMETRY.split('x')[0]),
            int(constants.GUI_WINDOW_GEOMETRY.split('x')[1]),
        )
        self.set_size_request(constants.GUI_WINDOW_MIN_WIDTH, constants.GUI_WINDOW_MIN_HEIGHT)

        cfg = self._load_config()
        self._model = cfg.get('model', constants.MODEL_NUDENET)
        self._folder = cfg.get('last_source_folder', '')
        self._theme_mode = cfg.get('theme', constants.THEME_SYSTEM)
        self._threshold = float(cfg.get('threshold_percent', constants.DEFAULT_THRESHOLD_PERCENT))

        self.is_processing = False
        self.processing_thread = None
        self.detected_results = []
        self.last_report_path = self._find_latest_report_path() or get_report_path()
        self._pulse_source_id = None

        self._build_ui()
        self._apply_theme(self._theme_mode)
        self.load_initial_session()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(header_bar)

        # Tab stack
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        toolbar_view.set_content(self.view_stack)

        # ViewSwitcherTitle replaces the plain window title in the header bar
        switcher_title = Adw.ViewSwitcherTitle()
        switcher_title.set_stack(self.view_stack)
        header_bar.set_title_widget(switcher_title)

        # Scan tab (existing behaviour)
        scan_widget = self._build_scan_page()
        scan_page = self.view_stack.add_titled(scan_widget, 'scan', 'Scan')
        scan_page.set_icon_name('edit-find-symbolic')

        # All Scans tab
        history_widget = self._build_scan_history_tab()
        history_page = self.view_stack.add_titled(history_widget, 'all-scans', 'All Scans')
        history_page.set_icon_name('document-open-recent-symbolic')

    def _build_scan_page(self):
        """Build and return the Scan tab widget (the original single-page layout)."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(outer)
        scroll.set_vexpand(True)

        # --- Header ---
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_box.set_margin_bottom(12)
        title_label = Gtk.Label(label='Nudity Detector')
        title_label.add_css_class('title-1')
        title_label.set_xalign(0)
        subtitle_label = Gtk.Label(
            label='Modern scan workflow with saved sessions, theme control, and post-scan review.'
        )
        subtitle_label.add_css_class('dim-label')
        subtitle_label.set_xalign(0)
        subtitle_label.set_wrap(True)
        header_box.append(title_label)
        header_box.append(subtitle_label)
        outer.append(header_box)

        # --- Scan settings ---
        settings_box = Gtk.Frame()
        settings_box.set_label('Scan Settings')
        settings_box.set_margin_bottom(12)
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        settings_box.set_child(grid)
        outer.append(settings_box)

        # Theme row
        theme_label = Gtk.Label(label='Theme')
        theme_label.set_xalign(0)
        grid.attach(theme_label, 0, 0, 1, 1)

        self.theme_dropdown = Gtk.DropDown.new_from_strings(list(constants.SUPPORTED_THEMES))
        self.theme_dropdown.set_hexpand(True)
        try:
            idx = list(constants.SUPPORTED_THEMES).index(self._theme_mode)
        except ValueError:
            idx = 0
        self.theme_dropdown.set_selected(idx)
        self.theme_dropdown.connect('notify::selected', self._on_theme_selected)
        grid.attach(self.theme_dropdown, 1, 0, 1, 1)

        model_label = Gtk.Label(label='Model')
        model_label.set_xalign(0)
        grid.attach(model_label, 2, 0, 1, 1)

        model_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.nudenet_radio = Gtk.CheckButton(label='NudeNet')
        self.deepstack_radio = Gtk.CheckButton(label='DeepStack')
        self.deepstack_radio.set_group(self.nudenet_radio)
        if self._model == constants.MODEL_NUDENET:
            self.nudenet_radio.set_active(True)
        else:
            self.deepstack_radio.set_active(True)
        model_box.append(self.nudenet_radio)
        model_box.append(self.deepstack_radio)
        grid.attach(model_box, 3, 0, 1, 1)

        # Source folder row
        folder_label = Gtk.Label(label='Source Folder')
        folder_label.set_xalign(0)
        grid.attach(folder_label, 0, 1, 1, 1)

        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_text(self._folder)
        self.folder_entry.set_hexpand(True)
        grid.attach(self.folder_entry, 1, 1, 2, 1)

        self.browse_button = Gtk.Button(label='Browse…')
        self.browse_button.connect('clicked', self._on_browse_clicked)
        grid.attach(self.browse_button, 3, 1, 1, 1)

        # Threshold row
        threshold_label = Gtk.Label(label='Threshold %')
        threshold_label.set_xalign(0)
        grid.attach(threshold_label, 0, 2, 1, 1)

        adj = Gtk.Adjustment(
            value=self._threshold,
            lower=0,
            upper=100,
            step_increment=1,
            page_increment=10,
        )
        self.threshold_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        grid.attach(self.threshold_spin, 1, 2, 1, 1)

        threshold_help = Gtk.Label(
            label='Only detections at or above this confidence are treated as explicit.'
        )
        threshold_help.set_xalign(0)
        threshold_help.add_css_class('dim-label')
        threshold_help.set_wrap(True)
        threshold_help.set_hexpand(True)
        grid.attach(threshold_help, 2, 2, 2, 1)

        # --- Action buttons ---
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_box.set_margin_bottom(12)
        outer.append(action_box)

        self.start_button = Gtk.Button(label='Start Scan')
        self.start_button.add_css_class('suggested-action')
        self.start_button.connect('clicked', self._on_start_clicked)
        action_box.append(self.start_button)

        self.stop_button = Gtk.Button(label='Stop')
        self.stop_button.add_css_class('destructive-action')
        self.stop_button.set_sensitive(False)
        self.stop_button.connect('clicked', self._on_stop_clicked)
        action_box.append(self.stop_button)

        self.save_session_button = Gtk.Button(label='Save Session')
        self.save_session_button.connect('clicked', self._on_save_session_clicked)
        action_box.append(self.save_session_button)

        self.load_session_button = Gtk.Button(label='Load Session')
        self.load_session_button.connect('clicked', self._on_load_session_clicked)
        action_box.append(self.load_session_button)

        self.open_report_button = Gtk.Button(label='Open Report')
        self.open_report_button.set_sensitive(False)
        self.open_report_button.connect('clicked', self._on_open_report_clicked)
        action_box.append(self.open_report_button)

        self.open_reports_button = Gtk.Button(label='Open Reports Folder')
        self.open_reports_button.connect('clicked', self._on_open_reports_clicked)
        action_box.append(self.open_reports_button)

        self.clear_all_button = Gtk.Button(label='Clear All Results')
        self.clear_all_button.connect('clicked', self._on_clear_all_clicked)
        action_box.append(self.clear_all_button)

        # --- Results section ---
        results_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        results_frame = Gtk.Frame()
        results_frame.set_label('Detected Media Review')
        results_frame.set_vexpand(True)
        results_frame.set_margin_bottom(12)
        results_frame.set_child(results_outer)
        results_outer.set_margin_top(8)
        results_outer.set_margin_bottom(8)
        results_outer.set_margin_start(8)
        results_outer.set_margin_end(8)
        outer.append(results_frame)

        self.summary_label = Gtk.Label(label='No scan has been run yet.')
        self.summary_label.add_css_class('dim-label')
        self.summary_label.set_xalign(0)
        self.summary_label.set_margin_bottom(8)
        results_outer.append(self.summary_label)

        # Results table + preview side by side
        results_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        results_hbox.set_vexpand(True)
        results_outer.append(results_hbox)

        # ColumnView
        self._list_store = Gio.ListStore(item_type=ResultItem)
        selection_model = Gtk.SingleSelection(model=self._list_store)
        selection_model.set_autoselect(False)
        selection_model.connect('selection-changed', self._on_result_selection_changed)

        self.column_view = Gtk.ColumnView(model=selection_model)
        self.column_view.set_show_row_separators(True)
        self.column_view.set_vexpand(True)
        self.column_view.set_hexpand(True)

        for title, attr, min_width, center in [
            ('File',       'name',       220, False),
            ('Type',       'media_type',  90, True),
            ('Confidence', 'confidence', 110, True),
            ('Model',      'model_name', 100, True),
            ('Path',       'path',       430, False),
        ]:
            factory = Gtk.SignalListItemFactory()
            factory.connect('setup', self._col_setup)
            factory.connect('bind', self._col_bind_factory(attr, center))
            col = Gtk.ColumnViewColumn(title=title, factory=factory)
            col.set_fixed_width(min_width)
            col.set_expand(attr == 'path')
            self.column_view.append_column(col)

        cv_scroll = Gtk.ScrolledWindow()
        cv_scroll.set_vexpand(True)
        cv_scroll.set_hexpand(True)
        cv_scroll.set_child(self.column_view)
        results_hbox.append(cv_scroll)

        # Preview panel
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        preview_box.set_size_request(constants.THUMBNAIL_SIZE_PREVIEW[0] + 16, -1)
        preview_title = Gtk.Label(label='Thumbnail Preview')
        preview_title.set_xalign(0)
        preview_box.append(preview_title)

        self.thumbnail_picture = Gtk.Picture()
        self.thumbnail_picture.set_size_request(
            constants.THUMBNAIL_SIZE_PREVIEW_IMAGE[0],
            constants.THUMBNAIL_SIZE_PREVIEW_IMAGE[1],
        )
        self.thumbnail_picture.set_can_shrink(True)
        preview_box.append(self.thumbnail_picture)

        self._thumb_placeholder = Gtk.Label(label=constants.NO_THUMBNAIL_TEXT)
        self._thumb_placeholder.add_css_class('dim-label')
        self._thumb_placeholder.set_wrap(True)
        self._thumb_placeholder.set_xalign(0)
        preview_box.append(self._thumb_placeholder)

        self.thumbnail_meta_label = Gtk.Label(label='Select a result to preview.')
        self.thumbnail_meta_label.set_xalign(0)
        self.thumbnail_meta_label.set_wrap(True)
        preview_box.append(self.thumbnail_meta_label)

        results_hbox.append(preview_box)

        # Row action buttons
        result_action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        result_action_box.set_margin_top(8)
        results_outer.append(result_action_box)

        self.open_file_button = Gtk.Button(label='Open File')
        self.open_file_button.set_sensitive(False)
        self.open_file_button.connect('clicked', self._on_open_file_clicked)
        result_action_box.append(self.open_file_button)

        self.open_location_button = Gtk.Button(label='Open Location')
        self.open_location_button.set_sensitive(False)
        self.open_location_button.connect('clicked', self._on_open_location_clicked)
        result_action_box.append(self.open_location_button)

        self.delete_button = Gtk.Button(label='Delete Selected')
        self.delete_button.add_css_class('destructive-action')
        self.delete_button.set_sensitive(False)
        self.delete_button.connect('clicked', self._on_delete_clicked)
        result_action_box.append(self.delete_button)

        # --- Activity Log ---
        log_frame = Gtk.Frame()
        log_frame.set_label('Activity Log')
        log_frame.set_vexpand(True)
        log_frame.set_margin_bottom(12)
        outer.append(log_frame)

        log_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        log_inner.set_margin_top(8)
        log_inner.set_margin_bottom(8)
        log_inner.set_margin_start(8)
        log_inner.set_margin_end(8)
        log_frame.set_child(log_inner)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_min_content_height(150)
        log_inner.append(log_scroll)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.log_view.add_css_class('monospace')
        log_scroll.set_child(self.log_view)

        # --- Footer ---
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer_box.set_margin_top(4)
        outer.append(footer_box)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        footer_box.append(self.progress_bar)

        self.status_label = Gtk.Label(label='Ready')
        self.status_label.set_xalign(1)
        footer_box.append(self.status_label)

        return scroll

    # ------------------------------------------------------------------
    # ColumnView factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _col_setup(_factory, list_item):
        label = Gtk.Label()
        label.set_xalign(0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        list_item.set_child(label)

    @staticmethod
    def _col_bind_factory(attr, center):
        def bind(_factory, list_item):
            label = list_item.get_child()
            item = list_item.get_item()
            label.set_text(str(getattr(item, attr, '')))
            label.set_xalign(0.5 if center else 0.0)
        return bind

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        config_path = os.path.join(constants.CONFIG_DIR, constants.CONFIG_FILE_NAME)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _save_config(self):
        config_path = os.path.join(constants.CONFIG_DIR, constants.CONFIG_FILE_NAME)
        try:
            os.makedirs(constants.CONFIG_DIR, exist_ok=True)
            data = {
                'theme': self._get_theme_mode(),
                'model': self._get_model(),
                'threshold_percent': self.threshold_spin.get_value(),
                'last_source_folder': self.folder_entry.get_text().strip(),
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except (OSError, IOError):
            pass

    # ------------------------------------------------------------------
    # Widget state accessors
    # ------------------------------------------------------------------

    def _get_model(self):
        return constants.MODEL_NUDENET if self.nudenet_radio.get_active() else constants.MODEL_DEEPSTACK

    def _get_theme_mode(self):
        idx = self.theme_dropdown.get_selected()
        themes = list(constants.SUPPORTED_THEMES)
        return themes[idx] if idx < len(themes) else constants.THEME_SYSTEM

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self, theme_mode):
        style_manager = Adw.StyleManager.get_default()
        if theme_mode == constants.THEME_DARK:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme_mode == constants.THEME_LIGHT:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_theme_selected(self, _dropdown, _param=None):
        self._apply_theme(self._get_theme_mode())
        self._save_config()

    # ------------------------------------------------------------------
    # Scan control state
    # ------------------------------------------------------------------

    def set_controls_for_processing(self, processing):
        self.start_button.set_sensitive(not processing)
        self.stop_button.set_sensitive(processing)
        self.browse_button.set_sensitive(not processing)
        self.folder_entry.set_sensitive(not processing)
        self.theme_dropdown.set_sensitive(not processing)
        self.threshold_spin.set_sensitive(not processing)
        self.nudenet_radio.set_sensitive(not processing)
        self.deepstack_radio.set_sensitive(not processing)
        self.clear_all_button.set_sensitive(not processing)
        for button_name in (
            'save_session_button',
            'load_session_button',
            'open_report_button',
            'open_reports_button',
        ):
            if hasattr(self, button_name):
                getattr(self, button_name).set_sensitive(not processing)

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f'[{timestamp}] {message}\n'
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, line)
        end_iter = self.log_buffer.get_end_iter()
        self.log_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Folder browse
    # ------------------------------------------------------------------

    def _on_browse_clicked(self, _button):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select folder to scan')
        dialog.select_folder(self, None, self._on_browse_done)

    def _on_browse_done(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self.folder_entry.set_text(folder.get_path())
        except GLib.Error:
            pass


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class NudityDetectorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='io.github.dewaldoosthuizen.nuditydetector')
        self.connect('activate', self._on_activate)

    def _on_activate(self, _app):
        win = NudityDetectorWindow(application=self)
        win.connect('close-request', self._on_close_request)
        win.present()

    def _on_close_request(self, win):
        if win.is_processing:
            dialog = Adw.AlertDialog(heading='Quit', body='Scanning is in progress. Do you want to quit?')
            dialog.add_response('cancel', 'Cancel')
            dialog.add_response('quit', 'Quit')
            dialog.set_response_appearance('quit', Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect('response', lambda _d, r: self._handle_quit_response(win, r))
            dialog.present(win)
            return True
        win._save_config()
        return False

    def _handle_quit_response(self, win, response):
        if response == 'quit':
            win.is_processing = False
            win._save_config()
            if hasattr(win, 'processing_thread') and win.processing_thread is not None:
                win.processing_thread.join(timeout=constants.WORKER_THREAD_TIMEOUT)
            self.quit()


def main():
    app = NudityDetectorApp()
    app.run(sys.argv)


if __name__ == '__main__':
    main()

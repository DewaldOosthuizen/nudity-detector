import json
import os
import shutil
import threading
from datetime import datetime

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, GObject, Gio, Gtk

from ..core import constants
from ..core.utils import DEFAULT_REPORT_DIR, get_report_path, load_scan_session


class ScanRunItem(GObject.Object):
    """GObject model for a single row in the scan history ColumnView."""
    __gtype_name__ = 'ScanRunItem'

    def __init__(self, dir_name, display_date, model_name, result_count,
                 source_folder, session_path, report_path):
        super().__init__()
        self.dir_name = dir_name
        self.display_date = display_date
        self.model_name = model_name
        self.result_count = result_count   # str
        self.source_folder = source_folder
        self.session_path = session_path
        self.report_path = report_path


class ScanHistoryMixin:
    """Previous scan runs list with Load and Export actions.
    Mixed into NudityDetectorWindow."""

    # ------------------------------------------------------------------
    # Build tab widget
    # ------------------------------------------------------------------

    def _build_scan_history_tab(self):
        """Build and return the All Scans tab widget."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # Header
        header_label = Gtk.Label(label='Previous Scan Runs')
        header_label.add_css_class('title-1')
        header_label.set_xalign(0)
        header_label.set_margin_bottom(4)
        box.append(header_label)

        subtitle_label = Gtk.Label(
            label='Select a previous scan to load it into the Scan tab, or export its report.'
        )
        subtitle_label.add_css_class('dim-label')
        subtitle_label.set_xalign(0)
        subtitle_label.set_wrap(True)
        subtitle_label.set_margin_bottom(12)
        box.append(subtitle_label)

        # ColumnView
        self._history_store = Gio.ListStore(item_type=ScanRunItem)
        self._history_selection = Gtk.SingleSelection(model=self._history_store)
        self._history_selection.set_autoselect(False)
        self._history_selection.connect('selection-changed', self._on_history_selection_changed)

        self.history_column_view = Gtk.ColumnView(model=self._history_selection)
        self.history_column_view.set_show_row_separators(True)
        self.history_column_view.set_vexpand(True)
        self.history_column_view.set_hexpand(True)

        for title, attr, width, expand in [
            ('Date / Time',   'display_date',  200, False),
            ('Model',         'model_name',    100, False),
            ('Results',       'result_count',   80, False),
            ('Source Folder', 'source_folder', 300, True),
        ]:
            factory = Gtk.SignalListItemFactory()
            factory.connect('setup', self._hist_col_setup)
            factory.connect('bind', self._hist_col_bind_factory(attr))
            col = Gtk.ColumnViewColumn(title=title, factory=factory)
            col.set_fixed_width(width)
            col.set_expand(expand)
            self.history_column_view.append_column(col)

        cv_scroll = Gtk.ScrolledWindow()
        cv_scroll.set_vexpand(True)
        cv_scroll.set_hexpand(True)
        cv_scroll.set_child(self.history_column_view)
        box.append(cv_scroll)

        # Action bar
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_box.set_margin_top(12)
        box.append(action_box)

        self.history_load_button = Gtk.Button(label='Load Scan')
        self.history_load_button.add_css_class('suggested-action')
        self.history_load_button.set_sensitive(False)
        self.history_load_button.connect('clicked', self._on_history_load_clicked)
        action_box.append(self.history_load_button)

        self.history_export_button = Gtk.Button(label='Export Report')
        self.history_export_button.set_sensitive(False)
        self.history_export_button.connect('clicked', self._on_history_export_clicked)
        action_box.append(self.history_export_button)

        self.history_delete_button = Gtk.Button(label='Delete Scan')
        self.history_delete_button.add_css_class('destructive-action')
        self.history_delete_button.set_sensitive(False)
        self.history_delete_button.connect('clicked', self._on_history_delete_clicked)
        action_box.append(self.history_delete_button)

        self.history_clear_all_button = Gtk.Button(label='Clear All Scans')
        self.history_clear_all_button.add_css_class('destructive-action')
        self.history_clear_all_button.connect('clicked', self._on_history_clear_all_clicked)
        action_box.append(self.history_clear_all_button)

        # Populate immediately
        self.refresh_scan_history()

        return box

    # ------------------------------------------------------------------
    # ColumnView factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hist_col_setup(_factory, list_item):
        label = Gtk.Label()
        label.set_xalign(0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        list_item.set_child(label)

    @staticmethod
    def _hist_col_bind_factory(attr):
        def bind(_factory, list_item):
            label = list_item.get_child()
            item = list_item.get_item()
            label.set_text(str(getattr(item, attr, '')))
        return bind

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh_scan_history(self):
        """Re-read the reports/ directory and rebuild the history list store."""
        self._history_store.remove_all()
        report_dir = DEFAULT_REPORT_DIR
        if not os.path.isdir(report_dir):
            self._history_selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self._update_history_action_state(False)
            return

        subdirs = sorted(
            (d for d in os.listdir(report_dir)
             if os.path.isdir(os.path.join(report_dir, d))),
            reverse=True,
        )

        for subdir in subdirs:
            subdir_path = os.path.join(report_dir, subdir)
            session_path = os.path.join(subdir_path, 'nudity_report_session.json')
            report_path = get_report_path(subdir_path)

            # Parse display date from dirname (YYYY-MM-DD_HH-MM-SS)
            try:
                dt = datetime.strptime(subdir, constants.SCAN_RUN_DATE_FORMAT)
                display_date = dt.strftime('%Y-%m-%d  %H:%M:%S')
            except ValueError:
                display_date = subdir

            model_name = ''
            result_count = '0'
            source_folder = ''

            if os.path.exists(session_path):
                try:
                    with open(session_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    scan_cfg = data.get('scan_config', {})
                    model_name = scan_cfg.get('model_name', '')
                    source_folder = scan_cfg.get('source_folder', '')
                    result_count = str(len(data.get('results', [])))
                except (OSError, json.JSONDecodeError):
                    pass

            load_path = session_path if os.path.exists(session_path) else report_path
            item = ScanRunItem(
                dir_name=subdir,
                display_date=display_date,
                model_name=model_name,
                result_count=result_count,
                source_folder=source_folder,
                session_path=load_path,
                report_path=report_path,
            )
            self._history_store.append(item)

        self._history_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self._update_history_action_state(False)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_history_selection_changed(self, selection, _position, _n_items):
        has_selection = selection.get_selected() != Gtk.INVALID_LIST_POSITION
        self._update_history_action_state(has_selection)

    def _update_history_action_state(self, has_selection):
        self.history_load_button.set_sensitive(has_selection)
        self.history_export_button.set_sensitive(has_selection)
        self.history_delete_button.set_sensitive(has_selection)

    def _get_selected_history_item(self):
        selected = self._history_selection.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return None
        return self._history_store.get_item(selected)

    # ------------------------------------------------------------------
    # Load action
    # ------------------------------------------------------------------

    def _on_history_load_clicked(self, _button):
        item = self._get_selected_history_item()
        if item is None:
            return
        path = item.session_path
        if not os.path.exists(path):
            self._show_error('Error', f'Scan files not found:\n{path}')
            return
        self.load_session_from_path(path, show_feedback=True)
        self.view_stack.set_visible_child_name('scan')

    # ------------------------------------------------------------------
    # Export action
    # ------------------------------------------------------------------

    def _on_history_export_clicked(self, _button):
        item = self._get_selected_history_item()
        if item is None:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title('Export Report')
        dialog.set_initial_name('nudity_report.xlsx')
        xlsx_filter = Gtk.FileFilter()
        xlsx_filter.set_name('Excel Report (*.xlsx)')
        xlsx_filter.add_pattern('*.xlsx')
        filters = Gio.ListStore(item_type=Gtk.FileFilter)
        filters.append(xlsx_filter)
        dialog.set_filters(filters)
        dialog.save(self, None, lambda d, r: self._on_history_export_done(d, r, item))

    def _on_history_export_done(self, dialog, result, item):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
        except GLib.Error:
            return

        dest_path = file.get_path()
        if not dest_path:
            self._show_error(
                'Export Failed',
                'The selected export location is not a local filesystem path.'
            )
            return
        if not dest_path.endswith('.xlsx'):
            dest_path += '.xlsx'

        # Prefer copying the existing xlsx; regenerate from session JSON if absent
        if os.path.exists(item.report_path):
            shutil.copy2(item.report_path, dest_path)
            self.log_message(f'Exported report to {dest_path}', 'success')
        elif os.path.exists(item.session_path):
            self._export_from_session_json(item.session_path, dest_path)
        else:
            self._show_error('Export Failed', 'No report data found for this scan run.')
            self.log_message('Export failed: no report data found for this scan run.', 'error')

    # ------------------------------------------------------------------
    # Delete action
    # ------------------------------------------------------------------

    def _on_history_delete_clicked(self, _button):
        item = self._get_selected_history_item()
        if item is None:
            return
        dialog = Adw.AlertDialog(
            heading='Delete Scan',
            body=f'Permanently delete scan from {item.display_date}? This cannot be undone.',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('delete', 'Delete')
        dialog.set_response_appearance('delete', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.connect('response', self._on_history_delete_response, item)
        dialog.present(self)

    def _on_history_delete_response(self, _dialog, response, item):
        if response != 'delete':
            return
        subdir_path = os.path.join(DEFAULT_REPORT_DIR, item.dir_name)

        # Disable action buttons while deletion runs in the background.
        self.history_load_button.set_sensitive(False)
        self.history_export_button.set_sensitive(False)
        self.history_delete_button.set_sensitive(False)

        def _do_delete():
            try:
                shutil.rmtree(subdir_path)
            except OSError as exc:
                GLib.idle_add(self._show_error, 'Delete Failed', str(exc))
                GLib.idle_add(self._update_history_action_state, True)
                return
            GLib.idle_add(self.log_message, f'Deleted scan: {item.dir_name}', 'success')
            GLib.idle_add(self.refresh_scan_history)

        threading.Thread(target=_do_delete, daemon=True).start()

    def _on_history_clear_all_clicked(self, _button):
        dialog = Adw.AlertDialog(
            heading='Clear All Scans',
            body='This will permanently delete all previous scan reports and cannot be undone.\n\nContinue?',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('clear', 'Clear All')
        dialog.set_response_appearance('clear', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.connect('response', self._on_history_clear_all_response)
        dialog.present(self)

    def _on_history_clear_all_response(self, _dialog, response):
        if response != 'clear':
            return
        report_dir = DEFAULT_REPORT_DIR

        # Disable action buttons while deletion runs in the background.
        self.history_load_button.set_sensitive(False)
        self.history_export_button.set_sensitive(False)
        self.history_delete_button.set_sensitive(False)

        def _do_clear_all():
            errors = []
            if os.path.isdir(report_dir):
                for name in os.listdir(report_dir):
                    entry_path = os.path.join(report_dir, name)
                    try:
                        if os.path.isdir(entry_path):
                            shutil.rmtree(entry_path)
                        elif os.path.isfile(entry_path):
                            os.remove(entry_path)
                    except OSError as exc:
                        errors.append(str(exc))
            if errors:
                GLib.idle_add(
                    self._show_error,
                    'Clear Failed',
                    'Some items could not be deleted:\n' + '\n'.join(errors),
                )
                GLib.idle_add(self.log_message, f'Scan history partially cleared; {len(errors)} item(s) could not be deleted.', 'warning')
            else:
                GLib.idle_add(self.log_message, 'All scan history has been cleared.', 'success')
            GLib.idle_add(self.history_clear_all_button.set_sensitive, True)
            GLib.idle_add(self.refresh_scan_history)

        threading.Thread(target=_do_clear_all, daemon=True).start()

    def _export_from_session_json(self, session_path, dest_path):
        try:
            from ..core.models import ReportEntry
            from ..reporting.report_manager import ReportManager
            data = load_scan_session(session_path)
            entries = [ReportEntry.from_dict(r) for r in data.get('results', [])]
            ReportManager.save_entries(entries, dest_path)
            self.log_message(f'Exported report to {dest_path}', 'success')
        except Exception as exc:
            self._show_error('Export Failed', str(exc))
            self.log_message(f'Export failed: {exc}', 'error')

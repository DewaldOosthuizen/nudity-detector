import os

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, Gtk

from ..core import constants
from ..core.utils import (
    delete_file_safely,
    nudity_report,
    open_file,
    open_file_location,
    replace_nudity_report,
    save_nudity_report,
)
from .result_item import ResultItem


class ResultsMixin:
    """Results table population, row selection, row actions, and clear-all.
    Mixed into NudityDetectorWindow."""

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_open_file_clicked(self, _button):
        self.open_selected_file()

    def _on_open_location_clicked(self, _button):
        self.open_selected_location()

    def _on_delete_clicked(self, _button):
        self.delete_selected_result()

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def populate_results(self, results):
        self._list_store.remove_all()
        for index, entry in enumerate(results):
            item = ResultItem(
                index=index,
                name=os.path.basename(entry.get('file', '')),
                media_type=entry.get('media_type', 'unknown'),
                confidence=f"{float(entry.get('confidence_percent', 0)):.2f}%",
                model_name=entry.get('model_name', ''),
                path=entry.get('file', ''),
            )
            self._list_store.append(item)

        if results:
            self.summary_label.set_text(
                f'{len(results)} explicit item(s) detected. Review actions are available below.'
            )
        else:
            self.summary_label.set_text('No explicit media detected in the current session.')
        self.update_result_action_state()
        self.clear_thumbnail_preview()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_result_selection_changed(self, _selection_model, _position, _n_items):
        self.update_result_action_state()
        self.update_thumbnail_preview()

    def update_result_action_state(self):
        selection = self.column_view.get_model()
        has_selection = (
            isinstance(selection, Gtk.SingleSelection)
            and selection.get_selected() != Gtk.INVALID_LIST_POSITION
        )
        sensitive = has_selection and not self.is_processing
        self.open_file_button.set_sensitive(sensitive)
        self.open_location_button.set_sensitive(sensitive)
        self.delete_button.set_sensitive(sensitive)

    def get_selected_entry(self):
        selection = self.column_view.get_model()
        if not isinstance(selection, Gtk.SingleSelection):
            return None
        idx = selection.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION or idx >= len(self.detected_results):
            return None
        return self.detected_results[idx]

    # ------------------------------------------------------------------
    # Row actions
    # ------------------------------------------------------------------

    def open_selected_file(self):
        entry = self.get_selected_entry()
        if entry is None:
            return
        file_path = entry.get('file', '')
        if not os.path.exists(file_path):
            self._show_error('Error', f'File no longer exists: {file_path}')
            return
        success, error_message = open_file(file_path)
        if not success:
            self._show_error('Error', f'Could not open file: {error_message}')

    def open_selected_location(self):
        entry = self.get_selected_entry()
        if entry is None:
            return
        success, error_message = open_file_location(entry.get('file', ''))
        if not success:
            self._show_error('Error', f'Could not open location: {error_message}')

    def delete_selected_result(self):
        selection = self.column_view.get_model()
        if not isinstance(selection, Gtk.SingleSelection):
            return
        idx = selection.get_selected()
        entry = self.get_selected_entry()
        if entry is None:
            return
        self._ask_yes_no(
            'Delete detected file',
            f"Move this file to trash if possible?\n\n{entry.get('file', '')}",
            lambda: self._do_delete(idx, entry),
        )

    def _do_delete(self, index, entry):
        success, message = delete_file_safely(entry.get('file', ''))
        if not success:
            self._show_error('Delete failed', message)
            return
        del self.detected_results[index]
        remaining = [item for item in nudity_report if item.get('file') != entry.get('file')]
        replace_nudity_report(remaining)
        save_nudity_report(nudity_report, self.last_report_path, session_state=self.build_session_state())
        self.populate_results(self.detected_results)
        self.log_message(f"Deleted {entry.get('file', '')}. {message}")

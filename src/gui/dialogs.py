import gi
gi.require_version('Adw', '1')
from gi.repository import Adw


class DialogsMixin:
    """Alert dialog helpers.  Mixed into NudityDetectorWindow."""

    def _show_error(self, title, message):
        dialog = Adw.AlertDialog(heading=title, body=message)
        dialog.add_response('ok', 'OK')
        dialog.present(self)

    def _show_warning(self, title, message):
        dialog = Adw.AlertDialog(heading=title, body=message)
        dialog.add_response('ok', 'OK')
        dialog.present(self)

    def _ask_yes_no(self, title, message, on_yes):
        dialog = Adw.AlertDialog(heading=title, body=message)
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('yes', 'Yes')
        dialog.set_response_appearance('yes', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', lambda _d, response: on_yes() if response == 'yes' else None)
        dialog.present(self)

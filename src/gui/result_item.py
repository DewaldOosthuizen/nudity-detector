import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GObject


class ResultItem(GObject.Object):
    """GObject-backed model for a single row in the ColumnView results table."""
    __gtype_name__ = 'ResultItem'

    def __init__(self, index, name, media_type, confidence, model_name, path):
        super().__init__()
        self.index = index
        self.name = name
        self.media_type = media_type
        self.confidence = confidence
        self.model_name = model_name
        self.path = path

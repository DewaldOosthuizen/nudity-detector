import base64
from io import BytesIO

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gdk, GdkPixbuf

try:
    from PIL import Image
except ImportError:
    Image = None

from ..core import constants
from ..processing.media_processor import ThumbnailGenerator


class PreviewMixin:
    """Thumbnail loading and preview panel.  Mixed into NudityDetectorWindow."""

    def clear_thumbnail_preview(self):
        self.thumbnail_picture.set_paintable(None)
        self._thumb_placeholder.set_text(constants.NO_THUMBNAIL_TEXT)
        self.thumbnail_meta_label.set_text('Select a result to preview.')

    def update_thumbnail_preview(self):
        entry = self.get_selected_entry()
        if entry is None:
            self.clear_thumbnail_preview()
            return

        thumbnail_b64 = entry.get('thumbnail', '') or ''
        meta_text = (
            f"Type: {entry.get('media_type', 'unknown')}\n"
            f"Confidence: {entry.get('confidence_percent', 0):.2f}%\n"
            f"Model: {entry.get('model_name', '')}"
        )

        if Image is None:
            self._thumb_placeholder.set_text(constants.NO_THUMBNAIL_TEXT)
            self.thumbnail_meta_label.set_text(meta_text)
            return

        pil_image = self._load_preview_image(entry, thumbnail_b64)
        if pil_image is not None:
            try:
                pixbuf = self._pil_to_pixbuf(pil_image)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.thumbnail_picture.set_paintable(texture)
                self._thumb_placeholder.set_text('')
                self.thumbnail_meta_label.set_text(meta_text)
                return
            except Exception:
                pass

        self.thumbnail_picture.set_paintable(None)
        self._thumb_placeholder.set_text(
            constants.NO_THUMBNAIL_TEXT if not thumbnail_b64 else 'Thumbnail unavailable'
        )
        self.thumbnail_meta_label.set_text(meta_text)

    def _load_preview_image(self, entry, thumbnail_b64):
        """Return a PIL image for preview, sourcing from the original file when available."""
        file_path = entry.get('file', '')
        media_type = entry.get('media_type', '')
        if file_path:
            import os
            if os.path.exists(file_path):
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

    def _load_preview_from_file(self, file_path, media_type):
        """Load a full-quality PIL image from the original file."""
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
        """Decode and upscale the stored base64 thumbnail as a fallback."""
        resampler = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        img = Image.open(BytesIO(base64.b64decode(thumbnail_b64)))
        w, h = constants.THUMBNAIL_SIZE_PREVIEW_IMAGE
        if img.width < w and img.height < h:
            return img.resize((w, h), resampler)
        img.thumbnail((w, h), resampler)
        return img

    def _pil_to_pixbuf(self, pil_image):
        """Convert a PIL Image to a GdkPixbuf.Pixbuf via PNG bytes."""
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')
        buf = BytesIO()
        pil_image.save(buf, format='PNG')
        buf.seek(0)
        loader = GdkPixbuf.PixbufLoader.new_with_type('png')
        loader.write(buf.read())
        loader.close()
        return loader.get_pixbuf()

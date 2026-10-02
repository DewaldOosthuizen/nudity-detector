"""
Media processing utilities for the Nudity Detector application.
Handles frame extraction, thumbnail generation, and media type detection.
Reduces code duplication across GUI and CLI applications.
"""

import base64
import logging
import os
import shutil
import tempfile
from io import BytesIO
from typing import Generator, List, Optional, Tuple

import magic

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image
except ImportError:
    Image = None

from ..core import constants


def detect_media_type(file_path: str) -> str:
    """Detect media type via extension and magic-byte MIME verification.

    The extension is used as a cheap first-pass filter; the file's real
    content is then inspected via libmagic and cross-checked against a
    narrowly-scoped MIME allowlist before the media type is trusted. This
    prevents a payload crafted to exploit a parser CVE from being classified
    as image/video purely because of a spoofed extension.

    Args:
        file_path: Path to media file

    Returns:
        Media type: 'image', 'video', or 'unknown'
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext not in constants.SUPPORTED_EXTENSIONS:
        return constants.MEDIA_TYPE_UNKNOWN

    try:
        mime = magic.from_file(file_path, mime=True)
    except (OSError, magic.MagicException) as e:
        logging.warning('Could not determine MIME type for %s: %s', file_path, e)
        return constants.MEDIA_TYPE_UNKNOWN

    if ext in constants.IMAGE_EXTENSIONS and mime in constants.MIME_IMAGE_TYPES:
        return constants.MEDIA_TYPE_IMAGE
    if ext in constants.VIDEO_EXTENSIONS and mime in constants.MIME_VIDEO_TYPES:
        return constants.MEDIA_TYPE_VIDEO

    return constants.MEDIA_TYPE_UNKNOWN


def is_supported_file(file_path: str) -> bool:
    """Check if file is a supported media type."""
    return detect_media_type(file_path) != constants.MEDIA_TYPE_UNKNOWN


class FrameExtractor:
    """Extracts video frames with configurable sampling rate.

    Supports both eager extraction via extract() and lazy/streaming
    extraction via iter_frames(). Use iter_frames() for large videos
    to enable early-exit and avoid writing unneeded frames to disk.
    """

    def __init__(self, frame_rate: int = constants.VIDEO_FRAME_RATE, temp_prefix: str = ''):
        """Initialize frame extractor.

        Args:
            frame_rate: Extract every Nth frame (must be >= 1)
            temp_prefix: Prefix for temporary directory

        Raises:
            ValueError: If frame_rate is less than 1
        """
        if frame_rate < 1:
            raise ValueError(f'frame_rate must be >= 1, got {frame_rate}')
        self.frame_rate = frame_rate
        self.temp_prefix = temp_prefix or constants.FRAME_TEMP_DIR_PREFIX_CLI_NUDENET
        self.temp_dir: Optional[str] = None
        self.frame_paths: List[str] = []

    def extract(self, file_path: str) -> Tuple[Optional[str], List[str]]:
        """Extract all frames from a video file (eager, backward-compatible shim).

        Materializes every sampled frame as a JPEG in a temporary directory and
        returns the directory path plus the list of frame paths. Unlike
        iter_frames(), the temp directory is NOT cleaned up here (auto-cleanup
        would delete the files before the caller can read them) — the caller
        MUST call self.cleanup() after consuming the returned files.

        This method intentionally does NOT delegate to iter_frames() (which now
        auto-cleans on exit); it drives the private _iter_frames_core() which
        yields live files without removing the temp directory.

        Args:
            file_path: Path to the video file.

        Returns:
            Tuple of (temp_dir, frame_paths). On success temp_dir is the path to
            the temporary directory holding the frame JPEGs (caller must clean up)
            and frame_paths lists every written frame. temp_dir is None only when
            no directory was created or cleanup() has already run; it mirrors the
            Optional[str] type of self.temp_dir (line 92).

        Raises:
            RuntimeError: If OpenCV is unavailable, the video cannot be opened,
                or no frames could be extracted.
        """
        if cv2 is None:
            raise RuntimeError('OpenCV (cv2) is required for frame extraction but is not installed')
        self._prepare_temp_dir()
        success = False
        try:
            for _ in self._iter_frames_core(file_path):
                pass
            success = True
            return self.temp_dir, self.frame_paths
        finally:
            if not success:
                self.cleanup()

    def _iter_frames_core(self, file_path: str) -> Generator[str, None, None]:
        """Internal extraction generator — yields frame paths WITHOUT auto-cleanup.

        Manages its own VideoCapture (released in a finally). Does not create or
        remove self.temp_dir; the caller prepares temp_dir and owns cleanup.
        Kept separate from iter_frames() so extract() can consume every frame
        and return live files that persist for the caller, while iter_frames()
        wraps this core with automatic cleanup on every exit path.
        """
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise RuntimeError(f'Could not open video file: {file_path}')
        try:
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % self.frame_rate == 0:
                    frame_path = os.path.join(
                        self.temp_dir,
                        constants.FRAME_FILE_NAME_PATTERN.format(frame_count)
                    )
                    if cv2.imwrite(frame_path, frame):
                        self.frame_paths.append(frame_path)
                        yield frame_path
                    else:
                        logging.warning(
                            'Failed to write frame %d from %s — skipping',
                            frame_count, file_path
                        )
                frame_count += 1
            if not self.frame_paths:
                raise RuntimeError(f'No frames could be extracted from video file: {file_path}')
        finally:
            cap.release()

    def _prepare_temp_dir(self) -> None:
        """Reset any previous run and create a fresh temp directory for extraction."""
        self.cleanup()
        self.temp_dir = tempfile.mkdtemp(prefix=self.temp_prefix)
        self.frame_paths = []

    # Benchmark note: For a 60-min video at 30fps with VIDEO_FRAME_RATE=10,
    # early exit at frame N saves writing approximately (10800 - N) JPEG frames to disk.
    def iter_frames(self, file_path: str) -> Generator[str, None, None]:
        """Yield one frame path at a time for lazy/streaming processing.

        Writes each sampled frame to a temporary directory on demand and
        yields its path. The caller can break early to avoid writing
        unneeded frames.

        The temporary directory is owned by self.temp_dir and is automatically
        cleaned up on every exit path (normal completion, early break,
        GeneratorExit/GC, or any exception). Explicit self.cleanup() after
        iteration remains safe because cleanup() is idempotent.

        Args:
            file_path: Path to the video file.

        Yields:
            Absolute path to each written frame JPEG.

        Raises:
            RuntimeError: If OpenCV is unavailable or the video cannot be opened.
        """
        if cv2 is None:
            raise RuntimeError('OpenCV (cv2) is required for frame extraction but is not installed')

        self._prepare_temp_dir()
        try:
            yield from self._iter_frames_core(file_path)
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up temporary frame directory."""
        if self.temp_dir and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.frame_paths = []


class ThumbnailGenerator:
    """Generates base64-encoded thumbnails from images and videos."""

    @staticmethod
    def generate_from_image(file_path: str, size: Tuple[int, int] = constants.THUMBNAIL_SIZE_REPORT) -> Optional[str]:
        """Generate thumbnail from image file.

        Args:
            file_path: Path to image file
            size: Thumbnail (width, height)

        Returns:
            Base64-encoded PNG thumbnail, or None if generation fails
        """
        if Image is None:
            logging.debug('PIL not available for thumbnail generation: %s', file_path)
            return None

        try:
            with Image.open(file_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)

                # Ensure RGB mode
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Encode to base64
                buffer = BytesIO()
                img.save(buffer, format=constants.THUMBNAIL_FORMAT)
                buffer.seek(0)
                encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return encoded
        except Exception as e:
            logging.warning('Failed to generate image thumbnail for %s: %s', file_path, e)
            return None

    @staticmethod
    def generate_from_video(file_path: str, size: Tuple[int, int] = constants.THUMBNAIL_SIZE_REPORT) -> Optional[str]:
        """Generate thumbnail from video file at progress point.

        Args:
            file_path: Path to video file
            size: Thumbnail (width, height)

        Returns:
            Base64-encoded PNG thumbnail, or None if generation fails
        """
        if cv2 is None:
            logging.debug('OpenCV not available for video thumbnail generation: %s', file_path)
            return None

        if Image is None:
            logging.debug('PIL not available for video thumbnail generation: %s', file_path)
            return None

        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                logging.warning('Could not open video file: %s', file_path)
                return None

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                logging.warning('Video has no frames: %s', file_path)
                cap.release()
                return None

            # Extract frame at progress point
            frame_index = max(0, int(total_frames * constants.THUMBNAIL_IMAGE_INDEX))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logging.warning('Could not extract frame from video: %s', file_path)
                return None

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail(size, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)

            # Encode to base64
            buffer = BytesIO()
            img.save(buffer, format=constants.THUMBNAIL_FORMAT)
            buffer.seek(0)
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return encoded
        except Exception as e:
            logging.warning('Failed to generate video thumbnail for %s: %s', file_path, e)
            return None

    @staticmethod
    def generate(file_path: str, media_type: Optional[str] = None, size: Tuple[int, int] = constants.THUMBNAIL_SIZE_REPORT) -> Optional[str]:
        """Generate thumbnail for image or video.

        Args:
            file_path: Path to media file
            media_type: 'image', 'video', or None (auto-detect)
            size: Thumbnail size

        Returns:
            Base64-encoded thumbnail or None
        """
        if not os.path.exists(file_path):
            return None

        media_type = media_type or detect_media_type(file_path)

        if media_type == constants.MEDIA_TYPE_IMAGE:
            return ThumbnailGenerator.generate_from_image(file_path, size)
        elif media_type == constants.MEDIA_TYPE_VIDEO:
            return ThumbnailGenerator.generate_from_video(file_path, size)

        return None

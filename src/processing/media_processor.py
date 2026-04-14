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
from typing import Optional, Tuple, List

import cv2

try:
    from PIL import Image
except ImportError:
    Image = None

from ..core import constants


def detect_media_type(file_path: str) -> str:
    """Detect media type from file extension.

    Args:
        file_path: Path to media file

    Returns:
        Media type: 'image', 'video', or 'unknown'
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in constants.IMAGE_EXTENSIONS:
        return constants.MEDIA_TYPE_IMAGE
    if ext in constants.VIDEO_EXTENSIONS:
        return constants.MEDIA_TYPE_VIDEO

    return constants.MEDIA_TYPE_UNKNOWN


def is_supported_file(file_path: str) -> bool:
    """Check if file is a supported media type."""
    return detect_media_type(file_path) != constants.MEDIA_TYPE_UNKNOWN


class FrameExtractor:
    """Extracts video frames with configurable sampling rate."""

    def __init__(self, frame_rate: int = constants.VIDEO_FRAME_RATE, temp_prefix: str = ''):
        """Initialize frame extractor.

        Args:
            frame_rate: Extract every Nth frame
            temp_prefix: Prefix for temporary directory
        """
        self.frame_rate = frame_rate
        self.temp_prefix = temp_prefix or constants.FRAME_TEMP_DIR_PREFIX_CLI_NUDENET
        self.temp_dir: Optional[str] = None
        self.frame_paths: List[str] = []

    def extract(self, file_path: str) -> Tuple[str, List[str]]:
        """Extract frames from video file.

        Args:
            file_path: Path to video file

        Returns:
            Tuple of (temp_dir, frame_paths)

        Raises:
            RuntimeError: If video cannot be opened
        """
        self.temp_dir = tempfile.mkdtemp(prefix=self.temp_prefix)
        self.frame_paths = []

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            self.cleanup()
            raise RuntimeError(f'Could not open video file: {file_path}')

        try:
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % self.frame_rate == 0:
                    frame_path = os.path.join(self.temp_dir, constants.FRAME_FILE_NAME_PATTERN.format(frame_count))
                    cv2.imwrite(frame_path, frame)
                    self.frame_paths.append(frame_path)

                frame_count += 1
        finally:
            cap.release()

        return self.temp_dir, self.frame_paths

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

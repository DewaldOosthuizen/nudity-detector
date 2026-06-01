"""Tests for src/processing/media_processor.py"""
import sys
import pytest
from unittest.mock import MagicMock

# Stub cv2 only if it is not already available (e.g. imported by an earlier
# test module in the same pytest session).  Unconditionally replacing a real
# cv2 import would pollute sys.modules for subsequent test files and cause
# tests that need the real cv2 (test_frame_extractor_issue15.py) to either
# run against a mock or incorrectly evaluate HAS_CV2 = True while
# media_processor.cv2 is still None.
if "cv2" not in sys.modules:
    try:
        import cv2  # noqa: F401 – check whether the real package is present
    except ImportError:
        sys.modules["cv2"] = MagicMock()

from src.processing.media_processor import detect_media_type, is_supported_file, FrameExtractor
from src.core import constants


@pytest.mark.parametrize("file_path,expected", [
    ("photo.jpg", constants.MEDIA_TYPE_IMAGE),
    ("photo.JPEG", constants.MEDIA_TYPE_IMAGE),
    ("clip.mp4", constants.MEDIA_TYPE_VIDEO),
    ("movie.MKV", constants.MEDIA_TYPE_VIDEO),
    ("document.pdf", constants.MEDIA_TYPE_UNKNOWN),
    ("no_extension", constants.MEDIA_TYPE_UNKNOWN),
])
def test_detect_media_type(file_path, expected):
    assert detect_media_type(file_path) == expected


def test_is_supported_file_true():
    assert is_supported_file("image.png") is True


def test_is_supported_file_false():
    assert is_supported_file("file.txt") is False


def test_frame_extractor_invalid_frame_rate():
    with pytest.raises(ValueError, match="frame_rate must be >= 1"):
        FrameExtractor(frame_rate=0)


def test_frame_extractor_default_frame_rate():
    extractor = FrameExtractor()
    assert extractor.frame_rate >= 1

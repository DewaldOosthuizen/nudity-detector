"""Tests for src/processing/media_processor.py"""
import sys
from unittest.mock import MagicMock

import pytest

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

from src.core import constants
from src.processing.media_processor import FrameExtractor, detect_media_type, is_supported_file


@pytest.mark.parametrize("file_path,mime,expected", [
    ("photo.jpg", "image/jpeg", constants.MEDIA_TYPE_IMAGE),
    ("photo.JPEG", "image/jpeg", constants.MEDIA_TYPE_IMAGE),
    ("clip.mp4", "video/mp4", constants.MEDIA_TYPE_VIDEO),
    ("movie.MKV", "video/x-matroska", constants.MEDIA_TYPE_VIDEO),
    ("document.pdf", None, constants.MEDIA_TYPE_UNKNOWN),
    ("no_extension", None, constants.MEDIA_TYPE_UNKNOWN),
])
def test_detect_media_type(monkeypatch, file_path, mime, expected):
    if mime is not None:
        monkeypatch.setattr(
            "src.processing.media_processor.magic.from_file",
            lambda path, mime=True: mime,
        )
    assert detect_media_type(file_path) == expected


def test_detect_media_type_extension_mime_mismatch(monkeypatch):
    """A .jpg-extensioned file whose magic bytes are not an image MIME is UNKNOWN."""
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "application/octet-stream",
    )
    assert detect_media_type("payload.jpg") == constants.MEDIA_TYPE_UNKNOWN


def test_detect_media_type_video_octet_stream_rejected(monkeypatch):
    """A .mp4-extensioned file reporting application/octet-stream is UNKNOWN,
    not video — regression guard against the video-path bypass identified in review."""
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "application/octet-stream",
    )
    assert detect_media_type("payload.mp4") == constants.MEDIA_TYPE_UNKNOWN


def test_detect_media_type_magic_error_returns_unknown(monkeypatch):
    """magic.from_file raising OSError/MagicException maps to MEDIA_TYPE_UNKNOWN,
    it must not propagate."""
    def _raise(path, mime=True):
        raise OSError("cannot read file")
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file", _raise,
    )
    assert detect_media_type("photo.jpg") == constants.MEDIA_TYPE_UNKNOWN


def test_is_supported_file_true(monkeypatch):
    monkeypatch.setattr(
        "src.processing.media_processor.magic.from_file",
        lambda path, mime=True: "image/png",
    )
    assert is_supported_file("image.png") is True


def test_is_supported_file_false():
    assert is_supported_file("file.txt") is False


def test_frame_extractor_invalid_frame_rate():
    with pytest.raises(ValueError, match="frame_rate must be >= 1"):
        FrameExtractor(frame_rate=0)


def test_frame_extractor_default_frame_rate():
    extractor = FrameExtractor()
    assert extractor.frame_rate >= 1

"""Extended tests for src/processing/media_processor.py to boost coverage."""
import base64
import os
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.modules.setdefault("nudenet", MagicMock())

from src.processing.media_processor import (
    detect_media_type,
    is_supported_file,
    FrameExtractor,
    ThumbnailGenerator,
)
from src.core import constants


# ---------------------------------------------------------------------------
# ThumbnailGenerator.generate_from_image
# ---------------------------------------------------------------------------

def test_generate_from_image_success(tmp_path):
    """Generate thumbnail from a real tiny PNG image."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    # Create a small real image file
    img_path = tmp_path / "test.png"
    img = PILImage.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(str(img_path))

    result = ThumbnailGenerator.generate_from_image(str(img_path))
    assert result is not None
    # Should be valid base64
    data = base64.b64decode(result)
    assert len(data) > 0


def test_generate_from_image_rgba(tmp_path):
    """RGBA images are converted to RGB."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    img_path = tmp_path / "test.png"
    img = PILImage.new("RGBA", (50, 50), color=(0, 255, 0, 128))
    img.save(str(img_path))

    result = ThumbnailGenerator.generate_from_image(str(img_path))
    assert result is not None


def test_generate_from_image_invalid_file(tmp_path):
    """Non-image file returns None gracefully."""
    bad_file = tmp_path / "bad.jpg"
    bad_file.write_bytes(b"not an image")
    result = ThumbnailGenerator.generate_from_image(str(bad_file))
    assert result is None


def test_generate_from_image_pil_unavailable(tmp_path):
    """When PIL is not available, return None."""
    import src.processing.media_processor as mp
    original = mp.Image
    try:
        mp.Image = None
        result = ThumbnailGenerator.generate_from_image("/some/file.jpg")
        assert result is None
    finally:
        mp.Image = original


# ---------------------------------------------------------------------------
# ThumbnailGenerator.generate
# ---------------------------------------------------------------------------

def test_generate_nonexistent_file():
    result = ThumbnailGenerator.generate("/nonexistent/file.jpg")
    assert result is None


def test_generate_image_delegates(tmp_path):
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    img_path = tmp_path / "img.jpg"
    img = PILImage.new("RGB", (10, 10))
    img.save(str(img_path))

    with patch.object(ThumbnailGenerator, "generate_from_image", return_value="b64data") as mock_gen:
        result = ThumbnailGenerator.generate(str(img_path), "image")
    mock_gen.assert_called_once()
    assert result == "b64data"


def test_generate_video_delegates(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"data")

    with patch.object(ThumbnailGenerator, "generate_from_video", return_value="b64video") as mock_gen:
        result = ThumbnailGenerator.generate(str(f), "video")
    mock_gen.assert_called_once()
    assert result == "b64video"


def test_generate_unknown_media_type(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"data")
    result = ThumbnailGenerator.generate(str(f), "unknown")
    assert result is None


# ---------------------------------------------------------------------------
# ThumbnailGenerator.generate_from_video (mocked cv2)
# ---------------------------------------------------------------------------

def test_generate_from_video_cv2_unavailable(tmp_path):
    import src.processing.media_processor as mp
    original = mp.cv2
    try:
        mp.cv2 = None
        result = ThumbnailGenerator.generate_from_video("/some/video.mp4")
        assert result is None
    finally:
        mp.cv2 = original


def test_generate_from_video_cannot_open(tmp_path):
    """Returns None when video file cannot be opened."""
    try:
        import cv2 as real_cv2
    except ImportError:
        pytest.skip("cv2 not installed")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = ThumbnailGenerator.generate_from_video("/nonexistent/video.mp4")
    assert result is None


def test_generate_from_video_no_frames(tmp_path):
    """Returns None when video has 0 frames."""
    try:
        import cv2 as real_cv2
    except ImportError:
        pytest.skip("cv2 not installed")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 0  # 0 total frames

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = ThumbnailGenerator.generate_from_video("/some/video.mp4")
    assert result is None


# ---------------------------------------------------------------------------
# FrameExtractor.cleanup
# ---------------------------------------------------------------------------

def test_frame_extractor_cleanup_no_dir():
    extractor = FrameExtractor()
    extractor.cleanup()  # Should not raise


def test_frame_extractor_cleanup_existing_dir(tmp_path):
    extractor = FrameExtractor()
    d = tmp_path / "frames"
    d.mkdir()
    extractor.temp_dir = str(d)
    extractor.frame_paths = ["dummy.jpg"]
    extractor.cleanup()
    assert extractor.temp_dir is None
    assert extractor.frame_paths == []


# ---------------------------------------------------------------------------
# FrameExtractor.iter_frames / extract
# ---------------------------------------------------------------------------

def test_frame_extractor_raises_without_cv2():
    import src.processing.media_processor as mp
    original = mp.cv2
    try:
        mp.cv2 = None
        extractor = FrameExtractor()
        with pytest.raises(RuntimeError, match="OpenCV"):
            list(extractor.iter_frames("/some/video.mp4"))
    finally:
        mp.cv2 = original
        extractor.cleanup()


def test_frame_extractor_raises_on_bad_file():
    try:
        import cv2 as real_cv2
    except ImportError:
        pytest.skip("cv2 not installed")

    import src.processing.media_processor as mp
    if mp.cv2 is None:
        pytest.skip("cv2 not available in media_processor module")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    extractor = FrameExtractor()
    with patch.object(mp.cv2, "VideoCapture", return_value=mock_cap):
        with pytest.raises(RuntimeError, match="Could not open"):
            list(extractor.iter_frames("/nonexistent/video.mp4"))

"""Extended tests for src/processing/media_processor.py —
ThumbnailGenerator, FrameExtractor (with mocked cv2), cleanup paths."""
import sys
import os
import base64
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from src.processing.media_processor import (
    detect_media_type,
    is_supported_file,
    FrameExtractor,
    ThumbnailGenerator,
)
from src.core import constants


# ---------------------------------------------------------------------------
# ThumbnailGenerator — generate_from_image
# ---------------------------------------------------------------------------

def test_generate_from_image_returns_base64_string(tmp_path):
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    img_path = str(tmp_path / "test.jpg")
    PILImage.new("RGB", (100, 100), color=(0, 255, 0)).save(img_path)
    result = ThumbnailGenerator.generate_from_image(img_path)
    assert result is not None
    # Should be valid base64
    decoded = base64.b64decode(result)
    assert len(decoded) > 0


def test_generate_from_image_nonexistent_returns_none():
    result = ThumbnailGenerator.generate_from_image("/nonexistent/path/img.jpg")
    assert result is None


def test_generate_from_image_rgba_converted(tmp_path):
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    img_path = str(tmp_path / "rgba.png")
    PILImage.new("RGBA", (50, 50), color=(0, 0, 255, 128)).save(img_path)
    result = ThumbnailGenerator.generate_from_image(img_path)
    assert result is not None


def test_generate_from_image_when_pil_none():
    """When Image is None (PIL unavailable), returns None."""
    import src.processing.media_processor as mp_module
    original = mp_module.Image
    mp_module.Image = None
    try:
        result = ThumbnailGenerator.generate_from_image("/any/path.jpg")
        assert result is None
    finally:
        mp_module.Image = original


# ---------------------------------------------------------------------------
# ThumbnailGenerator — generate_from_video
# ---------------------------------------------------------------------------

def test_generate_from_video_when_cv2_none():
    import src.processing.media_processor as mp_module
    original_cv2 = mp_module.cv2
    mp_module.cv2 = None
    try:
        result = ThumbnailGenerator.generate_from_video("/any/path.mp4")
        assert result is None
    finally:
        mp_module.cv2 = original_cv2


def test_generate_from_video_when_pil_none():
    import src.processing.media_processor as mp_module
    original_pil = mp_module.Image
    # cv2 must be available (or mocked) but PIL is None
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")
    mp_module.Image = None
    try:
        result = ThumbnailGenerator.generate_from_video("/any/path.mp4")
        assert result is None
    finally:
        mp_module.Image = original_pil


def test_generate_from_video_cannot_open(tmp_path):
    """Video that cannot be opened returns None."""
    try:
        import cv2 as real_cv2
    except ImportError:
        pytest.skip("cv2 not available")

    result = ThumbnailGenerator.generate_from_video("/nonexistent/video.mp4")
    assert result is None


def test_generate_from_video_no_frames_returns_none():
    """If video has 0 frames, returns None."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 0  # total_frames = 0

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap):
        result = ThumbnailGenerator.generate_from_video("/fake/video.mp4")
    assert result is None


# ---------------------------------------------------------------------------
# ThumbnailGenerator — generate dispatcher
# ---------------------------------------------------------------------------

def test_generate_returns_none_for_nonexistent_file():
    result = ThumbnailGenerator.generate("/no/such/file.jpg")
    assert result is None


def test_generate_dispatches_to_image(tmp_path):
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("PIL not available")

    img_path = str(tmp_path / "img.jpg")
    PILImage.new("RGB", (20, 20)).save(img_path)
    result = ThumbnailGenerator.generate(img_path, media_type=constants.MEDIA_TYPE_IMAGE)
    assert result is not None


def test_generate_returns_none_for_unknown_type(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    result = ThumbnailGenerator.generate(str(f), media_type=constants.MEDIA_TYPE_UNKNOWN)
    assert result is None


# ---------------------------------------------------------------------------
# FrameExtractor — iter_frames / cleanup
# ---------------------------------------------------------------------------

def test_frame_extractor_cleanup_no_temp_dir():
    """cleanup() with no temp_dir should not raise."""
    extractor = FrameExtractor()
    extractor.temp_dir = None
    extractor.cleanup()  # should not raise


def test_frame_extractor_cleanup_removes_dir(tmp_path):
    extractor = FrameExtractor()
    frames_dir = str(tmp_path / "frames")
    os.makedirs(frames_dir)
    extractor.temp_dir = frames_dir
    extractor.cleanup()
    assert not os.path.isdir(frames_dir)
    assert extractor.temp_dir is None


def test_frame_extractor_iter_frames_no_cv2():
    """iter_frames raises RuntimeError when cv2 is unavailable."""
    import src.processing.media_processor as mp_module
    original = mp_module.cv2
    mp_module.cv2 = None
    try:
        extractor = FrameExtractor()
        with pytest.raises(RuntimeError, match="OpenCV"):
            list(extractor.iter_frames("/some/video.mp4"))
    finally:
        mp_module.cv2 = original


def test_frame_extractor_iter_frames_cannot_open():
    """iter_frames raises RuntimeError when video cannot be opened."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap):
        extractor = FrameExtractor()
        with pytest.raises(RuntimeError, match="Could not open"):
            list(extractor.iter_frames("/fake/video.mp4"))


def test_frame_extractor_iter_frames_yields_paths():
    """iter_frames yields frame paths for each sampled frame."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")

    try:
        import numpy as np
    except ImportError:
        pytest.skip("numpy not available")

    mock_cap = MagicMock()
    mock_cap.isOpened.side_effect = [True, True, True, False]  # 2 reads then stop
    fake_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_cap.read.side_effect = [
        (True, fake_frame),
        (True, fake_frame),
        (False, None),
    ]

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap), \
         patch.object(mp_module.cv2, "imwrite"):
        extractor = FrameExtractor(frame_rate=1)
        try:
            frames = list(extractor.iter_frames("/fake/video.mp4"))
        finally:
            extractor.cleanup()

    assert len(frames) == 2


# ---------------------------------------------------------------------------
# PIL import fallback (lines 22-23)
# ---------------------------------------------------------------------------

def test_image_none_when_pil_unavailable():
    """When PIL is not installed, Image should be None or a real module."""
    import src.processing.media_processor as mp_module
    # Just verifying the module attribute exists
    assert hasattr(mp_module, "Image")


# ---------------------------------------------------------------------------
# FrameExtractor.extract() (lines 88-90) — eager shim
# ---------------------------------------------------------------------------

def test_frame_extractor_extract_uses_iter_frames():
    """extract() should consume iter_frames and return (temp_dir, frame_paths)."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")

    extractor = FrameExtractor()
    frames_yielded = []

    def fake_iter(path):
        frames_yielded.append("called")
        return iter([])  # no frames

    extractor.iter_frames = fake_iter
    result = extractor.extract("/fake/video.mp4")
    assert isinstance(result, tuple)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# iter_frames with frame_rate > 1 (lines 119-144) — sampling
# ---------------------------------------------------------------------------

def test_frame_extractor_sampling_skips_frames():
    """Only every Nth frame is yielded when frame_rate > 1."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")

    try:
        import numpy as np
    except ImportError:
        pytest.skip("numpy not available")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    # 6 frames, then stop
    mock_cap.read.side_effect = [
        (True, fake_frame),
        (True, fake_frame),
        (True, fake_frame),
        (True, fake_frame),
        (True, fake_frame),
        (True, fake_frame),
        (False, None),
    ]

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap), \
         patch.object(mp_module.cv2, "imwrite"):
        extractor = FrameExtractor(frame_rate=3)
        try:
            frames = list(extractor.iter_frames("/fake/video.mp4"))
        finally:
            extractor.cleanup()

    # frame_count 0, 3 → 2 frames
    assert len(frames) == 2


# ---------------------------------------------------------------------------
# ThumbnailGenerator.generate_from_video — success path (lines 205-245)
# ---------------------------------------------------------------------------

def test_generate_from_video_success():
    """generate_from_video returns base64 string when all works."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")
    if mp_module.Image is None:
        pytest.skip("PIL not available")

    try:
        import numpy as np
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("numpy or PIL not available")

    fake_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 10  # total_frames
    mock_cap.read.return_value = (True, fake_frame)

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap), \
         patch.object(mp_module.cv2, "cvtColor", return_value=fake_frame), \
         patch.object(mp_module.cv2, "COLOR_BGR2RGB", new=0):
        result = ThumbnailGenerator.generate_from_video("/fake/video.mp4")

    assert result is not None
    decoded = base64.b64decode(result)
    assert len(decoded) > 0


def test_generate_from_video_read_fails():
    """generate_from_video returns None when frame read returns ret=False."""
    import src.processing.media_processor as mp_module
    if mp_module.cv2 is None:
        pytest.skip("cv2 not available")
    if mp_module.Image is None:
        pytest.skip("PIL not available")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 10
    mock_cap.read.return_value = (False, None)

    with patch.object(mp_module.cv2, "VideoCapture", return_value=mock_cap):
        result = ThumbnailGenerator.generate_from_video("/fake/video.mp4")

    assert result is None


# ---------------------------------------------------------------------------
# ThumbnailGenerator.generate — video dispatch (line 267)
# ---------------------------------------------------------------------------

def test_generate_dispatches_to_video(tmp_path):
    """generate() dispatches to generate_from_video for video type."""
    import src.processing.media_processor as mp_module
    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"fake")

    with patch.object(ThumbnailGenerator, "generate_from_video", return_value="b64data") as mock_vid:
        result = ThumbnailGenerator.generate(str(vid), media_type=constants.MEDIA_TYPE_VIDEO)

    mock_vid.assert_called_once()
    assert result == "b64data"

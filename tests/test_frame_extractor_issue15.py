"""Tests for issue #15 - FrameExtractor lazy/streaming frame extraction."""
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

# We need cv2 for synthetic video creation
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.processing.media_processor import FrameExtractor


def create_synthetic_video(path, num_frames=30, width=64, height=64, fps=30):
    """Write a small synthetic video with num_frames frames."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), i * 8 % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()


@pytest.mark.skipif(not HAS_CV2, reason='cv2 not available')
def test_iter_frames_early_exit_writes_only_n_frames(tmp_path):
    """Test that breaking early from iter_frames only writes N frames to disk."""
    video_path = str(tmp_path / 'test_video.mp4')
    # 30 frames at frame_rate=1 -> 30 sampled frames; we break at 3
    create_synthetic_video(video_path, num_frames=30)

    extractor = FrameExtractor(frame_rate=1)
    count = 0
    for frame_path in extractor.iter_frames(video_path):
        count += 1
        if count == 3:
            break

    # Exactly 3 JPEG files should exist at break point
    temp_dir = extractor.temp_dir
    assert temp_dir is not None
    jpegs = [f for f in os.listdir(temp_dir) if f.endswith('.jpg')]
    assert len(jpegs) == 3

    extractor.cleanup()
    assert not os.path.isdir(temp_dir)


@pytest.mark.skipif(not HAS_CV2, reason='cv2 not available')
def test_iter_frames_reuse_does_not_accumulate_stale_paths(tmp_path):
    """Test that calling iter_frames twice resets state (no stale paths)."""
    video_path = str(tmp_path / 'test_video.mp4')
    # frame_rate=10, 30 frames -> 3 sampled frames (frames 0, 10, 20)
    create_synthetic_video(video_path, num_frames=30)

    extractor = FrameExtractor(frame_rate=10)

    # First pass
    first_paths = list(extractor.iter_frames(video_path))
    first_temp_dir = extractor.temp_dir

    # Second pass
    second_paths = list(extractor.iter_frames(video_path))
    second_temp_dir = extractor.temp_dir

    assert len(extractor.frame_paths) == 3, f'Expected 3, got {len(extractor.frame_paths)}'
    assert second_temp_dir != first_temp_dir, 'Expected a new temp_dir on second call'
    assert not os.path.isdir(first_temp_dir), 'Expected first temp_dir to be cleaned up on reuse'

    extractor.cleanup()


@pytest.mark.skipif(not HAS_CV2, reason='cv2 not available')
def test_extract_shim_still_returns_all_frames(tmp_path):
    """Test that extract() backward-compatible shim returns all sampled frames."""
    video_path = str(tmp_path / 'test_video.mp4')
    create_synthetic_video(video_path, num_frames=30)

    extractor = FrameExtractor(frame_rate=10)
    result = extractor.extract(video_path)

    assert isinstance(result, tuple), 'extract() must return a tuple'
    assert len(result) == 2, 'extract() must return (temp_dir, frame_paths)'
    temp_dir, frame_paths = result
    assert os.path.isdir(temp_dir)
    assert len(frame_paths) == 3, f'Expected 3 frames, got {len(frame_paths)}'

    extractor.cleanup()


def test_cleanup_called_unconditionally_on_zero_frame_video():
    """Test that cleanup() is called even when iter_frames() yields nothing."""
    extractor = FrameExtractor(frame_rate=1)
    cleanup_mock = MagicMock()
    extractor.cleanup = cleanup_mock

    # Mock iter_frames to yield nothing
    with patch.object(extractor, 'iter_frames', return_value=iter([])):
        # Simulate caller pattern from nudenet.py / helloz_nsfw.py
        try:
            for _ in extractor.iter_frames('dummy_path'):
                pass
        finally:
            extractor.cleanup()

    cleanup_mock.assert_called_once()

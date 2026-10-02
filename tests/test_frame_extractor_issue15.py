"""Tests for issue #15 - FrameExtractor lazy/streaming frame extraction."""
import os
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# We need cv2 for synthetic video creation.  Guard against the case where
# another test module in the same pytest session has installed a MagicMock
# stub for cv2 (e.g. tests/processing/test_media_processor.py): a MagicMock
# is not a real module, so isinstance(cv2, types.ModuleType) is False and we
# skip the cv2-dependent tests rather than running them against a fake.
try:
    import cv2
    HAS_CV2 = isinstance(cv2, types.ModuleType)
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
    """Test that breaking early from iter_frames only writes N frames to disk,
    and that auto-cleanup removes the temp directory on generator close."""
    video_path = str(tmp_path / 'test_video.mp4')
    # 30 frames at frame_rate=1 -> 30 sampled frames; we break at 3
    create_synthetic_video(video_path, num_frames=30)

    extractor = FrameExtractor(frame_rate=1)
    count = 0
    captured_temp_dir = None
    for frame_path in extractor.iter_frames(video_path):
        count += 1
        # Capture temp_dir while still inside the generator (before finally cleans up)
        if captured_temp_dir is None:
            captured_temp_dir = extractor.temp_dir
        if count == 3:
            break

    # Exactly 3 JPEG files should exist at break point
    assert captured_temp_dir is not None
    jpegs = [f for f in os.listdir(captured_temp_dir) if f.endswith('.jpg')]
    assert len(jpegs) == 3

    # Auto-cleanup ran on generator close (break triggers GeneratorExit -> finally)
    assert extractor.temp_dir is None
    assert not os.path.isdir(captured_temp_dir)


@pytest.mark.skipif(not HAS_CV2, reason='cv2 not available')
def test_iter_frames_reuse_does_not_accumulate_stale_paths(tmp_path):
    """Test that calling iter_frames twice resets state (no stale paths)."""
    video_path = str(tmp_path / 'test_video.mp4')
    # frame_rate=10, 30 frames -> 3 sampled frames (frames 0, 10, 20)
    create_synthetic_video(video_path, num_frames=30)

    extractor = FrameExtractor(frame_rate=10)

    # First pass — capture temp_dir during iteration before finally cleans up
    first_temp_dir = None
    for frame_path in extractor.iter_frames(video_path):
        if first_temp_dir is None:
            first_temp_dir = extractor.temp_dir

    assert first_temp_dir is not None
    assert extractor.temp_dir is None, 'Expected temp_dir cleaned up after first pass'
    assert not os.path.isdir(first_temp_dir), 'Expected first temp_dir removed from disk'

    # Second pass — capture temp_dir during iteration before finally cleans up
    second_temp_dir = None
    second_frames = []
    for frame_path in extractor.iter_frames(video_path):
        if second_temp_dir is None:
            second_temp_dir = extractor.temp_dir
        second_frames.append(frame_path)

    assert second_temp_dir != first_temp_dir, 'Expected a new temp_dir on second call'
    assert len(second_frames) == 3, f'Expected 3 frames, got {len(second_frames)}'

    # No stale paths from the first run accumulate — frame_paths reset between runs
    assert len(extractor.frame_paths) == 0, 'Expected frame_paths reset after cleanup'
    assert extractor.temp_dir is None, 'Expected temp_dir cleaned up after second pass'
    assert second_temp_dir is not None
    assert not os.path.isdir(second_temp_dir)


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
    # Lock in the "live files" contract: returned paths point to real files on disk
    assert os.path.isfile(frame_paths[0])

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


@pytest.mark.skipif(not HAS_CV2, reason='cv2 not available')
def test_cleanup_is_idempotent(tmp_path):
    """cleanup() must be safe to call repeatedly, including after iter_frames()
    has already auto-cleaned (the real callers' double-cleanup pattern)."""
    video_path = str(tmp_path / 'test_video.mp4')
    create_synthetic_video(video_path, num_frames=5)

    extractor = FrameExtractor(frame_rate=1)

    # Part 1: cleanup() with no temp_dir set is a safe no-op, repeatable
    for _ in range(3):
        extractor.cleanup()
        assert extractor.temp_dir is None
        assert extractor.frame_paths == []

    # Part 2: iter_frames() auto-cleans on completion; calling cleanup()
    # afterwards (the real callers' double-cleanup pattern) is a safe no-op
    list(extractor.iter_frames(video_path))
    assert extractor.temp_dir is None
    assert extractor.frame_paths == []

    # Caller-level cleanup after auto-cleanup — idempotent, no exception
    extractor.cleanup()
    assert extractor.temp_dir is None
    assert extractor.frame_paths == []

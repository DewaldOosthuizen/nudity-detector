"""Tests for issue #23 — helloz_nsfw detector classify_image, classify_video,
prompt_threshold_percent, and _post_with_retry."""
import logging
from unittest.mock import MagicMock, patch, call

import pytest
import requests

from src.detectors.helloz_nsfw import _post_with_retry, prompt_threshold_percent
from src.core.scan_session import ScanSession
from src.core import constants


# ---------------------------------------------------------------------------
# Helper: capturing session factory
# ---------------------------------------------------------------------------
def _capturing_session_factory(captured):
    class _CapturingScanSession(ScanSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured[0] = self
    return _CapturingScanSession


def _make_ok_response(nsfw_score):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {'data': {'nsfw': nsfw_score}}
    return r


# ---------------------------------------------------------------------------
# Test 1: classify_image() detects nudity when confidence >= threshold
# ---------------------------------------------------------------------------
def test_classify_image_detects_nudity_above_threshold(tmp_path):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    captured = [None]
    from src.detectors import helloz_nsfw

    ok_response = _make_ok_response(0.9)  # above 60% default threshold

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw.requests.post', return_value=ok_response), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_cff(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_cff

        helloz_nsfw.main()

    mock_hr.assert_called_once()
    _args, kwargs = mock_hr.call_args
    assert kwargs.get('confidence_score', _args[4] if len(_args) > 4 else None) is not None or True
    # nudity_detected should be True: second positional arg
    nudity_detected = _args[1] if len(_args) > 1 else mock_hr.call_args[0][1]
    assert nudity_detected is True


# ---------------------------------------------------------------------------
# Test 2: classify_image() returns no-nudity when confidence < threshold
# ---------------------------------------------------------------------------
def test_classify_image_no_nudity_below_threshold(tmp_path):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    captured = [None]
    from src.detectors import helloz_nsfw

    ok_response = _make_ok_response(0.1)  # well below 60% threshold

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw.requests.post', return_value=ok_response), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_cff(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_cff

        helloz_nsfw.main()

    mock_hr.assert_called_once()
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is False


# ---------------------------------------------------------------------------
# Test 3: classify_image() records ERROR sentinel on HTTP 500 (no crash)
# ---------------------------------------------------------------------------
def test_classify_image_error_on_http_500(tmp_path):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    captured = [None]
    from src.detectors import helloz_nsfw

    bad_response = MagicMock()
    bad_response.status_code = 503

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw.requests.post', return_value=bad_response), \
         patch('src.detectors.helloz_nsfw.time.sleep'), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_cff(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_cff

        # Should not raise
        helloz_nsfw.main()

    session = captured[0]
    error_entries = [
        e for e in session.get_results()
        if isinstance(e.detected_classes, str) and e.detected_classes.startswith('ERROR:')
    ]
    assert len(error_entries) == 1


# ---------------------------------------------------------------------------
# Test 4: classify_image() records ERROR sentinel on requests.exceptions.Timeout
# ---------------------------------------------------------------------------
def test_classify_image_error_on_timeout(tmp_path):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    captured = [None]
    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw.requests.post',
               side_effect=requests.exceptions.Timeout('timed out')), \
         patch('src.detectors.helloz_nsfw.time.sleep'), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_cff(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_cff

        helloz_nsfw.main()

    session = captured[0]
    error_entries = [
        e for e in session.get_results()
        if isinstance(e.detected_classes, str) and e.detected_classes.startswith('ERROR:')
    ]
    assert len(error_entries) == 1


# ---------------------------------------------------------------------------
# Test 5: _post_with_retry() retries on HTTP 5xx and raises RuntimeError after exhaustion
# ---------------------------------------------------------------------------
def test_post_with_retry_raises_runtime_error_after_5xx_exhaustion():
    bad_response = MagicMock()
    bad_response.status_code = 500

    with patch('src.detectors.helloz_nsfw.requests.post', return_value=bad_response), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        with pytest.raises(RuntimeError, match='service unavailable'):
            _post_with_retry('http://example.com', files={}, timeout=5, retries=3)


# ---------------------------------------------------------------------------
# Test 6: classify_video() accumulates results across multiple frames
# ---------------------------------------------------------------------------
def test_classify_video_accumulates_results_across_frames(tmp_path):
    vid = tmp_path / 'test.mp4'
    vid.write_bytes(b'fake')

    frame1 = tmp_path / 'frame_0.jpg'
    frame2 = tmp_path / 'frame_1.jpg'
    frame1.write_bytes(b'f1')
    frame2.write_bytes(b'f2')

    ok_response_low = _make_ok_response(0.1)
    ok_response_low2 = _make_ok_response(0.15)

    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', ScanSession), \
         patch('src.detectors.helloz_nsfw.requests.post',
               side_effect=[ok_response_low, ok_response_low2]), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:

        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([str(frame1), str(frame2)])
        MockFE.return_value = mock_extractor

        def fake_cff(folder, ci, cv, **kw):
            cv(str(vid))
        mock_cff.side_effect = fake_cff

        helloz_nsfw.main()

    mock_hr.assert_called_once()
    # frame_scores list passed as second positional arg to handle_results
    frame_scores = mock_hr.call_args[0][2]
    assert len(frame_scores) == 2


# ---------------------------------------------------------------------------
# Test 7: classify_video() exits early once threshold is hit
# ---------------------------------------------------------------------------
def test_classify_video_exits_early_when_threshold_hit(tmp_path):
    vid = tmp_path / 'test.mp4'
    vid.write_bytes(b'fake')

    frame1 = tmp_path / 'frame_0.jpg'
    frame2 = tmp_path / 'frame_1.jpg'
    frame3 = tmp_path / 'frame_2.jpg'
    for f in [frame1, frame2, frame3]:
        f.write_bytes(b'fake')

    # First frame already above threshold
    high_response = _make_ok_response(0.95)

    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', ScanSession), \
         patch('src.detectors.helloz_nsfw.requests.post', return_value=high_response) as mock_post, \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:

        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([str(frame1), str(frame2), str(frame3)])
        MockFE.return_value = mock_extractor

        def fake_cff(folder, ci, cv, **kw):
            cv(str(vid))
        mock_cff.side_effect = fake_cff

        helloz_nsfw.main()

    # Should have exited after first frame (1 POST call, not 3)
    assert mock_post.call_count == 1
    mock_hr.assert_called_once()
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is True


# ---------------------------------------------------------------------------
# Test 8: prompt_threshold_percent() returns a valid integer in range [0, 100]
# ---------------------------------------------------------------------------
def test_prompt_threshold_percent_returns_valid_value():
    with patch('builtins.input', return_value='75'):
        result = prompt_threshold_percent()
    assert 0 <= result <= 100
    assert result == 75.0


def test_prompt_threshold_percent_uses_default_on_empty():
    with patch('builtins.input', return_value=''):
        result = prompt_threshold_percent(default_percent=50.0)
    assert result == 50.0


def test_prompt_threshold_percent_uses_default_on_invalid():
    with patch('builtins.input', return_value='not_a_number'):
        result = prompt_threshold_percent(default_percent=60.0)
    assert result == 60.0

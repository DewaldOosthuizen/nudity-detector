"""Tests for issue #16 — retry logic and structured error reporting in helloz_nsfw."""
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.detectors.helloz_nsfw import _post_with_retry
from src.core.scan_session import ScanSession


# ---------------------------------------------------------------------------
# Helper: capture the ScanSession instance created inside main()
# ---------------------------------------------------------------------------
def _capturing_session_factory(captured):
    """Return a ScanSession subclass that stores itself in *captured[0]*."""
    class _CapturingScanSession(ScanSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured[0] = self
    return _CapturingScanSession


# ---------------------------------------------------------------------------
# Test 1: _post_with_retry succeeds on second attempt
# ---------------------------------------------------------------------------
def test_post_with_retry_succeeds_on_second_attempt():
    ok_response = MagicMock()
    ok_response.status_code = 200

    side_effects = [requests.exceptions.ConnectionError('conn error'), ok_response]

    with patch('src.detectors.helloz_nsfw.requests.post', side_effect=side_effects), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        result = _post_with_retry('http://example.com', files={}, timeout=5)

    assert result.status_code == 200


# ---------------------------------------------------------------------------
# Test 2: _post_with_retry raises after all retries exhausted (RequestException)
# ---------------------------------------------------------------------------
def test_post_with_retry_raises_after_all_retries_request_exception():
    exc = requests.exceptions.ConnectionError('gone')
    with patch('src.detectors.helloz_nsfw.requests.post', side_effect=exc), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        with pytest.raises(requests.exceptions.ConnectionError):
            _post_with_retry('http://example.com', files={}, timeout=5, retries=3)


# ---------------------------------------------------------------------------
# Test 3: _post_with_retry retries on HTTP 503 and raises RuntimeError
# ---------------------------------------------------------------------------
def test_post_with_retry_raises_runtime_error_on_503_exhaustion():
    bad_response = MagicMock()
    bad_response.status_code = 503

    with patch('src.detectors.helloz_nsfw.requests.post', return_value=bad_response), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        with pytest.raises(RuntimeError, match='service unavailable'):
            _post_with_retry('http://example.com', files={}, timeout=5, retries=3)


# ---------------------------------------------------------------------------
# Test 4: _post_with_retry returns immediately on HTTP 200 (no retries consumed)
# ---------------------------------------------------------------------------
def test_post_with_retry_returns_immediately_on_200():
    ok_response = MagicMock()
    ok_response.status_code = 200

    with patch('src.detectors.helloz_nsfw.requests.post', return_value=ok_response) as mock_post, \
         patch('src.detectors.helloz_nsfw.time.sleep') as mock_sleep:
        result = _post_with_retry('http://example.com', files={}, timeout=5, retries=3)

    assert result.status_code == 200
    mock_post.assert_called_once()
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: _post_with_retry: 5xx then success
# ---------------------------------------------------------------------------
def test_post_with_retry_5xx_then_success():
    bad_response = MagicMock()
    bad_response.status_code = 503
    ok_response = MagicMock()
    ok_response.status_code = 200

    with patch('src.detectors.helloz_nsfw.requests.post',
               side_effect=[bad_response, ok_response]) as mock_post, \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        result = _post_with_retry('http://example.com', files={}, timeout=5, retries=3)

    assert result.status_code == 200
    assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# Test 6: _post_with_retry: all RequestException → re-raise last
# ---------------------------------------------------------------------------
def test_post_with_retry_all_request_exception_reraises():
    exc = requests.exceptions.ConnectionError('network down')
    with patch('src.detectors.helloz_nsfw.requests.post', side_effect=exc), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        with pytest.raises(requests.exceptions.ConnectionError, match='network down'):
            _post_with_retry('http://example.com', files={}, timeout=5, retries=2)


# ---------------------------------------------------------------------------
# Test 7: _post_with_retry rewinds file-like seek(0) before each attempt
# ---------------------------------------------------------------------------
def test_post_with_retry_rewinds_file_before_each_attempt():
    ok_response = MagicMock()
    ok_response.status_code = 200
    bad_response = MagicMock()
    bad_response.status_code = 503

    mock_file = MagicMock()
    mock_file.seek = MagicMock()

    files = {'file': ('test.jpg', mock_file, 'image/jpeg')}

    with patch('src.detectors.helloz_nsfw.requests.post',
               side_effect=[bad_response, ok_response]), \
         patch('src.detectors.helloz_nsfw.time.sleep'):
        result = _post_with_retry('http://example.com', files=files, timeout=5, retries=3)

    assert result.status_code == 200
    # seek(0) should have been called at least twice (once per attempt)
    assert mock_file.seek.call_count >= 2
    mock_file.seek.assert_any_call(0)


# ---------------------------------------------------------------------------
# Test 8: classify_image() records ERROR entry when _post_with_retry raises
# ---------------------------------------------------------------------------
def test_classify_image_records_error_entry(tmp_path, caplog):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    captured = [None]
    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=RuntimeError('service down')), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_classify_files(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_classify_files

        helloz_nsfw.main()

    session = captured[0]
    assert session is not None
    error_entries = [
        e for e in session.get_results()
        if isinstance(e.detected_classes, str)
        and e.detected_classes.startswith('ERROR:')
    ]
    assert len(error_entries) == 1


# ---------------------------------------------------------------------------
# Test 9: classify_video() records ERROR entry when all frames fail
# ---------------------------------------------------------------------------
def test_classify_video_records_error_when_all_frames_fail(tmp_path):
    vid = tmp_path / 'test.mp4'
    vid.write_bytes(b'fake')

    # Create the frame file so the failure comes from _post_with_retry, not open()
    frame_file = tmp_path / 'frame_0.jpg'
    frame_file.write_bytes(b'fake_frame')

    captured = [None]
    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', _capturing_session_factory(captured)), \
         patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=RuntimeError('frame fail')), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:

        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([str(frame_file)])
        MockFE.return_value = mock_extractor

        def fake_classify_files(folder, ci, cv, **kw):
            cv(str(vid))
        mock_cff.side_effect = fake_classify_files

        helloz_nsfw.main()

    session = captured[0]
    assert session is not None
    error_entries = [
        e for e in session.get_results()
        if isinstance(e.detected_classes, str)
        and e.detected_classes.startswith('ERROR:')
    ]
    assert len(error_entries) == 1


# ---------------------------------------------------------------------------
# Test 10: classify_video() calls handle_results() when some frames succeed
# ---------------------------------------------------------------------------
def test_classify_video_partial_success_calls_handle_results(tmp_path):
    vid = tmp_path / 'test.mp4'
    vid.write_bytes(b'fake')

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.json.return_value = {'data': {'nsfw': 0.1}}

    frame1 = str(tmp_path / 'frame_0.jpg')
    frame2 = str(tmp_path / 'frame_1.jpg')
    for f in [frame1, frame2]:
        open(f, 'wb').close()

    post_side_effects = [RuntimeError('frame fail'), ok_response]

    from src.detectors import helloz_nsfw

    with patch('src.detectors.helloz_nsfw.ScanSession', ScanSession), \
         patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=post_side_effects), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:

        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([frame1, frame2])
        MockFE.return_value = mock_extractor

        def fake_classify_files(folder, ci, cv, **kw):
            cv(str(vid))
        mock_cff.side_effect = fake_classify_files

        helloz_nsfw.main()

    mock_hr.assert_called_once()


# ---------------------------------------------------------------------------
# Test 11: main() emits logging.warning when ERROR entries are present
# ---------------------------------------------------------------------------
def test_main_emits_warning_for_error_entries(tmp_path, caplog):
    img = tmp_path / 'test.jpg'
    img.write_bytes(b'fake')

    from src.detectors import helloz_nsfw

    with caplog.at_level(logging.WARNING, logger='root'), \
         patch('src.detectors.helloz_nsfw.ScanSession', ScanSession), \
         patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=RuntimeError('service down')), \
         patch('builtins.input', side_effect=[str(tmp_path), '60']), \
         patch('src.detectors.helloz_nsfw.save_nudity_report'), \
         patch('src.detectors.helloz_nsfw.classify_files_in_folder') as mock_cff:

        def fake_classify_files(folder, ci, cv, **kw):
            ci(str(img))
        mock_cff.side_effect = fake_classify_files

        helloz_nsfw.main()

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any('ERROR' in str(m) for m in warning_msgs)

"""Tests for issue #30 — classify_image/classify_video factory functions and extract_frames."""
from unittest.mock import MagicMock, patch

from src.core.scan_session import ScanSession


def _make_ok_response(nsfw_score):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {'data': {'nsfw': nsfw_score}}
    return r


def _make_session():
    return ScanSession()


# ---------------------------------------------------------------------------
# Tests for make_classify_image factory
# ---------------------------------------------------------------------------

def test_classify_image_above_threshold(tmp_path):
    """classify_image: confidence >= threshold → nudity_detected=True."""
    img = tmp_path / 'nude.jpg'
    img.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_image
    session = _make_session()
    classify_image = make_classify_image(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    ok_response = _make_ok_response(0.9)
    with patch('src.detectors.helloz_nsfw._post_with_retry', return_value=ok_response), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr:
        classify_image(str(img))

    mock_hr.assert_called_once()
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is True


def test_classify_image_below_threshold(tmp_path):
    """classify_image: confidence < threshold → nudity_detected=False."""
    img = tmp_path / 'safe.jpg'
    img.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_image
    session = _make_session()
    classify_image = make_classify_image(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    ok_response = _make_ok_response(0.1)
    with patch('src.detectors.helloz_nsfw._post_with_retry', return_value=ok_response), \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr:
        classify_image(str(img))

    mock_hr.assert_called_once()
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is False


def test_classify_image_non_200_status(tmp_path):
    """classify_image: non-200 status → ERROR entry recorded."""
    img = tmp_path / 'bad.jpg'
    img.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_image
    session = _make_session()
    classify_image = make_classify_image(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    bad_response = MagicMock()
    bad_response.status_code = 403
    with patch('src.detectors.helloz_nsfw._post_with_retry', return_value=bad_response):
        classify_image(str(img))

    results = session.get_results()
    assert len(results) == 1
    assert results[0].detected_classes.startswith('ERROR:')


def test_classify_image_json_parse_failure(tmp_path):
    """classify_image: JSON parse failure → ERROR entry recorded."""
    img = tmp_path / 'broken.jpg'
    img.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_image
    session = _make_session()
    classify_image = make_classify_image(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    bad_response = MagicMock()
    bad_response.status_code = 200
    bad_response.json.side_effect = ValueError('bad json')
    with patch('src.detectors.helloz_nsfw._post_with_retry', return_value=bad_response):
        classify_image(str(img))

    results = session.get_results()
    assert len(results) == 1
    assert results[0].detected_classes.startswith('ERROR:')


def test_classify_image_skips_existing_file(tmp_path):
    """classify_image: file in existing_files → skipped, no API call."""
    img = tmp_path / 'already.jpg'
    img.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_image
    session = _make_session()
    classify_image = make_classify_image(
        existing_files={str(img)},
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    with patch('src.detectors.helloz_nsfw._post_with_retry') as mock_post:
        classify_image(str(img))

    mock_post.assert_not_called()
    assert len(session.get_results()) == 0


# ---------------------------------------------------------------------------
# Tests for make_classify_video factory
# ---------------------------------------------------------------------------

def test_classify_video_single_frame_above_threshold_early_exit(tmp_path):
    """classify_video: single frame above threshold → early exit."""
    vid = tmp_path / 'nude.mp4'
    vid.write_bytes(b'fake')
    frame = tmp_path / 'frame_0.jpg'
    frame.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_video
    session = _make_session()
    classify_video = make_classify_video(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    high_response = _make_ok_response(0.95)
    with patch('src.detectors.helloz_nsfw._post_with_retry', return_value=high_response) as mock_post, \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:
        mock_extractor = MagicMock()
        # Three frames but should exit after first
        mock_extractor.iter_frames.return_value = iter([str(frame), str(frame), str(frame)])
        MockFE.return_value = mock_extractor
        classify_video(str(vid))

    assert mock_post.call_count == 1
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is True


def test_classify_video_two_frames_first_below_second_above(tmp_path):
    """classify_video: first frame below, second frame above threshold."""
    vid = tmp_path / 'vid.mp4'
    vid.write_bytes(b'fake')
    frame1 = tmp_path / 'f1.jpg'
    frame2 = tmp_path / 'f2.jpg'
    frame1.write_bytes(b'fake')
    frame2.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_video
    session = _make_session()
    classify_video = make_classify_video(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    low_response = _make_ok_response(0.1)
    high_response = _make_ok_response(0.9)

    with patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=[low_response, high_response]) as mock_post, \
         patch('src.detectors.helloz_nsfw.handle_results') as mock_hr, \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:
        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([str(frame1), str(frame2)])
        MockFE.return_value = mock_extractor
        classify_video(str(vid))

    assert mock_post.call_count == 2
    nudity_detected = mock_hr.call_args[0][1]
    assert nudity_detected is True


def test_classify_video_all_frames_fail_records_error_entry(tmp_path):
    """classify_video: all frames fail → ERROR entry recorded."""
    vid = tmp_path / 'bad.mp4'
    vid.write_bytes(b'fake')
    frame = tmp_path / 'frame_0.jpg'
    frame.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_video
    session = _make_session()
    classify_video = make_classify_video(
        existing_files=set(),
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    with patch('src.detectors.helloz_nsfw._post_with_retry',
               side_effect=RuntimeError('fail')), \
         patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:
        mock_extractor = MagicMock()
        mock_extractor.iter_frames.return_value = iter([str(frame)])
        MockFE.return_value = mock_extractor
        classify_video(str(vid))

    results = session.get_results()
    assert len(results) == 1
    assert results[0].detected_classes.startswith('ERROR:')


def test_classify_video_skips_existing_file(tmp_path):
    """classify_video: file in existing_files → skipped."""
    vid = tmp_path / 'already.mp4'
    vid.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import make_classify_video
    session = _make_session()
    classify_video = make_classify_video(
        existing_files={str(vid)},
        threshold_value=0.6,
        threshold_percent=60.0,
        session=session,
    )

    with patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:
        classify_video(str(vid))
        MockFE.assert_not_called()

    assert len(session.get_results()) == 0


# ---------------------------------------------------------------------------
# Test: extract_frames legacy wrapper delegates to FrameExtractor.extract
# ---------------------------------------------------------------------------

def test_extract_frames_delegates_to_frame_extractor(tmp_path):
    """extract_frames legacy wrapper calls FrameExtractor.extract."""
    vid = tmp_path / 'vid.mp4'
    vid.write_bytes(b'fake')

    from src.detectors.helloz_nsfw import extract_frames

    with patch('src.detectors.helloz_nsfw.FrameExtractor') as MockFE:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ['frame1.jpg']
        MockFE.return_value = mock_extractor

        result = extract_frames(str(vid))

    MockFE.assert_called_once()
    mock_extractor.extract.assert_called_once_with(str(vid))
    assert result == ['frame1.jpg']


# ---------------------------------------------------------------------------
# Test: prompt_threshold_percent
# ---------------------------------------------------------------------------

def test_prompt_threshold_percent_returns_valid_value():
    from src.detectors.helloz_nsfw import prompt_threshold_percent
    with patch('builtins.input', return_value='75'):
        result = prompt_threshold_percent()
    assert 0 <= result <= 100
    assert result == 75.0


def test_prompt_threshold_percent_uses_default_on_empty():
    from src.detectors.helloz_nsfw import prompt_threshold_percent
    with patch('builtins.input', return_value=''):
        result = prompt_threshold_percent(default_percent=50.0)
    assert result == 50.0


def test_prompt_threshold_percent_uses_default_on_invalid():
    from src.detectors.helloz_nsfw import prompt_threshold_percent
    with patch('builtins.input', return_value='not_a_number'):
        result = prompt_threshold_percent(default_percent=60.0)
    assert result == 60.0


# ---------------------------------------------------------------------------
# Tests for _check_server_reachable (issue #52)
# ---------------------------------------------------------------------------

def test_check_server_reachable_returns_false_on_connection_error():
    import requests as req
    from src.detectors.helloz_nsfw import _check_server_reachable
    with patch('src.detectors.helloz_nsfw.requests.get', side_effect=req.exceptions.ConnectionError()):
        assert _check_server_reachable() is False


def test_check_server_reachable_returns_true_on_200():
    from src.detectors.helloz_nsfw import _check_server_reachable
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch('src.detectors.helloz_nsfw.requests.get', return_value=mock_resp):
        assert _check_server_reachable() is True


def test_check_server_reachable_returns_false_on_5xx():
    from src.detectors.helloz_nsfw import _check_server_reachable
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch('src.detectors.helloz_nsfw.requests.get', return_value=mock_resp):
        assert _check_server_reachable() is False


def test_main_exits_with_code_1_when_server_unreachable():
    import pytest
    from src.detectors.helloz_nsfw import main
    with patch('src.detectors.helloz_nsfw._check_server_reachable', return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

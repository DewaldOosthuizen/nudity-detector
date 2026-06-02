"""Tests for src/detectors/nudenet.py – all NudeDetector calls are mocked."""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub nudenet before importing anything from src
sys.modules.setdefault("nudenet", MagicMock())

from src.core import constants
from src.detectors.nudenet import (
    get_nudenet_confidence,
    main,
    prompt_threshold_percent,
    simplify_nudenet_results,
)

# ---------------------------------------------------------------------------
# simplify_nudenet_results
# ---------------------------------------------------------------------------

def test_simplify_nudenet_results_typical():
    raw = [
        {"label": "EXPOSED_BREAST_F", "score": 0.9},
        {"label": "FACE_FEMALE", "score": 0.5},
    ]
    simplified = simplify_nudenet_results(raw)
    assert simplified == [
        {"class": "EXPOSED_BREAST_F", "score": 0.9},
        {"class": "FACE_FEMALE", "score": 0.5},
    ]


def test_simplify_nudenet_results_empty():
    assert simplify_nudenet_results([]) == []


def test_simplify_nudenet_results_missing_keys():
    raw = [{}]
    simplified = simplify_nudenet_results(raw)
    assert simplified == [{"class": "", "score": 0.0}]


# ---------------------------------------------------------------------------
# get_nudenet_confidence
# ---------------------------------------------------------------------------

def test_get_nudenet_confidence_with_nudity_class():
    nudity_class = next(iter(constants.NUDITY_CLASSES_STRICT))
    raw = [
        {"label": nudity_class, "score": 0.85},
        {"label": "FACE_FEMALE", "score": 0.5},
    ]
    conf = get_nudenet_confidence(raw)
    assert conf == pytest.approx(0.85)


def test_get_nudenet_confidence_no_nudity():
    raw = [{"label": "FACE_FEMALE", "score": 0.99}]
    conf = get_nudenet_confidence(raw)
    assert conf == 0.0


def test_get_nudenet_confidence_empty():
    assert get_nudenet_confidence([]) == 0.0


def test_get_nudenet_confidence_max_of_multiple():
    nudity_class = next(iter(constants.NUDITY_CLASSES_STRICT))
    raw = [
        {"label": nudity_class, "score": 0.7},
        {"label": nudity_class, "score": 0.95},
    ]
    assert get_nudenet_confidence(raw) == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# prompt_threshold_percent
# ---------------------------------------------------------------------------

def test_prompt_threshold_percent_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = prompt_threshold_percent()
    assert result == constants.DEFAULT_THRESHOLD_PERCENT


def test_prompt_threshold_percent_valid_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "75")
    result = prompt_threshold_percent()
    assert result == pytest.approx(75.0)


def test_prompt_threshold_percent_clamped_high(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "999")
    result = prompt_threshold_percent()
    assert result == constants.MAX_THRESHOLD_PERCENT


def test_prompt_threshold_percent_clamped_low(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "-5")
    result = prompt_threshold_percent()
    assert result == constants.MIN_THRESHOLD_PERCENT


def test_prompt_threshold_percent_invalid_returns_default(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "abc")
    result = prompt_threshold_percent()
    assert result == constants.DEFAULT_THRESHOLD_PERCENT


# ---------------------------------------------------------------------------
# main() -- test with mocked I/O and detector
# ---------------------------------------------------------------------------

def test_main_image_scan(tmp_path, monkeypatch):
    """main() classifies an image in a folder."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    nudity_class = next(iter(constants.NUDITY_CLASSES_STRICT))
    fake_detector = MagicMock()
    fake_detector.detect.return_value = [{"label": nudity_class, "score": 0.9}]

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value=set()):
        main()


def test_main_image_scan_skip_existing(tmp_path, monkeypatch):
    """main() skips files already in existing report."""
    img = tmp_path / "existing.jpg"
    img.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    fake_detector = MagicMock()

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value={str(img)}):
        main()

    fake_detector.detect.assert_not_called()


def test_main_image_error_handling(tmp_path, monkeypatch):
    """main() handles detection errors gracefully."""
    img = tmp_path / "bad.jpg"
    img.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    fake_detector = MagicMock()
    fake_detector.detect.side_effect = RuntimeError("model error")

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value=set()):
        main()  # Should not raise


def test_main_video_scan(tmp_path, monkeypatch):
    """main() classifies a video in a folder."""
    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    fake_detector = MagicMock()
    fake_detector.detect.return_value = []

    mock_extractor = MagicMock()
    mock_extractor.iter_frames.return_value = iter([])

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.FrameExtractor", return_value=mock_extractor), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value=set()):
        main()


def test_main_video_early_exit(tmp_path, monkeypatch):
    """main() breaks early from video when threshold exceeded."""
    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    nudity_class = next(iter(constants.NUDITY_CLASSES_STRICT))
    fake_detector = MagicMock()
    fake_detector.detect.return_value = [{"label": nudity_class, "score": 0.95}]

    frame_file = tmp_path / "frame_000000.jpg"
    frame_file.write_bytes(b"data")

    mock_extractor = MagicMock()
    mock_extractor.iter_frames.return_value = iter([str(frame_file)])

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.FrameExtractor", return_value=mock_extractor), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value=set()):
        main()


def test_main_video_error_handling(tmp_path, monkeypatch):
    """main() handles video classification errors gracefully."""
    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    fake_detector = MagicMock()
    mock_extractor = MagicMock()
    mock_extractor.iter_frames.side_effect = RuntimeError("video error")

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.FrameExtractor", return_value=mock_extractor), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value=set()):
        main()  # Should not raise


def test_main_video_skip_existing(tmp_path, monkeypatch):
    """main() skips video files already in existing report."""
    vid = tmp_path / "existing.mp4"
    vid.write_bytes(b"data")

    inputs = iter([str(tmp_path), "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    fake_detector = MagicMock()

    with patch("src.detectors.nudenet.NudeDetector", return_value=fake_detector), \
         patch("src.detectors.nudenet.save_nudity_report"), \
         patch("src.detectors.nudenet.get_report_path", return_value=str(tmp_path / "report.xlsx")), \
         patch("src.detectors.nudenet.load_existing_report", return_value={str(vid)}):
        main()

    fake_detector.detect.assert_not_called()

"""Tests for issue #51 - error sentinel entries in NudeNet classifier."""
import logging
import sys
from unittest.mock import MagicMock

# Stub nudenet before any src.detectors.nudenet import
sys.modules.setdefault('nudenet', MagicMock())

import pytest
from unittest.mock import patch

from src.core.scan_session import ScanSession
from src.core.models import ReportEntry


def _make_session():
    return ScanSession()


def _make_detector_and_session(threshold_percent=50.0):
    session = _make_session()
    return session


class TestClassifyImageErrorSentinel:
    def test_classify_image_records_error_sentinel(self):
        """When NudeDetector.detect raises, classify_image adds an ERROR sentinel entry."""
        from src.detectors.nudenet import main  # noqa: import for module load
        import src.detectors.nudenet as nudenet_module

        session = ScanSession()
        threshold_percent = 50.0

        with patch('src.detectors.nudenet.NudeDetector') as MockDetector:
            instance = MockDetector.return_value
            instance.detect.side_effect = RuntimeError('model exploded')

            with patch('src.detectors.nudenet.input', side_effect=['/tmp/test_folder', '']):
                with patch('src.detectors.nudenet.load_existing_report', return_value=set()):
                    with patch('src.detectors.nudenet.classify_files_in_folder') as mock_classify:
                        with patch('src.detectors.nudenet.save_nudity_report'):
                            with patch('src.detectors.nudenet.get_report_path', return_value='/tmp/report.json'):

                                captured_classify_image = {}

                                def fake_classify_files(folder, classify_image, classify_video):
                                    captured_classify_image['fn'] = classify_image
                                    captured_classify_image['video_fn'] = classify_video

                                mock_classify.side_effect = fake_classify_files

                                with patch('src.detectors.nudenet.ScanSession', return_value=session):
                                    with patch('src.detectors.nudenet.create_session_state'):
                                        with patch('src.detectors.nudenet.get_detected_results', return_value=[]):
                                            nudenet_module.main()

                                classify_image = captured_classify_image['fn']
                                classify_image('/tmp/test_folder/image.jpg')

        results = session.get_results()
        assert len(results) == 1
        entry = results[0]
        assert isinstance(entry.detected_classes, str)
        assert entry.detected_classes.startswith('ERROR:')

    def test_classify_video_records_error_sentinel(self):
        """When FrameExtractor.iter_frames raises, classify_video adds an ERROR sentinel."""
        import src.detectors.nudenet as nudenet_module

        session = ScanSession()

        with patch('src.detectors.nudenet.NudeDetector'):
            with patch('src.detectors.nudenet.input', side_effect=['/tmp/test_folder', '']):
                with patch('src.detectors.nudenet.load_existing_report', return_value=set()):
                    with patch('src.detectors.nudenet.classify_files_in_folder') as mock_classify:
                        with patch('src.detectors.nudenet.save_nudity_report'):
                            with patch('src.detectors.nudenet.get_report_path', return_value='/tmp/report.json'):
                                with patch('src.detectors.nudenet.FrameExtractor') as MockExtractor:
                                    instance = MockExtractor.return_value
                                    instance.iter_frames.side_effect = RuntimeError('frame extraction failed')

                                    captured = {}

                                    def fake_classify_files(folder, classify_image, classify_video):
                                        captured['video_fn'] = classify_video

                                    mock_classify.side_effect = fake_classify_files

                                    with patch('src.detectors.nudenet.ScanSession', return_value=session):
                                        with patch('src.detectors.nudenet.create_session_state'):
                                            with patch('src.detectors.nudenet.get_detected_results', return_value=[]):
                                                nudenet_module.main()

                                    classify_video = captured['video_fn']
                                    classify_video('/tmp/test_folder/video.mp4')

        results = session.get_results()
        assert len(results) == 1
        entry = results[0]
        assert isinstance(entry.detected_classes, str)
        assert entry.detected_classes.startswith('ERROR:')

    def test_main_warns_when_error_entries_present(self, caplog):
        """main() emits a warning when any ERROR sentinel entries are present."""
        import src.detectors.nudenet as nudenet_module

        with patch('src.detectors.nudenet.NudeDetector'):
            with patch('src.detectors.nudenet.input', side_effect=['/tmp/test_folder', '']):
                with patch('src.detectors.nudenet.load_existing_report', return_value=set()):
                    with patch('src.detectors.nudenet.classify_files_in_folder') as mock_classify:
                        with patch('src.detectors.nudenet.save_nudity_report'):
                            with patch('src.detectors.nudenet.get_report_path', return_value='/tmp/report.json'):
                                with patch('src.detectors.nudenet.FrameExtractor') as MockExtractor:
                                    instance = MockExtractor.return_value
                                    instance.iter_frames.side_effect = RuntimeError('frame extraction failed')

                                    captured = {}

                                    def fake_classify_files(folder, classify_image, classify_video):
                                        captured['video_fn'] = classify_video

                                    mock_classify.side_effect = fake_classify_files

                                    with patch('src.detectors.nudenet.create_session_state'):
                                        with patch('src.detectors.nudenet.get_detected_results', return_value=[]):
                                            with caplog.at_level(logging.WARNING):
                                                nudenet_module.main()

                                    classify_video = captured['video_fn']
                                    classify_video('/tmp/test_folder/video.mp4')

                                    # Re-run to trigger the warning in main after results populated
                                    # Instead, test that warning is emitted after session has error entries
                                    # by calling main again with a session that has errors pre-populated

        # Simpler: directly test the warning logic by mocking session.get_results
        from src.core.models import ReportEntry
        error_entry = ReportEntry(
            file='/tmp/video.mp4',
            media_type='video',
            model_name='nudenet',
            threshold_percent=50.0,
            confidence_percent=0.0,
            nudity_detected=False,
            detected_classes='ERROR: something failed',
            thumbnail='',
            date_classified='',
        )

        with patch('src.detectors.nudenet.NudeDetector'):
            with patch('src.detectors.nudenet.input', side_effect=['/tmp/test_folder', '']):
                with patch('src.detectors.nudenet.load_existing_report', return_value=set()):
                    with patch('src.detectors.nudenet.classify_files_in_folder'):
                        with patch('src.detectors.nudenet.save_nudity_report'):
                            with patch('src.detectors.nudenet.get_report_path', return_value='/tmp/report.json'):
                                mock_session = MagicMock()
                                mock_session.get_results.return_value = [error_entry]
                                with patch('src.detectors.nudenet.ScanSession', return_value=mock_session):
                                    with patch('src.detectors.nudenet.create_session_state'):
                                        with patch('src.detectors.nudenet.get_detected_results', return_value=[]):
                                            with caplog.at_level(logging.WARNING):
                                                nudenet_module.main()

        assert any(
            'could not be classified' in record.message or 'ERROR' in record.message
            for record in caplog.records
            if record.levelno >= logging.WARNING
        )

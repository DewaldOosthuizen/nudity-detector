"""Tests for src/gui/scanning.py — ScanningMixin (GTK/GObject stubbed via sys.modules)."""
import sys
import types
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub ALL gi / GTK imports before any src.gui module is imported
# ---------------------------------------------------------------------------
def _ensure_gi_stubs():
    if "gi" in sys.modules:
        gobject_mod = sys.modules.get("gi.repository.GObject")
        if gobject_mod is not None:
            class _Base:
                def __init__(self, *a, **kw): pass
            gobject_mod.Object = _Base
        return

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = MagicMock()
    repo_mod = types.ModuleType("gi.repository")

    class _GObjectBase:
        def __init__(self, *a, **kw): pass

    gobject_mod = MagicMock()
    gobject_mod.Object = _GObjectBase
    gtk_mod = MagicMock()
    gtk_mod.INVALID_LIST_POSITION = 4294967295
    adw_mod = MagicMock()
    glib_mod = MagicMock()
    gio_mod = MagicMock()
    gdk_mod = MagicMock()
    gdkpixbuf_mod = MagicMock()

    gi_mod.repository = repo_mod
    repo_mod.Gtk = gtk_mod
    repo_mod.Adw = adw_mod
    repo_mod.GLib = glib_mod
    repo_mod.GObject = gobject_mod
    repo_mod.Gio = gio_mod
    repo_mod.Gdk = gdk_mod
    repo_mod.GdkPixbuf = gdkpixbuf_mod

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.Adw"] = adw_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod
    sys.modules["gi.repository.Gio"] = gio_mod
    sys.modules["gi.repository.Gdk"] = gdk_mod
    sys.modules["gi.repository.GdkPixbuf"] = gdkpixbuf_mod


_ensure_gi_stubs()
sys.modules.setdefault("nudenet", MagicMock())

from src.core import constants  # noqa: E402
from src.core.scan_session import ScanSession  # noqa: E402
from src.gui.scanning import ScanningMixin  # noqa: E402


def _make_win(**extra):
    win = MagicMock()
    win.folder_entry = MagicMock()
    win.folder_entry.get_text.return_value = "/tmp"
    win.threshold_spin = MagicMock()
    win.threshold_spin.get_value.return_value = 60.0
    win.is_processing = False
    win.detected_results = []
    win.last_report_path = "/tmp/nudity_report.xlsx"
    win._scan_session = MagicMock()
    win._scan_session.get_results.return_value = []
    win.log_buffer = MagicMock()
    win.status_label = MagicMock()
    win.summary_label = MagicMock()
    win.progress_bar = MagicMock()
    win.start_button = MagicMock()
    win.stop_button = MagicMock()
    win.log_message = MagicMock()
    win.populate_results = MagicMock()
    win.append_results = MagicMock()
    win.update_result_action_state = MagicMock()
    win.open_report_button = MagicMock()
    win.set_controls_for_processing = MagicMock()
    win.refresh_scan_history = MagicMock()
    win.build_session_state = MagicMock(return_value={"scan_config": {}, "results": []})
    win._get_model = MagicMock(return_value=constants.MODEL_NUDENET)
    win._get_theme_mode = MagicMock(return_value="system")
    win._get_worker_thread_count = MagicMock(return_value=1)
    win._get_worker_thread_timeout = MagicMock(return_value=30)
    win._get_detect_timeout = MagicMock(return_value=10)
    win._get_video_frame_rate = MagicMock(return_value=10)
    win._get_progress_interval = MagicMock(return_value=10)
    win._get_helloz_nsfw_url = MagicMock(return_value=constants.HELLOZ_NSFW_URL)
    win._get_helloz_nsfw_request_timeout = MagicMock(return_value=10)
    win._get_helloz_nsfw_check_url = MagicMock(return_value="http://localhost:9999/health")
    win._get_helloz_nsfw_health_check_timeout = MagicMock(return_value=1)
    win._show_error = MagicMock()
    win._verbose_log = False
    win._pulse_source_id = None
    win._total_files = 0
    win._last_populated_count = 0
    win._progress_fraction = 0.0
    for k, v in extra.items():
        setattr(win, k, v)
    return win


# ---------------------------------------------------------------------------
# Basic delegates
# ---------------------------------------------------------------------------

class TestScanningMixinBasics:
    def test_importable(self):
        assert ScanningMixin is not None

    def test_on_start_clicked_delegates(self):
        win = _make_win()
        win.start_scanning = MagicMock()
        ScanningMixin._on_start_clicked(win, None)
        win.start_scanning.assert_called_once()

    def test_on_stop_clicked_delegates(self):
        win = _make_win()
        win.stop_scanning = MagicMock()
        ScanningMixin._on_stop_clicked(win, None)
        win.stop_scanning.assert_called_once()

    def test_start_scanning_empty_folder(self):
        win = _make_win()
        win.folder_entry.get_text.return_value = ""
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

    def test_start_scanning_nonexistent_folder(self):
        win = _make_win()
        win.folder_entry.get_text.return_value = "/absolutely/not/a/real/path"
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

    def test_check_helloz_nsfw_server_failure(self):
        win = _make_win()
        result = ScanningMixin.check_helloz_nsfw_server(win)
        assert result is False

    def test_check_helloz_nsfw_server_success(self):
        win = _make_win()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp):
            result = ScanningMixin.check_helloz_nsfw_server(win)
        assert result is True

    def test_check_helloz_nsfw_server_500(self):
        win = _make_win()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("requests.get", return_value=mock_resp):
            result = ScanningMixin.check_helloz_nsfw_server(win)
        assert result is False

    def test_start_scanning_helloz_server_unavailable(self, tmp_path):
        win = _make_win()
        win.folder_entry.get_text.return_value = str(tmp_path)
        win._get_model.return_value = constants.MODEL_HELLOZ_NSFW
        win.check_helloz_nsfw_server = MagicMock(return_value=False)
        ScanningMixin.start_scanning(win)
        win._show_error.assert_called()

    def test_stop_scanning(self):
        win = _make_win()
        win.is_processing = True
        ScanningMixin.stop_scanning(win)
        assert win.is_processing is False
        win.status_label.set_text.assert_called()

    def test_frame_temp_dir_base_linux(self):
        result = ScanningMixin._frame_temp_dir_base()
        # Just verify it returns None or a path string
        assert result is None or isinstance(result, str)

    def test_extract_video_frames(self, tmp_path):
        win = _make_win()
        fake_extractor = MagicMock()
        fake_extractor.iter_frames.return_value = iter(["/tmp/frame_0.jpg"])
        with patch("src.gui.scanning.FrameExtractor", return_value=fake_extractor):
            extractor, frames = ScanningMixin.extract_video_frames(win, str(tmp_path / "test.mp4"), "prefix_")
        assert extractor is fake_extractor

    def test_request_helloz_nsfw_score_success(self, tmp_path):
        win = _make_win()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"fakeimage")
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"nsfw": 0.8}}
        mock_requests.post.return_value = mock_resp
        result = ScanningMixin.request_helloz_nsfw_score(win, str(img), mock_requests, None, 10)
        assert result is not None
        result_data, confidence = result
        assert confidence == 0.8

    def test_request_helloz_nsfw_score_non_200(self, tmp_path):
        win = _make_win()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"fakeimage")
        mock_requests = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_requests.post.return_value = mock_resp
        result = ScanningMixin.request_helloz_nsfw_score(win, str(img), mock_requests, None, 10)
        assert result is None


class TestScanningMixinProgress:
    def test_set_scan_total(self):
        win = _make_win()
        ScanningMixin._set_scan_total(win, 42)
        assert win._total_files == 42

    def test_pulse_tick_while_processing(self):
        win = _make_win()
        win.is_processing = True
        win._progress_fraction = 0.0
        result = ScanningMixin._pulse_tick(win)
        assert result is True
        win.progress_bar.pulse.assert_called()

    def test_pulse_tick_with_fraction(self):
        win = _make_win()
        win.is_processing = True
        win._progress_fraction = 0.5
        result = ScanningMixin._pulse_tick(win)
        assert result is True
        win.progress_bar.set_fraction.assert_called_with(0.5)

    def test_pulse_tick_not_processing(self):
        win = _make_win()
        win.is_processing = False
        win._pulse_source_id = 123
        result = ScanningMixin._pulse_tick(win)
        assert result is False
        assert win._pulse_source_id is None

    def test_apply_intermediate_results_not_processing(self):
        win = _make_win()
        win.is_processing = False
        ScanningMixin._apply_intermediate_results(win, [], 0, 0, 0.0)
        win.append_results.assert_not_called()

    def test_apply_intermediate_results_with_new_items(self):
        win = _make_win()
        win.is_processing = True
        win._last_populated_count = 0
        results = [{"file": "/a.jpg", "confidence_percent": 80.0}]
        ScanningMixin._apply_intermediate_results(win, results, 1, 10, 0.1)
        win.append_results.assert_called_once()
        assert win._last_populated_count == 1
        win.summary_label.set_text.assert_called()

    def test_apply_intermediate_results_no_new(self):
        win = _make_win()
        win.is_processing = True
        win._last_populated_count = 1
        results = [{"file": "/a.jpg"}]
        ScanningMixin._apply_intermediate_results(win, results, 1, 10, 0.1)
        win.append_results.assert_not_called()

    def test_finish_processing(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        win.last_report_path = str(tmp_path / "report.xlsx")
        ScanningMixin.finish_processing(win)
        assert win.is_processing is False
        win.status_label.set_text.assert_called_with("Ready")
        win.set_controls_for_processing.assert_called_with(False)
        win.update_result_action_state.assert_called()


class TestScanningMixinHellozNsfw:
    def test_run_helloz_nsfw_image_not_processing(self, tmp_path):
        win = _make_win()
        win.is_processing = False
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        session = MagicMock()
        ScanningMixin.run_helloz_nsfw_image(
            win, str(img), set(), 0.6, 60.0, MagicMock(), None, 10, session
        )
        session.add_result.assert_not_called()

    def test_run_helloz_nsfw_image_already_scanned(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        session = MagicMock()
        existing = {str(img)}
        ScanningMixin.run_helloz_nsfw_image(
            win, str(img), existing, 0.6, 60.0, MagicMock(), None, 10, session
        )
        session.add_result.assert_not_called()

    def test_run_helloz_nsfw_image_success(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        session = ScanSession()
        resp_json = {"data": {"nsfw": 0.9}}
        # request_helloz_nsfw_score is an instance method called via self (the MagicMock).
        # Configure the return value so the unpack `result, confidence_score = scored_result` works.
        win.request_helloz_nsfw_score.return_value = (resp_json, 0.9)
        ScanningMixin.run_helloz_nsfw_image(
            win, str(img), set(), 0.6, 60.0, MagicMock(), constants.HELLOZ_NSFW_URL, 10, session
        )
        assert len(session.get_results()) == 1

    def test_run_helloz_nsfw_image_failed_request(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        session = ScanSession()
        # Simulate a failed request (None return) from request_helloz_nsfw_score
        win.request_helloz_nsfw_score.return_value = None
        ScanningMixin.run_helloz_nsfw_image(
            win, str(img), set(), 0.6, 60.0, MagicMock(), constants.HELLOZ_NSFW_URL, 10, session
        )
        # GLib.idle_add is mocked, nothing to assert except no crash


class TestScanningMixinHellozNsfwVideo:
    def test_run_helloz_nsfw_video_not_processing(self, tmp_path):
        win = _make_win()
        win.is_processing = False
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"x")
        session = MagicMock()
        ScanningMixin.run_helloz_nsfw_video(
            win, str(vid), set(), 0.6, 60.0, MagicMock(), None, 10, session
        )

    def test_run_helloz_nsfw_video_with_frames(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"x")
        frame = tmp_path / "frame_0.jpg"
        frame.write_bytes(b"x")

        session = ScanSession()
        # request_helloz_nsfw_score is called via self (MagicMock), configure its return value.
        win.request_helloz_nsfw_score.return_value = ({"data": {"nsfw": 0.5}}, 0.5)

        fake_extractor = MagicMock()
        frame_iter = iter([str(frame)])
        # extract_video_frames is also called via self (MagicMock), configure it.
        win.extract_video_frames.return_value = (fake_extractor, frame_iter)

        ScanningMixin.run_helloz_nsfw_video(
            win, str(vid), set(), 0.6, 60.0, MagicMock(), constants.HELLOZ_NSFW_URL, 10, session
        )
        fake_extractor.cleanup.assert_called()

    def test_create_helloz_nsfw_classifiers_returns_callables(self):
        win = _make_win()
        session = ScanSession()
        with patch("builtins.__import__", side_effect=lambda n, *a, **kw: MagicMock() if n == "requests" else __import__(n, *a, **kw)):
            classify_image, classify_video = ScanningMixin.create_helloz_nsfw_classifiers(
                win, set(), 0.6, 60.0, session
            )
        assert callable(classify_image)
        assert callable(classify_video)


class TestScanningMixinNudeNet:
    def test_create_nudenet_classifiers_returns_callables(self):
        win = _make_win()
        session = ScanSession()
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector):
            classify_image, classify_video = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        assert callable(classify_image)
        assert callable(classify_video)

    def test_nudenet_classify_image_not_processing(self, tmp_path):
        win = _make_win()
        win.is_processing = False
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_image(str(img))
        assert len(session.get_results()) == 0

    def test_nudenet_classify_image_existing(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, {str(img)}, 0.6, 60.0, session
            )
        classify_image(str(img))
        assert len(session.get_results()) == 0

    def test_nudenet_classify_image_timeout(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", side_effect=TimeoutError("timed out")):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_image(str(img))

    def test_nudenet_classify_image_error(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", side_effect=RuntimeError("fail")):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_image(str(img))

    def test_nudenet_classify_image_none_result(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", return_value=None):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_image(str(img))

    def test_nudenet_classify_image_success(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        detection = [{"label": "EXPOSED_BREAST_F", "score": 0.9}]
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", return_value=detection):
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_image(str(img))
        assert len(session.get_results()) == 1

    def test_nudenet_classify_video_success(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"x")
        frame = tmp_path / "frame_0.jpg"
        frame.write_bytes(b"x")
        fake_detector = MagicMock()
        detection = [{"label": "EXPOSED_BREAST_F", "score": 0.9}]
        fake_extractor = MagicMock()
        fake_extractor.iter_frames.return_value = iter([str(frame)])
        # extract_video_frames is called via self (MagicMock) — configure the return value.
        win.extract_video_frames.return_value = (fake_extractor, iter([str(frame)]))
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", return_value=detection):
            _, classify_video = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_video(str(vid))
        fake_extractor.cleanup.assert_called()

    def test_nudenet_classify_video_frame_timeout(self, tmp_path):
        win = _make_win()
        win.is_processing = True
        session = ScanSession()
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"x")
        frame = tmp_path / "frame_0.jpg"
        frame.write_bytes(b"x")
        fake_detector = MagicMock()
        fake_extractor = MagicMock()
        fake_extractor.iter_frames.return_value = iter([str(frame)])
        # extract_video_frames is called via self (MagicMock) — configure the return value.
        win.extract_video_frames.return_value = (fake_extractor, iter([str(frame)]))
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", side_effect=TimeoutError("timed")):
            _, classify_video = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
        classify_video(str(vid))
        fake_extractor.cleanup.assert_called()


class TestScanningMixinStartScanning:
    def test_start_scanning_nudenet_launches_thread(self, tmp_path):
        win = _make_win()
        win.folder_entry.get_text.return_value = str(tmp_path)
        win._get_model.return_value = constants.MODEL_NUDENET
        win.processing_thread = None

        # We don't want the thread to actually run process_files
        with patch.object(ScanningMixin, "process_files"):
            with patch("src.gui.scanning.threading.Thread") as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread
                with patch("src.gui.scanning.save_nudity_report"), \
                     patch("src.gui.scanning.os.makedirs"):
                    ScanningMixin.start_scanning(win)
        mock_thread.start.assert_called()

    def test_start_scanning_helloz_server_ok(self, tmp_path):
        win = _make_win()
        win.folder_entry.get_text.return_value = str(tmp_path)
        win._get_model.return_value = constants.MODEL_HELLOZ_NSFW
        win.check_helloz_nsfw_server = MagicMock(return_value=True)

        with patch("src.gui.scanning.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            with patch("src.gui.scanning.save_nudity_report"), \
                 patch("src.gui.scanning.os.makedirs"):
                ScanningMixin.start_scanning(win)
        mock_thread.start.assert_called()

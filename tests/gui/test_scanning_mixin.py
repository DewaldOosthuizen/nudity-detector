"""Tests for src/gui/scanning.py — ScanningMixin (GTK/GObject stubbed via sys.modules)."""
import json
import os
import sys
import threading
import types
from unittest.mock import MagicMock, patch

import pytest


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
    # GLib.Error must be a real exception class so `except GLib.Error:` works
    # and prevents MagicMock string paths being written to the filesystem.
    class _GLibError(Exception):
        pass
    glib_mod.Error = _GLibError
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
from tests.conftest import ensure_gi_stubs  # noqa: E402


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
    win._get_helloz_nsfw_url = MagicMock(return_value='http://localhost:6086/api/upload_check')
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
        with patch("src.gui.scanning.create_frame_extractor", return_value=fake_extractor):
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
            win, str(img), set(), 0.6, 60.0, MagicMock(), 'http://localhost:6086/api/upload_check', 10, session
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
            win, str(img), set(), 0.6, 60.0, MagicMock(), 'http://localhost:6086/api/upload_check', 10, session
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
            win, str(vid), set(), 0.6, 60.0, MagicMock(), 'http://localhost:6086/api/upload_check', 10, session
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


# ---------------------------------------------------------------------------
# Issue #91 — timeout unit boundary (real accessors must yield seconds)
# ---------------------------------------------------------------------------

def _load_nudity_window_class():
    """Import ``NudityDetectorWindow`` from ``src.gui.app`` using the shared stubs.

    ``src.gui.app`` subclasses ``Adw.ApplicationWindow``/``Adw.Application``, so
    the gi stubs installed by ``tests/conftest.py`` (which pin those to real
    classes) are repaired before the import. Repairing via the shared helper
    keeps a single source of truth for the stub set instead of duplicating it
    here.
    """
    ensure_gi_stubs()
    from src.gui.app import NudityDetectorWindow  # noqa: E402
    return NudityDetectorWindow


class _ImmediateThread:
    """Stand-in for ``threading.Thread`` that runs the target synchronously on start().

    Lets a test assert on the work the thread performs without depending on how
    ``start_scanning`` constructs the Thread (positional vs kwargs, argument order).
    """

    def __init__(self, target=None, args=(), kwargs=None, **_ignored):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        """Invoke the captured target immediately with its captured arguments."""
        if self._target is not None:
            self._target(*self._args, **self._kwargs)

    def is_alive(self):
        """Always False — the work already completed synchronously."""
        return False

    def join(self, timeout=None):
        """No-op: nothing to join."""
        return None


def _processing_thread_factory():
    """Return a Thread factory that runs only the scan's *processing* thread inline.

    ``ScanningMixin.process_files`` also spawns an internal async report-save thread
    and then joins it. Running that one synchronously would block forever on its
    queue, so exactly the first Thread constructed is made immediate and every later
    one gets a real daemon thread.

    Returns:
        A callable usable as the ``new`` argument of ``patch(...)``.
    """
    state = {"used": False}
    real_thread = threading.Thread  # captured before patch() rebinds the module attribute

    def factory(*args, **kwargs):
        if not state["used"]:
            state["used"] = True
            return _ImmediateThread(*args, **kwargs)
        return real_thread(*args, **kwargs)

    return factory


def _make_window_instance(window_cls, config_dict):
    """Construct a real NudityDetectorWindow with a scripted config and stubbed UI.

    This exercises the real ``__init__`` config read path — the code that issue #91 was
    actually fixed in — without needing a real GTK toolkit. A genuine instance (not a
    ``MagicMock``) is required so the ``super().__init__`` chain in the MRO resolves.

    Args:
        window_cls: The ``NudityDetectorWindow`` class under test.
        config_dict: The config mapping ``_load_config`` should return.

    Returns:
        The constructed window instance (UI construction is patched away).
    """
    win = object.__new__(window_cls)
    # The stub Adw base class carries no widget methods; __init__ calls set_title()
    # and friends. A permissive per-instance fallback supplies no-op stand-ins so
    # the real config read path can run without a GTK toolkit.
    # The startup migration persists the rewritten config; write_config is
    # redirected so the suite never touches the developer's real
    # config/app_config.json. The on-disk rewrite itself is covered in
    # tests/core/test_timeout_units_issue91.py.
    no_op_widgets = MagicMock()
    with patch.object(window_cls, "_load_config", return_value=config_dict), \
         patch.object(window_cls, "_build_ui"), \
         patch.object(window_cls, "_apply_theme"), \
         patch.object(window_cls, "load_initial_session"), \
         patch.object(window_cls, "_announce_config_migration"), \
         patch.object(window_cls, "_find_latest_report_path", return_value="/tmp/reports"), \
         patch("src.gui.app.get_report_path", return_value="/tmp/reports"), \
         patch("src.core.config_migration.write_config"), \
         patch.object(type(win).__mro__[-2], "__getattr__",
                      create=True, side_effect=lambda _name: MagicMock()):
        window_cls.__init__(win)
    win.log_message = no_op_widgets.log_message
    return win


def _attach_widget_stubs(win):
    """Attach the MagicMock widgets ``_save_config`` reads to a real window.

    ``_build_ui`` is patched away by :func:`_make_window_instance`, so a real
    instance has no widgets; ``_save_config`` needs them. Each accessor reads a
    real widget through ``get_value()``, which a bare MagicMock turns into a
    MagicMock rather than a number, so the numeric widgets are scripted here and
    the real accessors then coerce them.

    Args:
        win: The window instance to populate.

    Returns:
        The same instance, for chaining.
    """
    numeric_spins = {
        "threshold_spin": 60.0,
        "progress_interval_spin": 100,
        "video_frame_rate_spin": 5,
        "worker_thread_count_spin": 10,
        "worker_thread_timeout_spin": 5,
        "detect_timeout_spin": 60,
        "helloz_nsfw_port_spin": 6086,
        "helloz_nsfw_request_timeout_spin": 30,
        "helloz_nsfw_health_check_timeout_spin": 5,
    }
    for name, value in numeric_spins.items():
        setattr(win, name, MagicMock(**{"get_value.return_value": value}))
    win.theme_dropdown = MagicMock(**{"get_selected.return_value": 1})
    win.nudenet_radio = MagicMock(**{"get_active.return_value": False})
    win.folder_entry = MagicMock(**{"get_text.return_value": "/tmp"})
    win.helloz_nsfw_host_entry = MagicMock(**{"get_text.return_value": "localhost"})
    win.helloz_nsfw_endpoint_entry = MagicMock(**{"get_text.return_value": "/api/upload_check"})
    return win


def _read_src_app():
    """Return the source text of ``src/gui/app.py``.

    Some wiring obligations (a bound passed at a call site) are only visible in the
    source, since the real GTK window cannot be constructed in a headless run.

    Returns:
        The module's contents as a single string.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(repo_root, "src", "gui", "app.py"), encoding="utf-8") as handle:
        return handle.read()


class TestTimeoutUnits:
    """The GUI accessors are the unit boundary: they must return whole seconds."""

    def test_shared_gi_stubs_pin_adw_base_classes(self):
        """``ensure_gi_stubs`` is the single stub source of truth.

        A MagicMock-only Adw stub (as installed by sibling test modules) must be
        repaired to a real class, otherwise ``src.gui.app`` cannot be imported.
        """
        adw_mod = sys.modules["gi.repository.Adw"]
        try:
            adw_mod.ApplicationWindow = MagicMock()
            ensure_gi_stubs()
            assert isinstance(adw_mod.ApplicationWindow, type)
            assert issubclass(adw_mod.ApplicationWindow, object)
        finally:
            ensure_gi_stubs()

    def test_ensure_gi_stubs_does_not_mutate_real_gi_modules(self):
        """``ensure_gi_stubs`` must never overwrite the genuine PyGObject modules.

        A real, file-backed ``gi`` module (as ``send2trash`` imports transitively)
        must be left untouched: globally faking a third-party library from a
        fixture would silently break ``send2trash`` and make the suite
        order-dependent.
        """
        fake_real_gi = types.ModuleType("gi")
        fake_real_gi.__file__ = "/usr/lib/python3/dist-packages/gi/__init__.py"
        fake_real_adw = types.ModuleType("gi.repository.Adw")
        fake_real_adw.__file__ = "/usr/lib/python3/dist-packages/gi/repository/Adw.py"
        sentinel = object()
        setattr(fake_real_adw, "ApplicationWindow", sentinel)

        saved = {name: sys.modules.get(name) for name in ("gi", "gi.repository.Adw")}
        try:
            sys.modules["gi"] = fake_real_gi
            sys.modules["gi.repository.Adw"] = fake_real_adw
            ensure_gi_stubs()
            # Untouched: the sentinel survives and no stub base class was grafted on.
            assert fake_real_adw.ApplicationWindow is sentinel
            assert sys.modules["gi"] is fake_real_gi
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
            ensure_gi_stubs()

    def test_real_gi_is_reported_loudly(self):
        """Real PyGObject under the test suite is a hard error, not a silent pass.

        ``ensure_gi_stubs`` deliberately declines to fake a genuine ``gi`` module. If
        one is loaded anyway, the GUI tests would be exercising real GTK types while
        appearing to pass — so detection must be assertable, not just a silent
        early return.
        """
        from tests import conftest

        fake_real_gi = types.ModuleType("gi")
        fake_real_gi.__file__ = "/usr/lib/python3/dist-packages/gi/__init__.py"
        assert conftest._is_real_gi(fake_real_gi) is True
        # A stub (no __file__) is never treated as real.
        assert conftest._is_real_gi(types.ModuleType("gi")) is False
        assert conftest._is_real_gi(None) is False

    # -- widget accessors ---------------------------------------------------

    def test_accessor_worker_timeout_returns_seconds(self):
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win.worker_thread_timeout_spin.get_value.return_value = 5
        result = window_cls._get_worker_thread_timeout(win)
        assert result == 5
        assert result != 5000
        assert result != 0.005

    def test_accessor_detect_timeout_returns_seconds(self):
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win.detect_timeout_spin.get_value.return_value = 60
        result = window_cls._get_detect_timeout(win)
        assert result == 60

    def test_accessor_honours_large_seconds_value(self):
        """A spin button value is seconds as-is; no magnitude-based reinterpretation.

        Regression guard: the previous implementation converted any value >= 1000 to
        milliseconds, so a legitimate 300 s worker timeout became 0 (clamped to 1).
        """
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win.worker_thread_timeout_spin.get_value.return_value = 300
        assert window_cls._get_worker_thread_timeout(win) == 300

    # -- __init__ config path (the actual #91 fix) --------------------------

    def test_init_reads_seconds_config_keys(self):
        """A current-version config supplies the timeouts verbatim, in seconds."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'worker_thread_timeout_seconds': 12,
            'detect_timeout_seconds': 90,
        })
        assert win._worker_thread_timeout == 12
        assert win._detect_timeout == 90
        assert win._config_migration_notes == []
        # 12 and 90 are honoured verbatim, but both differ from the code defaults,
        # so the user is told about them (ADD-007: no silent divergence).
        assert len(win._config_divergence_notes) == 2

    def test_init_migrates_legacy_shipped_250_config(self):
        """The shipped 250 ms config must NOT survive as 250 seconds.

        This is the exact upgrade path of issue #91: an existing install with
        ``worker_thread_timeout: 250`` and ``detect_timeout: 250`` must end up with
        usable seconds-scale timeouts, not the 250-second freeze.
        """
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {
            'worker_thread_timeout': 250,
            'detect_timeout': 250,
        })
        assert win._worker_thread_timeout == constants.WORKER_THREAD_TIMEOUT
        assert win._detect_timeout == constants.DETECT_TIMEOUT
        assert len(win._config_migration_notes) == 2

    def test_init_migrates_legacy_unambiguous_millisecond_config(self):
        """A legacy millisecond value above one second converts faithfully."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {'detect_timeout': 90000})
        assert win._detect_timeout == 90

    def test_init_honours_large_seconds_config_value(self):
        """A current-version config with 3600 stays 3600 — no heuristic division."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'detect_timeout_seconds': 3600,
        })
        assert win._detect_timeout == 3600

    def test_large_seconds_value_survives_a_save(self, tmp_path):
        """3600 must be persisted as 3600, not truncated to the spin button's upper.

        Regression guard for the spin-button bounds: the detect-timeout adjustment
        used to be built with ``upper=600``, so GTK clamped the widget value and
        ``_save_config`` then persisted 600 — silent, unrecoverable loss of a value
        the config path had deliberately accepted.
        """
        window_cls = _load_nudity_window_class()
        win = _attach_widget_stubs(_make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'detect_timeout_seconds': 3600,
        }))
        win.detect_timeout_spin = MagicMock(**{"get_value.return_value": 3600})

        config_path = tmp_path / constants.CONFIG_FILE_NAME
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)):
            window_cls._save_config(win)

        persisted = json.loads(config_path.read_text())
        assert persisted['detect_timeout_seconds'] == 3600

    def test_save_config_uses_the_atomic_writer(self, tmp_path):
        """Both writers share one atomic implementation, so neither truncates."""
        window_cls = _load_nudity_window_class()
        win = _attach_widget_stubs(_make_window_instance(window_cls, {}))
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)), \
             patch("src.gui.app.config_migration.write_config") as mock_write:
            window_cls._save_config(win)
        mock_write.assert_called_once()
        written_path, written_data = mock_write.call_args.args
        assert written_path.endswith(constants.CONFIG_FILE_NAME)
        assert written_data[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION
        assert "detect_timeout_seconds" in written_data

    def test_save_config_logs_and_announces_a_write_failure(self, tmp_path, caplog):
        """A config that cannot be written is reported, not swallowed.

        ``_save_config`` previously caught ``OSError`` with a bare ``pass``, so a
        full disk or a permission change discarded every pending setting change
        with no log line and no activity-log entry.
        """
        window_cls = _load_nudity_window_class()
        win = _attach_widget_stubs(_make_window_instance(window_cls, {}))
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)), \
             patch("src.gui.app.config_migration.write_config", side_effect=OSError("read-only")), \
             caplog.at_level("WARNING", logger="src.gui.app"):
            window_cls._save_config(win)
        assert "read-only" in caplog.text
        win.log_message.assert_called()
        assert any("read-only" in call.args[0] for call in win.log_message.call_args_list)
        assert all(call.kwargs.get("level") == "warning" for call in win.log_message.call_args_list)

    def test_timeout_spin_buttons_accept_the_documented_maximum(self):
        """Every spin button's ``upper`` is the documented bound for that setting.

        The widget must be able to represent every value the config path accepts;
        otherwise ``_save_config`` silently rewrites the config on the next save.
        ``_build_settings_tab`` is driven for real — Gtk is a stub, so
        ``Gtk.Adjustment(**kwargs)`` records exactly the arguments the code passed.
        Asserting the whole set pins every bound at once, so a stale literal
        (the old 600/300/60) cannot return unnoticed.
        """
        window_cls = _load_nudity_window_class()
        Gtk = sys.modules["gi.repository.Gtk"]
        Gtk.Adjustment.reset_mock()
        # _build_settings_tab reads the values __init__ computed from the config,
        # so a real configured instance supplies them.
        win = _attach_widget_stubs(_make_window_instance(window_cls, {}))
        window_cls._build_settings_tab(win)

        uppers = {call.kwargs["upper"] for call in Gtk.Adjustment.call_args_list}
        for bound in constants.TIMEOUT_MAX_SECONDS.values():
            assert bound in uppers, f"no spin button accepts the documented maximum {bound}"
        assert constants.MAX_PORT in uppers
        # The old, silently-truncating timeout bounds — 600 for the detect timeout,
        # 300 for the worker and Helloz request timeouts, 60 for the Helloz health
        # check. None may return as a timeout spin button's upper.
        for stale_bound in (60, 300, 600):
            assert stale_bound not in uppers, f"a timeout spin button still uses the stale upper {stale_bound}"

    def test_value_beyond_the_maximum_is_clamped_and_announced(self, caplog):
        """A value past the bound is clamped, and the truncation is user-visible."""
        window_cls = _load_nudity_window_class()
        with caplog.at_level("WARNING", logger="src.core.constants"):
            win = _make_window_instance(window_cls, {
                constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
                'detect_timeout_seconds': constants.DETECT_TIMEOUT_MAX_SECONDS + 1,
            })
        assert win._detect_timeout == constants.DETECT_TIMEOUT_MAX_SECONDS
        assert len(win._config_truncation_notes) == 1
        assert "detect_timeout_seconds" in win._config_truncation_notes[0]
        # Merged into the announcement set, so the note reaches the activity log.
        assert win._config_truncation_notes[0] in win._config_migration_notes

    def test_truncation_notes_reach_the_activity_log(self):
        """A clamp the user cannot see is a clamp they cannot correct."""
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win._config_migration_notes = ["detect_timeout_seconds: clamped to 86400 s"]
        win._config_divergence_notes = []
        window_cls._announce_config_migration(win)
        assert "86400" in win.log_message.call_args.args[0]

    def test_init_clamps_an_out_of_range_port(self, caplog):
        """The port bound is enforced on the config path and logged."""
        window_cls = _load_nudity_window_class()
        with caplog.at_level("WARNING", logger="src.core.constants"):
            win = _make_window_instance(window_cls, {
                constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
                'helloz_nsfw_port': constants.MAX_PORT + 1,
            })
        assert win._helloz_nsfw_port == constants.MAX_PORT
        assert "helloz_nsfw_port" in caplog.text

    @pytest.mark.parametrize("accessor, spin_name", [
        ("_get_progress_interval", "progress_interval_spin"),
        ("_get_video_frame_rate", "video_frame_rate_spin"),
        ("_get_worker_thread_count", "worker_thread_count_spin"),
    ])
    def test_numeric_accessors_clamp_and_log(self, accessor, spin_name, caplog):
        """The three formerly hand-rolled accessors now clamp and log like the rest."""
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        getattr(win, spin_name).get_value.return_value = 0
        with caplog.at_level("WARNING", logger="src.core.constants"):
            assert getattr(window_cls, accessor)(win) == 1
        assert spin_name in caplog.text

    def test_port_accessor_logs_an_out_of_range_value(self, caplog):
        """The port accessor reports the clamp instead of substituting silently."""
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win.helloz_nsfw_port_spin.get_value.return_value = constants.MAX_PORT + 1
        with caplog.at_level("WARNING", logger="src.core.constants"):
            result = window_cls._get_helloz_nsfw_port(win)
        assert result == constants.MAX_PORT
        assert "helloz_nsfw_port_spin" in caplog.text

    @pytest.mark.parametrize("accessor, spin_name, maximum", [
        ("_get_worker_thread_timeout", "worker_thread_timeout_spin",
         constants.WORKER_THREAD_TIMEOUT_MAX_SECONDS),
        ("_get_detect_timeout", "detect_timeout_spin", constants.DETECT_TIMEOUT_MAX_SECONDS),
        ("_get_helloz_nsfw_request_timeout", "helloz_nsfw_request_timeout_spin",
         constants.HELLOZ_NSFW_REQUEST_TIMEOUT_MAX_SECONDS),
        ("_get_helloz_nsfw_health_check_timeout", "helloz_nsfw_health_check_timeout_spin",
         constants.HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT_MAX_SECONDS),
    ])
    def test_timeout_accessors_clamp_above_their_documented_bound(
            self, accessor, spin_name, maximum, caplog):
        """Every timeout accessor enforces its own bound on the save path.

        Regression guard: ``normalize_timeout_seconds`` inferred the bound from the
        ``name`` it was given, and an accessor passes a *widget* name
        (``detect_timeout_spin``), never a config key — so the lookup never matched
        and the clamp was inert on the very path (``_save_config``) where it matters.
        """
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        getattr(win, spin_name).get_value.return_value = maximum + 1
        with caplog.at_level("WARNING", logger="src.core.constants"):
            result = getattr(window_cls, accessor)(win)
        assert result == maximum
        assert spin_name in caplog.text

    def test_every_timeout_accessor_passes_its_bound_explicitly(self):
        """No accessor relies on ``normalize_timeout_seconds`` name-based inference.

        Asserted on the source because the clamp is a call-site obligation: the
        normalizer takes the bound per call, so an accessor that omits it loses the
        clamp silently.
        """
        app_source = _read_src_app()
        for constant_name in (
            "WORKER_THREAD_TIMEOUT_MAX_SECONDS",
            "DETECT_TIMEOUT_MAX_SECONDS",
            "HELLOZ_NSFW_REQUEST_TIMEOUT_MAX_SECONDS",
            "HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT_MAX_SECONDS",
        ):
            assert f"max_seconds=constants.{constant_name}" in app_source, (
                f"{constant_name} is not passed as an explicit bound in src/gui/app.py"
            )

    def test_save_config_preserves_keys_the_gui_does_not_own(self, tmp_path):
        """``helloz_nsfw_scheme`` and unknown keys survive a save verbatim.

        Regression guard: ``_save_config`` built the file from a literal whitelist of
        fifteen keys, so every other key was deleted — including
        ``helloz_nsfw_scheme``, the user's own escape hatch for forcing HTTPS against
        a remote host (``constants._validate_scheme`` reads it). Since the save runs
        on quit *and* on every theme change, a remote user's ``https`` was reverted
        the moment they touched the theme dropdown.
        """
        window_cls = _load_nudity_window_class()
        win = _attach_widget_stubs(_make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'helloz_nsfw_scheme': 'https',
            'helloz_nsfw_host': 'myserver',
            'some_future_key': {'nested': True},
        }))
        config_path = tmp_path / constants.CONFIG_FILE_NAME
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)):
            window_cls._save_config(win)

        persisted = json.loads(config_path.read_text())
        assert persisted['helloz_nsfw_scheme'] == 'https'
        assert persisted['some_future_key'] == {'nested': True}
        # The GUI-owned keys are still written.
        assert persisted['helloz_nsfw_host'] == 'localhost'
        assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION

    def test_save_config_keeps_the_https_scheme_out_of_the_gui_url(self, tmp_path):
        """The GUI URL builder honours the configured scheme and the loopback guard.

        Regression guard: both GUI URL helpers hardcoded ``http://``, bypassing
        ``constants._validate_scheme`` entirely, so a remote host configured with
        ``helloz_nsfw_scheme: http`` was contacted over plaintext by the GUI.
        """
        window_cls = _load_nudity_window_class()
        win = _attach_widget_stubs(_make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'helloz_nsfw_scheme': 'https',
            'helloz_nsfw_host': 'myserver',
        }))
        assert window_cls._get_helloz_nsfw_url(win) == 'https://localhost:6086/api/upload_check'

        win = _attach_widget_stubs(_make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'helloz_nsfw_scheme': 'http',
            'helloz_nsfw_host': 'myserver',
        }))
        win.helloz_nsfw_host_entry = MagicMock(**{"get_text.return_value": "myserver"})
        with pytest.raises(ValueError, match="'http' is not allowed for non-loopback host"):
            window_cls._get_helloz_nsfw_check_url(win)

    def test_init_missing_keys_fall_back_to_constants(self):
        """An empty config yields the constant defaults, without raising."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {})
        assert win._worker_thread_timeout == constants.WORKER_THREAD_TIMEOUT
        assert win._detect_timeout == constants.DETECT_TIMEOUT
        assert win._worker_thread_count == constants.WORKER_THREAD_COUNT
        assert win._video_frame_rate == constants.VIDEO_FRAME_RATE

    @pytest.mark.parametrize("bad_value", ["abc", float("inf"), True])
    def test_init_invalid_values_fall_back_to_constants(self, bad_value):
        """An unparseable current-version value falls back to the constant default."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'worker_thread_timeout_seconds': bad_value,
            'detect_timeout_seconds': bad_value,
        })
        assert win._worker_thread_timeout == constants.WORKER_THREAD_TIMEOUT
        assert win._detect_timeout == constants.DETECT_TIMEOUT

    def test_init_negative_value_clamps_to_one_and_logs(self, caplog):
        """An out-of-range negative value clamps to 1 and the clamp is logged."""
        window_cls = _load_nudity_window_class()
        with caplog.at_level("WARNING", logger="src.core.constants"):
            win = _make_window_instance(window_cls, {
                constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
                'detect_timeout_seconds': -5,
            })
        assert win._detect_timeout == 1
        assert "detect_timeout_seconds" in caplog.text

    def test_init_invalid_values_are_logged_naming_the_key(self, caplog):
        """Config coercion failures are visible, not silent."""
        window_cls = _load_nudity_window_class()
        with caplog.at_level("WARNING", logger="src.core.constants"):
            _make_window_instance(window_cls, {
                constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
                'detect_timeout_seconds': "abc",
            })
        assert "detect_timeout_seconds" in caplog.text

    def test_migration_notes_are_shown_in_the_activity_log(self):
        """A rewrite the user cannot see is a rewrite they cannot correct.

        The GUI user reads the activity log, not the Python logger, so migration
        notes must reach ``log_message``.
        """
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win._config_migration_notes = ["detect_timeout: legacy 250 ms is sub-second"]
        win._config_divergence_notes = []
        window_cls._announce_config_migration(win)
        win.log_message.assert_called_once()
        assert "250" in win.log_message.call_args.args[0]

    def test_divergence_notes_are_shown_in_the_activity_log(self):
        """A right-unit / wrong-magnitude value is surfaced to the user too.

        Per ADD-007 the user must be told their 300 s request timeout differs
        from the 30 s code default, even though the configured value is honoured.
        """
        window_cls = _load_nudity_window_class()
        win = MagicMock()
        win._config_migration_notes = []
        win._config_divergence_notes = ["helloz_nsfw_request_timeout_seconds: 300 vs 30"]
        window_cls._announce_config_migration(win)
        win.log_message.assert_called_once()
        assert "300" in win.log_message.call_args.args[0]

    def test_init_reports_config_constant_divergence(self):
        """A 300 s request timeout against a 30 s constant is recorded as a note."""
        window_cls = _load_nudity_window_class()
        win = _make_window_instance(window_cls, {
            constants.CONFIG_VERSION_KEY: constants.CONFIG_VERSION,
            'helloz_nsfw_request_timeout_seconds': 300,
        })
        # The configured value is still honoured — only the divergence is reported.
        assert win._helloz_nsfw_request_timeout == 300
        assert len(win._config_divergence_notes) == 1
        assert "helloz_nsfw_request_timeout_seconds" in win._config_divergence_notes[0]

    def test_init_persists_the_migration_on_startup(self, tmp_path):
        """The startup path rewrites the on-disk config, not just the in-memory dict.

        Regression guard for the documented "rewritten on disk, never re-migrated"
        guarantee: a user who upgrades and never touches a setting must still get
        a repaired config file rather than a legacy one.
        """
        window_cls = _load_nudity_window_class()
        config_path = tmp_path / constants.CONFIG_FILE_NAME
        config_path.write_text(json.dumps({'worker_thread_timeout': 250, 'detect_timeout': 250}))

        win = object.__new__(window_cls)
        no_op_widgets = MagicMock()
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)), \
             patch.object(window_cls, "_load_config", return_value=json.loads(config_path.read_text())), \
             patch.object(window_cls, "_build_ui"), \
             patch.object(window_cls, "_apply_theme"), \
             patch.object(window_cls, "load_initial_session"), \
             patch.object(window_cls, "_announce_config_migration"), \
             patch.object(window_cls, "_find_latest_report_path", return_value="/tmp/reports"), \
             patch("src.gui.app.get_report_path", return_value="/tmp/reports"), \
             patch.object(type(win).__mro__[-2], "__getattr__",
                          create=True, side_effect=lambda _name: MagicMock()):
            window_cls.__init__(win)
        win.log_message = no_op_widgets.log_message

        persisted = json.loads(config_path.read_text())
        assert persisted['worker_thread_timeout_seconds'] == constants.WORKER_THREAD_TIMEOUT
        assert persisted['detect_timeout_seconds'] == constants.DETECT_TIMEOUT
        assert persisted[constants.CONFIG_VERSION_KEY] == constants.CONFIG_VERSION
        assert 'worker_thread_timeout' not in persisted
        assert win._worker_thread_timeout == constants.WORKER_THREAD_TIMEOUT

    def test_init_renames_unsuffixed_timeout_keys_on_startup(self, tmp_path):
        """A pre-ADD-007 ``helloz_nsfw_request_timeout`` is renamed, not converted.

        The value already held seconds, so the migration must not turn 300 s into
        0.3 s; the key simply gains the suffix that states its unit.
        """
        window_cls = _load_nudity_window_class()
        config_path = tmp_path / constants.CONFIG_FILE_NAME
        config_path.write_text(json.dumps({'helloz_nsfw_request_timeout': 300}))

        win = object.__new__(window_cls)
        no_op_widgets = MagicMock()
        with patch("src.core.constants.CONFIG_DIR", str(tmp_path)), \
             patch.object(window_cls, "_load_config", return_value=json.loads(config_path.read_text())), \
             patch.object(window_cls, "_build_ui"), \
             patch.object(window_cls, "_apply_theme"), \
             patch.object(window_cls, "load_initial_session"), \
             patch.object(window_cls, "_announce_config_migration"), \
             patch.object(window_cls, "_find_latest_report_path", return_value="/tmp/reports"), \
             patch("src.gui.app.get_report_path", return_value="/tmp/reports"), \
             patch.object(type(win).__mro__[-2], "__getattr__",
                          create=True, side_effect=lambda _name: MagicMock()):
            window_cls.__init__(win)
        win.log_message = no_op_widgets.log_message

        assert win._helloz_nsfw_request_timeout == 300
        persisted = json.loads(config_path.read_text())
        assert persisted['helloz_nsfw_request_timeout_seconds'] == 300
        assert 'helloz_nsfw_request_timeout' not in persisted

    def test_classify_files_in_folder_receives_seconds(self, tmp_path):
        """The seconds value produced by the boundary reaches classify_files_in_folder.

        The fake Thread runs its target with the captured arguments, so the assertion
        does not depend on how start_scanning happens to build the Thread call.
        """
        window_cls = _load_nudity_window_class()
        win = _make_win()
        win.folder_entry.get_text.return_value = str(tmp_path)
        win._get_model.return_value = constants.MODEL_NUDENET
        win._get_worker_thread_count = MagicMock(return_value=1)
        # Bind the REAL accessor so this test exercises the unit boundary itself.
        win._get_worker_thread_timeout = types.MethodType(
            window_cls._get_worker_thread_timeout, win
        )
        win.worker_thread_timeout_spin.get_value.return_value = 5
        win.create_nudenet_classifiers = MagicMock(return_value=(MagicMock(), MagicMock()))
        win.process_files = types.MethodType(ScanningMixin.process_files, win)

        with patch("src.gui.scanning.classify_files_in_folder") as mock_classify, \
             patch("src.gui.scanning.count_supported_files", return_value=1), \
             patch("src.gui.scanning.save_nudity_report"), \
             patch("src.gui.scanning.os.makedirs"), \
             patch("src.gui.scanning.threading.Thread", new=_processing_thread_factory()):
            ScanningMixin.start_scanning(win)

        assert mock_classify.call_args.kwargs["worker_timeout"] == 5

    def test_detect_with_timeout_receives_seconds(self, tmp_path):
        window_cls = _load_nudity_window_class()
        win = _make_win()
        win.is_processing = True
        # Bind the REAL accessor so the value reaching detect_with_timeout is the
        # normalized seconds value produced by the unit boundary.
        win._get_detect_timeout = types.MethodType(
            window_cls._get_detect_timeout, win
        )
        win.detect_timeout_spin.get_value.return_value = 60
        session = ScanSession()
        img = tmp_path / "img.jpg"
        img.write_bytes(b"x")
        fake_detector = MagicMock()
        with patch("nudenet.NudeDetector", return_value=fake_detector), \
             patch("src.gui.scanning.detect_with_timeout", return_value=[]) as mock_detect:
            classify_image, _ = ScanningMixin.create_nudenet_classifiers(
                win, set(), 0.6, 60.0, session
            )
            classify_image(str(img))
        # detect_with_timeout(detector, file_path, timeout_seconds)
        assert mock_detect.call_args.args[2] == 60


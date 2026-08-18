"""Tests for issue #57 — per-model worker thread count/timeout configuration.

Covers:
- MainWindow.__init__ resolving nudenet_*/helloz_nsfw_* config keys, including
  fallback to constants when app_config.json omits them.
- _get_worker_thread_count_for_model / _get_worker_thread_timeout_for_model
  dispatching on model_name.
- scanning.py's classify_files_in_folder call site passing per-model resolved
  values based on model_name.
"""
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
        glib_mod = sys.modules.get("gi.repository.GLib")
        if glib_mod is not None:
            class _GLibError(Exception):
                pass
            glib_mod.Error = _GLibError
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
from src.gui.app import NudityDetectorWindow  # noqa: E402
from src.gui.scanning import ScanningMixin  # noqa: E402


def _build_window(cfg):
    """Construct a NudityDetectorWindow instance running only the config-resolution
    portion of __init__ (UI building / session loading are stubbed out)."""
    win = NudityDetectorWindow.__new__(NudityDetectorWindow)
    with patch.object(NudityDetectorWindow, '_load_config', return_value=cfg), \
         patch.object(NudityDetectorWindow, '_build_ui', MagicMock()), \
         patch.object(NudityDetectorWindow, '_apply_theme', MagicMock()), \
         patch.object(NudityDetectorWindow, 'load_initial_session', MagicMock()), \
         patch.object(NudityDetectorWindow, '_find_latest_report_path', return_value=None), \
         patch('src.gui.app.get_report_path', return_value='/tmp/report.xlsx'):
        NudityDetectorWindow.__init__(win)
    return win


class TestPerModelWorkerConfigLoading:
    def test_resolves_nudenet_and_helloz_keys_from_config(self):
        cfg = {
            'nudenet_worker_thread_count': 2,
            'nudenet_worker_thread_timeout': 7,
            'helloz_nsfw_worker_thread_count': 15,
            'helloz_nsfw_worker_thread_timeout': 40,
        }
        win = _build_window(cfg)
        assert win._nudenet_worker_thread_count == 2
        assert win._nudenet_worker_thread_timeout == 7
        assert win._helloz_nsfw_worker_thread_count == 15
        assert win._helloz_nsfw_worker_thread_timeout == 40

    def test_falls_back_to_constants_when_keys_absent(self):
        win = _build_window({})
        assert win._nudenet_worker_thread_count == constants.NUDENET_WORKER_THREAD_COUNT
        assert win._nudenet_worker_thread_timeout == constants.NUDENET_WORKER_THREAD_TIMEOUT
        assert win._helloz_nsfw_worker_thread_count == constants.HELLOZ_NSFW_WORKER_THREAD_COUNT
        assert win._helloz_nsfw_worker_thread_timeout == constants.HELLOZ_NSFW_WORKER_THREAD_TIMEOUT

    def test_falls_back_to_constants_on_invalid_values(self):
        cfg = {
            'nudenet_worker_thread_count': 'not-a-number',
            'helloz_nsfw_worker_thread_timeout': None,
        }
        win = _build_window(cfg)
        assert win._nudenet_worker_thread_count == constants.NUDENET_WORKER_THREAD_COUNT
        assert win._helloz_nsfw_worker_thread_timeout == constants.HELLOZ_NSFW_WORKER_THREAD_TIMEOUT


class TestGetWorkerThreadForModelHelpers:
    def _make_win(self):
        win = MagicMock()
        win._nudenet_worker_thread_count = 4
        win._nudenet_worker_thread_timeout = 10
        win._helloz_nsfw_worker_thread_count = 20
        win._helloz_nsfw_worker_thread_timeout = 35
        win._get_worker_thread_count = MagicMock(return_value=10)
        win._get_worker_thread_timeout = MagicMock(return_value=250)
        return win

    def test_count_dispatches_to_nudenet(self):
        win = self._make_win()
        result = NudityDetectorWindow._get_worker_thread_count_for_model(win, constants.MODEL_NUDENET)
        assert result == 4

    def test_count_dispatches_to_helloz_nsfw(self):
        win = self._make_win()
        result = NudityDetectorWindow._get_worker_thread_count_for_model(win, constants.MODEL_HELLOZ_NSFW)
        assert result == 20

    def test_timeout_dispatches_to_nudenet(self):
        win = self._make_win()
        result = NudityDetectorWindow._get_worker_thread_timeout_for_model(win, constants.MODEL_NUDENET)
        assert result == 10

    def test_timeout_dispatches_to_helloz_nsfw(self):
        win = self._make_win()
        result = NudityDetectorWindow._get_worker_thread_timeout_for_model(win, constants.MODEL_HELLOZ_NSFW)
        assert result == 35

    def test_count_and_timeout_return_distinct_values_for_different_models(self):
        win = self._make_win()
        nudenet_count = NudityDetectorWindow._get_worker_thread_count_for_model(win, constants.MODEL_NUDENET)
        helloz_count = NudityDetectorWindow._get_worker_thread_count_for_model(win, constants.MODEL_HELLOZ_NSFW)
        assert nudenet_count != helloz_count

    def test_unknown_model_falls_back_to_flat_getters(self):
        win = self._make_win()
        count = NudityDetectorWindow._get_worker_thread_count_for_model(win, 'unknown_model')
        timeout = NudityDetectorWindow._get_worker_thread_timeout_for_model(win, 'unknown_model')
        assert count == 10
        assert timeout == 250
        win._get_worker_thread_count.assert_called_once()
        win._get_worker_thread_timeout.assert_called_once()


class TestScanningCallSiteUsesPerModelValues:
    def _make_scanning_win(self, model_name):
        win = MagicMock()
        win.folder_entry = MagicMock()
        win.folder_entry.get_text.return_value = "/tmp"
        win.threshold_spin = MagicMock()
        win.threshold_spin.get_value.return_value = 60.0
        win.is_processing = True
        win.detected_results = []
        win.last_report_path = "/tmp/nudity_report.xlsx"
        win._scan_session = MagicMock()
        win._scan_session.get_results.return_value = []
        win.log_buffer = MagicMock()
        win._get_model = MagicMock(return_value=model_name)
        win._get_theme_mode = MagicMock(return_value="system")
        win._get_progress_interval = MagicMock(return_value=1_000_000)
        win._get_worker_thread_count_for_model = MagicMock(return_value=42)
        win._get_worker_thread_timeout_for_model = MagicMock(return_value=99)
        win.create_nudenet_classifiers = MagicMock(return_value=(MagicMock(), MagicMock()))
        win.create_helloz_nsfw_classifiers = MagicMock(return_value=(MagicMock(), MagicMock()))
        return win

    def test_process_files_passes_model_resolved_values_for_nudenet(self):
        win = self._make_scanning_win(constants.MODEL_NUDENET)
        with patch("src.gui.scanning.count_supported_files", return_value=0):
            ScanningMixin.process_files(win, "/tmp", "/tmp/run")
        win._get_worker_thread_count_for_model.assert_not_called()

    def test_process_files_passes_model_resolved_values_when_files_present(self):
        win = self._make_scanning_win(constants.MODEL_HELLOZ_NSFW)
        with patch("src.gui.scanning.count_supported_files", return_value=1), \
             patch("src.gui.scanning.classify_files_in_folder") as mock_classify, \
             patch("src.gui.scanning.GLib"):
            ScanningMixin.process_files(win, "/tmp", "/tmp/run")

        assert mock_classify.called
        _, kwargs = mock_classify.call_args
        win._get_worker_thread_count_for_model.assert_called_once_with(constants.MODEL_HELLOZ_NSFW)
        win._get_worker_thread_timeout_for_model.assert_called_once_with(constants.MODEL_HELLOZ_NSFW)
        assert kwargs["worker_count"] == 42
        assert kwargs["worker_timeout"] == 99

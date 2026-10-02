"""Shared pytest fixtures for the nudity-detector test suite.

Per AGENTS.md §F, GTK/gi modules are stubbed via ``sys.modules`` before any
``src`` import. This happens here, in the root conftest, so it applies to every
test module regardless of collection order.

Rationale: ``src/core/utils.py`` imports ``send2trash``, which imports the real
``gi.repository``. When a core test is collected before the gui tests (pytest
collects alphabetically), that leaves the *real* gi loaded in ``sys.modules``
and the per-module gui stubs then corrupt it, aborting collection of
``tests/gui/test_gui_mixins_extended.py``, ``test_results_mixin.py``,
``test_scan_history.py`` and ``test_scan_history_mixin.py``. Installing a
complete stub set here — before any ``src`` import — keeps the gui test modules
collectable and preserves the intended "no real GTK needed" test contract.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# gi / GTK stubs (idempotent) — must run before any src import
# ---------------------------------------------------------------------------
class _GObjectBase:
    """Real Python class so ``GObject.Object`` subclasses (ResultItem,
    ScanRunItem) can be defined regardless of which test file runs first."""

    def __init__(self, *args, **kwargs):
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


class _GLibError(Exception):
    """Real exception class so ``except GLib.Error:`` works and prevents
    MagicMock string paths being written to the filesystem."""


def _ensure_gi_stubs():
    if "gi" in sys.modules:
        # Another module may already have installed stubs (or a partial set);
        # re-pin the members the gui modules depend on being real classes.
        gobject_mod = sys.modules.get("gi.repository.GObject")
        if gobject_mod is not None:
            gobject_mod.Object = _GObjectBase
        glib_mod = sys.modules.get("gi.repository.GLib")
        if glib_mod is not None:
            glib_mod.Error = _GLibError
        gtk_mod = sys.modules.get("gi.repository.Gtk")
        if gtk_mod is not None:
            gtk_mod.INVALID_LIST_POSITION = 4294967295
        return

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = MagicMock()
    repo_mod = types.ModuleType("gi.repository")

    gtk_mod = MagicMock()
    gtk_mod.INVALID_LIST_POSITION = 4294967295
    adw_mod = MagicMock()
    glib_mod = MagicMock()
    glib_mod.Error = _GLibError
    gobject_mod = MagicMock()
    gobject_mod.Object = _GObjectBase
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


@pytest.fixture
def tmp_report_dir(tmp_path):
    """Temporary report directory backed by pytest's tmp_path."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    return str(report_dir)


@pytest.fixture
def fake_report_entry():
    """Factory fixture that returns a callable producing fake report entry dicts."""
    def _factory(
        file="/tmp/test_image.jpg",
        media_type="image",
        model_name="nudenet",
        threshold_percent=60.0,
        confidence_percent=85.0,
        nudity_detected=True,
        detected_classes="[]",
        thumbnail="",
        date_classified="2024-01-01 00:00:00",
    ):
        return {
            "file": file,
            "media_type": media_type,
            "model_name": model_name,
            "threshold_percent": threshold_percent,
            "confidence_percent": confidence_percent,
            "nudity_detected": nudity_detected,
            "detected_classes": detected_classes,
            "thumbnail": thumbnail,
            "date_classified": date_classified,
        }
    return _factory
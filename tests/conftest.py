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


class _FakeAdwWindow:
    """Real class so ``Adw.ApplicationWindow`` can be used as a base class by
    ``src.gui.app.NudityDetectorWindow``."""

    def __init__(self, *args, **kwargs):
        pass


class _FakeAdwApplication:
    """Real class so ``Adw.Application`` can be used as a base class by
    ``src.gui.app.NudityDetectorApp``."""

    def __init__(self, *args, **kwargs):
        pass


def _pin_real_classes(gi_modules):
    """Re-pin the members the gui modules need to be real Python classes.

    Args:
        gi_modules: Mapping of ``sys.modules``-style gi module names to module objects.

    Returns:
        None. Mutates the supplied module objects in place.
    """
    pins = {
        "GObject": {"Object": _GObjectBase, "GObject": _GObjectBase},
        "GLib": {"Error": _GLibError},
        "Gtk": {"INVALID_LIST_POSITION": 4294967295},
        "Adw": {"ApplicationWindow": _FakeAdwWindow, "Application": _FakeAdwApplication},
    }
    repo_mod = gi_modules.get("gi.repository")
    for short_name, attributes in pins.items():
        module = gi_modules.get(f"gi.repository.{short_name}")
        if module is not None:
            for attribute, value in attributes.items():
                setattr(module, attribute, value)
        # A partial stub set may expose the module only as a ``gi.repository``
        # attribute (or only in ``sys.modules``) — pin both views.
        attached = getattr(repo_mod, short_name, None) if repo_mod is not None else None
        if attached is not None and attached is not module:
            for attribute, value in attributes.items():
                setattr(attached, attribute, value)


def ensure_gi_stubs():
    """Install (or repair) the complete gi/GTK stub set in ``sys.modules``.

    Idempotent: safe to call repeatedly and safe to call after another test
    module has installed a partial or MagicMock-only stub set. Every member the
    gui modules subclass, catch, or compare is pinned to a real Python class or
    value so import order cannot corrupt the stubs.

    Returns:
        None.
    """
    existing = {name: sys.modules.get(name) for name in (
        "gi", "gi.repository", "gi.repository.Gtk", "gi.repository.Adw",
        "gi.repository.GLib", "gi.repository.GObject", "gi.repository.Gio",
        "gi.repository.Gdk", "gi.repository.GdkPixbuf",
    )}
    if "gi" in sys.modules:
        # Another module already installed stubs (possibly the real gi, via
        # send2trash, possibly a partial set) — repair the members we need.
        _pin_real_classes(existing)
        return

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = MagicMock()
    repo_mod = types.ModuleType("gi.repository")

    gtk_mod = MagicMock()
    adw_mod = MagicMock()
    glib_mod = MagicMock()
    gobject_mod = MagicMock()
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

    _pin_real_classes({name: sys.modules[name] for name in existing})


# Backwards-compatible private alias for existing test modules.
_ensure_gi_stubs = ensure_gi_stubs

ensure_gi_stubs()
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

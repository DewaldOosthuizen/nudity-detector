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
# Names of every gi module the gui code touches. Single source of truth: the stub
# installer populates sys.modules from this tuple and the real-class pinning reads
# the same tuple back, so the two views can never drift apart.
STUBBED_GI_MODULES = (
    "gi", "gi.repository", "gi.repository.Gtk", "gi.repository.Adw",
    "gi.repository.GLib", "gi.repository.GObject", "gi.repository.Gio",
    "gi.repository.Gdk", "gi.repository.GdkPixbuf",
)

# Marks the stub modules this conftest owns, so we never patch a real PyGObject
# module that some third-party import (send2trash) pulled in.
_STUB_MARKER = "__nudity_detector_gi_stub__"

# Records the ``__file__`` of any genuine PyGObject detected while the stubs were
# being installed. ``ensure_gi_stubs`` refuses to fake a real third-party library,
# so this is how the gui test session learns that it may be exercising real GTK.
REAL_GI_DETECTED = []


class _GObjectBase:
    """Real Python class so ``GObject.Object`` subclasses (ResultItem,
    ScanRunItem) can be defined regardless of which test file runs first."""

    def __init__(self, *args, **kwargs):
        pass


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


def _is_our_stub(module):
    """Return whether the given module object is a stub owned by this conftest.

    Only stub-owned modules may ever be patched. Real PyGObject modules (pulled in
    transitively by ``send2trash``) are left untouched — globally overwriting a
    third-party library from a test fixture makes the suite order-dependent and
    would silently fake out ``send2trash`` itself.

    Args:
        module: A module object, or None.

    Returns:
        True if the module carries this conftest's stub marker.
    """
    return module is not None and getattr(module, _STUB_MARKER, False) is True


def _is_real_gi(module):
    """Return whether the module object is the genuine PyGObject ``gi`` package.

    Genuine modules are file-backed packages; anything a test installs is either
    a ``types.ModuleType`` stub without a real ``__file__`` or a ``MagicMock``.
    This distinction decides whether we may repair the module in place.

    Args:
        module: A module object, or None.

    Returns:
        True if the module looks like the real PyGObject package.
    """
    if module is None or _is_our_stub(module):
        return False
    if isinstance(module, MagicMock):
        return False
    # A genuine package/module always has a real filesystem origin.
    return bool(getattr(module, "__file__", None))


def _pin_real_classes(gi_modules):
    """Pin the members the gui modules need to real Python classes.

    Only modules owned by this conftest's stub set are mutated; the real
    PyGObject modules, if any are loaded, are left exactly as they are.

    Args:
        gi_modules: Mapping of ``sys.modules``-style gi module names to module objects.

    Returns:
        None. Mutates the supplied stub-owned module objects in place.
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
        if _is_our_stub(module):
            for attribute, value in attributes.items():
                setattr(module, attribute, value)
        # A partial stub set may expose the module only as a ``gi.repository``
        # attribute (or only in ``sys.modules``) — pin both stub-owned views.
        attached = getattr(repo_mod, short_name, None) if repo_mod is not None else None
        if attached is not None and attached is not module and _is_our_stub(attached):
            for attribute, value in attributes.items():
                setattr(attached, attribute, value)

    # A sibling test module may have installed its own, unmarked stub set (which
    # is MagicMock-based and lacks the real base classes). Those are test-owned
    # fakes, not a third-party library, so repairing them is safe — and required,
    # because ``src.gui.app`` subclasses ``Adw.ApplicationWindow``.
    if not _is_real_gi(gi_modules.get("gi")):
        for short_name, attributes in pins.items():
            module = gi_modules.get(f"gi.repository.{short_name}")
            if module is not None and not _is_our_stub(module):
                for attribute, value in attributes.items():
                    setattr(module, attribute, value)


def ensure_gi_stubs():
    """Install (or repair) the complete gi/GTK stub set in ``sys.modules``.

    Idempotent: safe to call repeatedly and safe to call after another test
    module has installed a partial or MagicMock-only stub set. Every member the
    gui modules subclass, catch, or compare is pinned to a real Python class or
    value so import order cannot corrupt the stubs.

    If the *real* PyGObject is already loaded (e.g. imported transitively by
    ``send2trash`` before this conftest ran), this function deliberately leaves
    the real modules alone rather than overwriting a third-party library's
    attributes for the rest of the session. The gui modules under test do not
    subclass GTK types in that scenario, because the root conftest runs before
    any ``src`` import and therefore wins the race.

    Returns:
        None.
    """
    already_present = "gi" in sys.modules
    if already_present and _is_real_gi(sys.modules["gi"]):
        # The genuine PyGObject is loaded (e.g. pulled in by send2trash). Leave a
        # third-party library's attributes untouched rather than faking them out.
        # This is a real problem for the gui tests, which would then subclass and
        # construct genuine GTK types while appearing to pass — so make it loud.
        REAL_GI_DETECTED.append(sys.modules["gi"].__file__)
        return

    if already_present:
        # A stub set is already installed — ours or a sibling's. Repair the members
        # in place instead of rebuilding, so modules other test modules already hold
        # references to keep working.
        _pin_real_classes({name: sys.modules.get(name) for name in STUBBED_GI_MODULES})
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

    # Mark the stub modules we own so later calls can distinguish them from real gi.
    for name in STUBBED_GI_MODULES:
        setattr(sys.modules[name], _STUB_MARKER, True)

    # Build the module map from the same tuple used for installation.
    _pin_real_classes({name: sys.modules[name] for name in STUBBED_GI_MODULES})


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

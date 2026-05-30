"""Tests for src/core/scan_session.py — issue #17"""
import sys
import threading
import pytest
from unittest.mock import MagicMock

sys.modules.setdefault("nudenet", MagicMock())

from src.core.scan_session import ScanSession


def _make_entry(file="a.jpg", nudity_detected=True):
    from src.core.models import ReportEntry
    return ReportEntry(
        file=file,
        media_type="image",
        model_name="nudenet",
        threshold_percent=60.0,
        confidence_percent=80.0,
        nudity_detected=nudity_detected,
        detected_classes="[]",
        thumbnail="",
        date_classified="2024-01-01 00:00:00",
    )


def test_empty_construction():
    session = ScanSession()
    assert session.get_results() == []


def test_add_result():
    session = ScanSession()
    entry = _make_entry("b.jpg")
    session.add_result(entry)
    results = session.get_results()
    assert len(results) == 1
    assert results[0].file == "b.jpg"


def test_get_results_returns_copy():
    session = ScanSession()
    entry = _make_entry("c.jpg")
    session.add_result(entry)
    r1 = session.get_results()
    r1.append(_make_entry("extra.jpg"))
    r2 = session.get_results()
    assert len(r2) == 1  # mutation of r1 did not affect internal state


def test_reset():
    session = ScanSession()
    session.add_result(_make_entry("d.jpg"))
    assert len(session.get_results()) == 1
    session.reset()
    assert session.get_results() == []


def test_initial_results_constructor_arg():
    entries = [_make_entry("e.jpg"), _make_entry("f.jpg")]
    session = ScanSession(initial_results=entries)
    assert len(session.get_results()) == 2


def test_concurrent_append():
    N_THREADS = 20
    APPENDS_PER_THREAD = 50
    session = ScanSession()

    def worker():
        for _ in range(APPENDS_PER_THREAD):
            session.add_result(_make_entry("t.jpg"))

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(session.get_results()) == N_THREADS * APPENDS_PER_THREAD


# ---------------------------------------------------------------------------
# session-reload path (mirrors src/gui/session.py load_session_from_path)
# ---------------------------------------------------------------------------

def test_session_reload_creates_scan_session_with_loaded_entries():
    entries = [_make_entry("x.jpg"), _make_entry("y.jpg")]
    session = ScanSession(initial_results=entries)
    assert len(session.get_results()) == 2
    assert {e.file for e in session.get_results()} == {"x.jpg", "y.jpg"}


def test_session_reload_replaces_previous_session():
    session = ScanSession(initial_results=[_make_entry("old.jpg")])
    session = ScanSession(initial_results=[_make_entry("new1.jpg"), _make_entry("new2.jpg")])
    results = session.get_results()
    assert len(results) == 2
    assert all(e.file in {"new1.jpg", "new2.jpg"} for e in results)


# ---------------------------------------------------------------------------
# result-deletion path (mirrors src/gui/results.py _do_delete)
# ---------------------------------------------------------------------------

def test_result_deletion_removes_entry_from_session():
    entries = [_make_entry("a.jpg"), _make_entry("b.jpg"), _make_entry("c.jpg")]
    session = ScanSession(initial_results=entries)
    target_file = "b.jpg"
    remaining = [e for e in session.get_results() if e.file != target_file]
    session.reset()
    for e in remaining:
        session.add_result(e)
    results = session.get_results()
    assert len(results) == 2
    assert all(e.file != target_file for e in results)


def test_result_deletion_no_global_side_effects():
    s1 = ScanSession(initial_results=[_make_entry("shared.jpg")])
    s2 = ScanSession(initial_results=[_make_entry("shared.jpg")])
    s1.reset()
    assert len(s1.get_results()) == 0
    assert len(s2.get_results()) == 1

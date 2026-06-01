"""Tests for issue #24 - Fix periodic report save inside report_lock blocking.

Ensures that:
1. ReportManager.save_entries is never called while ScanSession._lock is held.
2. Checkpoint saves fire every 500 entries.
3. Worker throughput does not degrade at the 500-entry boundary under concurrency.
"""
import sys
import time
import threading
from unittest.mock import MagicMock, patch

# Stub heavy optional deps before importing source modules
sys.modules.setdefault("nudenet", MagicMock())

from src.core.scan_session import ScanSession
from src.core.utils import handle_results


def _wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _make_entry_kwargs(tmp_path, idx=0):
    return dict(
        file_path=str(tmp_path / f"file_{idx}.jpg"),
        nudity_detected=False,
        raw_result=[],
        session=None,  # overridden by caller
        report_dir=str(tmp_path),
    )


class _LockSpy:
    """Wraps a threading.Lock and records whether save_entries is ever called
    while the lock is held."""

    def __init__(self, real_lock):
        self._lock = real_lock
        self.held = False
        self.violation = False

    def acquire(self, *a, **kw):
        result = self._lock.acquire(*a, **kw)
        if result:
            self.held = True
        return result

    def release(self):
        self.held = False
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()

    @property
    def locked(self):
        return self._lock.locked()


def test_checkpoint_fires_every_500_entries(tmp_path):
    """ReportManager.save_entries must be called once per 500 entries added."""
    session = ScanSession()

    save_calls = []

    def fake_save(entries, path):
        save_calls.append(len(entries))

    with patch("src.core.utils.ReportManager") as MockRM:
        MockRM.save_entries.side_effect = fake_save

        for i in range(1500):
            kwargs = _make_entry_kwargs(tmp_path, i)
            kwargs["session"] = session
            handle_results(**kwargs)

        assert _wait_until(lambda: len(save_calls) == 3)

    # Should have fired at counts 500, 1000, 1500
    assert save_calls == [500, 1000, 1500]


def test_save_entries_not_called_while_lock_held(tmp_path):
    """save_entries must never be called while ScanSession._lock is held."""
    session = ScanSession()

    import threading as _threading
    real_lock = _threading.Lock()
    spy = _LockSpy(real_lock)
    session._lock = spy  # type: ignore[assignment]

    violation_flag = threading.Event()
    save_called = threading.Event()

    def fake_save(entries, path):
        save_called.set()
        if spy.held:
            violation_flag.set()

    with patch("src.core.utils.ReportManager") as MockRM:
        MockRM.save_entries.side_effect = fake_save

        # Add exactly 500 entries to trigger the checkpoint
        for i in range(500):
            kwargs = _make_entry_kwargs(tmp_path, i)
            kwargs["session"] = session
            handle_results(**kwargs)

        assert save_called.wait(timeout=2)

    assert not violation_flag.is_set(), (
        "save_entries was called while ScanSession._lock was held (lock contention bug)"
    )


def test_concurrent_throughput_at_500_boundary(tmp_path):
    """A blocked checkpoint save should not block worker progress."""
    N_THREADS = 8
    ENTRIES_PER_THREAD = 100  # total = 800, will hit 500-boundary once
    TOTAL_ENTRIES = N_THREADS * ENTRIES_PER_THREAD

    session = ScanSession()
    save_started = threading.Event()
    allow_save_to_finish = threading.Event()
    save_calls = []

    def fake_save(entries, path):
        save_calls.append(len(entries))
        save_started.set()
        assert allow_save_to_finish.wait(timeout=2), "Timed out waiting to release checkpoint save"

    with patch("src.core.utils.ReportManager") as MockRM:
        MockRM.save_entries.side_effect = fake_save

        def worker(thread_idx):
            for i in range(ENTRIES_PER_THREAD):
                kwargs = _make_entry_kwargs(tmp_path, thread_idx * 1000 + i)
                kwargs["session"] = session
                handle_results(**kwargs)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(N_THREADS)]
        for th in threads:
            th.start()

        assert save_started.wait(timeout=2)
        assert _wait_until(lambda: len(session.get_results()) == TOTAL_ENTRIES)

        allow_save_to_finish.set()
        for th in threads:
            th.join(timeout=2)

    assert all(not th.is_alive() for th in threads)
    assert save_calls == [500]

"""Encapsulated scan-session context object."""
from threading import Lock
from typing import List, Optional
from .models import ReportEntry


class ScanSession:
    """Encapsulates the mutable state of a single scan run.

    Each scan run creates one ScanSession instance. Detectors append results
    via add_result(); the GUI and CLI read them via get_results(). The internal
    Lock makes concurrent appends from worker threads safe without callers
    managing any lock themselves.
    """

    def __init__(self, initial_results: Optional[List] = None) -> None:
        self._results: List[ReportEntry] = list(initial_results or [])
        self._lock = Lock()

    def add_result(self, entry: ReportEntry) -> int:
        """Append *entry* and return the new total count, both under the lock."""
        with self._lock:
            self._results.append(entry)
            return len(self._results)

    def get_results(self) -> List[ReportEntry]:
        with self._lock:
            return list(self._results)

    def reset(self) -> None:
        with self._lock:
            self._results.clear()

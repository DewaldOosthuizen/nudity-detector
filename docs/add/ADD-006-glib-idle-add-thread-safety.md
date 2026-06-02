# ADD-006 — GLib.idle_add for GUI Updates from Worker Threads

| Field      | Value                     |
|------------|---------------------------|
| Status     | Accepted                  |
| Date       | 2024-04-01                |
| Author     | Dewald Oosthuizen         |
| Relates to | ADD-001, ADD-002          |

---

## Context

Scans run in a pool of worker threads spawned by `src/core/utils.py`. Each
worker processes a file, produces a `ReportEntry`, and needs to update the
GUI — appending a row to the results `Gio.ListStore`, incrementing a progress
bar, or updating a summary label.

GTK4 is strictly single-threaded: modifying any widget from a non-main thread
produces undefined behaviour and commonly causes segfaults or silent data
corruption. A mechanism is required to marshal GUI updates back onto the
GTK main loop safely.

---

## Decision

All GUI updates originating from worker threads are deferred to the GTK main
loop using **`GLib.idle_add`**:

```python
# In a worker thread — do NOT touch GTK widgets directly
def _on_file_processed(entry: ReportEntry) -> None:
    GLib.idle_add(self._append_result_row, entry)

# In the main thread — safe to modify widgets
def _append_result_row(self, entry: ReportEntry) -> bool:
    item = ResultItem(...)
    self._list_store.append(item)
    return GLib.SOURCE_REMOVE   # do not repeat
```

`GLib.idle_add` schedules the callable to run on the next iteration of the
GLib main loop, which always runs on the main thread. Returning
`GLib.SOURCE_REMOVE` (equivalent to `False`) from the callback ensures it
is not called again.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| Direct widget access from threads | Zero overhead — but causes segfaults and data corruption | Rejected |
| `GLib.idle_add` (current) | Standard GLib pattern; safe; no extra threading primitives | **Accepted** |
| `threading.Event` + main-thread poll | Requires a polling loop; wastes CPU; complicates shutdown | Rejected |
| `asyncio` + GTK event loop integration | Clean for async-native code — but the detector backends are synchronous; integration adds complexity | Rejected |
| Qt-style signal/slot across threads | Qt automatically queues cross-thread signals — GTK has no equivalent built-in; `GLib.idle_add` is the idiomatic equivalent | N/A |

---

## Consequences

**Positive:**
- GTK4 widget access remains strictly on the main thread — no mutex needed
  for widget operations.
- `GLib.idle_add` is the canonical GLib/GTK pattern; it is well-documented
  and understood by GTK4 contributors.
- Returning `GLib.SOURCE_REMOVE` from every callback keeps the idle source
  list clean — no accumulation of stale callbacks.

**Negative / Trade-offs:**
- There is an inherent delay between a worker completing a file and the GUI
  updating — typically one main loop iteration (< 1 ms), which is imperceptible.
- Callbacks scheduled via `idle_add` are fire-and-forget. If the window is
  destroyed before the callback runs, accessing `self` in the callback
  results in a use-after-free. The scan lifecycle in `ScanningMixin` cancels
  the scan and joins threads before the window is destroyed to mitigate this.
- Testing `GLib.idle_add` calls requires mocking `GLib` at the module level
  in `src.gui.*` — the mock must be the same object that the source module
  bound at import time (patching `src.gui.scanning.GLib`, not `gi.repository.GLib`).
  This distinction caused test failures that are documented in the test suite
  for `test_scan_history_mixin.py`.

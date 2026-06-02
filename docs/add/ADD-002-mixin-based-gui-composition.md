# ADD-002 — Mixin-Based GUI Composition

| Field      | Value                     |
|------------|---------------------------|
| Status     | Accepted                  |
| Date       | 2024-01-15                |
| Author     | Dewald Oosthuizen         |
| Relates to | ADD-001                   |

---

## Context

`NudityDetectorWindow` started as a single monolithic class in `src/gui/app.py`.
As features grew — scanning, thumbnails, session management, results table,
scan history, dialogs — the file grew to several thousand lines with no clear
internal boundaries. Any change to one area risked breaking unrelated areas.
Unit testing individual behaviours was impossible without constructing the
entire GTK4 window.

The problem:
- One class owned scanning, preview, session I/O, table management, dialogs,
  and scan history simultaneously.
- Every test had to mock the entire GTK widget tree.
- New features had nowhere natural to live.

---

## Decision

Split `NudityDetectorWindow` into **six focused mixins**, each owning a single
slice of the window's behaviour:

| Mixin | File | Responsibility |
|-------|------|----------------|
| `ScanningMixin` | `scanning.py` | Scan thread lifecycle, classifier setup, progress |
| `PreviewMixin` | `preview.py` | Thumbnail loading (PIL → GdkPixbuf → Gtk.Picture) |
| `SessionMixin` | `session.py` | Save/load session JSON, open/browse report files |
| `ResultsMixin` | `results.py` | Populate `Gio.ListStore`, row open/delete actions |
| `DialogsMixin` | `dialogs.py` | `Adw.AlertDialog` error, warning, confirm helpers |
| `ScanHistoryMixin` | `scan_history.py` | Previous scan runs tab, load/export/delete |

`app.py` remains the composition root — it inherits all mixins and calls
`_build_ui()` to wire widgets together. Mixins communicate only through
shared widget attributes set by `_build_ui`; they do not import each other.

```python
class NudityDetectorWindow(
    ScanningMixin, PreviewMixin, SessionMixin,
    ResultsMixin, DialogsMixin, ScanHistoryMixin,
    Adw.ApplicationWindow,
):
    ...
```

Each mixin is tested in isolation against a lightweight `FakeWindow` stub
that provides only the widget attributes the mixin under test requires.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| Single monolithic class | Already in place — unmanageable at scale | Rejected |
| Mixin inheritance | Standard Python pattern for GTK4 window composition; easy to test | **Accepted** |
| Separate Window subclasses per feature | Requires widget duplication or complex delegation | Rejected |
| Component objects (delegation) | Clean separation but GTK4 signal wiring becomes verbose across object boundaries | Rejected for now |

---

## Consequences

**Positive:**
- Each mixin can be unit tested with a `FakeWindow` stub — no real GTK4
  display server needed.
- New features (e.g. a new tab) map directly to a new mixin file.
- `app.py` is stable — it changes only when new mixins are added or removed.
- Ruff linting, coverage, and static analysis are all mixin-scoped.

**Negative / Trade-offs:**
- Multiple inheritance can hide method resolution order (MRO) bugs. All mixins
  must avoid defining the same method name without an explicit `super()` chain.
- `_build_ui` in `app.py` must remain the single place that creates and names
  shared widget attributes — if a mixin references `self.results_store` and
  `_build_ui` renames it, the failure is silent until runtime.
- `FakeWindow` stubs in tests must stay in sync with the attribute names
  that `_build_ui` creates. When a new widget is added to `app.py`, the
  corresponding test stub must be updated.

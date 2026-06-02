# Architecture Overview

Nudity Detector is a GTK4/libadwaita desktop application that detects explicit
content in images and videos using pluggable AI backends. The codebase follows
a strict layered architecture — each layer has a single responsibility and
dependencies flow inward toward the core.

---

## Folder Structure

```text
nudity-detector/
├── run_gui.py                       ← Launch the GTK4 GUI
├── run_nudenet.py                   ← Launch the NudeNet CLI
├── run_helloz_nsfw.py               ← Launch the Helloz NSFW CLI
├── config/
│   └── app_config.json              ← Runtime configuration (host, port, endpoints)
├── docker-compose.yml               ← Helloz NSFW Docker service
├── requirements.txt                 ← Pinned runtime dependencies (pip-compile output)
├── requirements-dev.txt             ← Dev/test extras (includes requirements.txt)
├── requirements.in                  ← Human-edited abstract dep spec (pip-tools source)
├── pyproject.toml                   ← Ruff linting configuration
├── scripts/                         ← Linux packaging tooling
│   ├── build_linux.sh               ← Full build pipeline (venv → PyInstaller → AppImage)
│   ├── nudity-detector.spec         ← PyInstaller spec (one-dir mode, GTK4 hidden imports)
│   ├── AppRun                       ← AppImage entry point (env var wiring)
│   └── nudity-detector.desktop      ← FreeDesktop entry used by appimagetool
├── docs/
│   ├── ARCHITECTURE.md              ← This file
│   ├── add/                         ← Architectural Decision Documents
│   └── diagrams/                    ← Mermaid architecture and flow diagrams
├── tests/                           ← pytest test suite (mirrors src/ layout)
│   ├── conftest.py
│   ├── core/
│   ├── detectors/
│   ├── gui/
│   ├── processing/
│   ├── reporting/
│   └── test_frame_extractor_issue15.py
└── src/
    ├── core/
    │   ├── constants.py             ← Single source of truth for all config values
    │   ├── models.py                ← Typed dataclasses (ScanConfig, ReportEntry, SessionState)
    │   ├── scan_session.py          ← Thread-safe scan run state container
    │   └── utils.py                 ← Orchestration coordinator & public API
    ├── processing/
    │   └── media_processor.py       ← Frame extraction (cv2), thumbnails (PIL), type detection
    ├── reporting/
    │   └── report_manager.py        ← Excel I/O (openpyxl), session JSON persistence
    ├── gui/
    │   ├── app.py                   ← NudityDetectorWindow: GTK4/Adw window, _build_ui, mixin wiring
    │   ├── scanning.py              ← ScanningMixin — scan lifecycle, threading, progress
    │   ├── preview.py               ← PreviewMixin — PIL → GdkPixbuf thumbnail display
    │   ├── session.py               ← SessionMixin — save/load session, report open/browse
    │   ├── results.py               ← ResultsMixin — ColumnView population and row actions
    │   ├── dialogs.py               ← DialogsMixin — Adw.AlertDialog helpers
    │   ├── scan_history.py          ← ScanHistoryMixin + ScanRunItem GObject model
    │   └── result_item.py           ← ResultItem GObject model for ColumnView rows
    └── detectors/
        ├── nudenet.py               ← NudeNet local detector (CLI wrapper)
        └── helloz_nsfw.py           ← Helloz NSFW Docker detector (HTTP client)
```

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Entry Points                                               │
│  run_gui.py   run_nudenet.py   run_helloz_nsfw.py           │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  Presentation Layer  (src/gui/)                             │
│  app.py + ScanningMixin + PreviewMixin + SessionMixin       │
│  ResultsMixin + DialogsMixin + ScanHistoryMixin             │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  Coordination Layer  (src/core/utils.py)                    │
│  scan orchestration, worker threads, file ops, public API   │
└──────┬────────────────────────────────────────┬─────────────┘
       │                                        │
┌──────▼──────────────┐              ┌──────────▼──────────────┐
│  Detection Layer    │              │  Infrastructure Layer    │
│  src/detectors/     │              │  src/processing/        │
│  nudenet.py         │              │  media_processor.py     │
│  helloz_nsfw.py     │              │                         │
└──────┬──────────────┘              └──────────┬──────────────┘
       │                                        │
┌──────▼────────────────────────────────────────▼─────────────┐
│  Core Layer  (src/core/)                                     │
│  constants.py   models.py   scan_session.py                  │
└──────────────────────────────────────────────┬──────────────┘
                                               │
┌──────────────────────────────────────────────▼─────────────┐
│  Persistence Layer  (src/reporting/)                        │
│  report_manager.py — Excel I/O + session JSON               │
└─────────────────────────────────────────────────────────────┘
```

Dependencies flow downward only. The GUI never imports from detectors directly;
both go through the coordination layer in `src/core/utils.py`.

---

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `src/core/constants.py` | Single source of truth for all magic values — thresholds, extensions, model names, file paths |
| `src/core/models.py` | Typed dataclasses only — `ScanConfig`, `ReportEntry`, `SessionState` |
| `src/core/scan_session.py` | Thread-safe scan run state — `ScanSession` wraps a lock-protected list of `ReportEntry` |
| `src/core/utils.py` | Public API and orchestration — spawns worker threads, wires detectors to storage, file open/delete |
| `src/processing/media_processor.py` | Media operations — type detection, `FrameExtractor` (cv2), `ThumbnailGenerator` (PIL) |
| `src/reporting/report_manager.py` | Report I/O only — Excel generation (openpyxl), session JSON read/write |
| `src/gui/app.py` | GTK4/Adw window shell — `_build_ui`, mixin composition, widget wiring |
| `src/gui/scanning.py` | `ScanningMixin` — scan thread lifecycle, classifier setup, progress pulse |
| `src/gui/preview.py` | `PreviewMixin` — PIL image → GdkPixbuf → `Gtk.Picture` thumbnail display |
| `src/gui/session.py` | `SessionMixin` — save/load session JSON, open/browse report files |
| `src/gui/results.py` | `ResultsMixin` — populate `Gio.ListStore`, row actions (open, delete) |
| `src/gui/dialogs.py` | `DialogsMixin` — `Adw.AlertDialog` error, warning, and confirmation helpers |
| `src/gui/scan_history.py` | `ScanHistoryMixin` + `ScanRunItem` — previous scan runs tab, load/export/delete |
| `src/gui/result_item.py` | `ResultItem` — `GObject.Object` model powering the results `Gtk.ColumnView` |
| `src/detectors/nudenet.py` | NudeNet local detector — CLI invocation and result parsing |
| `src/detectors/helloz_nsfw.py` | Helloz NSFW detector — HTTP POST to Docker-hosted AI service |

---

## GUI Mixin Composition

`NudityDetectorWindow` in `src/gui/app.py` inherits from six mixins. Each mixin
owns a distinct slice of the window's behaviour and has no direct dependency on
the others — they communicate only through shared widget attributes set by
`_build_ui` in `app.py`.

```
NudityDetectorWindow(
    ScanningMixin,      ← scan lifecycle & threading
    PreviewMixin,       ← thumbnail loading & display
    SessionMixin,       ← save/load session, open/browse reports
    ResultsMixin,       ← results table & row actions
    DialogsMixin,       ← Adw.AlertDialog helpers
    ScanHistoryMixin,   ← previous scan runs tab
    Adw.ApplicationWindow
)
```

The composition is intentional — GTK4 widgets cannot easily be built as
standalone components, so the mixin pattern keeps each behaviour unit testable
in isolation (each mixin is tested against a `FakeWindow` stub).

---

## Data Flow

```
User action (GUI or CLI)
        │
        ▼
src/core/utils.py  ← normalize_threshold, build ScanConfig
        │
        ├─ spawn N worker threads
        │        │
        │        ├─ src/processing/media_processor.py
        │        │     detect_media_type()
        │        │     FrameExtractor.iter_frames()   (videos only)
        │        │     ThumbnailGenerator.generate()
        │        │
        │        └─ detector (nudenet.py or helloz_nsfw.py)
        │               returns confidence score + detected classes
        │
        ├─ ScanSession.add_result(ReportEntry)    ← thread-safe
        │
        └─ src/reporting/report_manager.py
              ReportManager.save_entries()         ← Excel + session JSON
```

GUI updates are marshalled back to the main thread via `GLib.idle_add` so
that worker threads never touch GTK widgets directly.

---

## Session Persistence Format

Each completed scan produces two files written by `ReportManager` under
`reports/<YYYY-MM-DD_HH-MM-SS>/`:

```
reports/
└── 2024-11-15_14-30-00/
    ├── nudity_report.xlsx      ← Excel report with embedded thumbnails
    └── nudity_report_session.json  ← JSON blob with ScanConfig + all ReportEntry rows
```

The session JSON version is stored in `constants.SESSION_VERSION` (currently 1).
`ScanHistoryMixin` indexes `reports/` at startup to populate the All Scans tab.

---

## Build and Distribution

See `docs/diagrams/05-build-pipeline.md` for the full pipeline diagram.

### Build artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| PyInstaller bundle | `dist/nudity-detector/` | One-dir bundle; run without installing Python |
| AppImage | `dist/NudityDetector-<version>-x86_64.AppImage` | Single portable file; runs on any x86-64 Linux |

### CI workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| Lint | `.github/workflows/lint.yml` | Every push and pull request | `ruff check src/ tests/` — must pass before merge |
| Tests | `.github/workflows/tests.yml` | Every push and pull request | `pytest --cov` with coverage threshold |
| Dependency Audit | `.github/workflows/audit.yml` | Every push and pull request | `pip-audit` — flags known CVEs |
| Release | `.github/workflows/release.yml` | Tag `v*.*.*` pushed | Builds AppImage, creates GitHub Release |

See [docs/releasing.md](releasing.md) for the full release process, versioning
convention, and rollback procedure.

### Build-time host requirements

```
python3, python3-pip, python3-venv, patchelf
python3-gi, python3-gi-cairo
gir1.2-gtk-4.0, gir1.2-adw-1
libgtk-4-dev, libadwaita-1-dev
glib2.0-dev-bin, pkg-config
fuse / libfuse2 (or export APPIMAGE_EXTRACT_AND_RUN=1)
```

---

## Testing Strategy

Tests live under `tests/` and mirror the `src/` package layout exactly.
The test suite runs without a display server — all GTK widget calls are
satisfied by module-level `gi` stubs injected via `sys.modules` before any
`src` import occurs.

```
tests/
├── core/          ← unit tests for constants, models, utils, scan_session
├── detectors/     ← unit tests for nudenet and helloz_nsfw detectors
├── gui/           ← mixin tests using FakeWindow stubs (no real GTK)
├── processing/    ← FrameExtractor and ThumbnailGenerator tests
└── reporting/     ← ReportManager Excel and session JSON tests
```

Run the full suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=src --cov-report=term-missing tests/
```

Run linting:

```bash
ruff check src/ tests/
```

---

## Architectural Decision Documents

Key design decisions are documented in `docs/add/`. Read the index at
`docs/add/README.md` for the full list.

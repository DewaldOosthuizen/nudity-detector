# Architecture Overview

## Folder Structure

```text
nudity-detector/
├── run_gui.py                      ← Launch the GUI
├── run_nudenet.py                  ← Launch the NudeNet CLI
├── run_deepstack.py                ← Launch the DeepStack CLI
├── requirements.txt
├── docker-compose.yml
└── src/
    ├── core/
    │   ├── constants.py            ← All configuration values
    │   ├── models.py               ← Typed dataclasses
    │   └── utils.py                ← Orchestration & public API
    ├── processing/
    │   └── media_processor.py      ← Frame extraction & thumbnails
    ├── reporting/
    │   └── report_manager.py       ← Excel & session I/O
    ├── gui/
    │   ├── app.py                  ← GTK4 + libadwaita window, _build_ui, wiring
    │   ├── scanning.py             ← ScanningMixin  (scan lifecycle & threading)
    │   ├── preview.py              ← PreviewMixin   (thumbnail loading & display)
    │   ├── session.py              ← SessionMixin   (save/load session & reports)
    │   ├── results.py              ← ResultsMixin   (table population & row actions)
    │   ├── dialogs.py              ← DialogsMixin   (error/warning/confirm dialogs)
    │   └── result_item.py          ← ResultItem     (GObject model for ColumnView rows)
    └── detectors/
        ├── nudenet.py              ← NudeNet CLI detector
        └── deepstack.py            ← DeepStack CLI detector
```

## Module Dependency Graph

```text
┌──────────────────────────────────────────────────────────────────┐
│                        Entry Points                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  run_gui.py          run_nudenet.py          run_deepstack.py    │
│      │                    │                       │              │
└──────┼────────────────────┼───────────────────────┼──────────────┘
       │                    │                       │
       ▼                    ▼                       ▼
  src/gui/app.py    src/detectors/nudenet.py  src/detectors/deepstack.py
  (GTK4/Adw UI)     (NudeNet CLI)             (DeepStack CLI)
       │
       ├─ scanning.py   (ScanningMixin)
       ├─ preview.py    (PreviewMixin)
       ├─ session.py    (SessionMixin)
       ├─ results.py    (ResultsMixin)
       ├─ dialogs.py    (DialogsMixin)
       └─ result_item.py (ResultItem GObject)
       │                    │                       │
       └────────────────────┼───────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │     src/core/utils.py     │
              │      (Coordinator)        │
              └──────┬──────┬──────┬──────┘
                     │      │      │
          ┌──────────┘      │      └───────────────┐
          │                 │                      │
          ▼                 ▼                      ▼
 src/core/constants.py  src/core/models.py  src/reporting/
 (Configuration)        (Data Classes)      report_manager.py
                                            (Excel & Session I/O)
                                                    │
                                       src/processing/
                                       media_processor.py
                                       (Frames & Thumbnails)
```

## Module Responsibilities

```text
src/core/constants.py       → Configuration ONLY  (all magic values in one place)
src/core/models.py          → Data structures ONLY (ScanConfig, ReportEntry, etc.)
src/core/utils.py           → Coordination ONLY   (public API, threading, file ops)
src/processing/
  media_processor.py        → Media operations ONLY (frames, thumbnails, type detection)
src/reporting/
  report_manager.py         → Report I/O ONLY     (Excel generation, session persistence)
src/gui/app.py              → UI presentation ONLY (GTK4/libadwaita window, _build_ui, wiring)
src/gui/scanning.py         → Scan lifecycle ONLY  (threading, classifiers, progress pulse)
src/gui/preview.py          → Thumbnail display ONLY (PIL → GdkPixbuf → Gtk.Picture)
src/gui/session.py          → Session I/O ONLY     (save/load session, report open/browse)
src/gui/results.py          → Results table ONLY   (ColumnView population, row actions)
src/gui/dialogs.py          → Dialog helpers ONLY  (error, warning, confirm via Adw.AlertDialog)
src/gui/result_item.py      → GObject model ONLY   (ResultItem for Gio.ListStore ColumnView)
src/detectors/nudenet.py    → NudeNet CLI ONLY
src/detectors/deepstack.py  → DeepStack CLI ONLY
```

## Data Flow

```text
User Input
    │
    ▼
src/gui/app.py  (or src/detectors/nudenet.py / deepstack.py)
    ├─ Reads config from src/core/constants.py
    ├─ Uses src/core/models.ScanConfig for type safety
    │
    ├─ gui/scanning.py   → scan thread, classifier setup, progress
    ├─ gui/preview.py    → thumbnail load & display
    ├─ gui/session.py    → save/load session, open report
    ├─ gui/results.py    → populate ColumnView, row actions
    ├─ gui/dialogs.py    → alert dialogs
    ├─ gui/result_item.py → GObject row model
    │
    └─ Calls src/core/utils.py (coordinator)
              │
              ├─ Spawns worker threads → processes file queue
              │
              ├─ src/processing/media_processor.py
              │     └─ detect_media_type(), FrameExtractor, ThumbnailGenerator
              │
              ├─ src/reporting/report_manager.py
              │     └─ Excel I/O, session JSON read/write
              │
              └─ src/core/models.py
                    └─ ReportEntry, SessionState, DetectionResult
```

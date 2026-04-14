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
    │   └── app.py                  ← Tkinter GUI application
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
  (Tkinter UI)      (NudeNet CLI)             (DeepStack CLI)
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
src/gui/app.py              → UI presentation ONLY (tkinter, theme, scan workflow)
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

# Architecture Overview

## Folder Structure

```text
nudity-detector/
├── run_gui.py                      ← Launch the GUI
├── run_nudenet.py                  ← Launch the NudeNet CLI
├── run_deepstack.py                ← Launch the DeepStack CLI
├── requirements.txt
├── docker-compose.yml
├── scripts/                        ← Build tooling
│   ├── build_linux.sh              ← Main Linux build script
│   ├── nudity-detector.spec        ← PyInstaller spec (one-dir mode)
│   ├── AppRun                      ← AppImage entry point
│   └── nudity-detector.desktop     ← AppImage desktop entry
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

---

## Build & Distribution

### Overview

The `scripts/` folder contains all tooling required to package the application as a portable Linux binary. The pipeline is:

```
run_gui.py
    │
    ▼ PyInstaller (one-dir)
dist/nudity-detector/              ← standalone directory bundle
    │
    ▼ linuxdeploy --plugin gtk + appimagetool
dist/NudityDetector-x86_64.AppImage ← single portable file
```

### scripts/ contents

```text
scripts/
├── build_linux.sh              ← Orchestrates the full build pipeline
├── nudity-detector.spec        ← PyInstaller spec (one-dir, GTK4/gi hidden imports)
├── AppRun                      ← AppImage entry point; sets env vars before exec
└── nudity-detector.desktop     ← FreeDesktop entry used by appimagetool
```

### Build pipeline (build_linux.sh)

| Step | Action |
|------|--------|
| 1 | Check prerequisites (`python3`, `pip3`, `patchelf`, `Gtk-4.0.typelib`) |
| 2 | Download `appimagetool`, `linuxdeploy`, and `linuxdeploy-plugin-gtk.sh` into `scripts/` (cached) |
| 3 | Create isolated build venv in `build/.build-venv`; expose system `gi` via `.pth` file |
| 4 | Install `requirements.txt` + `pyinstaller` into the build venv |
| 5 | Run PyInstaller with `scripts/nudity-detector.spec` → `dist/nudity-detector/` |
| 6 | Copy required GTK4/Adw typelibs from `/usr/lib/girepository-1.0/` into the bundle |
| 7 | Assemble `build/AppDir/` with the bundle, desktop file, icon, and `AppRun` |
| 8 | Run `linuxdeploy --plugin gtk` to gather GTK4 shared libraries, GSettings schemas, and themes |
| 9 | Compile GSettings schemas inside AppDir with `glib-compile-schemas` |
| 10 | Run `appimagetool` → `dist/NudityDetector-x86_64.AppImage` |

### What is bundled vs. host-provided

| Component | Bundled | Notes |
|-----------|---------|-------|
| Python runtime | Yes | PyInstaller embeds the interpreter |
| pip dependencies (`requirements.txt`) | Yes | Collected by PyInstaller |
| GTK4 shared libraries | Best-effort | `linuxdeploy-plugin-gtk` collects what it finds |
| GTK4 GI typelibs | Yes | Copied explicitly by the build script |
| GSettings schemas & themes | Yes | Collected by `linuxdeploy-plugin-gtk` |
| NudeNet model weights | No | Downloaded on first run; requires internet |
| libadwaita | Best-effort | Gathered by `linuxdeploy`; must exist on host to build |

### Build outputs

All artifacts are written to `dist/` which is excluded from version control:

```text
dist/
├── nudity-detector/                ← PyInstaller one-dir bundle
│   ├── nudity-detector             ← executable
│   ├── _internal/                  ← Python runtime + dependencies
│   └── config/                     ← Bundled app config
└── NudityDetector-x86_64.AppImage  ← Portable AppImage
```

### Build-time dependencies (host)

```
python3, python3-pip, python3-venv
patchelf                          ← required by PyInstaller
python3-gi, python3-gi-cairo      ← system gi (cannot be pip-installed)
gir1.2-gtk-4.0, gir1.2-adw-1     ← GTK4 + libadwaita typelibs
libgtk-4-dev, libadwaita-1-dev    ← development headers (for linuxdeploy)
glib2.0-dev-bin                   ← glib-compile-schemas
FUSE (or APPIMAGE_EXTRACT_AND_RUN=1)
```

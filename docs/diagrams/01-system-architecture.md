# 01 — System Architecture

Full component overview showing all source layers and their dependency direction.
Dependencies flow strictly downward — upper layers never import from layers above them.

```mermaid
graph TD
    subgraph Entry["Entry Points"]
        GUI["run_gui.py"]
        CLI_NN["run_nudenet.py"]
        CLI_HZ["run_helloz_nsfw.py"]
    end

    subgraph Presentation["Presentation Layer — src/gui/"]
        APP["app.py\nNudityDetectorWindow"]
        SCAN["scanning.py\nScanningMixin"]
        PREV["preview.py\nPreviewMixin"]
        SESS["session.py\nSessionMixin"]
        RES["results.py\nResultsMixin"]
        DIAL["dialogs.py\nDialogsMixin"]
        HIST["scan_history.py\nScanHistoryMixin"]
        RITEM["result_item.py\nResultItem GObject"]
    end

    subgraph Coord["Coordination Layer — src/core/utils.py"]
        UTILS["utils.py\norchestrator + public API"]
    end

    subgraph Det["Detection Layer — src/detectors/"]
        NN["nudenet.py\nNudeNet local"]
        HZ["helloz_nsfw.py\nHelloz NSFW HTTP"]
    end

    subgraph Infra["Infrastructure Layer — src/processing/"]
        MP["media_processor.py\nFrameExtractor · ThumbnailGenerator"]
    end

    subgraph Core["Core Layer — src/core/"]
        CONST["constants.py\nconfiguration values"]
        MODELS["models.py\nScanConfig · ReportEntry · SessionState"]
        SSCN["scan_session.py\nScanSession thread-safe container"]
    end

    subgraph Persist["Persistence Layer — src/reporting/"]
        RM["report_manager.py\nExcel I/O · session JSON"]
    end

    GUI --> APP
    CLI_NN --> NN
    CLI_HZ --> HZ

    APP --> SCAN & PREV & SESS & RES & DIAL & HIST & RITEM
    SCAN --> UTILS
    SESS --> UTILS
    RES --> UTILS
    HIST --> UTILS

    UTILS --> NN
    UTILS --> HZ
    UTILS --> MP
    UTILS --> RM
    UTILS --> MODELS
    UTILS --> SSCN

    NN --> MODELS
    HZ --> MODELS
    MP --> CONST
    RM --> MODELS
    RM --> CONST

    MODELS --> CONST
    SSCN --> MODELS
```

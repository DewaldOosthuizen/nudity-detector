# 04 — Session Persistence

Shows how scan results are saved to disk and how the scan history tab
re-indexes the reports directory on startup.

## Session Save

```mermaid
flowchart TD
    A([Scan Complete]) --> B[ReportManager.save_entries]
    B --> C{report_dir exists?}
    C -- No --> D[mkdir reports/YYYY-MM-DD_HH-MM-SS/]
    C -- Yes --> E[use existing dir]
    D --> F[Write nudity_report.xlsx\nopenpyxl with embedded thumbnails]
    E --> F
    F --> G[Write nudity_report_session.json\nScanConfig + all ReportEntry rows]
    G --> H([Report dir: reports/YYYY-MM-DD_HH-MM-SS/])

    H --> I[ScanHistoryMixin._refresh_history]
    I --> J[Scan reports/ for session JSON files]
    J --> K[Parse each session.json → ScanRunItem]
    K --> L[Populate history_store Gio.ListStore]
    L --> M([All Scans tab updated])
```

## Session Load

```mermaid
flowchart TD
    A([User selects row in All Scans tab]) --> B[ScanHistoryMixin._on_history_load]
    B --> C[Read session_path from ScanRunItem]
    C --> D[load_scan_session session_path]
    D --> E{JSON valid?}
    E -- No --> F[DialogsMixin._show_error\nCannot load session]
    E -- Yes --> G[Deserialise SessionState\nScanConfig + List of ReportEntry]
    G --> H[Apply ScanConfig to GUI controls\nfolder, model, threshold, theme]
    H --> I[ResultsMixin._populate_results entries]
    I --> J([Results tab populated — ready for review])
```

## Session file format

```mermaid
classDiagram
    class SessionJSON {
        <<reports/run/nudity_report_session.json>>
        version : int
        scan_config : ScanConfig
        entries : List~ReportEntry~
    }
    class ScanConfig {
        source_folder : str
        model_name : str
        threshold_percent : float
        theme_mode : str
    }
    class ReportEntry {
        file : str
        media_type : str
        model_name : str
        threshold_percent : float
        confidence_percent : float
        nudity_detected : bool
        detected_classes : str
        thumbnail : str
        date_classified : str
    }
    SessionJSON "1" *-- "1" ScanConfig
    SessionJSON "1" *-- "0..*" ReportEntry
```

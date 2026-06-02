# 03 — Scan Data Flow

End-to-end sequence for a scan initiated from the GUI.
Worker threads process files concurrently; all GUI updates are marshalled back
to the main thread via `GLib.idle_add` (see ADD-006).

```mermaid
sequenceDiagram
    actor User
    participant GUI as NudityDetectorWindow<br/>(main thread)
    participant ScanMixin as ScanningMixin
    participant Utils as src/core/utils.py
    participant Session as ScanSession
    participant Worker as Worker Thread(s)
    participant Detector as nudenet.py / helloz_nsfw.py
    participant MP as media_processor.py
    participant RM as ReportManager

    User->>GUI: Click "Start Scan"
    GUI->>ScanMixin: _start_scan()
    ScanMixin->>Utils: scan_folder(ScanConfig)
    Utils->>Session: ScanSession() — create empty container
    Utils->>Worker: spawn N threads from file queue

    loop For each file in source folder
        Worker->>MP: detect_media_type(file)
        alt Image
            Worker->>Detector: classify(file, threshold)
        else Video
            Worker->>MP: FrameExtractor.iter_frames(file)
            loop For each frame
                Worker->>Detector: classify(frame, threshold)
            end
        end
        Detector-->>Worker: (confidence, detected_classes)
        Worker->>MP: ThumbnailGenerator.generate(file)
        MP-->>Worker: base64 thumbnail
        Worker->>Session: add_result(ReportEntry) — thread-safe
        Worker->>GUI: GLib.idle_add(_append_result_row)
        GUI->>GUI: ResultsMixin._append_result_row(entry)
        GUI->>GUI: update progress bar
    end

    Worker->>Utils: join() — all threads complete
    Utils->>RM: ReportManager.save_entries(entries, report_dir)
    RM-->>Utils: report path + session path
    Utils-->>ScanMixin: scan complete callback
    ScanMixin->>GUI: GLib.idle_add(_on_scan_complete)
    GUI->>User: Show summary label + enable actions

    Note over GUI,RM: Reports saved to reports/<YYYY-MM-DD_HH-MM-SS>/
```

## Error paths

```mermaid
sequenceDiagram
    participant Worker as Worker Thread
    participant Detector as Detector
    participant GUI as GUI (main thread)

    Worker->>Detector: classify(file, threshold)

    alt NudeNet raises Python exception
        Detector-->>Worker: Exception
        Worker->>GUI: GLib.idle_add(_show_error, "Detection failed", details)
        Worker->>Worker: continue with next file
    else Helloz NSFW — service unreachable
        Detector-->>Worker: ConnectionError / timeout
        Worker->>GUI: GLib.idle_add(_show_error, "Helloz NSFW unreachable")
        Worker->>Worker: abort scan
    end
```

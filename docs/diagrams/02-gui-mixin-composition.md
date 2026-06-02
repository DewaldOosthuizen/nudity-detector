# 02 — GUI Mixin Composition

`NudityDetectorWindow` inherits from six focused mixins and `Adw.ApplicationWindow`.
Each mixin owns a single slice of the window's behaviour.
Mixins do not import each other — they communicate only through shared widget
attributes created by `_build_ui` in `app.py`.

```mermaid
classDiagram
    class AdwApplicationWindow {
        <<GTK4 / libadwaita>>
        +present()
        +set_title()
    }

    class ScanningMixin {
        <<src/gui/scanning.py>>
        +_start_scan()
        +_cancel_scan()
        +_on_scan_complete()
        -_scan_thread : Thread
        -_progress_pulse()
    }

    class PreviewMixin {
        <<src/gui/preview.py>>
        +_load_thumbnail(path)
        +_clear_preview()
        -_pil_to_gdkpixbuf()
    }

    class SessionMixin {
        <<src/gui/session.py>>
        +_save_session()
        +_load_session()
        +_open_report()
        +_browse_reports()
    }

    class ResultsMixin {
        <<src/gui/results.py>>
        +_populate_results(entries)
        +_on_open_file()
        +_on_delete_file()
        +_clear_results()
    }

    class DialogsMixin {
        <<src/gui/dialogs.py>>
        +_show_error(title, body)
        +_show_warning(title, body)
        +_show_confirm(title, body, callback)
    }

    class ScanHistoryMixin {
        <<src/gui/scan_history.py>>
        +_build_scan_history_tab()
        +_refresh_history()
        +_on_history_load()
        +_on_history_export()
        +_on_history_delete()
    }

    class NudityDetectorWindow {
        <<src/gui/app.py>>
        +_build_ui()
        -folder_entry : Gtk.Entry
        -results_store : Gio.ListStore
        -history_store : Gio.ListStore
        -progress_bar : Gtk.ProgressBar
        -summary_label : Gtk.Label
    }

    class ResultItem {
        <<src/gui/result_item.py>>
        <<GObject.Object>>
        +file_path : str
        +confidence : str
        +media_type : str
        +thumbnail : str
    }

    class ScanRunItem {
        <<src/gui/scan_history.py>>
        <<GObject.Object>>
        +dir_name : str
        +display_date : str
        +model_name : str
        +result_count : str
        +session_path : str
        +report_path : str
    }

    NudityDetectorWindow --|> ScanningMixin
    NudityDetectorWindow --|> PreviewMixin
    NudityDetectorWindow --|> SessionMixin
    NudityDetectorWindow --|> ResultsMixin
    NudityDetectorWindow --|> DialogsMixin
    NudityDetectorWindow --|> ScanHistoryMixin
    NudityDetectorWindow --|> AdwApplicationWindow

    ResultsMixin ..> ResultItem : creates
    ScanHistoryMixin ..> ScanRunItem : creates
```

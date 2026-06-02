# ADD-001 — GTK4 + libadwaita as the GUI Framework

| Field      | Value                  |
|------------|------------------------|
| Status     | Accepted               |
| Date       | 2024-01-01             |
| Author     | Dewald Oosthuizen      |
| Relates to | ADD-002, ADD-006       |

---

## Context

The application needs a native desktop GUI on Linux for displaying scan
results, thumbnails, and interactive review actions (open file, delete, load
session). Python's GUI toolkit ecosystem offers several options. The GUI must
feel native on GNOME-based desktops, support a dark/light theme toggle, and
be distributable as an AppImage without requiring the end user to install Python.

The NudeNet and Helloz NSFW backends are Python-only, so the GUI must run in
the same Python process (no Electron-style subprocess split).

---

## Decision

Use **GTK4** for the widget layer and **libadwaita** for GNOME HIG-compliant
styling (`Adw.ApplicationWindow`, `Adw.StyleManager`, `Adw.AlertDialog`).
PyGObject (`gi.repository`) provides the Python bindings.

```python
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
```

`Gtk.ColumnView` backed by a `Gio.ListStore` is used for the results and
scan history tables instead of the deprecated `Gtk.TreeView`.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| GTK4 + libadwaita | Native GNOME widgets, HIG-compliant | **Accepted** |
| Qt6 (PyQt6 / PySide6) | Cross-platform, mature — but non-native on GNOME, requires separate license consideration | Rejected |
| Tkinter | stdlib, zero extra deps — but dated appearance, no native theming | Rejected |
| Electron + Python subprocess | Modern UI — but doubles runtime size and adds JS/Node dependency | Rejected |

---

## Consequences

**Positive:**
- Native GNOME HIG look and feel out of the box via libadwaita.
- `Adw.StyleManager` provides system/light/dark theme switching with a single call.
- `Gtk.ColumnView` + `Gio.ListStore` scales to thousands of rows without
  per-row widget allocation.
- GTK4 typelibs and shared libraries are available on all major Linux distros,
  simplifying the AppImage bundle.

**Negative / Trade-offs:**
- PyGObject (`gi`) cannot be installed via `pip` — it is a system package.
  Developers must expose it to their venv manually via a `.pth` file.
  The `scripts/build_linux.sh` script handles this automatically for the
  packaged build.
- The application is Linux-only. Windows and macOS do not have first-class
  GTK4 support in Python.
- Testing GTK4 widgets requires full stub injection of the `gi` module tree
  at the `sys.modules` level before any `src` import occurs (see ADD-002).

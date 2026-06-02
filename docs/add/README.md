# Architectural Decision Documents (ADD)

Records of significant design decisions made in the Nudity Detector project.
Each document captures the context, options considered, the decision taken,
and its consequences — so future maintainers understand *why* the code is
structured as it is, not just *how* it works.

| ADD  | Title                                                    | Status   |
|------|----------------------------------------------------------|----------|
| 001  | GTK4 + libadwaita as the GUI framework                   | Accepted |
| 002  | Mixin-based GUI composition                              | Accepted |
| 003  | Pluggable detector backends                              | Accepted |
| 004  | PyInstaller one-dir + AppImage packaging pipeline        | Accepted |
| 005  | Ruff as the sole linting tool                            | Accepted |
| 006  | GLib.idle_add for GUI updates from worker threads        | Accepted |

## Conventions

- **Status values:** Proposed / Accepted / Deprecated / Superseded
- Superseded entries reference the ADD that replaces them.
- Do not delete superseded ADDs — update their status and add a forward reference.
- Keep prose concise; code snippets are illustrative, not normative.
- The date recorded is the date the decision was implemented.

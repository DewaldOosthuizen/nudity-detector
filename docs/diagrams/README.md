# Diagrams

Mermaid architecture and flow diagrams for Nudity Detector.
All diagrams render natively on GitHub in fenced ```mermaid code blocks.

| File | Diagram Type | Purpose |
|------|-------------|---------|
| [01-system-architecture.md](01-system-architecture.md) | graph TD | Full component overview and layer dependencies |
| [02-gui-mixin-composition.md](02-gui-mixin-composition.md) | classDiagram | NudityDetectorWindow mixin hierarchy and responsibilities |
| [03-scan-data-flow.md](03-scan-data-flow.md) | sequenceDiagram | End-to-end scan lifecycle from user action to report |
| [04-session-persistence.md](04-session-persistence.md) | flowchart TD | Session save/load and scan history indexing |
| [05-build-pipeline.md](05-build-pipeline.md) | flowchart TD | PyInstaller → AppImage build pipeline and CI release |

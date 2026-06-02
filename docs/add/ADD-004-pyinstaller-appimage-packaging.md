# ADD-004 — PyInstaller One-Dir + AppImage Packaging Pipeline

| Field      | Value                     |
|------------|---------------------------|
| Status     | Accepted                  |
| Date       | 2024-03-01                |
| Author     | Dewald Oosthuizen         |
| Relates to | —                         |

---

## Context

Distributing a GTK4 Python application to end users without requiring them to
install Python, PyGObject, and NudeNet is non-trivial. The application bundles:

- Python 3.12 runtime
- PyGObject (`gi`) — a system package, not pip-installable
- GTK4 + libadwaita shared libraries and typelibs
- NudeNet and its ONNX model dependencies
- OpenCV (cv2) for video frame extraction

The packaging approach must produce a single artifact that:
1. Runs on any x86-64 Linux without requiring the user to install anything.
2. Includes all Python and native dependencies.
3. Is reproducible on a clean CI runner (GitHub Actions).

---

## Decision

Two-stage pipeline in `scripts/build_linux.sh`:

**Stage 1 — PyInstaller one-dir bundle**

`scripts/nudity-detector.spec` drives PyInstaller in `onedir` mode. This
produces `dist/nudity-detector/` — a directory containing the executable and
all Python dependencies alongside it. One-dir is chosen over one-file because
one-file extracts to `/tmp` on every launch, which triggers security policies
on some systems and slows startup significantly for a large bundle.

`gi` is exposed to the isolated build venv by writing a `.pth` file pointing
at the system PyGObject site-packages — the only reliable way to include
`gi` in a non-system Python environment.

**Stage 2 — linuxdeploy + appimagetool**

`linuxdeploy --plugin gtk` gathers GTK4 shared libraries, GSettings schemas,
and icon themes from the build host. `appimagetool` wraps the assembled
`AppDir` into a single executable AppImage.

The `AppRun` script in `scripts/AppRun` sets all required environment variables
(`LD_LIBRARY_PATH`, `GI_TYPELIB_PATH`, `GSETTINGS_SCHEMA_DIR`, `XDG_DATA_DIRS`)
relative to the AppImage mount point before delegating to the PyInstaller bundle.

**CI integration**

A GitHub Actions release workflow (`.github/workflows/release.yml`) triggers on
`v*.*.*` tags and runs `scripts/build_linux.sh` with `APPIMAGE_EXTRACT_AND_RUN=1`
(GitHub Actions runners have no FUSE). The resulting AppImage is renamed to
`NudityDetector-<version>-x86_64.AppImage` and published as a GitHub Release asset.

---

## Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| PyInstaller one-file | Single executable — but slow startup (extraction to /tmp) and security restrictions | Rejected |
| PyInstaller one-dir (current) | Directory bundle; fast startup; all deps alongside binary | **Stage 1 — Accepted** |
| AppImage (appimagetool only) | Portable single file — but requires all deps pre-gathered | **Stage 2 — Accepted** |
| Flatpak | Sandboxed, distro-agnostic — but requires Flatpak runtime on target; complex manifest | Deferred |
| Snap | Ubuntu-native — not portable across all distros without snapd | Rejected |
| Docker image | Reproducible — but requires Docker on end-user machine; not suitable for desktop GUI | Rejected |
| Nix/Nixpkg | Fully reproducible builds — but steep learning curve; not applicable to current team | Rejected |

---

## Consequences

**Positive:**
- The AppImage runs on Ubuntu 20.04+ and all major GNOME-based distros.
- `scripts/build_linux.sh` is self-contained — it downloads tools on first
  run and caches them; developers can build locally without any CI dependency.
- NudeNet model weights are NOT bundled — they are downloaded on first run,
  keeping the AppImage size reasonable.
- `APPIMAGE_EXTRACT_AND_RUN=1` makes the build portable across FUSE and
  non-FUSE environments without code changes.

**Negative / Trade-offs:**
- GTK4 and libadwaita must be installed on the build host (not the target host).
  The `linuxdeploy-plugin-gtk` bundles what it can find, but full portability
  depends on how the target distro ships GTK4.
- The build script downloads `linuxdeploy` and `appimagetool` at build time
  from GitHub releases. If those URLs change, the build breaks.
- NudeNet requires internet access on first launch — unsuitable for air-gapped
  environments without pre-staging the model cache.

# Nudity Detector

Python-based application for detecting nudity in images and videos using AI backends.
Suitable for content moderation, safety filters, and compliance checks.

Two detector backends:
- **NudeNet** — local detection via the `nudenet` library, no server required.
- **Helloz NSFW** — remote detection via the `helloz/nsfw` Docker AI server (http://localhost:6086).

Always reference these instructions first and fall back to search or bash commands only when you encounter information that does not match what is documented here.

---

## Repository Structure

```
.
├── run_gui.py                  # GTK4 + libadwaita GUI entry point (recommended)
├── run_nudenet.py              # CLI entry point — NudeNet backend
├── run_helloz_nsfw.py          # CLI entry point — Helloz NSFW backend
├── src/
│   ├── core/                   # Shared domain logic (constants, config, models)
│   ├── detectors/              # NudeNet and Helloz NSFW detector implementations
│   ├── gui/                    # GTK4/libadwaita GUI components
│   ├── processing/             # File processing, frame extraction (video)
│   └── reporting/              # Excel report and session state generation
├── tests/                      # Pytest test suite (mirrors src/ structure)
├── config/
│   └── app_config.json         # Runtime config — Helloz host/port/endpoint
├── .env.example                # Available env overrides with defaults
├── scripts/
│   ├── build_linux.sh          # Linux PyInstaller + AppImage build script
│   └── nudity-detector.spec    # PyInstaller spec
├── openspec/                   # openspec change specs and archive
├── docs/
│   └── ARCHITECTURE.md         # Architecture documentation
├── docker-compose.yml          # Helloz NSFW Docker AI server
├── requirements.txt            # Pinned runtime dependencies (==)
└── requirements-dev.txt        # Runtime + dev/test tools (pip-audit, pytest)
```

---

## Working Effectively

### Bootstrap and Dependencies

Install system GTK dependencies (required for the GUI — Linux only):

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Expose system GTK bindings to the venv (PyGObject cannot be pip-installed):

```bash
VENV_SITE_PACKAGES="$(.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])')"
GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)')"
printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
```

Install dependencies:

```bash
# Runtime only
pip install -r requirements.txt

# Development + security auditing
pip install -r requirements-dev.txt

# Audit for known vulnerabilities
pip-audit -r requirements.txt
```

> Takes ~45–90 seconds. Do NOT cancel. Set timeout to 900+ seconds.

### AI Backend Setup

#### NudeNet (local — no extra setup)

Works immediately after pip install. No server required.

```bash
python3 -c "from nudenet import NudeDetector; d = NudeDetector(); print('NudeNet ready')"
```

#### Helloz NSFW (Docker server)

```bash
docker-compose up --build
```

> First run downloads the image (~47 seconds). Do NOT cancel. Set timeout to 600+ seconds.
> Container needs ~10 seconds to fully initialize after starting.

Verify the server is ready:

```bash
curl -X POST -F file=@test.jpg 'http://localhost:6086/api/upload_check'
```

The endpoint is configurable via `config/app_config.json` keys:
`helloz_nsfw_host`, `helloz_nsfw_port`, `helloz_nsfw_api_endpoint`.
See `.env.example` for defaults.

---

## Running the Application

### GUI (Recommended)

Requires GTK4 + libadwaita (pre-installed on most GNOME desktops). Not available in headless environments.

```bash
python3 run_gui.py
```

Features: model selection, theme control (`system`/`light`/`dark`), folder browsing, threshold control,
progress tracking, detected-media review table, thumbnail preview, save/load sessions.

### CLI

```bash
# NudeNet
python3 run_nudenet.py

# Helloz NSFW (requires Docker server running)
python3 run_helloz_nsfw.py
```

Both CLIs prompt for: source folder path and detection threshold percentage.

---

## Testing

```bash
# Run the full test suite
pytest tests/

# With coverage
pytest --cov tests/
```

Tests mirror `src/` — `tests/core/`, `tests/detectors/`, `tests/gui/`, `tests/processing/`, `tests/reporting/`.

> GTK/gi cannot be imported in headless test environments. GUI modules must be mocked or skipped.

---

## Output

Reports are saved under `reports/<timestamp>/` in the working directory.
Source files are **not** moved or copied — they stay in their original location.

Each report includes:
- `nudity_report.xlsx` — file path, media type, model, threshold, confidence, nudity classes, embedded thumbnail.
- Session data — theme mode, source folder, selected model, threshold, detected rows — for GUI `Load Session`.

---

## Supported File Formats

Images: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF
Videos: MP4, AVI, MKV, MOV, VOB, WMV, FLV, 3GP, WEBM

Videos are processed by extracting frames and analysing them as images.

---

## Building a Linux Package

Prerequisites:

```bash
sudo apt-get install python3 python3-pip python3-venv patchelf \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
    libgtk-4-dev libadwaita-1-dev glib2.0-dev-bin
```

Build:

```bash
bash scripts/build_linux.sh
```

Outputs in `dist/`:
- `dist/nudity-detector/` — PyInstaller self-contained bundle.
- `dist/NudityDetector-x86_64.AppImage` — single portable file.

Run without installing:

```bash
./dist/nudity-detector/nudity-detector
# or
chmod +x dist/NudityDetector-x86_64.AppImage && ./dist/NudityDetector-x86_64.AppImage
```

On systems without FUSE (some CI): `export APPIMAGE_EXTRACT_AND_RUN=1`

Custom icon: place a 256×256 PNG at `scripts/nudity-detector.png` before building.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'gi'` | GTK bindings not exposed to venv | Complete the `system-gi.pth` step above |
| GUI fails with "no display" | Headless environment | Use CLI entry points instead |
| Helloz NSFW API 404 | Container still initializing | Wait 15+ seconds after `docker-compose up` |
| Import errors on pip install | Incomplete install | Re-run `pip install -r requirements.txt` with timeout ≥900s |
| Docker permission error | User not in docker group | Add user or prefix with `sudo` |

---

<!-- graph-tools-start -->

## Code Exploration and Token Efficiency

Use these tools in order before opening raw source files:

### codegraph (`.codegraph/` present)

Use FIRST for symbol lookup, call tracing, and targeted context.

```bash
codegraph context "<task description>" -p .   # which symbols matter?
codegraph query "<ClassName or function>" -p . # where is X defined/used?
codegraph affected <changed-files> -p .        # which tests are affected?
codegraph sync .                               # after any code change
```

### understand-anything (`.understand-anything/knowledge-graph.json` present)

Use for architecture questions — layers, communities, entry points.

```bash
cd ~/.understand-anything-plugin/packages/dashboard
GRAPH_DIR=$(pwd) npx vite --host 127.0.0.1
```

For prose questions, load the `understand-chat` skill in Hermes.

Fall back to grep or direct file reading only when these tools return insufficient results.

<!-- graph-tools-end -->

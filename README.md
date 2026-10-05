# Nudity Detector

[![Tests](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/test.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/test.yml)
[![Lint](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/lint.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/lint.yml)
[![Dependency Audit](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/audit.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/audit.yml)
[![Release](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml/badge.svg)](https://github.com/DewaldOosthuizen/nudity-detector/actions/workflows/release.yml)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/paypalme/DewaldOosthuizen1)

This project, Nudity Detector, is a Python-based application designed to detect nudity in images and videos. It provides an
efficient and automated solution for identifying explicit content, making it suitable for applications such as content
moderation, safety filters, and compliance checks.

## Overview

The **Nudity Detector** application identifies nudity in images and videos using AI-based models. It scans files, stores reports in a dedicated reports folder, and presents detected items in the GUI for review actions.

Two detector backends are available:

- **NudeNet**: Uses the `nudenet` library for local nudity detection.
  - Basic
  - Not always accurate
  - Processes videos by extracting frames and analysing them as images.
- **Helloz NSFW**: Uses the `helloz/nsfw` Docker AI server for detection.

## Features

1. **Graphical User Interface**: Modern GTK4 + libadwaita GUI with native theming, model selection, threshold control, and progress tracking.
2. **File Classification**: Identifies nudity in supported image and video files.
3. **File Management**: Keeps detected files in their original location for direct review.
4. **Report Generation**: Creates an Excel report in the `reports` folder summarizing detection results.
5. **Multi-Threading**: Speeds up classification by processing files in parallel.
6. **Real-time Progress**: Visual progress indicators and logging during scanning.
7. **Saved Scan Sessions**: Stores scan settings and detected-media state so you can reload a prior review later.
8. **Review Actions**: Lists detected images and videos with confidence scores and allows opening file locations or deleting files.
9. **Thumbnail Support**: Generates and displays thumbnails in reports and in the GUI review pane.

---

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/DewaldOosthuizen/nudity-detector.git
   ```

2. **Navigate to inside the repository**:

   ```Bash
   cd nudity-detector
   ```

3. **Create a virtual environment** (optional but recommended):

   ```bash
   python3 -m venv .venv
   ```

4. **Install system GTK dependencies** (required for the GUI):

   On Ubuntu/Debian:

   ```bash
   sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
   ```

   > **Note:** Windows and macOS are not officially supported by GTK4 on Python. The GUI is designed for Linux.

5. **Expose the system GTK bindings to the virtual environment** (required for the GUI):

   PyGObject (`gi`) is a system package and cannot be installed via pip. Run the following to make it accessible inside the venv:

   ```bash
   VENV_SITE_PACKAGES="$(.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])')"
   GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)')"
   printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
   ```

   > **Note:** If you see `ModuleNotFoundError: No module named 'gi'` when running the GUI, this step was not completed. Step 4 must be done first.

7. **Install the `libmagic` system library** (required for magic-byte media type detection):

   The `python-magic` dependency wraps the system `libmagic` shared library, which is used to
   verify a file's real content type before trusting its extension.

   On Ubuntu/Debian:

   ```bash
   sudo apt-get install libmagic1
   ```

   > **Note:** `libmagic1` is already present on most Linux systems (it backs the `file` command).

7. **Install requirements**:

  Two dependency files are provided:

  - `requirements.txt` — pinned runtime dependencies (all versions locked with `==`).
  - `requirements-dev.txt` — includes `requirements.txt` plus dev/testing tools (`pip-audit`, `pytest`).

  Activate the venv environment if you are using one.

  ```bash
  source ./.venv/bin/activate
  ```

  For running the application (runtime only):

  ```bash
  pip install -r requirements.txt
  ```

  For development and security auditing:

  ```bash
  pip install -r requirements-dev.txt
  ```

  To audit dependencies for known vulnerabilities:

  ```bash
  pip-audit -r requirements.txt
  ```

  or

  ```bash
  ./.venv/bin/pip install -r requirements.txt
  ```

7. **Install docker and docker compose**

    - Follow the instructions for your OS on the official Docker website: <https://docs.docker.com/get-docker/>
    - Ensure Docker Compose is installed. Instructions can be found here: <https://docs.docker.com/compose/install/>
  
8. **Prepare Models**:

   - Nudenet
     - For Nudenet no setup is required.
   - Helloz NSFW
     - Run the docker-compose.yml file to start your server

       ```bash
       docker-compose up --build
       ```

   - Once started, Helloz NSFW will be available at <http://localhost:6086>.
   - You can test if your server is running by executing the following (Replace the image path with an existing image)

    ```bash
    curl -X POST -F file=@test.jpg 'http://localhost:6086/api/upload_check'
    ```

   - The Helloz NSFW endpoint is configurable via `config/app_config.json` using the keys
     `helloz_nsfw_host`, `helloz_nsfw_port`, and `helloz_nsfw_api_endpoint`.

## Configuration

The Nudity Detector application has a single configuration surface: `config/app_config.json`.
That file is created by the app on first run and is **not tracked in git** — it also
holds mutable user state (`theme`, `model`, `last_source_folder`), so tracking it would leave
every working tree permanently dirty. The documented defaults live in the immutable fixture
`tests/fixtures/app_config.default.json`.
No environment-variable overrides are supported — there is no `python-dotenv` or `os.environ`
usage anywhere in the codebase. `.env.example` is a plain-text reference table documenting all
`app_config.json` keys, their code-default constants (where applicable), and default values; it
is not an env-var template.

All 19 keys in `config/app_config.json`:

| Key | Default | Constant (src/core/constants.py) | Scope |
|-----|---------|----------------------------------|-------|
| `config_version` | `2` | `CONFIG_VERSION` | app-wide |
| `theme` | `"dark"` | `THEME_DARK` | app-wide |
| `model` | `"helloz_nsfw"` | *no constant* | app-wide |
| `threshold_percent` | `60.0` | `DEFAULT_THRESHOLD_PERCENT` | app-wide |
| `last_source_folder` | `""` | *no constant* | app-wide |
| `progress_update_interval` | `100` | `SCAN_PROGRESS_UPDATE_INTERVAL` | app-wide |
| `video_frame_rate` | `5` | `VIDEO_FRAME_RATE` | app-wide |
| `worker_thread_count` | `10` | `WORKER_THREAD_COUNT` | app-wide |
| `worker_thread_timeout_seconds` | `5` | `WORKER_THREAD_TIMEOUT` | app-wide |
| `nudenet_worker_thread_count` | `4` | *no constant*, *dead* — see #104 | app-wide |
| `nudenet_worker_thread_timeout_seconds` | `10` | *no constant*, *dead* — see #104 | app-wide |
| `helloz_nsfw_worker_thread_count` | `20` | *no constant*, *dead* — see #104 | Helloz-NSFW |
| `helloz_nsfw_worker_thread_timeout_seconds` | `35` | *no constant*, *dead* — see #104 | Helloz-NSFW |
| `detect_timeout_seconds` | `60` | `DETECT_TIMEOUT` | app-wide |
| `helloz_nsfw_host` | `"localhost"` | `HELLOZ_NSFW_HOST` | Helloz-NSFW |
| `helloz_nsfw_port` | `6086` | `HELLOZ_NSFW_PORT` | Helloz-NSFW |
| `helloz_nsfw_api_endpoint` | `"/api/upload_check"` | `HELLOZ_NSFW_API_ENDPOINT` | Helloz-NSFW |
| `helloz_nsfw_request_timeout_seconds` | `30` | `HELLOZ_NSFW_REQUEST_TIMEOUT` | Helloz-NSFW |
| `helloz_nsfw_health_check_timeout_seconds` | `5` | `HELLOZ_NSFW_HEALTH_CHECK_TIMEOUT` | Helloz-NSFW |

Note on units: the `_seconds` suffix is the unit declaration. All timeout values are
stored in **seconds**, matching the constants in `src/core/constants.py` and the
`threading` API. No value is ever re-interpreted on the strength of its magnitude, so
`detect_timeout_seconds: 3600` means one hour, as written.

Every timeout key states its unit in its name — there is no bare `*_timeout` key,
so the suffix is a reliable marker and not a convention. Four entries are
nonetheless **not read by any code** (no `src/` references) and are retained only as
reference entries: `nudenet_worker_thread_count`,
`helloz_nsfw_worker_thread_count`, `nudenet_worker_thread_timeout_seconds` and
`helloz_nsfw_worker_thread_timeout_seconds`. Their removal is tracked in issue #104,
and `constants.DEAD_CONFIG_KEYS` is the single source of that list — a test greps
`src/` for every shipped key, so a key cannot be documented as live without a reader.

Only `worker_thread_count` is read for the worker pool; the per-detector counts above
are inert.

### Automatic migration (issue #91)

The config carries a `config_version`. Before version 2 the two timeout keys were
named `worker_thread_timeout` / `detect_timeout` and held **milliseconds** — which is
what produced the reported 250-second hangs on the values the project shipped.

On startup, `src/core/config_migration.py` converts any pre-version-2 config once,
deterministically:

- A legacy value of at least one second (`>= 1000` ms) is converted ms → s,
  round-half-up (`2500` → `3`).
- A legacy value below one second — including the shipped `250` — becomes the code
  default (`5` s / `60` s). The whole `0–999` ms band is treated this way, *not* just
  values that round to 0 s: 250 ms is 0.25 s and 700 ms is 0.7 s, neither of which is
  a usable whole-second timeout, and rounding either up to 1 s would time out on
  essentially every file.
- Four keys that already held seconds but lacked the suffix
  (`helloz_nsfw_request_timeout`, `helloz_nsfw_health_check_timeout`,
  `nudenet_worker_thread_timeout`, `helloz_nsfw_worker_thread_timeout`) are **renamed**
  with their values untouched — the unit was always seconds for those keys.
- When a config carries *both* spellings of a key, the `_seconds` value is authoritative:
  the legacy key is dropped and the explicit value kept, never overwritten.
- The migrated file is written back to disk at startup — atomically, via a sibling temp
  file and `os.replace`, so an interrupted rewrite cannot truncate the user's only config
  file — and stamped `config_version: 2`, so the conversion never runs twice.

Every rewrite is logged at WARNING level **and** written to the on-screen activity log,
naming the key and both the old and new value. So is a config file that could not be read
or rewritten, which is the state in which a stale on-disk config matters most. Re-check
your timeout values once after upgrading; the log tells you exactly what changed.

Exactly one config entry has no corresponding constant in `src/core/constants.py` and
is read directly from `config/app_config.json` at runtime: `last_source_folder`. The
four entries listed above as dead have no constant *and* no reader. A test enumerates
both sets (`FIXTURE_NON_CONSTANT_KEYS` / `constants.DEAD_CONFIG_KEYS`) so the
classification cannot drift.

Every numeric config value — in `__init__` and in every widget accessor — is coerced by
`constants.normalize_positive_int` / `constants.normalize_timeout_seconds`: an
unparseable, boolean, or out-of-range value falls back to the constant default (or is
clamped to the documented bound) and is logged at WARNING level, so no config error is
applied silently.

Supported ranges: `helloz_nsfw_port` is clamped to `1..65535`, and the timeout keys to
their `TIMEOUT_MAX_SECONDS` bound (`worker_thread_timeout_seconds` and
`detect_timeout_seconds`: 86400 s; the two Helloz timeouts: 3600 s). The GUI spin
buttons use the same bounds, so a value inside the supported range is never truncated
by the widget. A value *beyond* it is clamped, and
`constants.log_timeout_truncations` reports the truncation at WARNING with the key,
the configured value and the applied maximum — the note reaches the activity log, so a
clamped value is visible rather than silently rewritten on the next save.

A value that is the right unit but the wrong magnitude relative to its constant (e.g. a
hand-tuned `helloz_nsfw_request_timeout_seconds: 300` against the 30 s code default) is
legitimate and is honoured as written — but `constants.log_config_default_divergences`
reports it at WARNING on startup and the note reaches the activity log, so the shipped
defaults agree with `constants.py` on day one and any later divergence is visible.

Startup validation: if `config/app_config.json` is missing or contains invalid JSON,
`_load_helloz_config` in `src/core/constants.py` logs a `WARNING` and falls back to
the built-in defaults from `constants.py`. See the `logger.warning` call in that
function for the exact message.

9. **Run the process**:

### Option 1: GUI Application (Recommended)

The GUI requires **GTK4** and **libadwaita**. These are pre-installed on most modern GNOME-based Linux desktops.

  Then run:

  ```bash
  python3 run_gui.py
  ```

  The GUI provides a modern libadwaita interface with:

- Model selection (NudeNet or Helloz NSFW)
- Theme selection (`system`, `light`, `dark`) via `Adw.StyleManager`
- Folder browsing and selection
- Detection threshold control in percentages
- Progress tracking with visual indicators
- Automatic report and session generation
- Detected media review table with confidence percentages
- Thumbnail preview panel for selected results
- Save/load workflow for returning to a previous review session
- Quick access to reports and source file locations

### Option 2: Command Line

- NudeNet

  ```bash
  python3 run_nudenet.py
  ```

  Prompts:
  - source folder path
  - detection threshold percentage

- Helloz NSFW

  ```bash
  python3 run_helloz_nsfw.py
  ```

  Prompts:
  - source folder path
  - detection threshold percentage

## Supported File Formats

### Images

- PNG
- JPG
- JPEG
- GIF
- BMP
- WEBP
- TIFF

### Videos

- MP4
- AVI
- MKV
- MOV
- VOB
- WMV
- FLV
- 3GP
- WEBM

## Output

### Reports Folder

Reports are saved in a `reports` folder created in the current directory.

Detected files are **not copied** into the reports folder; source files remain in their original location.

### Report File

A detailed Excel report named nudity_report.xlsx is saved in the reports folder.
The report includes:

- File path
- Media type
- Model used
- Threshold percentage
- Confidence percentage
- Nudity detection status
- Detected nudity classes
- Thumbnail image (embedded)

### GUI Review

The GUI review panel includes:

- Detected-item table with confidence and source path
- Thumbnail preview for selected result rows
- `Open File` action to open the selected image/video directly
- `Open Location` action to open the parent folder

### Session State

Each saved report now stores companion session data so the GUI can restore:

- Theme mode
- Source folder
- Selected model
- Detection threshold
- Detected media rows with confidence and file paths

Use the GUI `Save Session` and `Load Session` actions to resume review work later.

## Building a Linux Package

The `scripts/build_linux.sh` script produces two distributable artifacts in the `dist/` folder:

| Artifact | Path | Description |
|---|---|---|
| PyInstaller bundle | `dist/nudity-detector/` | Self-contained directory, run without installing Python |
| AppImage | `dist/NudityDetector-x86_64.AppImage` | Single portable file, runs on any x86-64 Linux |

### Build prerequisites

Install the following before running the build script:

```bash
sudo apt-get install python3 python3-pip python3-venv patchelf \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
    libgtk-4-dev libadwaita-1-dev glib2.0-dev-bin
```

FUSE support is required to run AppImages. On systems without FUSE (e.g. some CI environments) set:

```bash
export APPIMAGE_EXTRACT_AND_RUN=1
```

### Run the build

```bash
bash scripts/build_linux.sh
```

The script will:
1. Download `appimagetool` and `linuxdeploy` (with GTK plugin) into `scripts/` on first run (cached for subsequent builds).
2. Create an isolated build virtual environment in `build/`.
3. Run PyInstaller using `scripts/nudity-detector.spec` to produce `dist/nudity-detector/`.
4. Bundle GTK4 typelibs and copy them into the PyInstaller output.
5. Assemble an AppDir and run `linuxdeploy --plugin gtk` to gather GTK4 shared libraries, schemas, and themes.
6. Package everything into `dist/NudityDetector-x86_64.AppImage` with `appimagetool`.

### Running the artifacts

```bash
# PyInstaller bundle (no install required)
./dist/nudity-detector/nudity-detector

# AppImage (make executable first)
chmod +x dist/NudityDetector-x86_64.AppImage
./dist/NudityDetector-x86_64.AppImage
```

### Custom icon

Place a `256×256` PNG at `scripts/nudity-detector.png` before building to embed a custom icon in the AppImage. If no custom icon is found, a system fallback icon is used.

### Runtime requirements on the target system

- GTK4 (`libgtk-4-1`) and libadwaita (`libadwaita-1-0`) must be installed on the target system. The `linuxdeploy` GTK plugin bundles the GTK shared libraries where possible, but full GTK4 portability depends on the target distribution.
- NudeNet model weights are **downloaded on first run** and require internet access.

### Build output location

Both artifacts are written to the `dist/` folder, which is excluded from version control via `.gitignore`.

---

## Notes

Helloz NSFW requires the Docker AI server to be running during script execution.
Ensure sufficient disk space for processing large files or folders.

## License

This project is licensed under the MIT License.

For contributions or support, feel free to open an issue or a pull request. 😊

## Releasing

A GitHub Release with an AppImage attached is created automatically when a
version tag is pushed. No manual steps are needed beyond tagging.

```
# stable release
git tag v1.2.0
git push origin v1.2.0

# pre-release  (tag contains a hyphen — marked pre-release automatically)
git tag v1.2.0-rc1
git push origin v1.2.0-rc1
```

The `Release` workflow builds the AppImage on a clean Ubuntu runner, verifies
the artifact, and publishes it to the GitHub Releases page with auto-generated
release notes from commits since the previous tag.

See [docs/releasing.md](docs/releasing.md) for the full process, versioning
convention, and rollback procedure.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture overview — layers, modules, data flow, testing strategy |
| [docs/add/README.md](docs/add/README.md) | Architectural Decision Documents index |
| [docs/diagrams/README.md](docs/diagrams/README.md) | Mermaid diagram suite |
| [docs/releasing.md](docs/releasing.md) | Full release process and versioning guide |

---
## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
the full workflow, including how to pick up an issue, branch naming conventions,
local validation steps, and the pull request process.

## Development

Install runtime and development dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run the test suite:

```bash
pytest tests/
```

Run with coverage report:

```bash
pytest --cov=src --cov-report=term-missing tests/
```

## Dependency Management

This project uses a pip-tools two-file workflow to keep dependencies fully pinned and reproducible.

- requirements.in  — human-edited abstract file with version ranges (source of truth)
- requirements.txt — auto-generated lock file produced by pip-compile (do NOT edit by hand)

### Upgrading or adding a dependency

1. Edit requirements.in (add a package or widen/tighten a version range).
2. Regenerate the lock file:
   pip-compile requirements.in -o requirements.txt
3. Install from the lock file:
   pip install -r requirements.txt
4. Run the test suite to confirm no regressions:
   pytest tests/
5. Commit both files together:
   git add requirements.in requirements.txt && git commit

Important: never use "pip freeze > requirements.txt". Always regenerate via pip-compile.

The project intentionally uses only the CPU-only `onnxruntime` variant. The
`vnudenet` package and its `onnxruntime-gpu` transitive dependency are
excluded from `requirements.in` because they are unused by this codebase and
would add approximately 500 MB of CUDA/cuDNN artifacts to CPU-only
installations. The rationale is also documented in a comment above the
`nudenet` line in `requirements.in`.

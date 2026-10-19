# Getting Started

## Prerequisites

### System GTK dependencies (required for the GUI)

On Ubuntu/Debian:

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libmagic1
```

- **GTK4** and **libadwaita** — pre-installed on most modern GNOME-based Linux desktops.
- **libmagic1** — backs the `file` command; required by `python-magic` for media type detection.

> **Note:** Windows and macOS are not officially supported by GTK4 on Python. The GUI is designed for Linux.

### Docker (required for Helloz NSFW backend)

Follow the instructions for your OS on the official Docker website: <https://docs.docker.com/get-docker/>

Ensure Docker Compose is installed: <https://docs.docker.com/compose/install/>

---

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/DewaldOosthuizen/nudity-detector.git
   cd nudity-detector
   ```

2. **Create a virtual environment** (optional but recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Expose the system GTK bindings to the virtual environment** (required for the GUI):

   PyGObject (`gi`) is a system package and cannot be installed via pip. Run the following to make it accessible inside the venv:

   ```bash
   VENV_SITE_PACKAGES="$(.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])')"
   GI_SYSTEM_PATH="$(/usr/bin/python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)')"
   printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
   ```

   > **Note:** If you see `ModuleNotFoundError: No module named 'gi'` when running the GUI, this step was not completed. System GTK dependencies must be installed first.

4. **Install requirements**:

   Two dependency files are provided:

   - `requirements.txt` — pinned runtime dependencies (all versions locked with `==`).
   - `requirements-dev.txt` — includes `requirements.txt` plus dev/testing tools (`pip-audit`, `pytest`).

   For running the application (runtime only):

   ```bash
   pip install -r requirements.txt
   ```

   For development and security auditing:

   ```bash
   pip install -r requirements-dev.txt
   ```

5. **Prepare Models**:

   - **NudeNet**: No setup required. Model weights are downloaded on first run (internet access needed).
   - **Helloz NSFW**: Start the Docker service:

     ```bash
     docker-compose up --build
     ```

     Once started, Helloz NSFW will be available at <http://localhost:6086>.

     Test the server (replace the image path with an existing image):

     ```bash
     curl -X POST -F file=@test.jpg 'http://localhost:6086/api/upload_check'
     ```

     The endpoint is configurable via `config/app_config.json` — see [configuration.md](configuration.md).

---

## Running the Application

### Option 1: GUI Application (Recommended)

```bash
python3 run_gui.py
```

The GUI provides:

- Model selection (NudeNet or Helloz NSFW)
- Theme selection (`system`, `light`, `dark`)
- Folder browsing and selection
- Detection threshold control in percentages
- Progress tracking with visual indicators
- Automatic report and session generation
- Detected media review table with confidence percentages
- Thumbnail preview panel for selected results
- Save/load workflow for returning to a previous review session
- Quick access to reports and source file locations

### Option 2: Command Line

**NudeNet:**

```bash
python3 run_nudenet.py
```

Prompts:

- Source folder path
- Detection threshold percentage

**Helloz NSFW:**

```bash
python3 run_helloz_nsfw.py
```

Prompts:

- Source folder path
- Detection threshold percentage

---

## Supported File Formats

### Images

PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF

### Videos

MP4, AVI, MKV, MOV, VOB, WMV, FLV, 3GP, WEBM

---

## Output

### Reports Folder

Reports are saved in a `reports` folder created in the current directory.

Detected files are **not copied** into the reports folder; source files remain in their original location.

### Report File

A detailed Excel report named `nudity_report.xlsx` is saved in the reports folder. The report includes:

- File path
- Media type
- Model used
- Threshold percentage
- Confidence percentage
- Nudity detection status
- Detected nudity classes
- Thumbnail image (embedded)

### Report Persistence and Save Failures

Each report run writes two files: the Excel workbook (`nudity_report.xlsx`) and the session file (`nudity_report_session.json`). Both must be written successfully for the save to be considered complete. If either write fails, the run is reported as a partial failure that names the file which could not be written: callers receive a `(workbook_saved, session_saved)` outcome instead of assuming success, and the GUI, CLI, and detector entry points log an error naming the missing file and warn the user where applicable. A failure of one file does not roll back the other; rerun or re-save once the underlying IO issue (permissions, full disk, read-only directory) is resolved.

### GUI Review

The GUI review panel includes:

- Detected-item table with confidence and source path
- Thumbnail preview for selected result rows
- `Open File` action to open the selected image/video directly
- `Open Location` action to open the parent folder

### Session State

Each saved report stores companion session data so the GUI can restore:

- Theme mode
- Source folder
- Selected model
- Detection threshold
- Detected media rows with confidence and file paths

Use the GUI `Save Session` and `Load Session` actions to resume review work later.

---

## Building a Linux Package

The `scripts/build_linux.sh` script produces two distributable artifacts in the `dist/` folder:

| Artifact | Path | Description |
|---|---|---|
| PyInstaller bundle | `dist/nudity-detector/` | Self-contained directory, run without installing Python |
| AppImage | `dist/NudityDetector-x86_64.AppImage` | Single portable file, runs on any x86-64 Linux |

### Build prerequisites

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

Place a `256x256` PNG at `scripts/nudity-detector.png` before building to embed a custom icon in the AppImage. If no custom icon is found, a system fallback icon is used.

### Runtime requirements on the target system

- GTK4 (`libgtk-4-1`) and libadwaita (`libadwaita-1-0`) must be installed on the target system. The `linuxdeploy` GTK plugin bundles the GTK shared libraries where possible, but full GTK4 portability depends on the target distribution.
- NudeNet model weights are **downloaded on first run** and require internet access.

### Build output location

Both artifacts are written to the `dist/` folder, which is excluded from version control via `.gitignore`.

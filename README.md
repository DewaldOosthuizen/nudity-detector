# Nudity Detector

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
- **DeepStack**: Uses the `DeepStack` AI server for detection.

## Features

1. **Graphical User Interface**: Modern GTK4 + libadwaita GUI with native theming, model selection, threshold control, and progress tracking.
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

3. **Install requirements**:

  Activate the venv environment if you are using one.

  ```bash
  source ./.venv/bin/activate
  ```

  ```bash
  pip install -r requirements.txt
  ```

  or

  ```bash
  ./.venv/bin/pip install -r requirements.txt
  ```

4. **Install docker and docker compose**

    - Follow the instructions for your OS on the official Docker website: <https://docs.docker.com/get-docker/>
    - Ensure Docker Compose is installed. Instructions can be found here: <https://docs.docker.com/compose/install/>
  
5. **Prepare Models**:

   - Nudenet
     - For Nudenet no setup is required.
   - Deepstack
     - Run the docker-compose.yml file to start your server

       ```bash
       docker-compose up --build
       ```

   - Once started, DeepStack will be available at <http://localhost:5000>.
   - You can test if your server is running by executing the following (Replace the image path with an existing image)

    ```bash
    curl -X POST -F image=@test.jpg 'http://localhost:5000/v1/vision/detection'
    ```

6. **Run the process**:

### Option 1: GUI Application (Recommended)

The GUI requires **GTK4** and **libadwaita**. These are pre-installed on most modern GNOME-based Linux desktops.

  On Ubuntu/Debian, you can install them using:

  ```bash
  sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
  ```

  > **Note:** Windows and macOS are not officially supported by GTK4 on Python. The GUI is designed for Linux.

  If you use a virtual environment, expose the system `gi` package to it:

  ```bash
  VENV_SITE_PACKAGES="$(
    .venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'
  )"
  GI_SYSTEM_PATH="$(
    python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).resolve().parent.parent)'
  )"
  printf '%s\n' "$GI_SYSTEM_PATH" > "$VENV_SITE_PACKAGES/system-gi.pth"
  ```

  Then run:

  ```bash
  python3 run_gui.py
  ```

  The GUI provides a modern libadwaita interface with:

- Model selection (NudeNet or DeepStack)
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

- DeepStack

  ```bash
  python3 run_deepstack.py
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

## Notes

DeepStack requires the AI server to be running during script execution.
Ensure sufficient disk space for processing large files or folders.

## License

This project is licensed under the MIT License.

For contributions or support, feel free to open an issue or a pull request. 😊

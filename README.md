# Nudity Detector

## Overview

The **Nudity Detector** script is a tool for identifying nudity in images and videos. It uses AI-based models to classify files and organizes detected content into a dedicated folder, generating a comprehensive report afterward.

Two versions of the script are available:

- **Nudenet**: Uses the `nudenet` library for nudity detection.
  - Basic
  - Not always accurate
  - Process videos by extracting frames and analyzing the frames as images.
- **DeepStack**: Uses the `DeepStack` AI server for detection. (In Progress)
  - Advanced
  - Higher acuuracy

## Features

1. **File Classification**: Identifies nudity in supported image and video files.
2. **File Management**: Copies files with detected nudity to an `exposed` folder for review.
3. **Report Generation**: Creates an Excel report in the `exposed` folder summarizing detection results.
4. **Multi-Threading**: Speeds up classification by processing files in parallel.

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

    ```bash
    pip install -r requirements.txt
    ```

4. **Perpare Models**:

   - Nudenet
     - For Nudenet no setup is required.
   - Deepstack
     - Download and install DeepStack from [DeepStack's official website](https://deepstack.cc/).
     - Start DeepStack with the nudity detection model:

     ```bash
     deepstack --VISION-DETECTION True --PORT 80
     ```

5. **Run the process**:

- nudenet

  ```bash
  python3 nudity-detector-nudenet.py
  ```

- Deepstack

    ```bash
  python3 nudity-detector-deepstack.py
  ```

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

### Exposed Folder

Detected files are copied to an exposed folder created in the current directory.

### Report File

A detailed Excel report named nudity_report.xlsx is saved in the exposed folder.
The report includes:

- File path
- Nudity detection status
- Detected nudity classes

## Notes

DeepStack requires the AI server to be running during script execution.
Ensure sufficient disk space for processing large files or folders.

## License

This project is licensed under the MIT License.

For contributions or support, feel free to open an issue or a pull request. 😊

# Nudity Detector

This project, Nudity Detector, is a Python-based script designed to detect nudity in images and videos. It provides an 
An efficient and automated solution for identifying explicit content, making it suitable for applications such as content 
moderation, safety filters, and compliance checks.

## Overview

The **Nudity Detector** script is a tool for identifying nudity in images and videos. It uses AI-based models to classify files and organizes detected content into a dedicated folder, generating a comprehensive report afterward.

Two versions of the script are available:

- **Nudenet**: Uses the `nudenet` library for nudity detection.
  - Basic
  - Not always accurate
  - Process videos by extracting frames and analyzing the frames as images.
- **DeepStack**: Uses the `DeepStack` AI server for detection. (In Progress)

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

4. Install docker and docker compose

5. **Perpare Models**:

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

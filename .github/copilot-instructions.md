# Nudity Detector

Nudity Detector is a Python-based application for detecting nudity in images and videos using AI models. It supports two AI backends: NudeNet (lightweight local processing) and DeepStack (robust Docker-based AI server). The application includes both GUI and CLI interfaces.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Dependencies
- Install system dependencies:
  ```bash
  sudo apt-get update && sudo apt-get install -y python3-tk
  ```
  - Takes ~60 seconds. NEVER CANCEL. Set timeout to 120+ seconds.

- Install Python dependencies:
  ```bash
  pip3 install -r requirements.txt
  ```
  - Takes ~45 seconds. NEVER CANCEL. Set timeout to 900+ seconds.
  - Installs: nudenet, vnudenet, openpyxl, requests and many sub-dependencies (opencv, numpy, scipy, etc.)

### AI Backend Setup and Testing

#### NudeNet Backend (Local Processing)
- No additional setup required - works immediately after pip install
- Test NudeNet functionality:
  ```bash
  python3 -c "from nudenet import NudeDetector; detector = NudeDetector(); print('NudeNet ready')"
  ```
  - Initialization: ~0.07 seconds
  - Detection per image: ~0.03 seconds

#### DeepStack Backend (Docker Server)
- Start DeepStack AI server:
  ```bash
  docker compose up --build -d
  ```
  - Docker image download: ~47 seconds first time. NEVER CANCEL. Set timeout to 600+ seconds.
  - Container startup: ~10 seconds additional initialization after container starts

- Test DeepStack is ready:
  ```bash
  curl -X POST -F image=@test_image.jpg 'http://localhost:5000/v1/vision/detection'
  ```
  - Should return: `{"success":true,"predictions":[],"duration":0}`

- Stop DeepStack when done:
  ```bash
  docker compose down
  ```
  - Takes ~10 seconds. NEVER CANCEL. Set timeout to 60+ seconds.

### Running the Applications

#### GUI Application (Recommended for Users)
- **LIMITATION**: Cannot run in headless environments (requires display)
- Start GUI:
  ```bash
  python3 nudity_detector_gui.py
  ```
- Provides interface for model selection, folder browsing, progress tracking

#### CLI Applications (Headless Compatible)
- **IMPORTANT**: CLI apps are interactive - they prompt for folder paths, no command-line arguments
- Run NudeNet CLI:
  ```bash
  python3 nudity-detector-nudenet.py
  ```
  - Will prompt: "Enter the path to the folder:"
  
- Run DeepStack CLI (requires Docker container running):
  ```bash
  python3 nudity-detector-deepstack.py
  ```
  - Will prompt: "Enter the path to the folder:"

## Validation Scenarios

### Complete Validation Workflow
Always test both AI backends after making changes:

1. **Create test setup**:
   ```bash
   mkdir -p test_images
   python3 -c "from PIL import Image; img = Image.new('RGB', (100, 100), color='red'); img.save('test_images/test.jpg')"
   ```

2. **Test NudeNet**:
   ```bash
   python3 -c "
   from nudenet import NudeDetector
   detector = NudeDetector()
   result = detector.detect('test_images/test.jpg')
   print(f'NudeNet result: {result}')
   assert isinstance(result, list), 'NudeNet should return a list'
   print('NudeNet validation passed')
   "
   ```

3. **Test DeepStack** (if using DeepStack features):
   ```bash
   # Start container
   docker compose up -d
   sleep 15  # Wait for initialization
   
   # Test API
   curl -f -X POST -F image=@test_images/test.jpg 'http://localhost:5000/v1/vision/detection'
   
   # Clean up
   docker compose down
   ```

4. **Clean up**:
   ```bash
   rm -rf test_images
   ```

### Complete End-to-End User Scenario
After making changes, ALWAYS test the complete user workflow:

```bash
# 1. Create test scenario
mkdir -p test_scenario
cd test_scenario
python3 -c "
from PIL import Image
img1 = Image.new('RGB', (200, 200), color='blue')
img1.save('test1.jpg')
img2 = Image.new('RGB', (150, 150), color='green') 
img2.save('test2.png')
with open('bad_file.txt', 'w') as f:
    f.write('This is not an image')
"
cd ..

# 2. Run NudeNet CLI interactively
python3 nudity-detector-nudenet.py
# When prompted, enter: test_scenario

# 3. Verify outputs
ls -la exposed/
file exposed/nudity_report.xlsx

# 4. Clean up
rm -rf test_scenario exposed
```

Expected results:
- Should process 2 images (test1.jpg, test2.png)
- Should skip bad_file.txt with "unsupported file" message
- Should create `exposed/` folder with `nudity_report.xlsx`
- Should show "Report saved to exposed/nudity_report.xlsx"

### Manual Testing Scenarios
- **Basic Image Processing**: Use the end-to-end scenario above
- **Report Generation**: Verify Excel reports are created correctly  
- **Error Handling**: Test handles invalid file types gracefully
- **DeepStack Integration**: Use docker compose workflow for DeepStack testing

## Build and Development

### No Build Process Required
- This is a Python application with no compilation step
- Dependencies are installed via pip, no additional build commands needed

### Code Structure
- `nudity_detector_gui.py` - Main GUI application with tkinter interface
- `nudity-detector-nudenet.py` - CLI application using NudeNet backend  
- `nudity-detector-deepstack.py` - CLI application using DeepStack backend
- `nudity_detector_utils.py` - Shared utility functions for file processing and reporting
- `requirements.txt` - Python dependencies
- `docker-compose.yml` - DeepStack AI server configuration

### Testing Changes
- Always run validation scenarios above after making code changes
- Test both NudeNet and DeepStack backends if modifying core detection logic
- Verify report generation works by checking `exposed/nudity_report.xlsx` creation

## Common Tasks

### Repository Structure
```
.
├── README.md                          # Project documentation
├── requirements.txt                   # Python dependencies  
├── docker-compose.yml                 # DeepStack server config
├── nudity_detector_gui.py            # GUI application (tkinter)
├── nudity-detector-nudenet.py        # NudeNet CLI
├── nudity-detector-deepstack.py      # DeepStack CLI  
├── nudity_detector_utils.py          # Shared utilities
└── .github/
    └── copilot-instructions.md       # This file
```

### Supported File Formats
- **Images**: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF
- **Videos**: MP4, AVI, MKV, MOV, VOB, WMV, FLV, 3GP, WEBM

### Key Dependencies (from requirements.txt)
```
nudenet          # Local AI nudity detection
vnudenet         # Enhanced nudity detection
openpyxl         # Excel report generation  
requests         # HTTP client for DeepStack API
```

### Environment Requirements
- **Python 3.12+** (tested with 3.12.3)
- **Docker** for DeepStack backend (optional)
- **tkinter** system package for GUI
- **Display/X11** for GUI (not available in headless environments)

### Troubleshooting
- **GUI fails with "no display"**: Normal in headless environments, use CLI instead
- **DeepStack API 404**: Wait 15+ seconds after container start for full initialization  
- **Import errors**: Ensure `pip3 install -r requirements.txt` completed successfully
- **Docker permission issues**: User must be in docker group or use sudo
# Final Merged Dashboard

A unified dashboard for comparing images and videos with AI-powered analysis.

## Features

### Image Comparison
- Compare two images to detect visual differences
- AI-powered difference detection using SSIM and computer vision
- Bounding boxes highlighting difference regions
- Configurable sensitivity threshold and minimum area
- Visual difference mask overlay

### Video Performance Comparison
- Compare two videos for scroll performance analysis
- Industry-standard metrics (jerkiness, jitter, FPS)
- Side-by-side performance visualization
- Detailed performance reports

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) For enhanced text extraction in image comparison, install Tesseract OCR:
   - **Windows**: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki) or use `choco install tesseract`
   - **macOS**: `brew install tesseract`
   - **Linux**: `sudo apt-get install tesseract-ocr` (Ubuntu/Debian) or `sudo yum install tesseract` (CentOS/RHEL)
   
   Then install Python wrapper:
   ```bash
   pip install pytesseract
   ```
   
   Note: The system works without OCR, but descriptions will be less detailed.

## Usage

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Use the tabs to switch between:
   - **Image Comparison**: Upload 2 images to compare
   - **Video Performance Comparison**: Upload 2 videos to compare

## API Endpoints

### Image Comparison
- `POST /api/compare-images`: Compare two images
  - Form data: `baseline` (image file), `actual` (image file), `threshold` (optional), `min_area` (optional)

### Video Comparison
- `POST /api/compare-videos`: Compare two videos
  - Form data: `video1` (video file), `video2` (video file), `session_id` (optional)

### Image Serving
- `GET /api/image/<session_id>/<filename>`: Serve images from uploads or results directory

## Directory Structure

```
final_merged_dashboard/
├── app.py                 # Main Flask application
├── scroll_analysis.py     # Video performance analysis
├── image_comparison.py    # Image comparison logic
├── requirements.txt       # Python dependencies
├── templates/
│   └── dashboard.html    # Unified dashboard UI
├── uploads/              # Uploaded files (auto-created)
└── results/              # Analysis results (auto-created)
```

## Notes

- Maximum file size: 500MB (configurable in app.py)
- Supported image formats: PNG, JPG, JPEG, GIF, BMP
- Supported video formats: MP4, AVI, MOV, MKV, WEBM
- All uploaded files and results are stored in session-based directories

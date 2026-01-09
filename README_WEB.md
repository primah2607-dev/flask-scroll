# Web Dashboard for Video Scroll Performance Analyzer

This is a web-based interface for comparing two video scroll performances. Access it via your browser at `http://localhost:5000`.

## Installation

1. Install Flask (if not already installed):
```bash
pip install Flask Werkzeug
```

Or install from requirements file:
```bash
pip install -r requirements_web.txt
```

## Running the Web Server

1. Start the web server:
```bash
python web_dashboard.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. The interface will allow you to:
   - Upload two video files (MP4, AVI, MOV, MKV, WEBM)
   - Compare their scroll performance
   - View detailed metrics and graphs

## Features

- **Web-based Interface**: Access via browser, no GUI dependencies
- **Video Upload**: Drag and drop or select two videos to compare
- **Real-time Analysis**: See progress while videos are being analyzed
- **Detailed Metrics**: View jerkiness, jitter, FPS, and overall ratings
- **Visual Graphs**: Side-by-side comparison charts
- **Industry Standards**: Ratings based on industry benchmarks

## API Endpoints

- `GET /` - Main web interface
- `POST /api/compare` - Upload and compare two videos
- `GET /api/image/<path>` - Serve analysis images
- `GET /api/status` - Server status check

## Notes

- Maximum file size: 500MB per video
- Supported formats: MP4, AVI, MOV, MKV, WEBM
- Analysis results are saved in the `uploads/` directory
- The server runs on port 5000 by default

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the web server.

# Deployment Guide - New Features

## Quick Start: Apply New Changes

### Step 1: Install Optional OCR (Recommended but Not Required)

The new features work **without OCR**, but for the best experience with detailed descriptions showing "baseline: '2', actual: '5'", install OCR:

#### For Windows:
```bash
# Option 1: Using Chocolatey
choco install tesseract

# Option 2: Download installer from
# https://github.com/UB-Mannheim/tesseract/wiki

# Then install Python wrapper
pip install pytesseract
```

#### For Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
pip install pytesseract
```

#### For macOS:
```bash
brew install tesseract
pip install pytesseract
```

**Note:** If you skip OCR installation, the system still works but descriptions won't show the exact text differences (e.g., "2" vs "5").

---

### Step 2: Restart Your Server

#### If running locally:
1. Stop the current server (Ctrl+C in the terminal)
2. Restart it:
   ```bash
   python app.py
   ```

#### If deployed on a cloud service:

**For Heroku:**
```bash
git add .
git commit -m "Add improved image comparison with box merging and OCR descriptions"
git push heroku main
```

**For AWS/EC2:**
```bash
# SSH into your server
ssh your-server

# Navigate to project directory
cd /path/to/final_merged_dashboard

# Pull latest changes (if using git)
git pull

# Restart the service
# If using systemd:
sudo systemctl restart your-app-name

# If using supervisor:
sudo supervisorctl restart your-app-name

# If running directly:
# Stop current process and restart
python app.py
```

**For Docker:**
```bash
# Rebuild and restart container
docker-compose down
docker-compose up --build -d
```

**For Railway/Render/Other PaaS:**
- Push your code changes to your Git repository
- The platform will automatically redeploy
- Or manually trigger a redeploy from the dashboard

---

### Step 3: Verify Changes Are Live

1. Open your dashboard in a browser
2. Go to the Image Comparison tab
3. Upload two images to compare
4. You should see:
   - **Less cluttered boxes** (merged nearby boxes)
   - **Better descriptions** with baseline vs actual content (if OCR is installed)
   - **Distinct colored boxes** that are easier to distinguish

---

## What Changed?

### ✅ New Features:
1. **Box Merging**: Automatically merges nearby boxes when there are many (>10) to reduce clutter
2. **OCR Text Extraction**: Shows exact text differences (e.g., "baseline: '2', actual: '5'")
3. **Better Visualization**: Cleaner boxes with only borders (no fill overlay)
4. **Improved Descriptions**: More detailed discrepancy descriptions

### 📦 Files Modified:
- `image_comparison.py` - Added box merging, OCR, and better descriptions
- `templates/dashboard.html` - Updated UI to show new descriptions
- `app.py` - Updated to pass new description data

### 🔧 No Breaking Changes:
- All existing functionality still works
- Backward compatible
- Works without OCR (just less detailed descriptions)

---

## Troubleshooting

### OCR Not Working?
- Check if Tesseract is installed: `tesseract --version`
- Check if pytesseract is installed: `pip list | grep pytesseract`
- The system works fine without OCR - you'll just get less detailed descriptions

### Changes Not Visible?
- Make sure you restarted the server
- Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
- Check server logs for errors

### Too Many Boxes Still?
- The merging only activates when there are >10 boxes
- You can adjust the `merge_threshold` parameter in `image_comparison.py` (line ~75)
- Lower threshold = more aggressive merging

---

## Need Help?

If you encounter issues:
1. Check server logs for error messages
2. Verify all dependencies are installed: `pip install -r requirements.txt`
3. Test locally first before deploying to production

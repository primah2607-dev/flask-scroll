from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import threading
from werkzeug.utils import secure_filename
from scroll_analysis import analyze_scroll, compare_videos

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('templates', exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/compare', methods=['POST'])
def compare_videos_api():
    try:
        if 'video1' not in request.files or 'video2' not in request.files:
            return jsonify({'error': 'Both video files are required'}), 400
        
        file1 = request.files['video1']
        file2 = request.files['video2']
        
        if file1.filename == '' or file2.filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        if not (allowed_file(file1.filename) and allowed_file(file2.filename)):
            return jsonify({'error': 'Invalid file type. Allowed: mp4, avi, mov, mkv, webm'}), 400
        
        # Save uploaded files
        filename1 = secure_filename(file1.filename)
        filename2 = secure_filename(file2.filename)
        
        session_id = request.form.get('session_id', 'default')
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        video1_path = os.path.join(session_dir, filename1)
        video2_path = os.path.join(session_dir, filename2)
        
        file1.save(video1_path)
        file2.save(video2_path)
        
        # Create comparison directory
        comparison_dir = os.path.join(session_dir, 'comparison')
        os.makedirs(comparison_dir, exist_ok=True)
        
        # Run comparison
        comparison = compare_videos(video1_path, video2_path, comparison_dir)
        
        if not comparison:
            return jsonify({'error': 'Comparison failed'}), 500
        
        # Prepare response
        response = {
            'success': True,
            'comparison': comparison,
            'dashboard_image': f'/api/image/{session_id}/comparison/comparison_dashboard.png',
            'video1_analysis': f'/api/image/{session_id}/comparison/video1_analysis/scroll_analysis_dashboard.png',
            'video2_analysis': f'/api/image/{session_id}/comparison/video2_analysis/scroll_analysis_dashboard.png',
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/image/<path:image_path>')
def get_image(image_path):
    """Serve images from the upload directory"""
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_file(full_path)
    return jsonify({'error': 'Image not found'}), 404

@app.route('/api/status')
def status():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("=" * 60)
    print("Starting Video Scroll Performance Analyzer Web Server")
    print("=" * 60)
    print("Access the interface at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

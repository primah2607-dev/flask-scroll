from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import uuid
import cv2
from scroll_analysis import compare_videos
from image_comparison import compare_images

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'

# Allowed extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)


def allowed_image_file(filename):
    """Check if file extension is allowed for images."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_video_file(filename):
    """Check if file extension is allowed for videos."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/compare-images', methods=['POST'])
def compare_images_api():
    """API endpoint for comparing two images."""
    try:
        # Check if files are present
        if 'baseline' not in request.files or 'actual' not in request.files:
            return jsonify({'error': 'Both baseline and actual images are required'}), 400
        
        baseline_file = request.files['baseline']
        actual_file = request.files['actual']
        
        if baseline_file.filename == '' or actual_file.filename == '':
            return jsonify({'error': 'Both files must be selected'}), 400
        
        if not (allowed_image_file(baseline_file.filename) and allowed_image_file(actual_file.filename)):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, BMP'}), 400
        
        # Get optional parameters
        threshold = float(request.form.get('threshold', 0.3))
        min_area = int(request.form.get('min_area', 100))
        
        # Create unique session ID
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Save uploaded files
        baseline_filename = secure_filename(baseline_file.filename)
        actual_filename = secure_filename(actual_file.filename)
        
        baseline_path = os.path.join(session_dir, f'baseline_{baseline_filename}')
        actual_path = os.path.join(session_dir, f'actual_{actual_filename}')
        
        baseline_file.save(baseline_path)
        actual_file.save(actual_path)
        
        # Create results directory
        results_dir = os.path.join(app.config['RESULTS_FOLDER'], session_id)
        os.makedirs(results_dir, exist_ok=True)
        
        # Compare images
        output_path = os.path.join(results_dir, 'comparison_result.png')
        result = compare_images(
            baseline_path, 
            actual_path, 
            output_path,
            threshold=threshold,
            min_area=min_area
        )
        
        # Save difference mask for visualization
        mask_path = os.path.join(results_dir, 'difference_mask.png')
        cv2.imwrite(mask_path, result['difference_mask'])
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'similarity_score': result['similarity_score'],
            'num_differences': result['num_differences'],
            'bounding_boxes': result['bounding_boxes'],
            'box_descriptions': result.get('box_descriptions', []),
            'output_image_url': f'/api/image/{session_id}/comparison_result.png',
            'baseline_image_url': f'/api/image/{session_id}/baseline_{baseline_filename}',
            'actual_image_url': f'/api/image/{session_id}/actual_{actual_filename}',
            'difference_mask_url': f'/api/image/{session_id}/difference_mask.png'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/compare-videos', methods=['POST'])
def compare_videos_api():
    """API endpoint for comparing two videos."""
    try:
        if 'video1' not in request.files or 'video2' not in request.files:
            return jsonify({'error': 'Both video files are required'}), 400
        
        file1 = request.files['video1']
        file2 = request.files['video2']
        
        if file1.filename == '' or file2.filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        if not (allowed_video_file(file1.filename) and allowed_video_file(file2.filename)):
            return jsonify({'error': 'Invalid file type. Allowed: mp4, avi, mov, mkv, webm'}), 400
        
        # Save uploaded files
        filename1 = secure_filename(file1.filename)
        filename2 = secure_filename(file2.filename)
        
        session_id = request.form.get('session_id', str(uuid.uuid4()))
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


@app.route('/api/image/<session_id>/<path:filename>')
def get_image(session_id, filename):
    """Serve images from upload or results directory."""
    # Try results directory first
    results_path = os.path.join(app.config['RESULTS_FOLDER'], session_id, filename)
    if os.path.exists(results_path):
        return send_file(results_path, mimetype='image/png')
    
    # Try uploads directory
    uploads_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, filename)
    if os.path.exists(uploads_path):
        # Determine MIME type based on extension
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        mimetype = 'image/png' if ext == 'png' else 'image/jpeg' if ext in ['jpg', 'jpeg'] else 'image/png'
        return send_file(uploads_path, mimetype=mimetype)
    
    return jsonify({'error': 'Image not found'}), 404


@app.route('/api/status')
def status():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Final Merged Dashboard")
    print("=" * 60)
    print("Access the interface at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

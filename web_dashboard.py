import os
import uuid
import threading
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

from scroll_analysis import compare_videos

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

jobs = {}


def run_compare_job(job_id, video1_path, video2_path, out_dir):
    try:
        jobs[job_id]["status"] = "processing"
        result = compare_videos(video1_path, video2_path, out_dir)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = result
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/compare", methods=["POST"])
def compare():
    if "video1" not in request.files or "video2" not in request.files:
        return jsonify({"error": "Both videos required"}), 400

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    v1 = request.files["video1"]
    v2 = request.files["video2"]

    v1_path = os.path.join(job_dir, secure_filename(v1.filename))
    v2_path = os.path.join(job_dir, secure_filename(v2.filename))

    v1.save(v1_path)
    v2.save(v2_path)

    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    jobs[job_id] = {"status": "queued"}

    threading.Thread(
        target=run_compare_job,
        args=(job_id, v1_path, v2_path, output_dir),
        daemon=True
    ).start()

    return jsonify({
        "job_id": job_id,
        "status": "started"
    })


@app.route("/api/status/<job_id>")
def status(job_id):
    return jsonify(jobs.get(job_id, {"status": "unknown"}))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

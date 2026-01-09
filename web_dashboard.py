from flask import Flask, request, jsonify, render_template
import threading
import uuid

from scroll_analysis import analyze_scroll, compare_videos

app = Flask(__name__)

jobs = {}

def run_compare_job(job_id, video1, video2):
    try:
        jobs[job_id]["status"] = "processing"
        result = compare_videos(video1, video2)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = result
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/compare", methods=["POST"])
def compare():
    video1 = request.files["video1"]
    video2 = request.files["video2"]

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued"}

    threading.Thread(
        target=run_compare_job,
        args=(job_id, video1, video2),
        daemon=True
    ).start()

    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    return jsonify(jobs.get(job_id, {"status": "unknown"}))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

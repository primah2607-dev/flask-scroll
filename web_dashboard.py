from flask import Flask, request, jsonify, render_template
import threading
import uuid

from scroll_analysis import compare_videos

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
    if "video1" not in request.files or "video2" not in request.files:
        return jsonify({"error": "Missing files"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued"}

    threading.Thread(
        target=run_compare_job,
        args=(job_id, request.files["video1"], request.files["video2"]),
        daemon=True
    ).start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)

    if not job:
        return jsonify({"status": "unknown"})

    if job["status"] == "error":
        return jsonify({
            "status": "error",
            "error": job.get("error", "Unknown error")
        })

    return jsonify(job)

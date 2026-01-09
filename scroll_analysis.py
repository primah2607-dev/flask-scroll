import cv2
import os
import numpy as np

if not os.path.exists(cv2.__file__):
    raise RuntimeError("OpenCV not installed correctly")

def analyze_scroll(video_file):
    cap = cv2.VideoCapture(video_file)
    frame_times = []

    prev_gray = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            frame_times.append(np.mean(diff))

        prev_gray = gray

    cap.release()

    return {
        "frames_analyzed": len(frame_times),
        "avg_jitter": float(np.mean(frame_times)) if frame_times else 0
    }

def compare_videos(video1, video2):
    result1 = analyze_scroll(video1)
    result2 = analyze_scroll(video2)

    return {
        "video1": result1,
        "video2": result2,
        "difference": abs(result1["avg_jitter"] - result2["avg_jitter"])
    }

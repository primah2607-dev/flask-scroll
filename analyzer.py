import cv2
import numpy as np
import json
import os
import matplotlib.pyplot as plt

class FrameAnalyzer:
    def __init__(self, movement_threshold=0.015):
        self.movement_threshold = movement_threshold  # T2 threshold
        self.frame_times = []
        self.lag_events = []
        self.flicker_events = []
        self.jerk_events = []

    def load_frame(self, path):
        frame = cv2.imread(path)
        if frame is None:
            raise ValueError(f"Cannot read frame: {path}")
        return frame

    def frame_difference_ratio(self, frame1, frame2):
        # Ensure frames are the same size before comparison
        h1, w1 = frame1.shape[:2]
        h2, w2 = frame2.shape[:2]
        
        if h1 != h2 or w1 != w2:
            # Resize frame2 to match frame1's dimensions
            frame2 = cv2.resize(frame2, (w1, h1))
        
        g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(g1, g2)
        changed_pixels = np.sum(diff > 20)
        total = diff.size
        return changed_pixels / total

    def screen_moved(self, frame1, frame2):
        ratio = self.frame_difference_ratio(frame1, frame2)
        return ratio > self.movement_threshold

    def analyze_frames(self, frames_dir):
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
        prev_frame = None
        timestamps = []
        reference_size = None

        for i, f in enumerate(frame_files):
            path = os.path.join(frames_dir, f)
            frame = self.load_frame(path)
            
            # Set reference size from first frame
            if reference_size is None:
                reference_size = (frame.shape[1], frame.shape[0])  # (width, height)
            
            # Resize frame to reference size if needed
            if frame.shape[1] != reference_size[0] or frame.shape[0] != reference_size[1]:
                frame = cv2.resize(frame, reference_size)
            
            timestamps.append(i)

            if prev_frame is not None:
                diff_ratio = self.frame_difference_ratio(prev_frame, frame)
                # Flicker
                if diff_ratio > 0.2:
                    self.flicker_events.append(i)
                # Lag
                if diff_ratio < 0.005:
                    self.lag_events.append(i)
                # Jerk: big sudden changes
                if diff_ratio > 0.1:
                    self.jerk_events.append(i)

            prev_frame = frame

        self.frame_times = timestamps

    def save_report(self, out_dir):
        report = {
            "total_frames": len(self.frame_times),
            "lag_events": self.lag_events,
            "flicker_events": self.flicker_events,
            "jerk_events": self.jerk_events
        }
        json_path = os.path.join(out_dir, "performance_report.json")
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[REPORT] JSON report saved at: {json_path}")

        # Optional: visual graph
        plt.figure(figsize=(12, 4))
        plt.plot(self.frame_times, [1 if i in self.lag_events else 0 for i in self.frame_times], label="Lag")
        plt.plot(self.frame_times, [1 if i in self.flicker_events else 0 for i in self.frame_times], label="Flicker")
        plt.plot(self.frame_times, [1 if i in self.jerk_events else 0 for i in self.frame_times], label="Jerk")
        plt.xlabel("Frame Index")
        plt.ylabel("Event Detected")
        plt.title("Realtime Scroll Analysis")
        plt.legend()
        plt.tight_layout()
        graph_path = os.path.join(out_dir, "scroll_analysis_graph.png")
        plt.savefig(graph_path)
        plt.close()
        print(f"[GRAPH] Graph saved at: {graph_path}")

    def create_video(self, frames_dir, fps, output_path=None):
        """Create an MP4 video from captured frames and return the path."""
        frame_files = sorted(
            f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")
        )
        if not frame_files:
            raise ValueError("No frames found to build video.")

        first = cv2.imread(os.path.join(frames_dir, frame_files[0]))
        if first is None:
            raise ValueError("Unable to read first frame for video creation.")

        height, width, _ = first.shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        output_path = output_path or os.path.join(frames_dir, "scroll_capture.mp4")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        try:
            for fname in frame_files:
                frame = cv2.imread(os.path.join(frames_dir, fname))
                if frame is None:
                    continue
                if frame.shape[0] != height or frame.shape[1] != width:
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)
        finally:
            writer.release()

        print(f"[VIDEO] Video saved at: {output_path}")
        return output_path
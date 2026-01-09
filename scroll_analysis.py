import argparse
import json
import os

import cv2
import matplotlib.pyplot as plt
import numpy as np

# -----------------------------
# CONFIG — tune for speed/safety
# -----------------------------
FRAME_SKIP = 5         # process only 1/5 frames
MAX_FRAMES = 2000       # hard upper bound (prevents infinite loop)
BLOCK_SIZE = 32         # for fast block motion scanning

# -----------------------------
# Industry-standard thresholds for scroll performance
# Based on 60 FPS target (16.67ms per frame) and mobile app standards
# -----------------------------
# Jitter thresholds (frame timing consistency)
JITTER_EXCELLENT = 3.0    # < 3ms: Perfectly smooth (industry benchmark)
JITTER_GOOD = 8.0         # < 8ms: Smooth scrolling (acceptable)
JITTER_FAIR = 16.0        # < 16ms: Noticeable but acceptable (target FPS)
JITTER_POOR = 16.0        # >= 16ms: Significant stutter (below 60 FPS)

# Jerkiness thresholds (motion consistency)
JERK_EXCELLENT = 2.0      # < 2: Very consistent motion
JERK_GOOD = 5.0           # < 5: Mostly smooth
JERK_FAIR = 10.0          # < 10: Some variability
JERK_POOR = 10.0          # >= 10: Very jerky


def analyze_scroll(video_path: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("ERROR: Could not open video:", video_path)
        return None

    prev_frame = None
    frame_idx = 0
    processed = 0

    velocities = []
    frame_intervals = []
    sample_times = []  # timestamp (ms) for each velocity sample
    last_ts = None

    print(f"Processing video: {video_path}")

    while processed < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break  # <-- GUARANTEES EXIT

        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)

        if frame_idx % FRAME_SKIP != 0:
            frame_idx += 1
            continue

        # Compute frame interval jitter
        if last_ts is not None:
            frame_intervals.append(timestamp - last_ts)
        last_ts = timestamp

        # Convert to gray
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Compute block-based vertical motion
        if prev_frame is not None:
            h, w = gray.shape
            motions = []

            for y in range(0, h - BLOCK_SIZE, BLOCK_SIZE):
                block_prev = prev_frame[y:y + BLOCK_SIZE, :]
                block_now = gray[y:y + BLOCK_SIZE, :]

                diff = np.mean(np.abs(block_now - block_prev))
                motions.append(diff)

            velocities.append(np.mean(motions))
            sample_times.append(timestamp)

        prev_frame = gray
        frame_idx += 1
        processed += 1

    cap.release()

    velocities = np.array(velocities)
    intervals = np.array(frame_intervals)
    sample_times = np.array(sample_times) if sample_times else np.array([])

    if len(velocities) == 0:
        print("ERROR: No frames processed - check video format")
        return None

    avg_speed = float(velocities.mean())
    jerkiness = float(velocities.std())
    jitter = float(intervals.std()) if len(intervals) > 0 else 0.0
    mean_frame_interval = float(intervals.mean()) if len(intervals) > 0 else 0.0
    estimated_fps = 1000.0 / mean_frame_interval if mean_frame_interval > 0 else 0.0

    # --------------------------
    # Industry-standard rating based on scroll performance benchmarks
    # --------------------------
    issues = []

    # Rating logic: Must meet BOTH jerkiness AND jitter thresholds for rating
    if jerkiness < JERK_EXCELLENT and jitter < JITTER_EXCELLENT:
        smoothness = "Excellent"
        smoothness_desc = "Perfectly smooth scrolling - meets industry benchmark standards"
    elif jerkiness < JERK_GOOD and jitter < JITTER_GOOD:
        smoothness = "Good"
        smoothness_desc = "Smooth scrolling with minimal stutter"
    elif jerkiness < JERK_FAIR and jitter < JITTER_FAIR:
        smoothness = "Fair"
        smoothness_desc = "Noticeable lag or stutter, but acceptable performance"
    else:
        smoothness = "Poor"
        smoothness_desc = "Significant stutter and lag - below industry standards"

    # Detailed issue detection
    if jerkiness >= JERK_POOR:
        issues.append(f"High jerkiness ({jerkiness:.2f}): Scrolling motion is very uneven and jerky.")
    elif jerkiness >= JERK_FAIR:
        issues.append(f"Moderate jerkiness ({jerkiness:.2f}): Some uneven motion detected.")
    
    if jitter >= JITTER_POOR:
        issues.append(f"High frame-time jitter ({jitter:.2f} ms): Significant frame timing variation causing stutter (target: < 16ms for 60 FPS).")
    elif jitter >= JITTER_FAIR:
        issues.append(f"Moderate frame-time jitter ({jitter:.2f} ms): Some frame timing inconsistency (target: < 8ms for smooth).")
    
    if estimated_fps > 0 and estimated_fps < 50:
        issues.append(f"Low frame rate (estimated {estimated_fps:.1f} FPS): Below optimal 60 FPS target.")
    
    if avg_speed < 1:
        issues.append("Low scroll activity: Scrolling speed is very low and may feel sluggish.")

    if not issues:
        issues.append("No major problems detected — scrolling meets industry standards.")

    summary = (
        f"Overall scroll smoothness: {smoothness} - {smoothness_desc}. "
        f"Activity score: {avg_speed:.2f} (content movement level), "
        f"Jerkiness: {jerkiness:.2f} (motion consistency, lower is better), "
        f"Frame-time jitter: {jitter:.2f} ms (timing stability, target < 8ms for smooth), "
        f"Estimated FPS: {estimated_fps:.1f} (target: 60 FPS)."
    )

    # --------------------------
    # Identify problematic time ranges for the dashboard
    # --------------------------
    problem_windows = []

    def _ranges_from_mask(mask: np.ndarray, min_len: int = 2):
        """Convert a boolean mask into contiguous index ranges [start, end]."""
        ranges = []
        if mask.size == 0:
            return ranges
        start = None
        for i, val in enumerate(mask):
            if val and start is None:
                start = i
            elif not val and start is not None:
                if i - start >= min_len:
                    ranges.append((start, i - 1))
                start = None
        if start is not None and len(mask) - start >= min_len:
            ranges.append((start, len(mask) - 1))
        return ranges

    if sample_times.size > 0:
        # Motion-related problem periods: where motion spikes far from the mean.
        motion_mask = np.abs(velocities - avg_speed) > max(jerkiness, 1.0)
        for s, e in _ranges_from_mask(motion_mask):
            t_start = sample_times[s] / 1000.0
            t_end = sample_times[e] / 1000.0
            problem_windows.append(
                {
                    "type": "motion_spike",
                    "start_sec": round(float(t_start), 2),
                    "end_sec": round(float(t_end), 2),
                    "description": "Content motion is very uneven in this range, which may feel jerky.",
                }
            )

        # Timing-related problem periods: where frame interval deviates a lot from the mean.
        if intervals.size > 0:
            mean_int = intervals.mean()
            timing_mask = np.abs(intervals - mean_int) > max(jitter, 8.0)
            for s, e in _ranges_from_mask(timing_mask):
                # intervals is one shorter than sample_times; clamp indices.
                s_idx = min(s, sample_times.size - 1)
                e_idx = min(e + 1, sample_times.size - 1)
                t_start = sample_times[s_idx] / 1000.0
                t_end = sample_times[e_idx] / 1000.0
                problem_windows.append(
                    {
                        "type": "timing_jitter",
                        "start_sec": round(float(t_start), 2),
                        "end_sec": round(float(t_end), 2),
                        "description": "Frame timing is unstable here and may look like stutter.",
                    }
                )

    report = {
        "frames_processed": processed,
        "average_scroll_activity": avg_speed,
        "scroll_jerkiness": jerkiness,
        "frame_time_jitter_ms": jitter,
        "estimated_fps": estimated_fps,
        "mean_frame_interval_ms": mean_frame_interval,
        "frame_skip": FRAME_SKIP,
        "max_frames": MAX_FRAMES,
        "smoothness_rating": smoothness,
        "smoothness_description": smoothness_desc,
        "summary": summary,
        "issues": issues,
        "problem_windows": problem_windows,
        "video_path": video_path,
    }

    # --------------------------
    # PRINT USER-FRIENDLY REPORT
    # --------------------------
    print("\n" + "=" * 50)
    print("SCROLL SMOOTHNESS REPORT")
    print("=" * 50)
    print(f"Video: {os.path.basename(video_path)}")
    print(f"Frames processed: {processed}")
    print(f"\nOverall rating: {smoothness}")
    print(f"  {smoothness_desc}")
    print(f"\n📊 KEY METRICS:")
    print(f"  • Activity Score: {avg_speed:.2f}")
    print(f"    → Meaning: How much the content moves during scrolling (higher = more movement)")
    print(f"  • Jerkiness: {jerkiness:.2f}")
    print(f"    → Meaning: How consistent the motion is (lower is better)")
    print(f"    → Industry standard: < 2 = Excellent, < 5 = Good, < 10 = Fair, ≥ 10 = Poor")
    print(f"  • Frame-time Jitter: {jitter:.2f} ms")
    print(f"    → Meaning: Variation in time between frames (lower is better)")
    print(f"    → Industry standard: < 3ms = Excellent, < 8ms = Good, < 16ms = Fair, ≥ 16ms = Poor")
    print(f"  • Estimated FPS: {estimated_fps:.1f}")
    print(f"    → Meaning: Average frames per second (target: 60 FPS for smooth scrolling)")
    print(f"\n💡 Key Takeaways:")
    for issue in issues:
        print(f"  • {issue}")

    if problem_windows:
        print("\nWhere the experience is weakest:")
        for win in problem_windows:
            print(
                f"- From {win['start_sec']:.2f}s to {win['end_sec']:.2f}s: "
                f"{win['description']}"
            )
    print("=" * 50 + "\n")

    # Save JSON
    json_path = os.path.join(out_dir, "scroll_analysis_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"📄 Analysis saved to {json_path}")
    
    # Save velocity and interval arrays for comparison
    np.savetxt(os.path.join(out_dir, "velocities.txt"), velocities)
    np.savetxt(os.path.join(out_dir, "intervals.txt"), intervals)
    np.savetxt(os.path.join(out_dir, "sample_times.txt"), sample_times)

    # Dashboard figure - smaller size for preview (can be opened in new window)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)

    # Top graph: how much the content is moving over time.
    axes[0].plot(
        velocities,
        label="How much the screen changes",
        color="#1f77b4",
        linewidth=2,
    )
    axes[0].set_title("Scroll activity over time (higher = more movement)", fontsize=16, fontweight="bold")
    axes[0].set_xlabel("Sample index (every FRAME_SKIP frames)", fontsize=14)
    axes[0].set_ylabel("Movement score", fontsize=14)
    axes[0].legend(loc="upper right", fontsize=12)
    axes[0].tick_params(labelsize=12)
    axes[0].grid(True, alpha=0.3)

    if len(intervals) > 0:
        axes[1].plot(
            intervals,
            label="Time between frames (ms)",
            color="#ff7f0e",
            linewidth=2,
        )
        axes[1].axhline(
            intervals.mean(),
            color="#2ca02c",
            linestyle="--",
            linewidth=2,
            label="Average timing",
        )
        axes[1].set_title("Frame timing stability (flatter line = smoother)", fontsize=16, fontweight="bold")
        axes[1].set_xlabel("Sample index", fontsize=14)
        axes[1].set_ylabel("Milliseconds between frames", fontsize=14)
        axes[1].legend(loc="upper right", fontsize=12)
        axes[1].tick_params(labelsize=12)
        axes[1].grid(True, alpha=0.3)
    else:
        axes[1].text(0.5, 0.5, "No interval data", ha="center", va="center")
        axes[1].set_axis_off()


    dash_path = os.path.join(out_dir, "scroll_analysis_dashboard.png")
    plt.savefig(dash_path)
    plt.close(fig)
    print(f"📊 Dashboard saved to {dash_path}")

    return report


def compare_videos(video_path1: str, video_path2: str, out_dir: str):
    """Analyze two videos and generate a comparison report."""
    os.makedirs(out_dir, exist_ok=True)
    
    print("\n" + "=" * 60)
    print("COMPARING TWO VIDEOS")
    print("=" * 60)
    print(f"Video 1: {os.path.basename(video_path1)}")
    print(f"Video 2: {os.path.basename(video_path2)}")
    print("=" * 60 + "\n")
    
    # Analyze both videos
    report1 = analyze_scroll(video_path1, os.path.join(out_dir, "video1_analysis"))
    report2 = analyze_scroll(video_path2, os.path.join(out_dir, "video2_analysis"))
    
    if not report1 or not report2:
        print("ERROR: Failed to analyze one or both videos")
        return None
    
    # Create comparison report
    comparison = {
        "video1": {
            "path": video_path1,
            "name": os.path.basename(video_path1),
            "rating": report1["smoothness_rating"],
            "activity_score": report1["average_scroll_activity"],
            "jerkiness": report1["scroll_jerkiness"],
            "jitter_ms": report1["frame_time_jitter_ms"],
            "estimated_fps": report1.get("estimated_fps", 0),
        },
        "video2": {
            "path": video_path2,
            "name": os.path.basename(video_path2),
            "rating": report2["smoothness_rating"],
            "activity_score": report2["average_scroll_activity"],
            "jerkiness": report2["scroll_jerkiness"],
            "jitter_ms": report2["frame_time_jitter_ms"],
            "estimated_fps": report2.get("estimated_fps", 0),
        },
    }
    
    # Determine winner for each metric
    better_jerkiness = "Video 1" if report1["scroll_jerkiness"] < report2["scroll_jerkiness"] else "Video 2"
    better_jitter = "Video 1" if report1["frame_time_jitter_ms"] < report2["frame_time_jitter_ms"] else "Video 2"
    better_fps = "Video 1" if report1.get("estimated_fps", 0) > report2.get("estimated_fps", 0) else "Video 2"
    
    # Overall winner (based on rating order)
    rating_order = {"Excellent": 4, "Good": 3, "Fair": 2, "Poor": 1}
    overall_winner = "Video 1" if rating_order.get(report1["smoothness_rating"], 0) > rating_order.get(report2["smoothness_rating"], 0) else "Video 2"
    if report1["smoothness_rating"] == report2["smoothness_rating"]:
        # Tie-breaker: use jitter as primary, then jerkiness
        if report1["frame_time_jitter_ms"] < report2["frame_time_jitter_ms"]:
            overall_winner = "Video 1"
        elif report1["frame_time_jitter_ms"] > report2["frame_time_jitter_ms"]:
            overall_winner = "Video 2"
        elif report1["scroll_jerkiness"] < report2["scroll_jerkiness"]:
            overall_winner = "Video 1"
        else:
            overall_winner = "Video 2 (or tie)"
    
    comparison["results"] = {
        "overall_winner": overall_winner,
        "better_jerkiness": better_jerkiness,
        "better_jitter": better_jitter,
        "better_fps": better_fps,
    }
    
    # Print comparison
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)
    print(f"\n📊 Overall Winner: {overall_winner}")
    print(f"\nMetric-by-Metric Comparison:")
    print(f"\n  Activity Score:")
    print(f"    Video 1: {report1['average_scroll_activity']:.2f}")
    print(f"    Video 2: {report2['average_scroll_activity']:.2f}")
    print(f"    → Higher values indicate more content movement (neither is inherently better)")
    
    print(f"\n  Jerkiness (lower is better):")
    print(f"    Video 1: {report1['scroll_jerkiness']:.2f} {'✓ Better' if better_jerkiness == 'Video 1' else ''}")
    print(f"    Video 2: {report2['scroll_jerkiness']:.2f} {'✓ Better' if better_jerkiness == 'Video 2' else ''}")
    print(f"    → Difference: {abs(report1['scroll_jerkiness'] - report2['scroll_jerkiness']):.2f}")
    
    print(f"\n  Frame-time Jitter (lower is better):")
    print(f"    Video 1: {report1['frame_time_jitter_ms']:.2f} ms {'✓ Better' if better_jitter == 'Video 1' else ''}")
    print(f"    Video 2: {report2['frame_time_jitter_ms']:.2f} ms {'✓ Better' if better_jitter == 'Video 2' else ''}")
    print(f"    → Difference: {abs(report1['frame_time_jitter_ms'] - report2['frame_time_jitter_ms']):.2f} ms")
    
    print(f"\n  Estimated FPS (higher is better):")
    print(f"    Video 1: {report1.get('estimated_fps', 0):.1f} FPS {'✓ Better' if better_fps == 'Video 1' else ''}")
    print(f"    Video 2: {report2.get('estimated_fps', 0):.1f} FPS {'✓ Better' if better_fps == 'Video 2' else ''}")
    print(f"    → Target: 60 FPS for smooth scrolling")
    
    print(f"\n  Overall Rating:")
    print(f"    Video 1: {report1['smoothness_rating']} - {report1.get('smoothness_description', '')}")
    print(f"    Video 2: {report2['smoothness_rating']} - {report2.get('smoothness_description', '')}")
    print("=" * 60 + "\n")
    
    # Save comparison JSON
    comparison_path = os.path.join(out_dir, "comparison_report.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"📄 Comparison report saved to {comparison_path}")
    
    # Create side-by-side comparison dashboard - smaller size for preview
    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    # Load saved data
    v1_dir = os.path.join(out_dir, "video1_analysis")
    v2_dir = os.path.join(out_dir, "video2_analysis")
    
    try:
        v1_velocities = np.loadtxt(os.path.join(v1_dir, "velocities.txt")) if os.path.exists(os.path.join(v1_dir, "velocities.txt")) else np.array([])
        v1_intervals = np.loadtxt(os.path.join(v1_dir, "intervals.txt")) if os.path.exists(os.path.join(v1_dir, "intervals.txt")) else np.array([])
        v2_velocities = np.loadtxt(os.path.join(v2_dir, "velocities.txt")) if os.path.exists(os.path.join(v2_dir, "velocities.txt")) else np.array([])
        v2_intervals = np.loadtxt(os.path.join(v2_dir, "intervals.txt")) if os.path.exists(os.path.join(v2_dir, "intervals.txt")) else np.array([])
    except Exception:
        v1_velocities = v1_intervals = v2_velocities = v2_intervals = np.array([])
    
    # Video 1 - Activity graph
    ax1 = fig.add_subplot(gs[0, 0])
    if len(v1_velocities) > 0:
        ax1.plot(v1_velocities, color="#1f77b4", label="Scroll activity", linewidth=2)
        ax1.set_ylabel("Movement score", fontsize=12)
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center")
    ax1.set_title(f"Video 1: {os.path.basename(video_path1)}\nActivity Over Time", fontsize=14, fontweight="bold")
    ax1.legend(fontsize=11)
    ax1.tick_params(labelsize=11)
    ax1.grid(True, alpha=0.3)
    
    # Video 2 - Activity graph
    ax2 = fig.add_subplot(gs[0, 1])
    if len(v2_velocities) > 0:
        ax2.plot(v2_velocities, color="#1f77b4", label="Scroll activity", linewidth=2)
        ax2.set_ylabel("Movement score", fontsize=12)
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=14)
    ax2.set_title(f"Video 2: {os.path.basename(video_path2)}\nActivity Over Time", fontsize=14, fontweight="bold")
    ax2.legend(fontsize=11)
    ax2.tick_params(labelsize=11)
    ax2.grid(True, alpha=0.3)
    
    # Video 1 - Frame timing graph
    ax3 = fig.add_subplot(gs[1, 0])
    if len(v1_intervals) > 0:
        ax3.plot(v1_intervals, color="#ff7f0e", label="Frame intervals", linewidth=2)
        ax3.axhline(v1_intervals.mean(), color="#2ca02c", linestyle="--", linewidth=2, label="Average")
        ax3.set_ylabel("Time (ms)", fontsize=12)
    else:
        ax3.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=14)
    ax3.set_title("Frame Timing Stability", fontsize=14, fontweight="bold")
    ax3.legend(fontsize=11)
    ax3.tick_params(labelsize=11)
    ax3.grid(True, alpha=0.3)
    
    # Video 2 - Frame timing graph
    ax4 = fig.add_subplot(gs[1, 1])
    if len(v2_intervals) > 0:
        ax4.plot(v2_intervals, color="#ff7f0e", label="Frame intervals", linewidth=2)
        ax4.axhline(v2_intervals.mean(), color="#2ca02c", linestyle="--", linewidth=2, label="Average")
        ax4.set_ylabel("Time (ms)", fontsize=12)
    else:
        ax4.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=14)
    ax4.set_title("Frame Timing Stability", fontsize=14, fontweight="bold")
    ax4.legend(fontsize=11)
    ax4.tick_params(labelsize=11)
    ax4.grid(True, alpha=0.3)
    
    # Comparison metrics summary
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis("off")
    
    winner_color1 = "#059669" if overall_winner == "Video 1" else "#6b7280"
    winner_color2 = "#059669" if overall_winner == "Video 2" else "#6b7280"
    
    winner_indicator1 = "🏆" if overall_winner == "Video 1" else "  "
    winner_indicator2 = "🏆" if overall_winner == "Video 2" else "  "
    
    summary_text = f"""
    COMPARISON SUMMARY
    {'='*70}
    
    Video 1: {os.path.basename(video_path1)}                                    Video 2: {os.path.basename(video_path2)}
    {winner_indicator1} Rating: {report1['smoothness_rating']}                                    {winner_indicator2} Rating: {report2['smoothness_rating']}
    
    Jerkiness: {report1['scroll_jerkiness']:.2f} {'(BETTER)' if better_jerkiness == 'Video 1' else ''}          Jerkiness: {report2['scroll_jerkiness']:.2f} {'(BETTER)' if better_jerkiness == 'Video 2' else ''}
    Jitter: {report1['frame_time_jitter_ms']:.2f} ms {'(BETTER)' if better_jitter == 'Video 1' else ''}          Jitter: {report2['frame_time_jitter_ms']:.2f} ms {'(BETTER)' if better_jitter == 'Video 2' else ''}
    Estimated FPS: {report1.get('estimated_fps', 0):.1f} {'(BETTER)' if better_fps == 'Video 1' else ''}          Estimated FPS: {report2.get('estimated_fps', 0):.1f} {'(BETTER)' if better_fps == 'Video 2' else ''}
    
    Overall Winner: {overall_winner}
    """
    
    ax5.text(0.5, 0.5, summary_text, ha="center", va="center", fontsize=12, 
             family="monospace", bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    
    comparison_dash_path = os.path.join(out_dir, "comparison_dashboard.png")
    plt.savefig(comparison_dash_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"📊 Comparison dashboard saved to {comparison_dash_path}")
    
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, help="Single video to analyze")
    parser.add_argument("--video1", type=str, help="First video for comparison")
    parser.add_argument("--video2", type=str, help="Second video for comparison")
    parser.add_argument("--out", type=str, default="session1")
    args = parser.parse_args()
    
    if args.video1 and args.video2:
        compare_videos(args.video1, args.video2, args.out)
    elif args.video:
        analyze_scroll(args.video, args.out)
    else:
        print("ERROR: Either provide --video for single analysis or --video1 and --video2 for comparison")

import argparse
import os
import time
import cv2

from analyzer import FrameAnalyzer
from scroll_controller import ScrollController


def _read_frame(path, retries=3, delay=0.1):
    """Attempt to read a frame from disk with small retries."""
    for _ in range(retries):
        frame = cv2.imread(path)
        if frame is not None:
            return frame
        time.sleep(delay)
    raise RuntimeError(f"Unable to read frame from {path}")


# -------------------------
# Mode 1: Scroll Until End
# -------------------------
def run_until_end(fps, out_dir, swipe_ms):
    scroll = ScrollController(swipe_ms=swipe_ms, out_dir=out_dir)
    analyzer = FrameAnalyzer(movement_threshold=0.015)

    frame_counter = 0
    no_move_count = 0
    max_no_move = 3

    # Start full-device recording in parallel to capture the entire scroll session.
    scroll.start_recording()

    prev_path = scroll.screenshot("frame_0.png")
    prev_frame = _read_frame(prev_path)

    while True:
        time.sleep(1 / fps)
        frame_counter += 1
        new_path = scroll.scroll_and_capture(frame_counter)
        new_frame = _read_frame(new_path)

        moved = analyzer.screen_moved(prev_frame, new_frame)

        if moved:
            print(f"[OK] Scroll {frame_counter}: Page moved")
            no_move_count = 0
        else:
            print(f"[!] Scroll {frame_counter}: No movement")
            no_move_count += 1

        if no_move_count >= max_no_move:
            print("\n[SUCCESS] Page end reached - stopping scroll.\n")
            break

        prev_frame = new_frame

    analyzer.analyze_frames(out_dir)
    analyzer.save_report(out_dir)
    analyzer.create_video(out_dir, fps)

    # Stop full recording and save alongside analysis outputs.
    full_video_path = scroll.stop_recording(os.path.join(out_dir, "scroll_full_record.mp4"))
    if full_video_path:
        print(f"[VIDEO] Full session video saved at: {full_video_path}")
        return full_video_path
    else:
        return os.path.join(out_dir, "scroll_full_record.mp4")

# -------------------------
# Mode 2: Fixed Scroll Count
# -------------------------
def run_scroll_count(scrolls, fps, out_dir, swipe_ms):
    scroll = ScrollController(swipe_ms=swipe_ms, out_dir=out_dir)
    analyzer = FrameAnalyzer(movement_threshold=0.015)

    for i in range(scrolls):
        time.sleep(1 / fps)
        scroll.scroll_and_capture(i)
        print(f"[OK] Scroll {i+1} completed")

    analyzer.analyze_frames(out_dir)
    analyzer.save_report(out_dir)

# -------------------------
# Mode 3: Time Duration
# -------------------------
def run_duration(duration, fps, out_dir, swipe_ms):
    scroll = ScrollController(swipe_ms=swipe_ms, out_dir=out_dir)
    analyzer = FrameAnalyzer(movement_threshold=0.015)

    total_frames = duration * fps
    for i in range(total_frames):
        time.sleep(1 / fps)
        scroll.scroll_and_capture(i)
        print(f"[OK] Frame {i+1}/{total_frames}")

    analyzer.analyze_frames(out_dir)
    analyzer.save_report(out_dir)

# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="duration", help="duration | until_end | scrolls")
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--scrolls", type=int, default=20)
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--swipe_ms", type=int, default=1200)  # slower scroll
    parser.add_argument("--out", type=str, default="session_output")

    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    if args.mode == "until_end":
        run_until_end(args.fps, args.out, args.swipe_ms)
    elif args.mode == "scrolls":
        run_scroll_count(args.scrolls, args.fps, args.out, args.swipe_ms)
    else:
        run_duration(args.duration, args.fps, args.out, args.swipe_ms)


if __name__ == "__main__":
    main()

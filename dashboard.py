import argparse
import os
import queue
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from tkinter import scrolledtext

from PIL import Image, ImageTk

try:
    from realtime_analyzer import run_until_end
    REALTIME_ANALYZER_AVAILABLE = True
except ImportError:
    REALTIME_ANALYZER_AVAILABLE = False
    run_until_end = None

from scroll_analysis import analyze_scroll, compare_videos


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📊 Video Scroll Performance Analyzer")
        # Larger window for bigger graphs
        self.geometry("1400x900")
        self.configure(bg="#f0f4f8")

        self.log_queue = queue.Queue()
        self.dashboard_img = None
        self.first_frame_img = None
        self.overall_text = tk.StringVar(value="Run an analysis to see overall rating and key numbers here.")
        self.selected_video_path = None
        self.selected_video_path_2 = None
        self.comparison_mode = False

        # Use a modern-themed ttk style with accent colors.
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Header.TLabel",
            font=("Segoe UI", 18, "bold"),
            foreground="#0f766e",
            background="#f0f4f8",
        )
        style.configure(
            "Section.TLabel",
            font=("Segoe UI", 12, "bold"),
            foreground="#1f2933",
            background="#f0f4f8",
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=10,
        )
        style.map(
            "Primary.TButton",
            foreground=[("!disabled", "#ffffff"), ("active", "#ffffff")],
            background=[("!disabled", "#2563eb"), ("active", "#1d4ed8")],
        )

        self._build_controls()
        self._build_preview()

        self.after(100, self._drain_logs)

    # ---------------- UI Builders ----------------
    def _build_controls(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.X)

        # Colorful header bar with gradient effect
        header_frame = tk.Frame(frm, bg="#0f766e", height=60)
        header_frame.grid(row=0, column=0, columnspan=6, sticky="nsew", pady=(0, 10))
        header_label = ttk.Label(
            header_frame,
            text="📊 Video Scroll Performance Analyzer",
            style="Header.TLabel",
        )
        header_label.pack(side=tk.LEFT, padx=20, pady=15)
        
        # Decorative subtitle
        subtitle_label = ttk.Label(
            header_frame,
            text="Compare two videos to analyze scroll smoothness and performance",
            font=("Segoe UI", 10),
            foreground="#a7f3d0",
            background="#0f766e",
        )
        subtitle_label.pack(side=tk.LEFT, padx=(20, 0), pady=15)

        # Internal config (not shown as inputs)
        self.out_var = tk.StringVar(value="session_ui")
        self.fps_var = tk.IntVar(value=20)
        self.swipe_var = tk.IntVar(value=3000)

        # Button container with decorative frame
        button_container = tk.Frame(frm, bg="#e0e7ff", relief=tk.RAISED, bd=2)
        button_container.grid(row=1, column=0, columnspan=6, pady=15, padx=10, sticky="ew")
        
        button_frame = ttk.Frame(button_container)
        button_frame.pack(pady=15, padx=20)
        
        # Only keep the Compare Two Videos button - make it prominent
        self.compare_btn = ttk.Button(
            button_frame,
            text="📁 Compare Two Pages Scroll (Upload)",
            style="Primary.TButton",
            command=self._upload_two_videos,
        )
        self.compare_btn.pack(side=tk.LEFT, padx=10)

        # Selected file label with better styling
        self.file_label = ttk.Label(
            button_frame,
            text="",
            font=("Segoe UI", 10, "italic"),
            foreground="#059669",
            background="#e0e7ff",
        )
        self.file_label.pack(side=tk.LEFT, padx=20)

        for i in range(6):
            frm.columnconfigure(i, weight=1)

    def _build_preview(self):
        # Use a paned window to allow resizing between log and preview areas
        main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top pane: Log area
        log_frame = ttk.Frame(main_paned)
        main_paned.add(log_frame, weight=1)
        
        log_header = tk.Frame(log_frame, bg="#1e293b", height=35)
        log_header.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(
            log_header, 
            text="📝 Activity Log", 
            style="Section.TLabel",
            background="#1e293b",
            foreground="#ffffff",
        ).pack(anchor="w", padx=10, pady=8)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            state=tk.DISABLED,
            wrap=tk.WORD,
            bg="#111827",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bottom pane: Preview and results area - make it scrollable
        preview_container = ttk.Frame(main_paned)
        main_paned.add(preview_container, weight=2)
        
        # Create scrollable canvas for preview area
        preview_canvas_wrapper = tk.Canvas(preview_container, highlightthickness=0, bg="#f3f5fb")
        preview_scrollbar = ttk.Scrollbar(preview_container, orient=tk.VERTICAL, command=preview_canvas_wrapper.yview)
        preview_scrollable_frame = ttk.Frame(preview_canvas_wrapper)
        
        def update_scroll_region(event=None):
            preview_canvas_wrapper.configure(scrollregion=preview_canvas_wrapper.bbox("all"))
        
        preview_scrollable_frame.bind("<Configure>", update_scroll_region)
        preview_canvas_wrapper.bind("<Configure>", lambda e: preview_canvas_wrapper.itemconfig(preview_canvas_wrapper.find_all()[0], width=e.width))
        
        preview_canvas_wrapper.create_window((0, 0), window=preview_scrollable_frame, anchor="nw")
        preview_canvas_wrapper.configure(yscrollcommand=preview_scrollbar.set)
        
        self.preview_canvas_wrapper = preview_canvas_wrapper
        self.preview_scrollable_frame = preview_scrollable_frame
        
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        preview_canvas_wrapper.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        preview_frame = preview_scrollable_frame

        # Dashboard graph section with decorative header
        graph_header_frame = tk.Frame(preview_frame, bg="#0f766e", relief=tk.RAISED, bd=2)
        graph_header_frame.pack(fill=tk.X, pady=(0, 5), padx=5)
        ttk.Label(
            graph_header_frame, 
            text="📊 Performance Analysis Dashboard", 
            style="Section.TLabel",
            background="#0f766e",
            foreground="#ffffff",
        ).pack(anchor="w", pady=10, padx=15)
        
        # Graph preview with smaller size (clickable to open in new window)
        graph_canvas_container = tk.Frame(preview_frame, bg="#ffffff", relief=tk.SUNKEN, bd=3)
        graph_canvas_container.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Graph canvas
        self.preview_canvas = tk.Canvas(
            graph_canvas_container, 
            highlightthickness=0,
            bg="#ffffff", 
            height=400,
            width=800
        )
        graph_vbar = ttk.Scrollbar(graph_canvas_container, orient=tk.VERTICAL, command=self.preview_canvas.yview)
        graph_hbar = ttk.Scrollbar(graph_canvas_container, orient=tk.HORIZONTAL, command=self.preview_canvas.xview)
        self.preview_canvas.configure(yscrollcommand=graph_vbar.set, xscrollcommand=graph_hbar.set)

        graph_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        graph_hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.preview = ttk.Label(self.preview_canvas, background="#ffffff")
        self.preview_window = self.preview_canvas.create_window((0, 0), window=self.preview, anchor="nw")

        def _on_graph_configure(event):
            self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

        self.preview.bind("<Configure>", _on_graph_configure)

        # Overall numeric summary area - always visible with decorative styling
        overall_frame = tk.Frame(preview_frame, bg="#dbeafe", relief=tk.RAISED, bd=2)
        overall_frame.pack(fill=tk.X, pady=(0, 6), padx=5)
        
        overall_title = ttk.Label(
            overall_frame,
            text="📈 Overall Rating and Metrics",
            font=("Segoe UI", 12, "bold"),
            foreground="#1e40af",
            background="#dbeafe",
        )
        overall_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        overall_content = tk.Frame(overall_frame, bg="#dbeafe")
        overall_content.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        self.overall_label = ttk.Label(
            overall_content,
            textvariable=self.overall_text,
            wraplength=1200,
            justify="left",
            font=("Segoe UI", 10),
            background="#dbeafe",
            foreground="#1e3a8a",
        )
        self.overall_label.pack(anchor="w", pady=(0, 6))
        
        # Reference ranges - clear formatting with decorative styling
        ref_frame = tk.Frame(overall_content, bg="#dbeafe")
        ref_frame.pack(fill=tk.X, pady=(0, 0))
        ref_title = ttk.Label(
            ref_frame,
            text="📚 Reference Ranges (What the Numbers Mean):",
            font=("Segoe UI", 10, "bold"),
            foreground="#1e40af",
            background="#dbeafe",
        )
        ref_title.pack(anchor="w", pady=(0, 6))
        
        ref_text = (
            "📊 ACTIVITY SCORE: How much content moves during scrolling (higher = more movement, neither high nor low is inherently better)\n"
            "⚡ JERKINESS: How consistent the motion is (lower is better)\n"
            "   • Excellent: < 2.0 (very consistent motion)\n"
            "   • Good: < 5.0 (mostly smooth)\n"
            "   • Fair: < 10.0 (some variability)\n"
            "   • Poor: ≥ 10.0 (very jerky)\n"
            "⏱️ FRAME-TIME JITTER: Variation in time between frames in milliseconds (lower is better)\n"
            "   • Excellent: < 3 ms (perfectly smooth, industry benchmark)\n"
            "   • Good: < 8 ms (smooth scrolling)\n"
            "   • Fair: < 16 ms (noticeable but acceptable, target: 60 FPS = 16.67 ms)\n"
            "   • Poor: ≥ 16 ms (significant stutter, below 60 FPS)"
        )
        ref_label = ttk.Label(
            ref_frame,
            text=ref_text,
            wraplength=1200,
            justify="left",
            font=("Segoe UI", 9),
            foreground="#1e3a8a",
            background="#dbeafe",
        )
        ref_label.pack(anchor="w")

    # ---------------- Logging helpers ----------------
    def log(self, msg: str):
        self.log_queue.put(msg)

    def _drain_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.after(100, self._drain_logs)

    # ---------------- Actions ----------------
    def _set_buttons_state(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.compare_btn.configure(state=state)

    def _upload_and_analyze(self):
        """Open file dialog to select video and analyze it."""
        video_path = filedialog.askopenfilename(
            title="Select Video File to Analyze",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*"),
            ],
        )

        if not video_path:
            return

        if not os.path.exists(video_path):
            self.log(f"[ERROR] Selected file does not exist: {video_path}")
            return

        self.selected_video_path = video_path
        self.file_label.config(
            text=f"Selected: {os.path.basename(video_path)}",
            foreground="#059669",
        )

        out_dir = self.out_var.get().strip() or "session_ui"
        os.makedirs(out_dir, exist_ok=True)

        def worker():
            try:
                self._set_buttons_state(False)
                self.log(f"[FILE] Selected video: {os.path.basename(video_path)}")
                self.log(f"[START] Analyzing uploaded video...")
                self.log(f"[FILE] Full path: {video_path}")
                self.log(f"[OUTPUT] Results will be saved to: {out_dir}\n")

                # Analyze the uploaded video using scroll_analysis.py
                report = analyze_scroll(video_path, out_dir)

                if report:
                    self.log("[OK] Analysis completed successfully\n")
                    self._report_summary(report)
                    self._load_dashboard_image(out_dir)
                else:
                    self.log("[WARNING] Analysis returned no report.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[ERROR] Analysis failed: {exc}")
            finally:
                self._set_buttons_state(True)

        threading.Thread(target=worker, daemon=True).start()

    def _upload_two_videos(self):
        """Open file dialogs to select two videos and compare them."""
        video_path1 = filedialog.askopenfilename(
            title="Select First Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*"),
            ],
        )

        if not video_path1:
            return

        video_path2 = filedialog.askopenfilename(
            title="Select Second Video File for Comparison",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*"),
            ],
        )

        if not video_path2:
            return

        if not os.path.exists(video_path1):
            self.log(f"[ERROR] First file does not exist: {video_path1}")
            return
        
        if not os.path.exists(video_path2):
            self.log(f"[ERROR] Second file does not exist: {video_path2}")
            return

        self.selected_video_path = video_path1
        self.selected_video_path_2 = video_path2
        self.comparison_mode = True
        
        self.file_label.config(
            text=f"Comparing: {os.path.basename(video_path1)} vs {os.path.basename(video_path2)}",
            foreground="#059669",
        )

        out_dir = self.out_var.get().strip() or "session_ui_comparison"
        os.makedirs(out_dir, exist_ok=True)

        def worker():
            try:
                self._set_buttons_state(False)
                self.log(f"[FILE] Video 1: {os.path.basename(video_path1)}")
                self.log(f"[FILE] Video 2: {os.path.basename(video_path2)}")
                self.log(f"[START] Analyzing and comparing videos...")
                self.log(f"[OUTPUT] Results will be saved to: {out_dir}\n")

                # Compare the two videos
                comparison = compare_videos(video_path1, video_path2, out_dir)

                if comparison:
                    self.log("[OK] Comparison completed successfully\n")
                    self._report_comparison(comparison)
                    self._load_dashboard_image(out_dir, "comparison_dashboard.png")
                else:
                    self.log("[WARNING] Comparison returned no results.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[ERROR] Comparison failed: {exc}")
            finally:
                self._set_buttons_state(True)
                self.comparison_mode = False

        threading.Thread(target=worker, daemon=True).start()

    def _report_comparison(self, comparison: dict):
        """Display comparison results in the dashboard."""
        video1 = comparison.get("video1", {})
        video2 = comparison.get("video2", {})
        results = comparison.get("results", {})
        
        # Build comparison summary
        overall_lines = []
        overall_lines.append("📊 VIDEO COMPARISON RESULTS")
        overall_lines.append("=" * 50)
        overall_lines.append(f"\n🏆 Overall Winner: {results.get('overall_winner', 'Unknown')}")
        overall_lines.append(f"\n📹 Video 1: {video1.get('name', 'Unknown')}")
        overall_lines.append(f"   Rating: {video1.get('rating', 'Unknown')}")
        overall_lines.append(f"   Jerkiness: {video1.get('jerkiness', 0):.2f} {'✓' if results.get('better_jerkiness') == 'Video 1' else ''}")
        overall_lines.append(f"   Jitter: {video1.get('jitter_ms', 0):.2f} ms {'✓' if results.get('better_jitter') == 'Video 1' else ''}")
        overall_lines.append(f"   Estimated FPS: {video1.get('estimated_fps', 0):.1f} {'✓' if results.get('better_fps') == 'Video 1' else ''}")
        
        overall_lines.append(f"\n📹 Video 2: {video2.get('name', 'Unknown')}")
        overall_lines.append(f"   Rating: {video2.get('rating', 'Unknown')}")
        overall_lines.append(f"   Jerkiness: {video2.get('jerkiness', 0):.2f} {'✓' if results.get('better_jerkiness') == 'Video 2' else ''}")
        overall_lines.append(f"   Jitter: {video2.get('jitter_ms', 0):.2f} ms {'✓' if results.get('better_jitter') == 'Video 2' else ''}")
        overall_lines.append(f"   Estimated FPS: {video2.get('estimated_fps', 0):.1f} {'✓' if results.get('better_fps') == 'Video 2' else ''}")
        
        overall_lines.append(f"\n💡 Interpretation:")
        overall_lines.append(f"   • Lower jerkiness = smoother, more consistent motion")
        overall_lines.append(f"   • Lower jitter = more stable frame timing (target < 8ms)")
        overall_lines.append(f"   • Higher FPS = smoother scrolling (target: 60 FPS)")
        
        self.overall_text.set("\n".join(overall_lines))
        
        
        # Update scroll region
        self.after(100, lambda: self.preview_canvas_wrapper.configure(
            scrollregion=self.preview_canvas_wrapper.bbox("all")
        ))
        
        # Log summary
        self.log("------ Comparison Summary ------")
        self.log(f"Overall Winner: {results.get('overall_winner', 'Unknown')}")
        self.log(f"Video 1 Rating: {video1.get('rating', 'Unknown')}")
        self.log(f"Video 2 Rating: {video2.get('rating', 'Unknown')}")
        self.log("------------------------------")

    def _capture_and_compare_two_videos(self):
        """Capture two videos sequentially and compare them."""
        if not REALTIME_ANALYZER_AVAILABLE:
            self.log("[ERROR] Capture feature is not available. scroll_controller module is missing.")
            return
        
        out_dir_base = self.out_var.get().strip() or "session_ui"
        fps = self.fps_var.get()
        swipe = self.swipe_var.get()
        
        # Create separate directories for each video
        out_dir1 = os.path.join(out_dir_base, "video1_capture")
        out_dir2 = os.path.join(out_dir_base, "video2_capture")
        comparison_dir = os.path.join(out_dir_base, "comparison")

        def worker():
            try:
                self._set_buttons_state(False)
                
                # ===== CAPTURE FIRST VIDEO =====
                self.log("=" * 60)
                self.log("[VIDEO 1] Starting first video capture...")
                self.log("=" * 60)
                self.log("[INFO] Please scroll on your app now. The capture will stop when scrolling ends.")
                
                shutil.rmtree(out_dir1, ignore_errors=True)
                os.makedirs(out_dir1, exist_ok=True)
                
                video_path1 = run_until_end(fps=fps, out_dir=out_dir1, swipe_ms=swipe)
                if not video_path1 or not os.path.exists(video_path1):
                    # Try alternative path
                    video_path1 = os.path.join(out_dir1, "scroll_full_record.mp4")
                
                if os.path.exists(video_path1):
                    self.log(f"[OK] First video captured: {os.path.basename(video_path1)}")
                else:
                    self.log("[ERROR] First video capture failed - file not found")
                    return
                
                # Brief pause between captures
                self.log("\n[PAUSE] Waiting 2 seconds before second capture...\n")
                time.sleep(2)
                
                # ===== CAPTURE SECOND VIDEO =====
                self.log("=" * 60)
                self.log("[VIDEO 2] Starting second video capture...")
                self.log("=" * 60)
                self.log("[INFO] Please scroll on your app again. The capture will stop when scrolling ends.")
                
                shutil.rmtree(out_dir2, ignore_errors=True)
                os.makedirs(out_dir2, exist_ok=True)
                
                video_path2 = run_until_end(fps=fps, out_dir=out_dir2, swipe_ms=swipe)
                if not video_path2 or not os.path.exists(video_path2):
                    # Try alternative path
                    video_path2 = os.path.join(out_dir2, "scroll_full_record.mp4")
                
                if os.path.exists(video_path2):
                    self.log(f"[OK] Second video captured: {os.path.basename(video_path2)}")
                else:
                    self.log("[ERROR] Second video capture failed - file not found")
                    return
                
                # ===== COMPARE THE TWO VIDEOS =====
                self.log("\n" + "=" * 60)
                self.log("[COMPARISON] Analyzing and comparing both videos...")
                self.log("=" * 60 + "\n")
                
                os.makedirs(comparison_dir, exist_ok=True)
                comparison = compare_videos(video_path1, video_path2, comparison_dir)
                
                if comparison:
                    self.log("[OK] Comparison completed successfully\n")
                    self._report_comparison(comparison)
                    self._load_dashboard_image(comparison_dir, "comparison_dashboard.png")
                    self.file_label.config(
                        text=f"Captured & Compared: Video 1 vs Video 2",
                        foreground="#059669",
                    )
                else:
                    self.log("[WARNING] Comparison returned no results.")
                    
            except Exception as exc:  # noqa: BLE001
                self.log(f"[ERROR] Capture and comparison failed: {exc}")
                import traceback
                self.log(f"[ERROR] Traceback: {traceback.format_exc()}")
            finally:
                self._set_buttons_state(True)

        threading.Thread(target=worker, daemon=True).start()

    def _run_pipeline(self):
        if not REALTIME_ANALYZER_AVAILABLE:
            self.log("[ERROR] Capture feature is not available. scroll_controller module is missing.")
            self.log("[INFO] Please use 'Upload & Analyze Video' or 'Compare Two Videos' instead.")
            return
            
        out_dir = self.out_var.get().strip() or "session_ui"
        fps = self.fps_var.get()
        swipe = self.swipe_var.get()

        def worker():
            try:
                self.log(f"[START] Clearing {out_dir} and starting capture...")
                shutil.rmtree(out_dir, ignore_errors=True)

                # Capture and analyze frames + full recording
                run_until_end(fps=fps, out_dir=out_dir, swipe_ms=swipe)
                self.log("[OK] Capture complete. Running video analysis...")

                video_path = os.path.join(out_dir, "scroll_full_record.mp4")
                report = analyze_scroll(video_path, out_dir)
                if report:
                    self._report_summary(report)
                    self._load_dashboard_image(out_dir)
                else:
                    self.log("[WARNING] Analysis returned no report.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[ERROR] Error: {exc}")
            finally:
                self._set_buttons_state(True)

        self._set_buttons_state(False)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Display helpers ----------------
    def _report_summary(self, report: dict):
        self.log("------ Analysis Summary ------")
        rating = report.get("smoothness_rating")
        summary = report.get("summary")
        issues = report.get("issues")
        windows = report.get("problem_windows") or []

        frames = report.get("frames_processed")
        avg = report.get("average_scroll_activity")
        jerk = report.get("scroll_jerkiness")
        jitter = report.get("frame_time_jitter_ms")

        # Build friendly overall text for the dedicated area with clear explanations
        overall_lines = []
        if rating:
            rating_desc = report.get("smoothness_description", "")
            overall_lines.append(f"📊 Overall Rating: {rating}")
            if rating_desc:
                overall_lines.append(f"   {rating_desc}")
        
        if frames is not None:
            overall_lines.append(f"\n📹 Frames Analyzed: {frames}")
        
        if avg is not None:
            overall_lines.append(f"\n📈 Activity Score: {avg:.2f}")
            overall_lines.append(f"   → Meaning: How much the content moves during scrolling")
            overall_lines.append(f"   → Interpretation: Higher values indicate more movement (neither high nor low is inherently better)")
        
        if jerk is not None:
            jerk_rating = "Excellent" if jerk < 2.0 else ("Good" if jerk < 5.0 else ("Fair" if jerk < 10.0 else "Poor"))
            overall_lines.append(f"\n⚡ Jerkiness: {jerk:.2f} ({jerk_rating})")
            overall_lines.append(f"   → Meaning: How consistent the motion is (lower is better)")
            overall_lines.append(f"   → Industry Standard: < 2 = Excellent, < 5 = Good, < 10 = Fair, ≥ 10 = Poor")
        
        if jitter is not None:
            jitter_rating = "Excellent" if jitter < 3.0 else ("Good" if jitter < 8.0 else ("Fair" if jitter < 16.0 else "Poor"))
            overall_lines.append(f"\n⏱️ Frame-time Jitter: {jitter:.2f} ms ({jitter_rating})")
            overall_lines.append(f"   → Meaning: Variation in time between frames (lower is better)")
            overall_lines.append(f"   → Industry Standard: < 3ms = Excellent, < 8ms = Good, < 16ms = Fair, ≥ 16ms = Poor")
        
        estimated_fps = report.get("estimated_fps")
        if estimated_fps is not None and estimated_fps > 0:
            overall_lines.append(f"\n🎬 Estimated FPS: {estimated_fps:.1f}")
            overall_lines.append(f"   → Meaning: Average frames per second")
            overall_lines.append(f"   → Target: 60 FPS for smooth scrolling (16.67 ms per frame)")
        
        if summary:
            overall_lines.append(f"\n💡 Summary: {summary}")
        self.overall_text.set("\n".join(overall_lines))


        # Update scroll region after content changes
        self.after(100, lambda: self.preview_canvas_wrapper.configure(
            scrollregion=self.preview_canvas_wrapper.bbox("all")
        ))

        # Still mirror key info into the log for history
        if rating:
            self.log(f"Overall scroll rating: {rating}")
        if summary:
            self.log(summary)

        self.log("------------------------------")

    def _load_dashboard_image(self, out_dir=None, filename="scroll_analysis_dashboard.png"):
        out_dir = out_dir or (self.out_var.get().strip() or "session_ui")
        path = os.path.join(out_dir, filename)
        if not os.path.exists(path):
            self.log(f"[WARNING] Dashboard image not found: {path}")
            return
        try:
            img = Image.open(path)
            # Resize to fit in the canvas preview
            img.thumbnail((800, 400), Image.Resampling.LANCZOS)
            self.dashboard_img = ImageTk.PhotoImage(img)
            self.preview.configure(image=self.dashboard_img)
            self.log(f"🖼️ Loaded dashboard: {path}")
            # Update scroll regions
            self.after(100, lambda: self.preview_canvas_wrapper.configure(
                scrollregion=self.preview_canvas_wrapper.bbox("all")
            ))
        except Exception as exc:  # noqa: BLE001
            self.log(f"[ERROR] Failed to load dashboard image: {exc}")



def main():
    parser = argparse.ArgumentParser(description="Interactive Tkinter dashboard for scroll analysis.")
    parser.add_argument("--out", type=str, default="session_ui", help="Default output folder")
    parser.add_argument("--fps", type=int, default=20, help="Capture FPS")
    parser.add_argument("--swipe_ms", type=int, default=3000, help="Swipe duration in ms")
    args = parser.parse_args()

    app = Dashboard()
    app.out_var.set(args.out)
    app.fps_var.set(args.fps)
    app.swipe_var.set(args.swipe_ms)
    app.mainloop()


if __name__ == "__main__":
    main()


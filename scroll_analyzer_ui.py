import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from PIL import Image, ImageTk

from scroll_analysiss import analyze_scroll


class ScrollAnalyzerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scroll Performance Analyzer")
        self.geometry("1000x700")
        self.configure(bg="#f3f5fb")

        self.out_dir = "session_ui"
        self.selected_video_path = None

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg="#0f766e", height=50)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Scroll Performance Analyzer",
            font=("Segoe UI", 16, "bold"),
            bg="#0f766e",
            fg="white",
        ).pack(pady=12)

        main = tk.Frame(self, bg="#f3f5fb", padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        controls = tk.Frame(main, bg="#f3f5fb")
        controls.pack(fill=tk.X, pady=(0, 15))

        # File selection button
        self.select_btn = tk.Button(
            controls,
            text="Select Video File",
            font=("Segoe UI", 11, "bold"),
            bg="#059669",
            fg="white",
            padx=15,
            pady=8,
            command=self._select_video,
            cursor="hand2",
        )
        self.select_btn.pack(side=tk.LEFT)

        # Selected file label
        self.file_label = tk.Label(
            controls,
            text="No file selected",
            font=("Segoe UI", 9),
            bg="#f3f5fb",
            fg="#6b7280",
            wraplength=400,
        )
        self.file_label.pack(side=tk.LEFT, padx=15)

        # Analyze button
        self.analyze_btn = tk.Button(
            controls,
            text="Analyze Video",
            font=("Segoe UI", 12, "bold"),
            bg="#2563eb",
            fg="white",
            padx=20,
            pady=10,
            command=self._start_analysis,
            state=tk.DISABLED,
            cursor="hand2",
        )
        self.analyze_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.status_label = tk.Label(
            controls, text="Ready", font=("Segoe UI", 10), bg="#f3f5fb", fg="#4b5563"
        )
        self.status_label.pack(side=tk.LEFT, padx=20)

        panes = tk.PanedWindow(main, orient=tk.HORIZONTAL, sashwidth=5)
        panes.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(panes, bg="#ffffff")
        panes.add(left, width=420)

        tk.Label(left, text="Activity Log", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.log_text = scrolledtext.ScrolledText(
            left, height=14, bg="#111827", fg="#e5e7eb", font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10)

        tk.Label(left, text="Analysis Results", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.results_text = scrolledtext.ScrolledText(
            left, height=12, bg="#ffffff", fg="#1f2933", font=("Segoe UI", 10)
        )
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=10)

        right = tk.Frame(panes, bg="#ffffff")
        panes.add(right, width=560)

        tk.Label(right, text="Scroll Activity Dashboard", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        self.graph_canvas = tk.Canvas(right, bg="#ffffff")
        self.graph_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.graph_label = tk.Label(self.graph_canvas, bg="#ffffff")
        self.graph_canvas.create_window((0, 0), window=self.graph_label, anchor="nw")

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.update()

    def _select_video(self):
        """Open file dialog to select a video file."""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*"),
            ],
        )

        if file_path:
            self.selected_video_path = file_path
            # Show shortened path if too long
            display_path = file_path
            if len(display_path) > 60:
                display_path = "..." + display_path[-57:]
            self.file_label.config(
                text=f"Selected: {os.path.basename(file_path)}",
                fg="#059669",
            )
            self.analyze_btn.config(state=tk.NORMAL)
            self.log(f"[FILE] Selected video: {os.path.basename(file_path)}")
            self.log(f"[FILE] Full path: {file_path}")

    def _start_analysis(self):
        if not self.selected_video_path:
            messagebox.showwarning("No File", "Please select a video file first.")
            return

        if not os.path.exists(self.selected_video_path):
            messagebox.showerror("Error", "Selected video file does not exist.")
            return

        self.analyze_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.DISABLED)
        self.results_text.delete(1.0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.status_label.config(text="Analyzing...", fg="#2563eb")

        def worker():
            try:
                self.log("[START] Starting video analysis...")
                self.log(f"[FILE] Analyzing: {os.path.basename(self.selected_video_path)}")
                self.log(f"[FILE] Output directory: {self.out_dir}\n")

                # Analyze the selected video
                report = analyze_scroll(self.selected_video_path, self.out_dir)
                self.log("[OK] Analysis completed successfully\n")

                self._display_results(report)
                self._load_graph()

                self.status_label.config(text="Complete", fg="#059669")
                self.log("[SUCCESS] Analysis finished! Check results below.")

            except Exception as e:
                error_msg = f"[ERROR] Analysis failed: {str(e)}"
                self.log(error_msg)
                messagebox.showerror("Error", f"Analysis failed:\n{str(e)}")
                self.status_label.config(text="Error", fg="#dc2626")
            finally:
                self.analyze_btn.config(state=tk.NORMAL)
                self.select_btn.config(state=tk.NORMAL)

        threading.Thread(target=worker, daemon=True).start()

    def _display_results(self, report):
        t = self.results_text
        t.delete(1.0, tk.END)

        rating = report.get("smoothness_rating", "Unknown")
        color = {
            "Excellent": "#059669",
            "Good": "#2563eb",
            "Fair": "#f59e0b",
            "Poor": "#dc2626",
        }.get(rating, "#4b5563")

        t.insert(tk.END, "OVERALL RATING\n")
        t.insert(tk.END, f"   {rating}\n\n")
        t.tag_add("rating", "2.0", "3.0")
        t.tag_config("rating", foreground=color, font=("Segoe UI", 14, "bold"))

        t.insert(tk.END, "KEY METRICS\n")

        t.insert(
            tk.END,
            f"   Frames processed: {report.get('frames_processed', 0)}\n"
            f"   Avg frame interval: {report.get('average_frame_interval_ms', 0):.2f} ms\n"
            f"   Frame-time jitter: {report.get('frame_time_jitter_ms', 0):.2f} ms\n"
            f"   Max frame gap: {report.get('max_frame_gap_ms', 0):.2f} ms\n\n"
        )

        t.insert(tk.END, "WHAT THIS MEANS\n")
        meanings = {
            "Excellent": "   Extremely smooth scrolling. No visible lag.\n",
            "Good": "   Smooth scrolling with minor timing variation.\n",
            "Fair": "   Noticeable micro-stutter during scroll.\n",
            "Poor": "   Laggy or jerky scrolling with dropped frames.\n",
        }
        t.insert(tk.END, meanings.get(rating, ""))

        t.insert(
            tk.END,
            "\nREFERENCE RANGES\n"
            "   Excellent: jitter < 5 ms\n"
            "   Good: jitter < 12 ms\n"
            "   Fair: jitter < 25 ms\n"
            "   Poor: jitter ≥ 25 ms\n"
        )

    def _load_graph(self):
        path = os.path.join(self.out_dir, "scroll_analysis_dashboard.png")
        if not os.path.exists(path):
            return
        img = Image.open(path)
        img.thumbnail((900, 600))
        self.graph_img = ImageTk.PhotoImage(img)
        self.graph_label.config(image=self.graph_img)


if __name__ == "__main__":
    ScrollAnalyzerUI().mainloop()

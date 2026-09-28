"""
Desktop GUI Application for Architecture Diagram Generator.

A Tkinter-based desktop interface that replaces the old Streamlit web UI.
It scans Java / Python source code, builds a dependency graph, optionally
enriches it via Ollama (phi3:mini), and produces a native .gaphor file.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Make sure the src package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DEFAULT_OUTPUT_FILENAME
from src.ingestion.file_traverser import collect_source_files
from src.ingestion.parser import parse_all_files
from src.graph.builder import build_graph
from src.graph.relationships import extract_edges
from src.ai.semantic_grouper import enrich_graph_with_contexts
from src.ai.summarizer import enrich_graph_with_summaries
from src.gaphor_gen.model_builder import build_gaphor_model, save_model


class ArchitectureDiagramApp:
    """Main Tkinter application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Architecture Diagram Generator")
        self.root.geometry("650x580")
        self.root.resizable(True, True)

        # Style
        style = ttk.Style()
        style.theme_use("clam")

        # Output file path (set after generation)
        self._last_output: str = ""

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        padx = 12

        # --- Title ---
        title = ttk.Label(
            self.root,
            text="Architecture Diagram Generator",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(pady=(14, 2), padx=padx)

        subtitle = ttk.Label(
            self.root,
            text="Scan a Java or Python codebase and generate a native .gaphor diagram.",
            foreground="#555",
        )
        subtitle.pack(pady=(0, 12))

        # --- Input frame ---
        input_frame = ttk.LabelFrame(self.root, text="Input", padding=10)
        input_frame.pack(fill="x", padx=padx, pady=6)

        ttk.Label(input_frame, text="Source Code Directory:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self.dir_var = tk.StringVar()
        dir_entry = ttk.Entry(input_frame, textvariable=self.dir_var, width=50)
        dir_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        browse_btn = ttk.Button(
            input_frame, text="Browse...", command=self._browse_dir
        )
        browse_btn.grid(row=1, column=1)
        input_frame.columnconfigure(0, weight=1)

        ttk.Label(input_frame, text="Output .gaphor File:").grid(
            row=2, column=0, sticky="w", pady=(10, 4)
        )
        self.out_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Desktop", DEFAULT_OUTPUT_FILENAME)
        )
        out_entry = ttk.Entry(input_frame, textvariable=self.out_var, width=50)
        out_entry.grid(row=3, column=0, sticky="ew", padx=(0, 6))
        out_browse = ttk.Button(
            input_frame, text="Save As...", command=self._browse_output
        )
        out_browse.grid(row=3, column=1)
        input_frame.columnconfigure(0, weight=1)

        # --- AI options ---
        ai_frame = ttk.LabelFrame(self.root, text="AI Enrichment (Ollama)", padding=10)
        ai_frame.pack(fill="x", padx=padx, pady=6)

        self.ai_var = tk.BooleanVar(value=True)
        ai_check = ttk.Checkbutton(
            ai_frame,
            text="Use Ollama (phi3:mini) for context grouping & summaries",
            variable=self.ai_var,
        )
        ai_check.pack(anchor="w")

        self.ai_status = ttk.Label(
            ai_frame, text="Ollama status: checking...", foreground="#888"
        )
        self.ai_status.pack(anchor="w", pady=(4, 0))
        self._check_ollama()

        # --- Generate button ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10, padx=padx)

        self.gen_btn = ttk.Button(
            btn_frame,
            text="Generate Architecture Diagram",
            command=self._on_generate,
        )
        self.gen_btn.pack()

        # --- Progress / status ---
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill="both", expand=True, padx=padx, pady=6)

        self.progress = ttk.Progressbar(
            status_frame, mode="indeterminate", length=400
        )

        self.status_text = tk.Text(
            status_frame,
            height=10,
            width=70,
            font=("Consolas", 9),
            state="disabled",
            wrap="word",
            bg="#fafafa",
        )
        scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)

        self.status_text.pack(fill="both", expand=True, side="left")
        scrollbar.pack(fill="y", side="right")

        # --- Open action buttons (hidden initially) ---
        self.action_frame = ttk.Frame(self.root)
        self.action_frame.pack(pady=(2, 10))

        self.open_file_btn = ttk.Button(
            self.action_frame,
            text="Open .gaphor File",
            command=self._open_file,
        )
        self.open_folder_btn = ttk.Button(
            self.action_frame,
            text="Show in Folder",
            command=self._show_in_folder,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        self.status_text.configure(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")
        self.root.update_idletasks()

    def _clear_log(self) -> None:
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.configure(state="disabled")

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.gen_btn.configure(state=state)

    def _browse_dir(self) -> None:
        path = filedialog.askdirectory(title="Select Source Code Directory")
        if path:
            self.dir_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save .gaphor File As",
            defaultextension=".gaphor",
            filetypes=[("Gaphor files", "*.gaphor"), ("All files", "*.*")],
            initialfile=DEFAULT_OUTPUT_FILENAME,
        )
        if path:
            self.out_var.set(path)

    def _check_ollama(self) -> None:
        """Ping Ollama in a background thread."""
        def _ping():
            try:
                import requests
                resp = requests.get("http://localhost:11434/api/tags", timeout=3)
                if resp.status_code == 200:
                    self.root.after(0, lambda: self.ai_status.configure(
                        text="Ollama status: connected", foreground="green"
                    ))
                else:
                    self.root.after(0, lambda: self.ai_status.configure(
                        text="Ollama status: unreachable (will skip AI)", foreground="orange"
                    ))
            except Exception:
                self.root.after(0, lambda: self.ai_status.configure(
                    text="Ollama status: not running (will skip AI)", foreground="#888"
                ))
        threading.Thread(target=_ping, daemon=True).start()

    def _open_file(self) -> None:
        if self._last_output and os.path.isfile(self._last_output):
            os.startfile(self._last_output)

    def _show_in_folder(self) -> None:
        if self._last_output and os.path.isfile(self._last_output):
            os.system(f'explorer /select,"{self._last_output}"')

    # ------------------------------------------------------------------
    # Pipeline execution (runs in background thread)
    # ------------------------------------------------------------------
    def _on_generate(self) -> None:
        src_dir = self.dir_var.get().strip()
        out_path = self.out_var.get().strip()

        if not src_dir or not os.path.isdir(src_dir):
            messagebox.showerror("Invalid Directory", "Please select a valid source code directory.")
            return
        if not out_path:
            messagebox.showerror("Invalid Output", "Please specify an output file path.")
            return

        self._set_buttons_enabled(False)
        self._clear_log()
        self.progress.pack(pady=(2, 6))
        self.progress.start()

        # Hide old action buttons
        self.open_file_btn.pack_forget()
        self.open_folder_btn.pack_forget()

        use_ai = self.ai_var.get()

        threading.Thread(
            target=self._run_pipeline,
            args=(src_dir, out_path, use_ai),
            daemon=True,
        ).start()

    def _run_pipeline(self, src_dir: str, out_path: str, use_ai: bool) -> None:
        try:
            # Phase 1: Ingestion
            self.root.after(0, lambda: self._log("Phase 1/4: Scanning source files..."))
            files = collect_source_files(src_dir)
            if not files:
                self.root.after(0, lambda: self._log("ERROR: No supported source files found."))
                self.root.after(0, self._pipeline_done)
                return
            self.root.after(0, lambda: self._log(f"  Found {len(files)} source file(s)."))

            metadata = parse_all_files(files)
            self.root.after(0, lambda: self._log(
                f"  Parsed {len(metadata.get('classes', []))} classes, "
                f"{len(metadata.get('interfaces', []))} interfaces."
            ))

            # Phase 2: Graph
            self.root.after(0, lambda: self._log("Phase 2/4: Building dependency graph..."))
            graph = build_graph(metadata)
            extract_edges(metadata, graph)
            self.root.after(0, lambda: self._log(
                f"  Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges."
            ))

            # Phase 3: AI enrichment
            if use_ai:
                self.root.after(0, lambda: self._log("Phase 3/4: AI enrichment (Ollama)..."))
                enrich_graph_with_contexts(graph)
                enrich_graph_with_summaries(graph)
                contexts = {graph.nodes[n].get("context", "N/A") for n in graph.nodes()}
                self.root.after(0, lambda: self._log(
                    f"  Contexts: {', '.join(sorted(contexts))}"
                ))
            else:
                self.root.after(0, lambda: self._log("Phase 3/4: AI enrichment skipped (disabled)."))

            # Phase 4: Gaphor generation
            self.root.after(0, lambda: self._log("Phase 4/4: Generating .gaphor model..."))
            tree = build_gaphor_model(graph)
            save_model(tree, out_path)
            self._last_output = out_path

            size_kb = os.path.getsize(out_path) / 1024
            self.root.after(0, lambda: self._log(
                f"\nDone! Architecture diagram saved to:\n  {out_path}\n  Size: {size_kb:.1f} KB"
            ))
            self.root.after(0, self._show_action_buttons)

        except Exception as exc:
            msg = str(exc)
            self.root.after(0, lambda m=msg: self._log(f"ERROR: {m}"))
        finally:
            self.root.after(0, self._pipeline_done)

    def _show_action_buttons(self) -> None:
        self.open_file_btn.pack(side="left", padx=6)
        self.open_folder_btn.pack(side="left", padx=6)

    def _pipeline_done(self) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self._set_buttons_enabled(True)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = ArchitectureDiagramApp()
    app.run()


if __name__ == "__main__":
    main()

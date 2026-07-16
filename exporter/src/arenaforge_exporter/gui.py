from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .core import Anchor, ExporterError, default_script_dir, load_saved_anchors, open_output_folder, run_export, ExportPaths


class ExporterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"ArenaForge MTGA Exporter {__version__}")
        self.geometry("820x680")
        self.minsize(720, 600)
        self.log_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.output_dir = tk.StringVar(value=str(default_script_dir()))
        self.raw_dir = tk.StringVar(value="")
        self.refresh_cache = tk.BooleanVar(value=False)
        self.use_saved = tk.BooleanVar(value=True)

        self.anchor_names: list[tk.StringVar] = []
        self.anchor_quantities: list[tk.StringVar] = []

        self._build_ui()
        self._load_saved_anchors()
        self.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(root, text="ArenaForge MTGA Collection Exporter", font=("Segoe UI", 16, "bold"))
        title.pack(anchor=tk.W)
        ttk.Label(
            root,
            text="Open MTG Arena, visit Collection or Decks, scroll around so cards load, then export.",
        ).pack(anchor=tk.W, pady=(4, 12))

        paths = ttk.LabelFrame(root, text="Paths", padding=12)
        paths.pack(fill=tk.X)
        self._path_row(paths, "Output folder", self.output_dir, self._choose_output, 0)
        self._path_row(paths, "MTGA Raw override", self.raw_dir, self._choose_raw, 1)
        ttk.Checkbutton(paths, text="Refresh card database cache", variable=self.refresh_cache).grid(
            row=2, column=1, sticky=tk.W, pady=(8, 0)
        )
        paths.columnconfigure(1, weight=1)

        anchors = ttk.LabelFrame(root, text="Anchor cards", padding=12)
        anchors.pack(fill=tk.X, pady=12)
        ttk.Label(anchors, text="Name").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(anchors, text="Owned quantity").grid(row=0, column=1, sticky=tk.W, padx=(8, 0))
        for index in range(5):
            name = tk.StringVar()
            qty = tk.StringVar(value="")
            self.anchor_names.append(name)
            self.anchor_quantities.append(qty)
            ttk.Entry(anchors, textvariable=name).grid(row=index + 1, column=0, sticky=tk.EW, pady=3)
            ttk.Entry(anchors, textvariable=qty, width=14).grid(row=index + 1, column=1, sticky=tk.W, padx=(8, 0), pady=3)
        anchors.columnconfigure(0, weight=1)
        ttk.Checkbutton(anchors, text="Use saved anchors when present", variable=self.use_saved).grid(
            row=6, column=0, sticky=tk.W, pady=(8, 0)
        )

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X)
        self.start_button = ttk.Button(actions, text="Start export", command=self._start_export)
        self.start_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="Open output folder", command=self._open_output).pack(side=tk.LEFT, padx=(8, 0))
        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))

        log_frame = ttk.LabelFrame(root, text="Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=14, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _path_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky=tk.EW, padx=8, pady=3)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, sticky=tk.E, pady=3)

    def _load_saved_anchors(self) -> None:
        try:
            anchors = load_saved_anchors(ExportPaths(Path(self.output_dir.get())))
        except Exception:
            anchors = []
        for index, anchor in enumerate(anchors[:5]):
            self.anchor_names[index].set(anchor.name)
            self.anchor_quantities[index].set(str(anchor.quantity))

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(default_script_dir()))
        if selected:
            self.output_dir.set(selected)
            self._load_saved_anchors()

    def _choose_raw(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.raw_dir.set(selected)

    def _open_output(self) -> None:
        open_output_folder(Path(self.output_dir.get()) / "mtga_collection.txt")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _collect_anchors(self) -> list[Anchor]:
        anchors: list[Anchor] = []
        for name_var, qty_var in zip(self.anchor_names, self.anchor_quantities):
            name = name_var.get().strip()
            qty_text = qty_var.get().strip()
            if not name and not qty_text:
                continue
            if not name or not qty_text:
                raise ExporterError("Each anchor row needs both a card name and quantity.")
            try:
                quantity = int(qty_text)
            except ValueError as exc:
                raise ExporterError(f"Invalid quantity for {name}: {qty_text}") from exc
            anchors.append(Anchor(0, quantity, name))

        if self.use_saved.get() and not anchors:
            anchors = load_saved_anchors(ExportPaths(Path(self.output_dir.get())))
        if not anchors:
            raise ExporterError("Enter at least one owned anchor card.")
        return anchors

    def _start_export(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            anchors = self._collect_anchors()
        except Exception as exc:
            messagebox.showerror("Anchor error", str(exc))
            return

        self.start_button.configure(state=tk.DISABLED)
        self.progress.configure(value=0)
        self._append_log("Starting export...")

        def worker() -> None:
            try:
                result = run_export(
                    anchors=anchors,
                    output_dir=self.output_dir.get(),
                    manual_raw_path=self.raw_dir.get().strip() or None,
                    refresh_cache=self.refresh_cache.get(),
                    log=lambda message: self.log_queue.put(("log", message)),
                    progress=lambda label, index, total: self.log_queue.put(("progress", (label, index, total))),
                )
                self.log_queue.put(("done", result))
            except Exception as exc:
                self.log_queue.put(("error", exc))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _drain_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "progress":
                    label, index, total = payload  # type: ignore[misc]
                    self.progress.configure(value=(index / max(total, 1)) * 100)
                    self._append_log(str(label))
                elif kind == "done":
                    self.start_button.configure(state=tk.NORMAL)
                    self.progress.configure(value=100)
                    result = payload
                    self._append_log(f"Export complete: {result.exported_cards} cards written.")
                    messagebox.showinfo("Export complete", f"Files saved to:\n{self.output_dir.get()}")
                    open_output_folder(Path(self.output_dir.get()) / "mtga_collection.txt")
                elif kind == "error":
                    self.start_button.configure(state=tk.NORMAL)
                    self._append_log(f"Error: {payload}")
                    messagebox.showerror("Export failed", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)


def main() -> None:
    app = ExporterApp()
    app.mainloop()


if __name__ == "__main__":
    main()

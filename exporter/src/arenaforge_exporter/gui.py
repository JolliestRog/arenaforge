from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .core import Anchor, ExporterError, default_script_dir, load_saved_anchors, open_output_folder, run_export, ExportPaths

DECKFORGE_URL = "https://deckforge.facey.page"

STEP1_TEXT = (
    "Open MTG Arena and go to your Collection screen.\n"
    "Scroll through it so the cards fully load — the exporter reads\n"
    "the card data Arena has loaded into memory."
)

STEP2_TEXT = (
    "Enter one card you know exactly how many copies of you own.\n"
    "This lets the exporter find your collection in Arena's memory.\n\n"
    "Good choices:  'Island' with 4 copies,  or any card you own exactly 1 of."
)

STEP3_TEXT = (
    "Click Export. Your collection will be saved as a .txt file.\n"
    "Then go to {url} and paste the contents to build your deck."
).format(url=DECKFORGE_URL)

SMARTSCREEN_TEXT = (
    "Windows may show a SmartScreen warning when you first run this.\n"
    "Click  More info → Run anyway.  This is normal for open-source tools\n"
    "without a code-signing certificate. Source code: github.com/JolliestRog/arenaforge"
)


def _section(parent: tk.Widget, number: str, title: str, body: str) -> ttk.Frame:
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, pady=(0, 12))

    header = ttk.Frame(frame)
    header.pack(fill=tk.X)

    badge = tk.Label(
        header,
        text=number,
        font=("Segoe UI", 11, "bold"),
        bg="#1a5c9a",
        fg="white",
        width=3,
        relief=tk.FLAT,
        padx=4,
        pady=2,
    )
    badge.pack(side=tk.LEFT)

    tk.Label(
        header,
        text=f"  {title}",
        font=("Segoe UI", 11, "bold"),
        anchor=tk.W,
    ).pack(side=tk.LEFT, fill=tk.X)

    ttk.Label(
        frame,
        text=body,
        wraplength=660,
        justify=tk.LEFT,
        foreground="#444",
    ).pack(anchor=tk.W, padx=(28, 0), pady=(4, 0))

    return frame


class ExporterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"ArenaForge MTGA Exporter  {__version__}")
        self.geometry("740x720")
        self.minsize(640, 620)
        self.configure(bg="#f5f6f8")
        self.resizable(True, True)

        self.log_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.output_dir = tk.StringVar(value=str(default_script_dir()))
        self.raw_dir = tk.StringVar(value="")
        self.refresh_cache = tk.BooleanVar(value=False)
        self.use_saved = tk.BooleanVar(value=True)
        self.anchor_name = tk.StringVar()
        self.anchor_qty = tk.StringVar()
        self._advanced_open = False

        self._build_ui()
        self._load_saved_anchors()
        self.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        # ── Header bar ───────────────────────────────────────────────────────
        header = tk.Frame(self, bg="#1a3a5c", pady=14)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="ArenaForge  MTGA Collection Exporter",
            font=("Segoe UI", 15, "bold"),
            bg="#1a3a5c",
            fg="white",
        ).pack(side=tk.LEFT, padx=20)
        tk.Label(
            header,
            text=DECKFORGE_URL,
            font=("Segoe UI", 9),
            bg="#1a3a5c",
            fg="#7ab8e8",
        ).pack(side=tk.RIGHT, padx=20)

        # ── SmartScreen notice ────────────────────────────────────────────────
        notice = tk.Frame(self, bg="#fff8e1", pady=8)
        notice.pack(fill=tk.X)
        tk.Label(
            notice,
            text=SMARTSCREEN_TEXT,
            font=("Segoe UI", 8),
            bg="#fff8e1",
            fg="#7a5800",
            justify=tk.LEFT,
        ).pack(padx=16, anchor=tk.W)

        # ── Scrollable body ───────────────────────────────────────────────────
        canvas = tk.Canvas(self, bg="#f5f6f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = ttk.Frame(canvas, padding=(20, 16, 20, 16))
        body_window = canvas.create_window((0, 0), window=body, anchor=tk.NW)

        def _on_configure(event: tk.Event) -> None:  # type: ignore[type-arg]
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(body_window, width=event.width)

        canvas.bind("<Configure>", _on_configure)
        body.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_mousewheel(event: tk.Event) -> None:  # type: ignore[type-arg]
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Step 1 ────────────────────────────────────────────────────────────
        _section(body, "1", "Open MTG Arena", STEP1_TEXT)
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # ── Step 2 ────────────────────────────────────────────────────────────
        _section(body, "2", "Enter an anchor card", STEP2_TEXT)

        anchor_frame = ttk.Frame(body)
        anchor_frame.pack(fill=tk.X, padx=(28, 0), pady=(6, 0))

        ttk.Label(anchor_frame, text="Card name:").grid(row=0, column=0, sticky=tk.W, pady=3)
        name_entry = ttk.Entry(anchor_frame, textvariable=self.anchor_name, width=28)
        name_entry.grid(row=0, column=1, sticky=tk.W, padx=8, pady=3)
        ttk.Label(anchor_frame, text='e.g.  "Island"', foreground="#888").grid(
            row=0, column=2, sticky=tk.W
        )

        ttk.Label(anchor_frame, text="Copies owned:").grid(row=1, column=0, sticky=tk.W, pady=3)
        qty_entry = ttk.Entry(anchor_frame, textvariable=self.anchor_qty, width=8)
        qty_entry.grid(row=1, column=1, sticky=tk.W, padx=8, pady=3)
        ttk.Label(anchor_frame, text='e.g.  "4"', foreground="#888").grid(
            row=1, column=2, sticky=tk.W
        )

        ttk.Checkbutton(
            anchor_frame,
            text="Remember this card for next time",
            variable=self.use_saved,
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(12, 4))

        # ── Step 3 ────────────────────────────────────────────────────────────
        _section(body, "3", "Export your collection", STEP3_TEXT)

        out_frame = ttk.Frame(body)
        out_frame.pack(fill=tk.X, padx=(28, 0), pady=(6, 0))
        ttk.Label(out_frame, text="Save to:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(out_frame, textvariable=self.output_dir).grid(
            row=0, column=1, sticky=tk.EW, padx=8, pady=3
        )
        ttk.Button(out_frame, text="Browse…", command=self._choose_output).grid(row=0, column=2)
        out_frame.columnconfigure(1, weight=1)

        # ── Action buttons ────────────────────────────────────────────────────
        actions = ttk.Frame(body)
        actions.pack(fill=tk.X, pady=(16, 0))

        self.start_button = ttk.Button(
            actions, text="  Export Collection  ", command=self._start_export
        )
        self.start_button.pack(side=tk.LEFT)

        ttk.Button(
            actions, text="Open output folder", command=self._open_output
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(14, 0))

        # ── Log ───────────────────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(body, text="Status", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        self.log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            height=7,
            state=tk.DISABLED,
            font=("Consolas", 9),
            relief=tk.FLAT,
            bg="#1e1e1e",
            fg="#cccccc",
            insertbackground="white",
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        # ── Advanced (collapsed) ──────────────────────────────────────────────
        adv_toggle = ttk.Button(body, text="▶  Advanced options", command=self._toggle_advanced)
        adv_toggle.pack(anchor=tk.W, pady=(12, 0))
        self._adv_toggle_btn = adv_toggle

        self._adv_frame = ttk.Frame(body)
        raw_row = ttk.Frame(self._adv_frame)
        raw_row.pack(fill=tk.X)
        ttk.Label(raw_row, text="MTGA Raw path override:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(raw_row, textvariable=self.raw_dir).grid(
            row=0, column=1, sticky=tk.EW, padx=8, pady=3
        )
        ttk.Button(raw_row, text="Browse…", command=self._choose_raw).grid(row=0, column=2)
        raw_row.columnconfigure(1, weight=1)
        ttk.Label(
            self._adv_frame,
            text="Only needed if Arena is installed in a non-standard location.",
            foreground="#888",
        ).pack(anchor=tk.W, padx=2)
        ttk.Checkbutton(
            self._adv_frame,
            text="Force refresh card database cache (slower, use if card names are wrong)",
            variable=self.refresh_cache,
        ).pack(anchor=tk.W, pady=(6, 0))

    def _toggle_advanced(self) -> None:
        if self._advanced_open:
            self._adv_frame.pack_forget()
            self._adv_toggle_btn.configure(text="▶  Advanced options")
        else:
            self._adv_frame.pack(fill=tk.X, pady=(6, 0))
            self._adv_toggle_btn.configure(text="▼  Advanced options")
        self._advanced_open = not self._advanced_open

    def _load_saved_anchors(self) -> None:
        try:
            anchors = load_saved_anchors(ExportPaths(Path(self.output_dir.get())))
        except Exception:
            return
        if anchors and self.use_saved.get():
            self.anchor_name.set(anchors[0].name)
            self.anchor_qty.set(str(anchors[0].quantity))

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
        name = self.anchor_name.get().strip()
        qty_text = self.anchor_qty.get().strip()

        if self.use_saved.get() and not name and not qty_text:
            saved = load_saved_anchors(ExportPaths(Path(self.output_dir.get())))
            if saved:
                return saved

        if not name:
            raise ExporterError(
                "Enter a card name in Step 2.\n\n"
                'Example: "Island" with copies set to "4"'
            )
        if not qty_text:
            raise ExporterError(
                f'How many copies of "{name}" do you own?\n\nEnter the number in the Copies owned field.'
            )
        try:
            quantity = int(qty_text)
        except ValueError as exc:
            raise ExporterError(f'"{qty_text}" is not a valid number.') from exc
        if quantity <= 0:
            raise ExporterError("Copies owned must be 1 or more.")

        return [Anchor(0, quantity, name)]

    def _start_export(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            anchors = self._collect_anchors()
        except ExporterError as exc:
            messagebox.showerror("Missing info", str(exc))
            return

        self.start_button.configure(state=tk.DISABLED)
        self.progress.configure(value=0)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._append_log("Starting export…")

        def worker() -> None:
            try:
                result = run_export(
                    anchors=anchors,
                    output_dir=self.output_dir.get(),
                    manual_raw_path=self.raw_dir.get().strip() or None,
                    refresh_cache=self.refresh_cache.get(),
                    log=lambda msg: self.log_queue.put(("log", msg)),
                    progress=lambda label, idx, total: self.log_queue.put(("progress", (label, idx, total))),
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
                    label, idx, total = payload  # type: ignore[misc]
                    self.progress.configure(value=(idx / max(total, 1)) * 100)
                    self._append_log(str(label))
                elif kind == "done":
                    self.start_button.configure(state=tk.NORMAL)
                    self.progress.configure(value=100)
                    result = payload
                    self._append_log(
                        f"\n✓ Done — {result.exported_cards} cards exported.\n"
                        f"  Saved to: {self.output_dir.get()}\n"
                        f"\n  Next: go to {DECKFORGE_URL} and paste your mtga_collection.txt"
                    )
                    messagebox.showinfo(
                        "Export complete",
                        f"{result.exported_cards} cards exported.\n\n"
                        f"Files saved to:\n{self.output_dir.get()}\n\n"
                        f"Open mtga_collection.txt, copy the contents,\n"
                        f"and paste it at {DECKFORGE_URL}",
                    )
                    open_output_folder(Path(self.output_dir.get()) / "mtga_collection.txt")
                elif kind == "error":
                    self.start_button.configure(state=tk.NORMAL)
                    self._append_log(f"\n✗ Error: {payload}")
                    messagebox.showerror("Export failed", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)


def main() -> None:
    app = ExporterApp()
    app.mainloop()


if __name__ == "__main__":
    main()

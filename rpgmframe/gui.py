"""RPGMFrame desktop GUI, inspired by RenFrame's lightweight frontend."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from rpgmframe.builder import BuildError
from rpgmframe.gui_support import (
    GuiBuildOutcome,
    InspectionSummary,
    build_for_gui,
    inspect_source_summary,
    output_path_for_source,
)
from rpgmframe.packaging import PackagingError
from rpgmframe.runtime import DEFAULT_NWJS_VERSION
from rpgmframe.source import SourceError


APP_NAME = "RPGMFrame"
APP_TAG = "RPG Maker MV / MZ → Steam Frame (Linux ARM64)"

C_BG = "#07111f"
C_PANEL = "#12233a"
C_PANEL_2 = "#1a3050"
C_BORDER = "#2a4a6a"
C_TEXT = "#f0e6d8"
C_MUTED = "#9eb0c4"
C_ACCENT = "#ff7a45"
C_ACCENT_HOVER = "#ff9466"
C_TEAL = "#3db8a8"
C_OK = "#5ecf8e"
C_ERR = "#ff6b7a"
C_GLOW = "#16304a"

FRAME_INSTRUCTIONS = """Copy the generated .tar.gz to your Steam Frame, then:

mkdir -p ~/Games
tar -xzf GAME-linux-aarch64.tar.gz -C ~/Games
cd ~/Games/GAME-frame
chmod +x launch.sh nw chrome_crashpad_handler 2>/dev/null || true
./launch.sh

RPGMFrame packages a native Linux ARM64 NW.js runtime. The first conversion may
download the pinned runtime; later conversions reuse the local cache.
"""

ctk: Any = None
tk: Any = None
filedialog: Any = None
messagebox: Any = None
DND_FILES: Any = None
TkinterDnD: Any = None
_HAS_DND = False


def _load_gui_dependencies() -> None:
    global ctk, tk, filedialog, messagebox, DND_FILES, TkinterDnD, _HAS_DND

    if ctk is not None:
        return

    try:
        import tkinter as _tk
        from tkinter import filedialog as _filedialog
        from tkinter import messagebox as _messagebox
    except ImportError as exc:
        raise SystemExit(
            "Missing Tk support. Install your platform's Tk package, then retry."
        ) from exc

    try:
        import customtkinter as _ctk
    except ImportError as exc:
        raise SystemExit(
            'Missing GUI dependency: customtkinter\n'
            '  pip install -e ".[gui]"'
        ) from exc

    tk = _tk
    filedialog = _filedialog
    messagebox = _messagebox
    ctk = _ctk

    try:
        from tkinterdnd2 import DND_FILES as _DND_FILES
        from tkinterdnd2 import TkinterDnD as _TkinterDnD

        DND_FILES = _DND_FILES
        TkinterDnD = _TkinterDnD
        _HAS_DND = True
    except ImportError:
        _HAS_DND = False


def _make_root():
    _load_gui_dependencies()
    ctk.set_appearance_mode("dark")

    if _HAS_DND:
        class CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.TkdndVersion = TkinterDnD._require(self)

        root = CTkDnD()
    else:
        root = ctk.CTk()

    root.title(APP_NAME)
    root.geometry("1040x760")
    root.minsize(900, 650)
    root.configure(fg_color=C_BG)
    return root


def _open_path(path: Path) -> None:
    target = path.expanduser().resolve()
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)
    except Exception:
        pass


class ConverterApp:
    def __init__(self) -> None:
        self.root = _make_root()
        self.source: Path | None = None
        self.last_output: Path | None = None
        self.last_archive: Path | None = None
        self.output_dir = Path.home() / "Desktop"
        if not self.output_dir.is_dir():
            self.output_dir = Path.home()

        self._busy = False
        self._inspection_generation = 0
        self.archive_var = tk.BooleanVar(value=True)
        self.force_var = tk.BooleanVar(value=False)
        self.runtime_var = tk.StringVar(value=DEFAULT_NWJS_VERSION)
        self._build_ui()

    def _build_ui(self) -> None:
        ctk.CTkFrame(
            self.root,
            fg_color=C_ACCENT,
            height=4,
            corner_radius=0,
        ).pack(fill="x", side="top")

        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(18, 4))

        ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=f"{APP_TAG}  ·  drop a game, inspect it, build a Frame-ready package",
            font=ctk.CTkFont(size=14),
            text_color=C_MUTED,
        ).pack(anchor="w", pady=(4, 0))

        steps = ctk.CTkFrame(self.root, fg_color=C_GLOW, corner_radius=12)
        steps.pack(fill="x", padx=28, pady=(12, 4))
        ctk.CTkLabel(
            steps,
            text="1  Drop game    →    2  Inspect    →    3  Convert    →    4  Copy archive to Frame",
            font=ctk.CTkFont(size=13),
            text_color=C_TEAL,
        ).pack(padx=16, pady=10)

        self.drop = ctk.CTkFrame(
            self.root,
            fg_color=C_PANEL,
            border_width=2,
            border_color=C_BORDER,
            corner_radius=16,
            height=132,
        )
        self.drop.pack(fill="x", padx=28, pady=12)
        self.drop.pack_propagate(False)

        self.drop_label = ctk.CTkLabel(
            self.drop,
            text="Drop an RPG Maker MV / MZ game folder or .zip here",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=C_TEXT,
        )
        self.drop_label.pack(expand=True, pady=(22, 2))

        self.path_label = ctk.CTkLabel(
            self.drop,
            text="or Browse…  ·  original files stay untouched",
            font=ctk.CTkFont(size=13),
            text_color=C_MUTED,
        )
        self.path_label.pack(pady=(0, 16))

        if _HAS_DND:
            try:
                self.drop.drop_target_register(DND_FILES)
                self.drop.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        controls = ctk.CTkFrame(self.root, fg_color="transparent")
        controls.pack(fill="x", padx=28, pady=(2, 4))

        ctk.CTkButton(
            controls,
            text="Browse…",
            width=120,
            height=42,
            corner_radius=10,
            fg_color=C_PANEL_2,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            command=self._browse,
        ).pack(side="left", padx=(0, 10))

        self.convert_btn = ctk.CTkButton(
            controls,
            text="Convert",
            width=168,
            height=42,
            corner_radius=10,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT_HOVER,
            text_color="#1a0f0a",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_convert,
        )
        self.convert_btn.pack(side="left")

        ctk.CTkButton(
            controls,
            text="Open output",
            width=124,
            height=42,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=C_BORDER,
            hover_color=C_PANEL,
            text_color=C_MUTED,
            command=self._open_output,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            controls,
            text="Output folder…",
            width=132,
            height=42,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=C_BORDER,
            hover_color=C_PANEL,
            text_color=C_MUTED,
            command=self._pick_output,
        ).pack(side="right")

        options = ctk.CTkFrame(self.root, fg_color="transparent")
        options.pack(fill="x", padx=28, pady=(2, 6))

        ctk.CTkCheckBox(
            options,
            text="Create transfer .tar.gz",
            variable=self.archive_var,
            fg_color=C_TEAL,
            hover_color=C_TEAL,
            border_color=C_BORDER,
            text_color=C_MUTED,
        ).pack(side="left")

        ctk.CTkCheckBox(
            options,
            text="Replace existing output",
            variable=self.force_var,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT_HOVER,
            border_color=C_BORDER,
            text_color=C_MUTED,
        ).pack(side="left", padx=(18, 0))

        ctk.CTkLabel(
            options,
            text="NW.js",
            text_color=C_MUTED,
            font=ctk.CTkFont(size=12),
        ).pack(side="right", padx=(8, 4))
        ctk.CTkEntry(
            options,
            width=92,
            height=30,
            textvariable=self.runtime_var,
            fg_color=C_PANEL,
            border_color=C_BORDER,
            text_color=C_TEXT,
        ).pack(side="right")

        self.out_label = ctk.CTkLabel(
            self.root,
            text=f"Output: {self.output_dir}",
            font=ctk.CTkFont(size=12),
            text_color=C_MUTED,
        )
        self.out_label.pack(anchor="e", padx=28)

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=10)

        left = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(
            left,
            text="Progress",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C_TEAL,
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self.log_box = ctk.CTkTextbox(
            left,
            font=ctk.CTkFont(size=13),
            fg_color=C_BG,
            text_color=C_TEXT,
            corner_radius=10,
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        right = ctk.CTkFrame(body, fg_color=C_PANEL, corner_radius=14, width=350)
        right.pack(side="right", fill="both", padx=(10, 0))
        right.pack_propagate(False)

        ctk.CTkLabel(
            right,
            text="Detected game",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C_ACCENT,
        ).pack(anchor="w", padx=14, pady=(14, 8))

        self.game_name_label = ctk.CTkLabel(
            right,
            text="No game selected",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=C_TEXT,
            anchor="w",
            justify="left",
            wraplength=310,
        )
        self.game_name_label.pack(fill="x", padx=14)

        self.engine_label = ctk.CTkLabel(
            right,
            text="Engine: —",
            font=ctk.CTkFont(size=13),
            text_color=C_MUTED,
            anchor="w",
        )
        self.engine_label.pack(fill="x", padx=14, pady=(7, 0))

        self.compat_label = ctk.CTkLabel(
            right,
            text="Compatibility: —",
            font=ctk.CTkFont(size=13),
            text_color=C_MUTED,
            anchor="w",
        )
        self.compat_label.pack(fill="x", padx=14, pady=(2, 10))

        ctk.CTkLabel(
            right,
            text="On the Frame later",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C_TEAL,
        ).pack(anchor="w", padx=14, pady=(4, 4))

        tip = ctk.CTkTextbox(
            right,
            font=ctk.CTkFont(size=12),
            fg_color=C_BG,
            text_color=C_MUTED,
            corner_radius=10,
            wrap="word",
        )
        tip.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        tip.insert("1.0", FRAME_INSTRUCTIONS)
        tip.configure(state="disabled")

        ctk.CTkButton(
            right,
            text="Copy Frame instructions",
            height=32,
            corner_radius=8,
            fg_color=C_PANEL_2,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            command=self._copy_instructions,
        ).pack(fill="x", padx=12, pady=(0, 12))

        self.progress = ctk.CTkProgressBar(
            self.root,
            mode="indeterminate",
            fg_color=C_PANEL,
            progress_color=C_TEAL,
        )
        self.progress.pack(fill="x", padx=28, pady=(0, 6))
        self.progress.stop()

        dnd_note = "" if _HAS_DND else "  ·  drag-drop optional (install tkinterdnd2)"
        self.status = ctk.CTkLabel(
            self.root,
            text="Ready" + dnd_note,
            font=ctk.CTkFont(size=12),
            text_color=C_MUTED,
        )
        self.status.pack(anchor="w", padx=28, pady=(0, 14))

    def _append_log(self, message: str) -> None:
        self.root.after(
            0,
            lambda: (
                self.log_box.insert("end", message + "\n"),
                self.log_box.see("end"),
            ),
        )

    def _set_status(self, message: str, color: str = C_MUTED) -> None:
        self.root.after(
            0,
            lambda: self.status.configure(text=message, text_color=color),
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.convert_btn.configure(state="disabled", text="Working…")
            self.progress.start()
        else:
            self.convert_btn.configure(state="normal", text="Convert")
            self.progress.stop()

    def _set_source(self, path: Path) -> None:
        source = path.expanduser().resolve()
        if not source.exists():
            messagebox.showerror(APP_NAME, f"Path does not exist:\n{source}")
            return
        if source.is_file() and source.suffix.lower() != ".zip":
            messagebox.showinfo(
                APP_NAME,
                "RPGMFrame currently accepts game folders and .zip archives.",
            )
            return

        self.source = source
        self.path_label.configure(text=str(source), text_color=C_TEAL)
        self.drop_label.configure(text="Ready to convert")
        self.drop.configure(border_color=C_TEAL)
        self.game_name_label.configure(text=source.stem if source.is_file() else source.name)
        self.engine_label.configure(text="Engine: inspecting…")
        self.compat_label.configure(text="Compatibility: checking…")
        self._set_status(f"Selected: {source.name}")
        self._start_inspection(source)

    def _start_inspection(self, source: Path) -> None:
        self._inspection_generation += 1
        generation = self._inspection_generation

        def worker() -> None:
            try:
                summary = inspect_source_summary(source)
            except Exception as exc:
                if generation == self._inspection_generation:
                    self.root.after(
                        0,
                        lambda: self._show_inspection_error(str(exc)),
                    )
                return

            if generation == self._inspection_generation:
                self.root.after(
                    0,
                    lambda: self._show_inspection(summary),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_inspection(self, summary: InspectionSummary) -> None:
        if summary.recognized:
            name = summary.game_name or (self.source.name if self.source else "RPG Maker game")
            version = f" {summary.engine_version}" if summary.engine_version else ""
            self.game_name_label.configure(text=name)
            self.engine_label.configure(
                text=f"Engine: RPG Maker {summary.engine.upper()}{version}",
                text_color=C_TEXT,
            )
            self.compat_label.configure(
                text=f"Compatibility: {summary.compatibility}  ·  confidence {summary.confidence}",
                text_color=C_OK if summary.compatibility == "supported" else C_TEAL,
            )
            self._set_status(f"Detected RPG Maker {summary.engine.upper()}", C_TEAL)
            for warning in summary.warnings:
                self._append_log("Inspect: " + warning)
        else:
            self.engine_label.configure(text="Engine: not recognized", text_color=C_ERR)
            self.compat_label.configure(text="Compatibility: unknown", text_color=C_ERR)
            self._set_status("No supported RPG Maker MV/MZ game detected", C_ERR)

    def _show_inspection_error(self, error: str) -> None:
        self.engine_label.configure(text="Engine: inspection failed", text_color=C_ERR)
        self.compat_label.configure(text="Compatibility: unknown", text_color=C_ERR)
        self._set_status("Inspection failed", C_ERR)
        self._append_log("Inspect error: " + error)

    def _on_drop(self, event) -> None:
        try:
            paths = self.root.tk.splitlist(event.data)
            if paths:
                self._set_source(Path(paths[0]))
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select RPG Maker ZIP (Cancel to pick a folder)",
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._set_source(Path(path))
            return

        folder = filedialog.askdirectory(title="Select RPG Maker game folder")
        if folder:
            self._set_source(Path(folder))

    def _pick_output(self) -> None:
        folder = filedialog.askdirectory(
            title="Output folder",
            initialdir=str(self.output_dir),
        )
        if folder:
            self.output_dir = Path(folder)
            self.out_label.configure(text=f"Output: {self.output_dir}")

    def _open_output(self) -> None:
        if self.last_archive and self.last_archive.exists():
            _open_path(self.last_archive.parent)
        elif self.last_output and self.last_output.exists():
            _open_path(self.last_output.parent)
        else:
            _open_path(self.output_dir)

    def _copy_instructions(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(FRAME_INSTRUCTIONS)
        self._set_status("Frame instructions copied", C_TEAL)

    def _start_convert(self) -> None:
        if self._busy:
            return
        if self.source is None:
            messagebox.showinfo(
                APP_NAME,
                "Drop or browse to an RPG Maker game folder or ZIP first.",
            )
            return

        runtime_version = self.runtime_var.get().strip()
        if not runtime_version:
            messagebox.showinfo(APP_NAME, "Enter an NW.js runtime version.")
            return

        source = self.source
        output_dir = self.output_dir
        force = bool(self.force_var.get())
        make_archive = bool(self.archive_var.get())

        self.log_box.delete("1.0", "end")
        self._append_log(f"Source: {source}")
        self._append_log(
            f"Output: {output_path_for_source(source, output_dir)}"
        )
        self._append_log(f"NW.js: {runtime_version}")
        self._set_busy(True)
        self._set_status("Converting…", C_TEAL)

        def worker() -> None:
            try:
                outcome = build_for_gui(
                    source,
                    output_dir=output_dir,
                    runtime_version=runtime_version,
                    force=force,
                    archive=make_archive,
                    progress=self._append_log,
                )
            except (BuildError, PackagingError, SourceError) as exc:
                self.root.after(0, lambda: self._fail(str(exc)))
                return
            except Exception as exc:
                self.root.after(
                    0,
                    lambda: self._fail(f"Unexpected error: {exc}"),
                )
                return

            self.root.after(0, lambda: self._done(outcome))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, outcome: GuiBuildOutcome) -> None:
        result = outcome.build
        self.last_output = result.output_path
        self.last_archive = outcome.archive_path
        self._set_busy(False)

        name = result.game_name or result.output_path.name
        version = f" {result.engine_version}" if result.engine_version else ""
        self.game_name_label.configure(text=name)
        self.engine_label.configure(
            text=f"Engine: RPG Maker {result.engine.value.upper()}{version}",
            text_color=C_TEXT,
        )
        self.compat_label.configure(
            text="Compatibility: build completed",
            text_color=C_OK,
        )

        self._append_log(f"Built: {result.output_path}")
        if outcome.archive_path:
            self._append_log(f"Archive: {outcome.archive_path}")
        for warning in result.warnings:
            self._append_log("Warning: " + warning)

        target = outcome.archive_path or result.output_path
        self._set_status(f"Done → {target}", C_OK)

        archive_line = (
            f"\nTransfer archive:\n{outcome.archive_path}\n"
            if outcome.archive_path
            else ""
        )
        messagebox.showinfo(
            APP_NAME,
            f"Converted {name}.\n\n"
            f"Build directory:\n{result.output_path}\n"
            f"{archive_line}\n"
            "Copy the archive/build to your Frame and run launch.sh.",
        )

    def _fail(self, message: str) -> None:
        self._set_busy(False)
        self._append_log("ERROR: " + message)
        self._set_status("Failed", C_ERR)
        messagebox.showerror(APP_NAME, message)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    ConverterApp().run()


if __name__ == "__main__":
    main()

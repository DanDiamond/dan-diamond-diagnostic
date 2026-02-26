"""YouTube Transcript – macOS desktop app.

A simple Tkinter GUI that wraps the youtube_bot package so non-technical
users can fetch and summarise YouTube transcripts without touching the
Terminal.

Features
--------
* First-launch API key setup (stored in ~/.config/yttranscript/config.json)
* Format selector: Markdown (summarised), Plain, Timestamped, SRT
* Transcripts saved to ~/Transcripts/<video-id>.<ext>
* Indeterminate progress bar during fetch / summary generation
* "Open Transcripts Folder" button on success
* ⚙ Update API Key link in the corner
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import webbrowser
import datetime
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "yttranscript"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRANSCRIPTS_DIR = Path.home() / "Transcripts"

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# API Key setup dialog
# ---------------------------------------------------------------------------


class ApiKeyDialog(tk.Toplevel):
    """Modal dialog for entering / updating the Anthropic API key."""

    def __init__(self, parent: tk.Tk, on_save) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self.title("Setup – Anthropic API Key")
        self.resizable(False, False)
        self.grab_set()  # modal – block main window

        pad = dict(padx=24, pady=6)

        ttk.Label(
            self,
            text=(
                "YouTube Transcript uses the Anthropic API to generate\n"
                "an AI summary of each video."
            ),
            justify="center",
        ).pack(**pad, pady=(20, 4))

        ttk.Label(self, text="Anthropic API Key:").pack(
            anchor="w", padx=24, pady=(8, 2)
        )

        self._key_var = tk.StringVar()
        key_entry = ttk.Entry(self, textvariable=self._key_var, width=48)
        key_entry.pack(padx=24, pady=(0, 4))
        key_entry.focus()

        link = tk.Label(
            self,
            text="Get a free key at console.anthropic.com →",
            fg="#0066cc",
            cursor="hand2",
        )
        link.pack(padx=24, pady=(0, 12))
        link.bind(
            "<Button-1>",
            lambda _: webbrowser.open("https://console.anthropic.com/"),
        )

        note = ttk.Label(
            self,
            text="(You can also skip this – transcripts will be saved without a summary.)",
            foreground="#888",
        )
        note.pack(padx=24, pady=(0, 8))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=24, pady=(4, 20), fill="x")
        ttk.Button(btn_frame, text="Skip for now", command=self.destroy).pack(
            side="left"
        )
        ttk.Button(btn_frame, text="Save & Continue", command=self._save).pack(
            side="right"
        )

    def _save(self) -> None:
        key = self._key_var.get().strip()
        if not key:
            messagebox.showwarning(
                "API Key Required",
                "Please enter your Anthropic API key, or click 'Skip for now'.",
                parent=self,
            )
            return
        self._on_save(key)
        self.destroy()


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------


class App(tk.Tk):
    """Main YouTube Transcript window."""

    FORMAT_LABELS = {
        "Markdown (AI Summary + Full Transcript)": "markdown",
        "Plain text": "plain",
        "Timestamped text": "timestamped",
        "SRT subtitles": "srt",
    }

    def __init__(self) -> None:
        super().__init__()

        self.title("YouTube Transcript")
        self.resizable(False, False)

        # Centre the window on screen
        self.update_idletasks()
        w, h = 540, 360
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._config = load_config()
        self._apply_api_key()
        self._build_ui()

        # Prompt for API key on first launch
        if not self._config.get("api_key"):
            self.after(150, self._prompt_api_key)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _apply_api_key(self) -> None:
        key = self._config.get("api_key", "")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = 20

        # ---- Header ----
        ttk.Label(
            self,
            text="YouTube Transcript",
            font=("System", 18, "bold"),
        ).grid(row=0, column=0, columnspan=2, padx=pad, pady=(20, 2), sticky="w")

        ttk.Label(
            self,
            text="Paste a YouTube URL to fetch and summarise its transcript.",
            foreground="#666",
        ).grid(row=1, column=0, columnspan=2, padx=pad, pady=(0, 14), sticky="w")

        # ---- URL input ----
        ttk.Label(self, text="YouTube URL").grid(
            row=2, column=0, columnspan=2, padx=pad, pady=(0, 2), sticky="w"
        )
        self._url_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._url_var, width=60).grid(
            row=3, column=0, columnspan=2, padx=pad, pady=(0, 14), sticky="ew"
        )

        # ---- Format selector ----
        ttk.Label(self, text="Format").grid(
            row=4, column=0, padx=pad, pady=(0, 2), sticky="w"
        )
        self._fmt_label_var = tk.StringVar(
            value="Markdown (AI Summary + Full Transcript)"
        )
        fmt_combo = ttk.Combobox(
            self,
            textvariable=self._fmt_label_var,
            state="readonly",
            values=list(self.FORMAT_LABELS),
            width=36,
        )
        fmt_combo.grid(row=5, column=0, padx=pad, pady=(0, 18), sticky="w")

        # ---- Fetch button ----
        self._fetch_btn = ttk.Button(
            self, text="Fetch Transcript", command=self._on_fetch
        )
        self._fetch_btn.grid(row=5, column=1, padx=pad, pady=(0, 18), sticky="e")

        # ---- Progress bar ----
        self._progress = ttk.Progressbar(
            self, mode="indeterminate", length=500
        )
        self._progress.grid(
            row=6, column=0, columnspan=2, padx=pad, pady=(0, 8), sticky="ew"
        )

        # ---- Status label ----
        self._status_var = tk.StringVar(value="Ready.")
        self._status_label = ttk.Label(
            self,
            textvariable=self._status_var,
            foreground="#444",
            wraplength=500,
        )
        self._status_label.grid(
            row=7, column=0, columnspan=2, padx=pad, pady=(0, 6), sticky="w"
        )

        # ---- Bottom row: open-folder button + settings link ----
        self._open_btn = ttk.Button(
            self, text="Open Transcripts Folder", command=self._open_folder
        )
        self._open_btn.grid(row=8, column=0, padx=pad, pady=(0, 18), sticky="w")
        self._open_btn.grid_remove()  # hidden until first success

        settings_link = tk.Label(
            self, text="⚙  Update API Key", fg="#0066cc", cursor="hand2"
        )
        settings_link.grid(row=8, column=1, padx=pad, pady=(0, 18), sticky="e")
        settings_link.bind("<Button-1>", lambda _: self._prompt_api_key())

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

    # ------------------------------------------------------------------
    # API key dialog
    # ------------------------------------------------------------------

    def _prompt_api_key(self) -> None:
        def on_save(key: str) -> None:
            self._config["api_key"] = key
            save_config(self._config)
            os.environ["ANTHROPIC_API_KEY"] = key

        ApiKeyDialog(self, on_save)

    # ------------------------------------------------------------------
    # Fetch logic
    # ------------------------------------------------------------------

    def _on_fetch(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning(
                "No URL", "Please paste a YouTube URL into the field above."
            )
            return

        fmt = self.FORMAT_LABELS[self._fmt_label_var.get()]
        self._set_busy(True)
        self._open_btn.grid_remove()
        self._set_status("Fetching transcript…", "#444")

        thread = threading.Thread(
            target=self._fetch_thread, args=(url, fmt), daemon=True
        )
        thread.start()

    def _fetch_thread(self, url: str, fmt: str) -> None:
        try:
            from youtube_bot.formatter import (
                format_markdown,
                format_plain,
                format_srt,
                format_timestamped,
            )
            from youtube_bot.transcript import TranscriptFetcher

            formatters = {
                "plain": format_plain,
                "timestamped": format_timestamped,
                "markdown": format_markdown,
                "srt": format_srt,
            }

            fetcher = TranscriptFetcher()
            transcript = fetcher.fetch(url)

            if fmt == "markdown":
                self.after(
                    0,
                    lambda: self._set_status(
                        "Generating AI summary… (this may take up to 60 seconds)",
                        "#444",
                    ),
                )

            text = formatters[fmt](transcript)

            TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            ext = "srt" if fmt == "srt" else "md"
            date_str = datetime.date.today().strftime("%Y-%m-%d")
            filename = f"{transcript.video_id}_{date_str}.{ext}"
            out_path = TRANSCRIPTS_DIR / filename
            out_path.write_text(text, encoding="utf-8")

            self.after(0, self._on_success, str(out_path))

        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    # ------------------------------------------------------------------
    # Result handlers (called on the main thread via after())
    # ------------------------------------------------------------------

    def _on_success(self, path: str) -> None:
        self._set_busy(False)
        self._set_status(f"Saved to: {path}", "#267326")
        self._open_btn.grid()

    def _on_error(self, msg: str) -> None:
        self._set_busy(False)
        self._set_status(f"Error: {msg}", "#cc0000")

    def _set_status(self, msg: str, color: str) -> None:
        self._status_var.set(msg)
        self._status_label.configure(foreground=color)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self._fetch_btn.configure(state="disabled")
            self._progress.start(10)
        else:
            self._fetch_btn.configure(state="normal")
            self._progress.stop()

    def _open_folder(self) -> None:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(TRANSCRIPTS_DIR)])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

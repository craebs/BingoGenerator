# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Small reusable GUI widgets used by the main CustomTkinter interface.

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from bingo.layout_engine import calculate_layout_metrics
from bingo.models import GameSettings
from bingo.word_utils import normalize_hex


class ToolTip:
    """Small tooltip widget for Tk/CustomTkinter controls."""

    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show(self) -> None:
        if self._tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#FFFDF7",
            foreground="#333333",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=360,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


class LayoutSketch(ctk.CTkFrame):
    """Compact sketch shown on the Layout tab.

    The sketch visualizes margins, title block, intro, grid and footer reserve.
    It is intentionally more abstract than the full preview.
    """

    def __init__(self, master, settings_provider: Callable[[], GameSettings], translator: Callable[[str], str], **kwargs):
        super().__init__(master, **kwargs)
        self.settings_provider = settings_provider
        self.t = translator
        self.canvas = tk.Canvas(self, width=320, height=455, bg="#F2F2F2", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<Configure>", lambda _e: self.draw())

    def draw(self) -> None:
        self.canvas.delete("all")
        try:
            s = self.settings_provider()
            metrics = calculate_layout_metrics(s)
        except Exception:
            return

        cw = max(240, self.canvas.winfo_width())
        ch = max(340, self.canvas.winfo_height())
        pad = 18
        page_ratio = s.page_height_inch / s.page_width_inch
        page_w = min(cw - pad * 2, int((ch - pad * 2) / page_ratio))
        page_h = int(page_w * page_ratio)
        x0 = (cw - page_w) // 2
        y0 = (ch - page_h) // 2
        scale = page_w / s.page_width_inch

        self.canvas.create_rectangle(x0 + 5, y0 + 5, x0 + page_w + 5, y0 + page_h + 5, fill="#D8D8D8", outline="")
        self.canvas.create_rectangle(x0, y0, x0 + page_w, y0 + page_h, fill="white", outline="#CFCFCF")

        ml = int(s.margins.left * scale)
        mr = int(s.margins.right * scale)
        mt = int(s.margins.top * scale)
        mb = int(s.margins.bottom * scale)
        self.canvas.create_rectangle(x0 + ml, y0 + mt, x0 + page_w - mr, y0 + page_h - mb, outline="#E4BFAE", dash=(4, 3))
        self.canvas.create_text(x0 + ml + 5, y0 + mt + 10, text=self.t("sketch.margin"), anchor="w", fill="#A36B5C", font=("Arial", 9))

        header_top = y0 + mt
        header_h = int(metrics.header_height * scale)
        self.canvas.create_rectangle(x0 + ml, header_top, x0 + page_w - mr, header_top + header_h, fill="#F9F3EE", outline="#E8D6CE")

        cx = x0 + page_w // 2
        yy = header_top + 20
        for label, fill in [
            (self.t("sketch.title"), "#96B4AF"),
            (self.t("sketch.subtitle"), "#B5958B"),
            (self.t("sketch.date"), "#B5958B"),
        ]:
            self.canvas.create_text(cx, yy, text=label, fill=fill, font=("Arial", 9, "bold" if label == self.t("sketch.title") else "normal"))
            yy += 18

        intro_y = y0 + int(metrics.intro_top * scale)
        intro_h = max(10, int(metrics.intro_height * scale))
        self.canvas.create_rectangle(x0 + ml, intro_y, x0 + page_w - mr, intro_y + intro_h, fill="#FFFDFB", outline="#EADFD7")
        self.canvas.create_text(cx, intro_y + intro_h / 2, text=self.t("sketch.intro"), fill="#594E4A", font=("Arial", 9))

        # Corner images as small placeholders.
        self.canvas.create_oval(x0 + ml + 4, y0 + mt + 4, x0 + ml + 38, y0 + mt + 38, outline="#92B19A")
        self.canvas.create_oval(x0 + page_w - mr - 38, y0 + mt + 4, x0 + page_w - mr - 4, y0 + mt + 38, outline="#92B19A")

        grid_x = x0 + int(metrics.grid_left * scale)
        grid_y = y0 + int(metrics.grid_top * scale)
        cell = int(metrics.grid_size * scale)
        for r in range(s.rows):
            for c in range(s.cols):
                fill = f"#{normalize_hex(s.cell_bg_dark if (r + c) % 2 else s.cell_bg_light)}"
                self.canvas.create_rectangle(
                    grid_x + c * cell,
                    grid_y + r * cell,
                    grid_x + (c + 1) * cell,
                    grid_y + (r + 1) * cell,
                    fill=fill,
                    outline=f"#{normalize_hex(s.grid_border_color)}",
                )
        self.canvas.create_text(grid_x + cell * s.cols / 2, grid_y + cell * s.rows / 2, text=self.t("sketch.grid"), fill="#8E7D74", font=("Arial", 10, "bold"))

        footer_y = y0 + page_h - mb - int(metrics.footer_reserved_height * scale)
        self.canvas.create_rectangle(x0 + ml, footer_y, x0 + page_w - mr, y0 + page_h - mb, fill="#F8FBF8", outline="#DDEADD")
        self.canvas.create_text(cx, footer_y + 14, text=self.t("sketch.footer"), fill="#7FA185", font=("Arial", 9))
        self.canvas.create_oval(x0 + ml + 4, y0 + page_h - mb - 38, x0 + ml + 38, y0 + page_h - mb - 4, outline="#92B19A")
        self.canvas.create_oval(x0 + page_w - mr - 38, y0 + page_h - mb - 38, x0 + page_w - mr - 4, y0 + page_h - mb - 4, outline="#92B19A")

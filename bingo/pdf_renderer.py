# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Native PDF renderer. This avoids external office suites for PDF export by
# drawing the page directly with ReportLab. It shares the same layout metrics as
# the DOCX renderer, so grid position, margins and image placement stay aligned.

from __future__ import annotations

from pathlib import Path
import re

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import portrait
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .layout_engine import calculate_layout_metrics
from .models import CornerImage, GameSettings
from .word_utils import normalize_hex

try:  # Optional helper used to locate installed font files by family name.
    from matplotlib import font_manager as mpl_font_manager
except Exception:  # pragma: no cover - preview/export still works with Helvetica
    mpl_font_manager = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POINTS_PER_INCH = 72.0


class PdfBingoRenderer:
    """Render Bingo cards directly into a PDF file."""

    def __init__(self, settings: GameSettings):
        self.settings = settings
        self.metrics = calculate_layout_metrics(settings)
        self._registered_fonts: dict[tuple[str, bool, bool], str] = {}

    def render(self, cards: list[list[str]], output_path: str | Path | None = None) -> Path:
        """Create and save the PDF document."""
        output = Path(output_path or self.settings.output_path).with_suffix(".pdf")
        output.parent.mkdir(parents=True, exist_ok=True)

        page_size = portrait((self.settings.page_width_inch * POINTS_PER_INCH, self.settings.page_height_inch * POINTS_PER_INCH))
        pdf = canvas.Canvas(str(output), pagesize=page_size)
        for index, card in enumerate(cards):
            self._draw_page(pdf, card)
            if index < len(cards) - 1:
                pdf.showPage()
        pdf.save()
        return output

    def _draw_page(self, pdf: canvas.Canvas, card_items: list[str]) -> None:
        """Draw a single Bingo card page."""
        width_pt = self.settings.page_width_inch * POINTS_PER_INCH
        height_pt = self.settings.page_height_inch * POINTS_PER_INCH
        scale = POINTS_PER_INCH

        # White page background. PDF pages are white by default, but drawing the
        # rectangle makes this explicit and mirrors the preview.
        pdf.setFillColor(HexColor("#FFFFFF"))
        pdf.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)

        # Corner images are anchored to the printable margin corners.
        self._draw_corner_image(pdf, self.settings.top_left_image, self.settings.margins.left * scale, height_pt - self.settings.margins.top * scale, "tl")
        self._draw_corner_image(pdf, self.settings.top_right_image, width_pt - self.settings.margins.right * scale, height_pt - self.settings.margins.top * scale, "tr")
        self._draw_corner_image(pdf, self.settings.bottom_left_image, self.settings.margins.left * scale, self.settings.margins.bottom * scale, "bl")
        self._draw_corner_image(pdf, self.settings.bottom_right_image, width_pt - self.settings.margins.right * scale, self.settings.margins.bottom * scale, "br")

        self._draw_header_text(pdf, width_pt, height_pt)
        self._draw_intro(pdf, height_pt)
        self._draw_grid(pdf, card_items, height_pt)

    def _draw_header_text(self, pdf: canvas.Canvas, width_pt: float, height_pt: float) -> None:
        """Draw title, subtitle and date centered in the header area."""
        y = height_pt - (self.settings.margins.top * POINTS_PER_INCH + self.settings.title_top_spacing_pt)
        y = self._centered_text(pdf, self.settings.title, width_pt / 2, y, self.settings.title_font, self.settings.title_size_pt, self.settings.title_color, bold=True)
        y -= 2
        y = self._centered_text(pdf, self.settings.subtitle, width_pt / 2, y, self.settings.subtitle_font, self.settings.subtitle_size_pt, self.settings.subtitle_color)
        y = self._centered_text(pdf, self.settings.date, width_pt / 2, y, self.settings.date_font, self.settings.date_size_pt, self.settings.date_color)

    def _draw_intro(self, pdf: canvas.Canvas, height_pt: float) -> None:
        """Draw the intro sentence immediately above the grid."""
        if not self.settings.intro_text.strip():
            return
        font_name = self._font_name(self.settings.intro_font, bold=True)
        font_size = self.settings.intro_size_pt
        pdf.setFont(font_name, font_size)
        pdf.setFillColor(HexColor(f"#{normalize_hex(self.settings.intro_color)}"))
        grid_x = self.metrics.grid_left * POINTS_PER_INCH
        grid_w = self.metrics.grid_width * POINTS_PER_INCH
        # Draw the baseline just above the grid. This removes the visual blank
        # line without allowing descenders to touch the top grid border.
        y = height_pt - self.metrics.grid_top * POINTS_PER_INCH + max(5.0, font_size * 0.50)
        text_width = pdf.stringWidth(self.settings.intro_text, font_name, font_size)
        if self.settings.intro_alignment == "left":
            x = grid_x
        elif self.settings.intro_alignment == "right":
            x = grid_x + grid_w - text_width
        else:
            x = grid_x + (grid_w - text_width) / 2
        pdf.drawString(x, y, self.settings.intro_text)

    def _draw_grid(self, pdf: canvas.Canvas, card_items: list[str], height_pt: float) -> None:
        """Draw square cells and wrapped question text."""
        cell_pt = self.metrics.grid_size * POINTS_PER_INCH
        grid_x = self.metrics.grid_left * POINTS_PER_INCH
        grid_top = self.metrics.grid_top * POINTS_PER_INCH
        grid_y_top = height_pt - grid_top
        border_width = max(0.1, self.settings.grid_border_width_pt)

        cell_font = self._font_name(self.settings.cell_font)
        for row in range(self.settings.rows):
            for col in range(self.settings.cols):
                x = grid_x + col * cell_pt
                y = grid_y_top - (row + 1) * cell_pt
                fill = self.settings.cell_bg_dark if (row + col) % 2 else self.settings.cell_bg_light
                pdf.setFillColor(HexColor(f"#{normalize_hex(fill)}"))
                pdf.setStrokeColor(HexColor(f"#{normalize_hex(self.settings.grid_border_color)}"))
                pdf.setLineWidth(border_width)
                pdf.rect(x, y, cell_pt, cell_pt, stroke=1, fill=1)

                index = row * self.settings.cols + col
                text = card_items[index] if index < len(card_items) else ""
                self._draw_cell_text(pdf, text, x, y, cell_pt, cell_font)

    def _draw_cell_text(self, pdf: canvas.Canvas, text: str, x: float, y: float, size: float, font_name: str) -> None:
        """Draw wrapped, centered text inside one cell."""
        if not text:
            return
        padding = max(4.0, self.settings.cell_padding_twips / 20.0)
        max_width = max(1.0, size - 2 * padding)
        font_size = self.settings.cell_font_size_pt
        pdf.setFont(font_name, font_size)
        pdf.setFillColor(HexColor(f"#{normalize_hex(self.settings.cell_text_color)}"))

        lines = self._wrap_text(pdf, text, font_name, font_size, max_width)
        line_height = font_size * 1.12
        max_lines = max(1, int((size - 2 * padding) // line_height))
        lines = lines[:max_lines]
        total_height = len(lines) * line_height
        text_y = y + (size - total_height) / 2 + (len(lines) - 1) * line_height + font_size * 0.20
        for line in lines:
            text_width = pdf.stringWidth(line, font_name, font_size)
            pdf.drawString(x + (size - text_width) / 2, text_y, line)
            text_y -= line_height

    @staticmethod
    def _wrap_text(pdf: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
        """Wrap text to a maximum width using ReportLab font metrics."""
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdf.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _centered_text(self, pdf: canvas.Canvas, text: str, x_center: float, baseline_y: float, family: str, size: float, color: str, bold: bool = False) -> float:
        """Draw one centered text line and return the next baseline position."""
        if not text:
            return baseline_y
        font_name = self._font_name(family, bold=bold)
        pdf.setFont(font_name, size)
        pdf.setFillColor(HexColor(f"#{normalize_hex(color)}"))
        text_width = pdf.stringWidth(text, font_name, size)
        pdf.drawString(x_center - text_width / 2, baseline_y - size, text)
        return baseline_y - size * 1.12

    def _font_name(self, family: str, bold: bool = False, italic: bool = False) -> str:
        """Return a ReportLab font name, registering a TTF if possible."""
        key = (family, bold, italic)
        if key in self._registered_fonts:
            return self._registered_fonts[key]

        if mpl_font_manager is not None and family:
            try:
                prop = mpl_font_manager.FontProperties(
                    family=family,
                    weight="bold" if bold else "normal",
                    style="italic" if italic else "normal",
                )
                path = mpl_font_manager.findfont(prop, fallback_to_default=True)
                safe_name = "Bingo_" + re.sub(r"[^A-Za-z0-9]+", "_", f"{family}_{'b' if bold else 'r'}_{'i' if italic else 'n'}")
                if safe_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(safe_name, path))
                self._registered_fonts[key] = safe_name
                return safe_name
            except Exception:
                pass

        fallback = "Helvetica-Bold" if bold else "Helvetica"
        self._registered_fonts[key] = fallback
        return fallback

    def _resolve_image_path(self, image: CornerImage) -> Path | None:
        """Resolve an absolute or project-relative image path."""
        if not image.path:
            return None
        raw = Path(image.path)
        candidates = [raw]
        if not raw.is_absolute():
            candidates.append(PROJECT_ROOT / raw)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _image_size_points(self, image: CornerImage) -> tuple[float, float] | None:
        """Return rendered image width and height in PDF points."""
        path = self._resolve_image_path(image)
        if not path:
            return None
        try:
            with Image.open(path) as im:
                width = image.width_inch * POINTS_PER_INCH
                height = width * im.height / max(1, im.width)
                return width, height
        except OSError:
            return None

    def _draw_corner_image(self, pdf: canvas.Canvas, image: CornerImage, x_anchor: float, y_anchor: float, anchor: str) -> None:
        """Draw a corner image with a given anchor."""
        path = self._resolve_image_path(image)
        size = self._image_size_points(image)
        if not path or not size:
            return
        width, height = size
        if anchor == "tl":
            x, y = x_anchor, y_anchor - height
        elif anchor == "tr":
            x, y = x_anchor - width, y_anchor - height
        elif anchor == "bl":
            x, y = x_anchor, y_anchor
        else:
            x, y = x_anchor - width, y_anchor
        pdf.drawImage(ImageReader(str(path)), x, y, width=width, height=height, mask="auto")

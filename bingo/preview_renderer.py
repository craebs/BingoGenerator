# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Fast visual preview renderer. This is not a DOCX renderer, but it uses the
# same layout metrics as the Word export to provide a reliable approximation.

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .layout_engine import calculate_layout_metrics
from .models import CornerImage, GameSettings
from .word_utils import normalize_hex

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:  # Matplotlib is optional and helps locate real system font files for preview rendering.
    from matplotlib import font_manager as mpl_font_manager
except Exception:  # pragma: no cover - optional convenience import
    mpl_font_manager = None


class PreviewRenderer:
    def __init__(self, settings: GameSettings):
        self.settings = settings
        self.metrics = calculate_layout_metrics(settings)
        self._font_cache: dict[tuple[str, int, bool, bool], ImageFont.ImageFont] = {}

    def render(self, sample_card: list[str] | None = None, width_px: int = 794) -> Image.Image:
        ratio = self.settings.page_height_inch / self.settings.page_width_inch
        page_w = width_px
        page_h = int(width_px * ratio)
        scale = page_w / self.settings.page_width_inch

        # UI background plus a real white page in the middle.
        canvas_pad = max(18, int(width_px * 0.035))
        canvas = Image.new("RGB", (page_w + canvas_pad * 2, page_h + canvas_pad * 2), "#EDEDED")
        img = Image.new("RGBA", (page_w, page_h), "white")
        draw = ImageDraw.Draw(img)

        m_left = int(self.settings.margins.left * scale)
        m_right = int(self.settings.margins.right * scale)
        m_top = int(self.settings.margins.top * scale)
        m_bottom = int(self.settings.margins.bottom * scale)

        # Printable area / margins as a guide line.
        draw.rectangle(
            [m_left, m_top, page_w - m_right, page_h - m_bottom],
            outline="#E6D8CF",
            width=1,
        )

        self._draw_corner_image(draw, img, self.settings.top_left_image, m_left, m_top, scale, anchor="tl")
        self._draw_corner_image(draw, img, self.settings.top_right_image, page_w - m_right, m_top, scale, anchor="tr")
        self._draw_corner_image(draw, img, self.settings.bottom_left_image, m_left, page_h - m_bottom, scale, anchor="bl")
        self._draw_corner_image(draw, img, self.settings.bottom_right_image, page_w - m_right, page_h - m_bottom, scale, anchor="br")

        title_font = self._font(self.settings.title_font, self.settings.title_size_pt, scale, bold=True)
        sub_font = self._font(self.settings.subtitle_font, self.settings.subtitle_size_pt, scale)
        date_font = self._font(self.settings.date_font, self.settings.date_size_pt, scale)
        intro_font = self._font(self.settings.intro_font, self.settings.intro_size_pt, scale, bold=True)
        cell_font = self._font(self.settings.cell_font, self.settings.cell_font_size_pt, scale)

        # Top title block, separated from the intro sentence.
        y = m_top + int(self.settings.title_top_spacing_pt * scale / 72)
        self._centered_text(draw, self.settings.title, page_w // 2, y, title_font, self.settings.title_color)
        y += self._line_height(draw, title_font) + max(1, int(2 * scale / 72))
        self._centered_text(draw, self.settings.subtitle, page_w // 2, y, sub_font, self.settings.subtitle_color)
        y += self._line_height(draw, sub_font)
        self._centered_text(draw, self.settings.date, page_w // 2, y, date_font, self.settings.date_color)

        cell_size = int(self.metrics.grid_size * scale)
        grid_x = int(self.metrics.grid_left * scale)
        grid_y = int(self.metrics.grid_top * scale)
        grid_w = int(self.metrics.grid_width * scale)
        intro_y = int(self.metrics.intro_top * scale)

        self._aligned_text(
            draw,
            self.settings.intro_text,
            grid_x,
            intro_y,
            grid_w,
            intro_font,
            self.settings.intro_color,
            self.settings.intro_alignment,
        )

        sample_card = sample_card or [f"Frage {i + 1}" for i in range(self.settings.grid_cells)]
        border_width = max(1, int(round(self.settings.grid_border_width_pt * scale / 72 * 5)))
        for r in range(self.settings.rows):
            for c in range(self.settings.cols):
                x1 = grid_x + c * cell_size
                y1 = grid_y + r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                bg = self.settings.cell_bg_dark if (r + c) % 2 else self.settings.cell_bg_light
                draw.rectangle(
                    [x1, y1, x2, y2],
                    fill=f"#{normalize_hex(bg)}",
                    outline=f"#{normalize_hex(self.settings.grid_border_color)}",
                    width=border_width,
                )
                text = sample_card[r * self.settings.cols + c] if r * self.settings.cols + c < len(sample_card) else ""
                pad = max(4, int(0.06 * cell_size))
                self._draw_wrapped_centered(
                    draw,
                    text,
                    (x1 + pad, y1 + pad, x2 - pad, y2 - pad),
                    cell_font,
                    self.settings.cell_text_color,
                )

        # Page shadow and outline.
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rectangle([4, 4, page_w - 1, page_h - 1], fill=(0, 0, 0, 26))
        canvas.paste(shadow, (canvas_pad + 5, canvas_pad + 5), shadow)
        canvas.paste(img, (canvas_pad, canvas_pad), img)
        outline = ImageDraw.Draw(canvas)
        outline.rectangle([canvas_pad, canvas_pad, canvas_pad + page_w, canvas_pad + page_h], outline="#D7D7D7", width=1)
        return canvas

    def _font(self, family: str, size_pt: float, scale: float, bold: bool = False, italic: bool = False) -> ImageFont.ImageFont:
        """Load the selected system font when possible.

        Word and Tk use font families, while PIL needs a concrete font file.
        matplotlib.font_manager usually finds a matching file on Windows, macOS
        and Linux. If that fails, the preview falls back to DejaVu/Liberation.
        """
        size_px = max(7, int(size_pt * scale / 72))
        key = (family, size_px, bold, italic)
        if key in self._font_cache:
            return self._font_cache[key]

        candidates: list[str] = []
        if mpl_font_manager is not None and family:
            try:
                prop = mpl_font_manager.FontProperties(
                    family=family,
                    weight="bold" if bold else "normal",
                    style="italic" if italic else "normal",
                )
                candidates.append(mpl_font_manager.findfont(prop, fallback_to_default=True))
            except Exception:
                pass

        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "arial.ttf",
        ])
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size_px)
                self._font_cache[key] = font
                return font
            except OSError:
                continue
        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    @staticmethod
    def _line_height(draw: ImageDraw.ImageDraw, font) -> int:
        bbox = draw.textbbox((0, 0), "Hg", font=font)
        return max(8, bbox[3] - bbox[1] + 2)

    def _centered_text(self, draw: ImageDraw.ImageDraw, text: str, cx: int, y: int, font, color: str) -> None:
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text((cx - (bbox[2] - bbox[0]) / 2, y), text, fill=f"#{normalize_hex(color)}", font=font)

    def _aligned_text(self, draw: ImageDraw.ImageDraw, text: str, x: int, y: int, width: int, font, color: str, alignment: str) -> None:
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        if alignment == "left":
            tx = x
        elif alignment == "right":
            tx = x + width - text_w
        else:
            tx = x + (width - text_w) / 2
        draw.text((tx, y), text, fill=f"#{normalize_hex(color)}", font=font)

    def _draw_wrapped_centered(self, draw: ImageDraw.ImageDraw, text: str, box, font, color: str) -> None:
        x1, y1, x2, y2 = box
        max_width = max(1, x2 - x1)
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if not lines:
            return

        line_height = self._line_height(draw, font)
        max_lines = max(1, int((y2 - y1) // line_height))
        lines = lines[:max_lines]
        total_h = line_height * len(lines)
        y = y1 + ((y2 - y1) - total_h) / 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = x1 + (max_width - (bbox[2] - bbox[0])) / 2
            draw.text((x, y), line, fill=f"#{normalize_hex(color)}", font=font)
            y += line_height

    def _resolve_path(self, corner: CornerImage) -> Path | None:
        if not corner.path:
            return None
        raw = Path(corner.path)
        candidates = [raw]
        if not raw.is_absolute():
            candidates.append(PROJECT_ROOT / raw)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _draw_corner_image(self, draw, canvas: Image.Image, corner: CornerImage, x: int, y: int, scale: float, anchor: str) -> None:
        path = self._resolve_path(corner)
        if not path:
            return
        try:
            pic = Image.open(path).convert("RGBA")
        except OSError:
            return
        target_w = max(1, int(corner.width_inch * scale))
        ratio = target_w / pic.width
        target_h = max(1, int(pic.height * ratio))
        pic = pic.resize((target_w, target_h), Image.Resampling.LANCZOS)

        if anchor == "tl":
            pos = (x, y)
        elif anchor == "tr":
            pos = (x - target_w, y)
        elif anchor == "bl":
            pos = (x, y - target_h)
        else:  # br
            pos = (x - target_w, y - target_h)
        canvas.alpha_composite(pic, dest=pos)

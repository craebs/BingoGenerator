# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Shared layout calculations for Word export and preview rendering. Keeping all
# measurements in one place is important: otherwise the preview and DOCX export
# would drift apart quickly.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .models import GameSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class LayoutMetrics:
    """Calculated layout values in inches."""

    usable_width: float
    usable_height: float
    header_height: float
    intro_height: float
    footer_reserved_height: float
    grid_size: float
    grid_width: float
    grid_height: float
    grid_left: float
    grid_top: float
    intro_top: float


def resolve_project_path(path: str) -> Path | None:
    """Resolve absolute paths and paths relative to the project root."""
    if not path:
        return None
    raw = Path(path)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.append(PROJECT_ROOT / raw)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _image_height_inch(path: str, width_inch: float) -> float:
    """Estimate an image height in inches when inserted with a fixed width."""
    resolved = resolve_project_path(path)
    if not resolved:
        return 0.0
    try:
        with Image.open(resolved) as im:
            if im.width <= 0:
                return 0.0
            return max(0.0, width_inch * im.height / im.width)
    except OSError:
        return 0.0


def estimate_header_height(settings: GameSettings) -> float:
    """Estimate the title block height, excluding the intro sentence.

    The previous version used a conservative fixed minimum that pushed the grid
    too far down. The current formula tracks the actual font sizes and corner
    image height more closely, so the grid can stay visually centered.
    """
    title_block = (
        settings.title_top_spacing_pt / 72.0
        + settings.title_size_pt / 72.0 * 1.10
        + settings.subtitle_size_pt / 72.0 * 1.06
        + settings.date_size_pt / 72.0 * 1.06
        + 0.06
    )
    image_block = max(
        _image_height_inch(settings.top_left_image.path, settings.top_left_image.width_inch),
        _image_height_inch(settings.top_right_image.path, settings.top_right_image.width_inch),
    )
    return max(title_block, image_block, 1.85)


def estimate_intro_height(settings: GameSettings) -> float:
    """Estimate the height of the intro line directly above the grid."""
    if not settings.intro_text.strip():
        return 0.0
    return max(settings.intro_size_pt / 72.0 * 1.20, 0.20)


def estimate_footer_reserved_height(settings: GameSettings) -> float:
    """Reserve enough space for the bottom corner images in the footer.

    This does not insert anything into the document flow. It only helps the grid
    avoid colliding with footer graphics on printers with non-printable areas.
    """
    image_block = max(
        _image_height_inch(settings.bottom_left_image.path, settings.bottom_left_image.width_inch),
        _image_height_inch(settings.bottom_right_image.path, settings.bottom_right_image.width_inch),
    )
    return max(settings.margins.footer_distance + 0.12, image_block + 0.06, 0.30)


def calculate_layout_metrics(settings: GameSettings) -> LayoutMetrics:
    """Calculate grid size and position.

    Rules implemented here:
    - The grid is always horizontally centered on the physical page area between
      the left and right margins.
    - The intro sentence is immediately above the grid.
    - The title block is independent from the intro sentence.
    - The grid is vertically balanced between the title area and the footer area.
    - The cell size is dynamic and shrinks automatically when the page would not
      fit, even when the user has disabled auto-size.
    """
    usable_width = max(0.1, settings.page_width_inch - settings.margins.left - settings.margins.right)
    usable_height = max(0.1, settings.page_height_inch - settings.margins.top - settings.margins.bottom)
    header_height = estimate_header_height(settings)
    intro_height = estimate_intro_height(settings)
    footer_reserved = estimate_footer_reserved_height(settings)

    intro_gap = max(0.0, settings.grid_top_gap_inch)
    above_grid_reserved = header_height + intro_height + intro_gap

    max_by_width = usable_width / max(settings.cols, 1)
    max_by_height = max(0.25, (usable_height - above_grid_reserved - footer_reserved) / max(settings.rows, 1))
    dynamic_size = max(0.25, min(max_by_width, max_by_height) * 0.985)

    # auto_cell_size=False means "try to use the user value", but we still
    # shrink it if the document would otherwise overflow.
    cell_size = dynamic_size if settings.auto_cell_size else min(settings.cell_size_inch, dynamic_size)
    if settings.auto_cell_size:
        cell_size = min(settings.cell_size_inch, dynamic_size)

    grid_width = cell_size * settings.cols
    grid_height = cell_size * settings.rows
    grid_left = settings.margins.left + (usable_width - grid_width) / 2.0

    # Center the grid itself in the printable vertical area. The header, intro
    # and footer still act as collision constraints, but they no longer pull the
    # grid down. This makes small and large matrices feel centered on the page.
    grid_top_ideal = settings.margins.top + max(0.0, (usable_height - grid_height) / 2.0)

    min_grid_top = settings.margins.top + header_height + intro_height + intro_gap
    max_grid_top = max(min_grid_top, settings.page_height_inch - settings.margins.bottom - footer_reserved - grid_height)
    grid_top = min(max(grid_top_ideal, min_grid_top), max_grid_top)

    intro_top = grid_top - intro_height - intro_gap

    return LayoutMetrics(
        usable_width=usable_width,
        usable_height=usable_height,
        header_height=header_height,
        intro_height=intro_height,
        footer_reserved_height=footer_reserved,
        grid_size=cell_size,
        grid_width=grid_width,
        grid_height=grid_height,
        grid_left=grid_left,
        grid_top=grid_top,
        intro_top=intro_top,
    )

# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# This file contains the persistent data models used by the application.
# All values that should survive a restart are represented here and serialized
# to JSON by bingo/config_io.py.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class CategoryConfig:
    """Question category plus card-generation limits.

    A category can be used in three different ways:
    - min_per_card > 0 forces at least that many questions per card.
    - max_per_card limits the category on each card; None means no limit.
    - use_as_filler lets the generator use this category to fill remaining cells.
    """

    name: str
    questions: list[str] = field(default_factory=list)
    min_per_card: int = 0
    max_per_card: Optional[int] = None
    use_as_filler: bool = True
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CategoryConfig":
        """Create a category from JSON-safe data."""
        return cls(
            name=str(data.get("name", "New Category")),
            questions=[str(q).strip() for q in data.get("questions", []) if str(q).strip()],
            min_per_card=int(data.get("min_per_card", 0) or 0),
            max_per_card=(None if data.get("max_per_card") in (None, "") else int(data.get("max_per_card"))),
            use_as_filler=bool(data.get("use_as_filler", True)),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)

    def validate(self, grid_cells: int) -> None:
        """Validate settings that can make card generation impossible."""
        if not self.name.strip():
            raise ValueError("A category has no name.")
        if self.min_per_card < 0:
            raise ValueError(f"Category '{self.name}': minimum cannot be negative.")
        if self.max_per_card is not None and self.max_per_card < self.min_per_card:
            raise ValueError(f"Category '{self.name}': maximum is smaller than minimum.")
        if self.min_per_card > len(self.questions):
            raise ValueError(
                f"Category '{self.name}': minimum {self.min_per_card} is larger than the number of questions ({len(self.questions)})."
            )
        if self.min_per_card > grid_cells:
            raise ValueError(f"Category '{self.name}': minimum does not fit into the grid.")


@dataclass
class CornerImage:
    """Image placed in one corner of the page.

    The image path can be absolute or relative to the project root. The width is
    stored in inches because python-docx works nicely with inch-based image sizes.
    """

    path: str = ""
    width_inch: float = 1.25

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CornerImage":
        if not data:
            return cls()
        return cls(path=str(data.get("path", "")), width_inch=float(data.get("width_inch", 1.25) or 1.25))


@dataclass
class PageMargins:
    """Printable page margins in inches."""

    top: float = 0.35
    bottom: float = 0.45
    left: float = 0.45
    right: float = 0.45
    footer_distance: float = 0.35

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PageMargins":
        if not data:
            return cls()
        return cls(
            top=float(data.get("top", 0.35)),
            bottom=float(data.get("bottom", 0.45)),
            left=float(data.get("left", 0.45)),
            right=float(data.get("right", 0.45)),
            footer_distance=float(data.get("footer_distance", 0.35)),
        )


@dataclass
class GameSettings:
    """Central settings for game generation, layout, preview and export."""

    # GUI / language
    language: str = "de"

    # Game parameters
    rows: int = 5
    cols: int = 5
    number_of_cards: int = 80
    random_seed: Optional[int] = None

    # Header and intro text
    title: str = "Bingo Generator"
    subtitle: str = "Braut ❤ Bräutigam"
    date: str = "04.07.2026"
    intro_text: str = "Finde jemanden, der oder die ..."
    intro_alignment: str = "center"  # left | center | right

    # Fonts and sizes
    title_font: str = "Brush Script MT"
    subtitle_font: str = "Calibri"
    date_font: str = "Calibri"
    intro_font: str = "Calibri"
    cell_font: str = "Calibri"
    title_size_pt: float = 36
    subtitle_size_pt: float = 15
    date_size_pt: float = 14
    intro_size_pt: float = 12
    cell_font_size_pt: float = 8

    # Colors as hex strings, with or without '#'
    title_color: str = "96B4AF"
    subtitle_color: str = "B5958B"
    date_color: str = "B5958B"
    intro_color: str = "594E4A"
    cell_text_color: str = "594E4A"
    grid_border_color: str = "F2D6C4"
    cell_bg_light: str = "FFFDFB"
    cell_bg_dark: str = "FAF0E6"

    # Page and grid
    page_width_inch: float = 8.27
    page_height_inch: float = 11.69
    margins: PageMargins = field(default_factory=PageMargins)
    auto_cell_size: bool = True
    cell_size_inch: float = 1.25
    cell_padding_twips: int = 100
    title_top_spacing_pt: float = 22
    grid_top_gap_inch: float = 0.0
    grid_border_width_pt: float = 1.0

    # Corner images
    top_left_image: CornerImage = field(default_factory=lambda: CornerImage(path="assets/corners/eucalyptus_top_left.png", width_inch=1.25))
    top_right_image: CornerImage = field(default_factory=lambda: CornerImage(path="assets/corners/eucalyptus_top_right.png", width_inch=1.25))
    bottom_left_image: CornerImage = field(default_factory=lambda: CornerImage(path="assets/corners/eucalyptus_bottom_left.png", width_inch=1.25))
    bottom_right_image: CornerImage = field(default_factory=lambda: CornerImage(path="assets/corners/eucalyptus_bottom_right.png", width_inch=1.25))

    # Export
    output_path: str = "bingo_cards.docx"
    output_format: str = "docx"  # docx | pdf

    @property
    def grid_cells(self) -> int:
        return self.rows * self.cols

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSettings":
        """Create settings from JSON-safe data with backward compatibility."""
        raw_subtitle = str(data.get("subtitle", "Braut ❤ Bräutigam"))
        if "date" in data:
            subtitle = raw_subtitle
            date = str(data.get("date", "04.07.2026"))
        else:
            lines = [line.strip() for line in raw_subtitle.splitlines() if line.strip()]
            subtitle = lines[0] if lines else "Braut ❤ Bräutigam"
            date = lines[1] if len(lines) > 1 else "04.07.2026"

        output_path = str(data.get("output_path", "bingo_cards.docx"))
        inferred_format = "pdf" if output_path.lower().endswith(".pdf") else "docx"
        default = cls()

        return cls(
            language=str(data.get("language", "de")),
            rows=int(data.get("rows", 5)),
            cols=int(data.get("cols", 5)),
            number_of_cards=int(data.get("number_of_cards", 80)),
            random_seed=(None if data.get("random_seed") in (None, "") else int(data.get("random_seed"))),
            title=str(data.get("title", default.title)),
            subtitle=subtitle,
            date=date,
            intro_text=str(data.get("intro_text", default.intro_text)),
            intro_alignment=str(data.get("intro_alignment", default.intro_alignment)),
            title_font=str(data.get("title_font", default.title_font)),
            subtitle_font=str(data.get("subtitle_font", default.subtitle_font)),
            date_font=str(data.get("date_font", data.get("subtitle_font", default.date_font))),
            intro_font=str(data.get("intro_font", default.intro_font)),
            cell_font=str(data.get("cell_font", default.cell_font)),
            title_size_pt=float(data.get("title_size_pt", default.title_size_pt)),
            subtitle_size_pt=float(data.get("subtitle_size_pt", default.subtitle_size_pt)),
            date_size_pt=float(data.get("date_size_pt", default.date_size_pt)),
            intro_size_pt=float(data.get("intro_size_pt", default.intro_size_pt)),
            cell_font_size_pt=float(data.get("cell_font_size_pt", default.cell_font_size_pt)),
            title_color=str(data.get("title_color", default.title_color)),
            subtitle_color=str(data.get("subtitle_color", default.subtitle_color)),
            date_color=str(data.get("date_color", data.get("subtitle_color", default.date_color))),
            intro_color=str(data.get("intro_color", default.intro_color)),
            cell_text_color=str(data.get("cell_text_color", default.cell_text_color)),
            grid_border_color=str(data.get("grid_border_color", default.grid_border_color)),
            cell_bg_light=str(data.get("cell_bg_light", default.cell_bg_light)),
            cell_bg_dark=str(data.get("cell_bg_dark", default.cell_bg_dark)),
            page_width_inch=float(data.get("page_width_inch", default.page_width_inch)),
            page_height_inch=float(data.get("page_height_inch", default.page_height_inch)),
            margins=PageMargins.from_dict(data.get("margins")),
            auto_cell_size=bool(data.get("auto_cell_size", default.auto_cell_size)),
            cell_size_inch=float(data.get("cell_size_inch", default.cell_size_inch)),
            cell_padding_twips=int(data.get("cell_padding_twips", default.cell_padding_twips)),
            title_top_spacing_pt=float(data.get("title_top_spacing_pt", default.title_top_spacing_pt)),
            grid_top_gap_inch=float(data.get("grid_top_gap_inch", default.grid_top_gap_inch)),
            grid_border_width_pt=float(data.get("grid_border_width_pt", default.grid_border_width_pt)),
            top_left_image=CornerImage.from_dict(data.get("top_left_image")) if data.get("top_left_image") is not None else default.top_left_image,
            top_right_image=CornerImage.from_dict(data.get("top_right_image")) if data.get("top_right_image") is not None else default.top_right_image,
            bottom_left_image=CornerImage.from_dict(data.get("bottom_left_image")) if data.get("bottom_left_image") is not None else default.bottom_left_image,
            bottom_right_image=CornerImage.from_dict(data.get("bottom_right_image")) if data.get("bottom_right_image") is not None else default.bottom_right_image,
            output_path=output_path,
            output_format=str(data.get("output_format", inferred_format)).lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        """Fail early when settings cannot produce a valid document."""
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("Grid rows and columns must be greater than 0.")
        if self.number_of_cards <= 0:
            raise ValueError("Number of cards must be greater than 0.")
        if self.cell_size_inch <= 0:
            raise ValueError("Cell size must be greater than 0.")
        if self.page_width_inch <= 0 or self.page_height_inch <= 0:
            raise ValueError("Page size must be greater than 0.")
        if self.margins.left + self.margins.right >= self.page_width_inch:
            raise ValueError("Left and right margins are wider than the page.")
        if self.margins.top + self.margins.bottom >= self.page_height_inch:
            raise ValueError("Top and bottom margins are higher than the page.")
        if self.cell_padding_twips < 0:
            raise ValueError("Cell padding cannot be negative.")
        if self.grid_border_width_pt < 0:
            raise ValueError("Grid border width cannot be negative.")
        if self.intro_alignment not in {"left", "center", "right"}:
            raise ValueError("Intro alignment must be left, center or right.")
        if self.output_format not in {"docx", "pdf"}:
            raise ValueError("Output format must be docx or pdf.")

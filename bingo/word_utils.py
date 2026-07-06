# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Small python-docx / OOXML helper functions used by the DOCX renderer.

from __future__ import annotations

from docx.shared import RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def normalize_hex(hex_color: str) -> str:
    """Normalize a HEX color string for Word XML."""
    cleaned = (hex_color or "000000").strip().replace("#", "").upper()
    if len(cleaned) != 6:
        return "000000"
    return cleaned


def rgb_from_hex(hex_color: str) -> RGBColor:
    """Convert a HEX color to python-docx RGBColor."""
    h = normalize_hex(hex_color)
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def set_table_layout_fixed(table) -> None:
    """Force fixed table layout to keep square cells stable."""
    tblPr = table._tbl.tblPr
    tblLayout = OxmlElement("w:tblLayout")
    tblLayout.set(qn("w:type"), "fixed")
    tblPr.append(tblLayout)


def set_table_borders_none(table) -> None:
    """Remove all visible table borders."""
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement("w:tblBorders")
    for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "none")
        tblBorders.append(border)
    tblPr.append(tblBorders)


def set_cell_margins(cell, top: int = 0, bottom: int = 0, left: int = 0, right: int = 0) -> None:
    """Set table-cell margins in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_appearance(cell, fill_hex: str, border_color_hex: str, border_width_pt: float = 1.0) -> None:
    """Set background and border styling for one Bingo cell."""
    border_size = max(1, int(round(border_width_pt * 8)))  # OOXML stores border width in eighths of a point.
    tcPr = cell._tc.get_or_add_tcPr()

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), normalize_hex(fill_hex))
    tcPr.append(shd)

    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        border = OxmlElement(f"w:{edge}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(border_size))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), normalize_hex(border_color_hex))
        tcBorders.append(border)
    tcPr.append(tcBorders)


def set_column_width(cell, width_twips: int) -> None:
    """Set a cell width in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(width_twips))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def set_row_height_exact(row, height_twips: int) -> None:
    """Force exact row height so the cells remain square."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    trHeight = OxmlElement("w:trHeight")
    trHeight.set(qn("w:val"), str(height_twips))
    trHeight.set(qn("w:hRule"), "exact")
    trPr.append(trHeight)

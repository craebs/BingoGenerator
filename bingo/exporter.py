# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Export helpers for DOCX and PDF. DOCX export is handled by python-docx. PDF
# export is handled natively with ReportLab, so no external LibreOffice
# installation is required.

from __future__ import annotations

from pathlib import Path

try:
    from reportlab import Version as _REPORTLAB_VERSION  # noqa: F401
except Exception:  # pragma: no cover - handled at runtime for user-friendly error
    _REPORTLAB_VERSION = None

from .models import GameSettings
from .pdf_renderer import PdfBingoRenderer
from .word_renderer import WordBingoRenderer


class ExportError(RuntimeError):
    """User-facing export error."""


def export_cards(cards: list[list[str]], settings: GameSettings) -> Path:
    """Create the output file selected in the settings."""
    output = Path(settings.output_path)
    fmt = settings.output_format.lower()
    if output.suffix.lower() == ".pdf":
        fmt = "pdf"
    elif output.suffix.lower() == ".docx":
        fmt = "docx"

    if fmt == "docx":
        output = output.with_suffix(".docx")
        settings.output_path = str(output)
        return WordBingoRenderer(settings).render(cards, output)

    if fmt == "pdf":
        if _REPORTLAB_VERSION is None:
            raise ExportError("PDF export requires the Python package 'reportlab'. Install it with: pip install reportlab")
        output = output.with_suffix(".pdf")
        settings.output_path = str(output)
        return PdfBingoRenderer(settings).render(cards, output)

    raise ExportError(f"Unknown output format: {settings.output_format}")

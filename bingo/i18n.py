# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Lightweight JSON-based translation support. Every file in config/lang/*.json
# is detected automatically, which makes adding new languages simple.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TranslationManager:
    """Load and provide translated GUI strings from JSON files."""

    def __init__(self, lang_dir: Path, default_language: str = "de"):
        self.lang_dir = Path(lang_dir)
        self.lang_dir.mkdir(parents=True, exist_ok=True)
        self.default_language = default_language
        self.translations: dict[str, dict[str, Any]] = {}
        self.language = default_language
        self.reload()

    def reload(self) -> None:
        """Reload all language files from disk."""
        self.translations.clear()
        for path in sorted(self.lang_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    self.translations[path.stem] = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
        if self.default_language not in self.translations and self.translations:
            self.default_language = sorted(self.translations)[0]
        if self.language not in self.translations:
            self.language = self.default_language

    def available_languages(self) -> list[str]:
        """Return available language codes sorted by filename."""
        return sorted(self.translations) or [self.default_language]

    def display_name(self, lang_code: str) -> str:
        """Return the human readable language name from the _meta block."""
        meta = self.translations.get(lang_code, {}).get("_meta", {})
        return str(meta.get("name", lang_code))

    def set_language(self, lang_code: str) -> None:
        """Switch the active language if the code exists."""
        if lang_code in self.translations:
            self.language = lang_code

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a dotted key and format it with keyword arguments."""
        text = self._lookup(self.language, key)
        if text is None and self.language != self.default_language:
            text = self._lookup(self.default_language, key)
        if text is None:
            text = key
        try:
            return str(text).format(**kwargs)
        except Exception:
            return str(text)

    def _lookup(self, lang: str, key: str) -> Any:
        node: Any = self.translations.get(lang, {})
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

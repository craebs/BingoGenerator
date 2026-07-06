# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# JSON persistence for settings, categories and language files.

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import CategoryConfig, GameSettings


def sanitize_filename(name: str) -> str:
    """Return a safe filename for a category JSON file."""
    safe = re.sub(r"[^A-Za-z0-9_\-äöüÄÖÜß]+", "_", name.strip())
    return safe.strip("_") or "Category"


class ConfigManager:
    """Read and write the application's JSON configuration files."""

    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir)
        self.config_dir = self.root_dir / "config"
        self.category_dir = self.config_dir / "categories"
        self.lang_dir = self.config_dir / "lang"
        self.settings_file = self.config_dir / "settings.json"
        self.category_dir.mkdir(parents=True, exist_ok=True)
        self.lang_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> GameSettings:
        """Load settings.json or create it with defaults."""
        if not self.settings_file.exists():
            settings = GameSettings()
            self.save_settings(settings)
            return settings
        with self.settings_file.open("r", encoding="utf-8") as f:
            return GameSettings.from_dict(json.load(f))

    def save_settings(self, settings: GameSettings) -> None:
        """Write settings.json."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with self.settings_file.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)

    def load_categories(self) -> list[CategoryConfig]:
        """Load every JSON file in config/categories as a category."""
        categories: list[CategoryConfig] = []
        for path in sorted(self.category_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as f:
                categories.append(CategoryConfig.from_dict(json.load(f)))
        return categories

    def save_category(self, category: CategoryConfig) -> Path:
        """Write one category to its own JSON file."""
        path = self.category_dir / f"{sanitize_filename(category.name)}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(category.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def delete_category_file(self, category_name: str) -> None:
        """Delete a category JSON file if it exists."""
        path = self.category_dir / f"{sanitize_filename(category_name)}.json"
        if path.exists():
            path.unlink()


    def save_all_categories(self, categories: list[CategoryConfig]) -> None:
        """Rewrite the category directory from the current in-memory state.

        The GUI keeps unsaved category edits in memory until the user clicks
        Save. Rewriting the directory on save prevents stale JSON files from
        surviving after a category has been renamed or deleted.
        """
        self.category_dir.mkdir(parents=True, exist_ok=True)
        for path in self.category_dir.glob("*.json"):
            path.unlink()
        for category in categories:
            self.save_category(category)

    def ensure_default_files(self, default_categories: list[CategoryConfig]) -> None:
        """Create default settings and example categories on first launch."""
        if not self.settings_file.exists():
            self.save_settings(GameSettings())
        if not any(self.category_dir.glob("*.json")):
            for category in default_categories:
                self.save_category(category)

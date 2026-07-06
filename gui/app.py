# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Main graphical user interface. The GUI is deliberately kept as a thin layer:
# it reads/writes JSON settings, lets the user edit categories and delegates the
# real work to bingo/deck_generator.py, bingo/preview_renderer.py and
# bingo/exporter.py.

from __future__ import annotations

from pathlib import Path
import ctypes
import tkinter as tk
from tkinter import colorchooser, filedialog, font as tkfont, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from bingo.config_io import ConfigManager
from bingo.deck_generator import DeckGenerationError, generate_cards
from bingo.defaults import default_categories
from bingo.exporter import ExportError, export_cards
from bingo.i18n import TranslationManager
from bingo.models import CategoryConfig, CornerImage, GameSettings, PageMargins
from bingo.preview_renderer import PreviewRenderer
from bingo.word_utils import normalize_hex
from gui.widgets import LayoutSketch, ToolTip


class BingoApp(ctk.CTk):
    """Main application window."""

    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.config_manager = ConfigManager(root_dir)
        self.config_manager.ensure_default_files(default_categories())

        self.settings: GameSettings = self.config_manager.load_settings()
        self.categories: list[CategoryConfig] = self.config_manager.load_categories()
        self.selected_category_index: int | None = None

        self.preview_photo: ImageTk.PhotoImage | None = None
        self.preview_image_id: int | None = None
        self.preview_zoom = tk.DoubleVar(value=0.95)
        self._dirty = False
        self._tracking_enabled = False
        # Guard flag used while the category list is rebuilt. Without this,
        # Tk can fire <<ListboxSelect>> events while rows are deleted/reinserted,
        # which would overwrite the editor with stale category data.
        self._suppress_category_select = False

        self.i18n = TranslationManager(self.config_manager.lang_dir, default_language="de")
        self.i18n.set_language(self.settings.language)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("green")

        self._available_fonts = self._load_font_names()
        self.geometry("1360x900")
        self.minsize(1180, 780)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_app_icon()
        self.after(80, self._maximize_window)

        self._create_variables()
        self._build_ui()
        self._attach_dirty_tracking()
        self._refresh_category_list()
        self._update_preview()
        self._dirty = False

    # ---------------------------------------------------------------------
    # Translation, window icon and font discovery
    # ---------------------------------------------------------------------
    def t(self, key: str, **kwargs) -> str:
        """Translate a key with optional format arguments."""
        return self.i18n.t(key, **kwargs)

    def _set_app_icon(self) -> None:
        """Load the PNG/ICO app icon for the window and Windows taskbar.

        Tk on Windows sometimes keeps the default Tcl/Tk taskbar icon unless
        the process exposes an explicit AppUserModelID. The ctypes call is
        ignored on non-Windows systems and harmless if it fails.
        """
        png_path = self.root_dir / "assets" / "app_icon.png"
        ico_path = self.root_dir / "assets" / "app_icon.ico"
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CraebsMedia.BingoGenerator")
        except Exception:
            pass
        try:
            if png_path.exists():
                self._app_icon_photo = ImageTk.PhotoImage(Image.open(png_path))
                self.iconphoto(True, self._app_icon_photo)
            if ico_path.exists() and self.tk.call("tk", "windowingsystem") == "win32":
                self.iconbitmap(str(ico_path))
        except Exception:
            # Icons are cosmetic. A missing/broken icon must not prevent the app
            # from starting.
            pass

    def _maximize_window(self) -> None:
        """Start maximized while keeping normal resizing available."""
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def _load_font_names(self) -> list[str]:
        """Read installed Tk fonts and add common fallbacks."""
        try:
            names = sorted(set(tkfont.families(self)))
        except tk.TclError:
            names = []
        common = ["Calibri", "Arial", "Times New Roman", "Brush Script MT", "Georgia", "Verdana"]
        for name in reversed(common):
            if name not in names:
                names.insert(0, name)
        return names

    def _language_display_map(self) -> dict[str, str]:
        """Map localized language names to language codes."""
        return {self.i18n.display_name(code): code for code in self.i18n.available_languages()}

    # ---------------------------------------------------------------------
    # Variables and parsing
    # ---------------------------------------------------------------------
    def _create_variables(self) -> None:
        """Create Tk variables from the current GameSettings object."""
        s = self.settings
        self.vars: dict[str, tk.Variable] = {
            "language": tk.StringVar(value=self.i18n.display_name(s.language)),
            "rows": tk.StringVar(value=str(s.rows)),
            "cols": tk.StringVar(value=str(s.cols)),
            "number_of_cards": tk.StringVar(value=str(s.number_of_cards)),
            "random_seed": tk.StringVar(value="" if s.random_seed is None else str(s.random_seed)),
            "title": tk.StringVar(value=s.title),
            "subtitle": tk.StringVar(value=s.subtitle),
            "date": tk.StringVar(value=s.date),
            "intro_text": tk.StringVar(value=s.intro_text),
            "intro_alignment": tk.StringVar(value=s.intro_alignment),
            "title_font": tk.StringVar(value=s.title_font),
            "subtitle_font": tk.StringVar(value=s.subtitle_font),
            "date_font": tk.StringVar(value=s.date_font),
            "intro_font": tk.StringVar(value=s.intro_font),
            "cell_font": tk.StringVar(value=s.cell_font),
            "title_size_pt": tk.StringVar(value=str(s.title_size_pt)),
            "subtitle_size_pt": tk.StringVar(value=str(s.subtitle_size_pt)),
            "date_size_pt": tk.StringVar(value=str(s.date_size_pt)),
            "intro_size_pt": tk.StringVar(value=str(s.intro_size_pt)),
            "cell_font_size_pt": tk.StringVar(value=str(s.cell_font_size_pt)),
            "title_color": tk.StringVar(value=s.title_color),
            "subtitle_color": tk.StringVar(value=s.subtitle_color),
            "date_color": tk.StringVar(value=s.date_color),
            "intro_color": tk.StringVar(value=s.intro_color),
            "cell_text_color": tk.StringVar(value=s.cell_text_color),
            "grid_border_color": tk.StringVar(value=s.grid_border_color),
            "cell_bg_light": tk.StringVar(value=s.cell_bg_light),
            "cell_bg_dark": tk.StringVar(value=s.cell_bg_dark),
            "cell_size_inch": tk.StringVar(value=str(s.cell_size_inch)),
            "cell_padding_twips": tk.StringVar(value=str(s.cell_padding_twips)),
            "title_top_spacing_pt": tk.StringVar(value=str(s.title_top_spacing_pt)),
            "grid_top_gap_inch": tk.StringVar(value=str(s.grid_top_gap_inch)),
            "grid_border_width_pt": tk.StringVar(value=str(s.grid_border_width_pt)),
            "margin_top": tk.StringVar(value=str(s.margins.top)),
            "margin_bottom": tk.StringVar(value=str(s.margins.bottom)),
            "margin_left": tk.StringVar(value=str(s.margins.left)),
            "margin_right": tk.StringVar(value=str(s.margins.right)),
            "footer_distance": tk.StringVar(value=str(s.margins.footer_distance)),
            "auto_cell_size": tk.BooleanVar(value=s.auto_cell_size),
            "top_left_image": tk.StringVar(value=s.top_left_image.path),
            "top_left_width": tk.StringVar(value=str(s.top_left_image.width_inch)),
            "top_right_image": tk.StringVar(value=s.top_right_image.path),
            "top_right_width": tk.StringVar(value=str(s.top_right_image.width_inch)),
            "bottom_left_image": tk.StringVar(value=s.bottom_left_image.path),
            "bottom_left_width": tk.StringVar(value=str(s.bottom_left_image.width_inch)),
            "bottom_right_image": tk.StringVar(value=s.bottom_right_image.path),
            "bottom_right_width": tk.StringVar(value=str(s.bottom_right_image.width_inch)),
            "output_path": tk.StringVar(value=s.output_path),
            "output_format": tk.StringVar(value=s.output_format),
        }

        self.cat_name = tk.StringVar()
        self.cat_min = tk.StringVar(value="0")
        self.cat_max = tk.StringVar(value="")
        self.cat_enabled = tk.BooleanVar(value=True)
        self.cat_filler = tk.BooleanVar(value=True)

    def _attach_dirty_tracking(self) -> None:
        """Mark the project as dirty when settings variables change."""
        self._tracking_enabled = True
        for var in self.vars.values():
            try:
                var.trace_add("write", lambda *_: self._mark_dirty())
            except Exception:
                pass
        for var in [self.cat_name, self.cat_min, self.cat_max, self.cat_enabled, self.cat_filler]:
            var.trace_add("write", lambda *_: self._mark_dirty())

    def _mark_dirty(self) -> None:
        """Set the dirty flag and update the status line."""
        if not self._tracking_enabled:
            return
        self._dirty = True
        if hasattr(self, "status_label"):
            self.status_label.configure(text=self.t("app.unsaved"))

    def _current_settings_from_ui(self) -> GameSettings:
        """Parse the current UI values into a GameSettings object."""
        def as_int(key: str) -> int:
            return int(float(str(self.vars[key].get()).strip().replace(",", ".")))

        def as_float(key: str) -> float:
            return float(str(self.vars[key].get()).strip().replace(",", "."))

        def optional_int(key: str) -> int | None:
            value = str(self.vars[key].get()).strip()
            return None if value == "" else int(float(value))

        display_to_code = self._language_display_map()
        lang_code = display_to_code.get(str(self.vars["language"].get()), self.settings.language)

        return GameSettings(
            language=lang_code,
            rows=as_int("rows"),
            cols=as_int("cols"),
            number_of_cards=as_int("number_of_cards"),
            random_seed=optional_int("random_seed"),
            title=str(self.vars["title"].get()),
            subtitle=str(self.vars["subtitle"].get()),
            date=str(self.vars["date"].get()),
            intro_text=str(self.vars["intro_text"].get()),
            intro_alignment=str(self.vars["intro_alignment"].get()),
            title_font=str(self.vars["title_font"].get()),
            subtitle_font=str(self.vars["subtitle_font"].get()),
            date_font=str(self.vars["date_font"].get()),
            intro_font=str(self.vars["intro_font"].get()),
            cell_font=str(self.vars["cell_font"].get()),
            title_size_pt=as_float("title_size_pt"),
            subtitle_size_pt=as_float("subtitle_size_pt"),
            date_size_pt=as_float("date_size_pt"),
            intro_size_pt=as_float("intro_size_pt"),
            cell_font_size_pt=as_float("cell_font_size_pt"),
            title_color=str(self.vars["title_color"].get()),
            subtitle_color=str(self.vars["subtitle_color"].get()),
            date_color=str(self.vars["date_color"].get()),
            intro_color=str(self.vars["intro_color"].get()),
            cell_text_color=str(self.vars["cell_text_color"].get()),
            grid_border_color=str(self.vars["grid_border_color"].get()),
            cell_bg_light=str(self.vars["cell_bg_light"].get()),
            cell_bg_dark=str(self.vars["cell_bg_dark"].get()),
            margins=PageMargins(
                top=as_float("margin_top"),
                bottom=as_float("margin_bottom"),
                left=as_float("margin_left"),
                right=as_float("margin_right"),
                footer_distance=as_float("footer_distance"),
            ),
            auto_cell_size=bool(self.vars["auto_cell_size"].get()),
            cell_size_inch=as_float("cell_size_inch"),
            cell_padding_twips=as_int("cell_padding_twips"),
            title_top_spacing_pt=as_float("title_top_spacing_pt"),
            grid_top_gap_inch=as_float("grid_top_gap_inch"),
            grid_border_width_pt=as_float("grid_border_width_pt"),
            top_left_image=CornerImage(str(self.vars["top_left_image"].get()), as_float("top_left_width")),
            top_right_image=CornerImage(str(self.vars["top_right_image"].get()), as_float("top_right_width")),
            bottom_left_image=CornerImage(str(self.vars["bottom_left_image"].get()), as_float("bottom_left_width")),
            bottom_right_image=CornerImage(str(self.vars["bottom_right_image"].get()), as_float("bottom_right_width")),
            output_path=str(self.vars["output_path"].get()),
            output_format=str(self.vars["output_format"].get()),
        )

    # ---------------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the complete tabbed interface."""
        self.title(self.t("app.title"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(self, command=self._on_tab_changed)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self._tab_names = {
            "game": self.t("tabs.game"),
            "layout": self.t("tabs.layout"),
            "categories": self.t("tabs.categories"),
            "preview": self.t("tabs.preview"),
            "help": self.t("tabs.help"),
        }
        for label in self._tab_names.values():
            self.tabs.add(label)

        self._build_game_tab(self.tabs.tab(self._tab_names["game"]))
        self._build_layout_tab(self.tabs.tab(self._tab_names["layout"]))
        self._build_categories_tab(self.tabs.tab(self._tab_names["categories"]))
        self._build_preview_tab(self.tabs.tab(self._tab_names["preview"]))
        self._build_help_tab(self.tabs.tab(self._tab_names["help"]))

        footer = ctk.CTkFrame(self)
        footer.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(footer, text=self.t("app.ready"))
        self.status_label.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkButton(footer, text=self.t("app.save_settings"), command=self._save_all).grid(row=0, column=1, padx=6, pady=8)
        ctk.CTkButton(footer, text=self.t("app.update_preview"), command=self._update_preview).grid(row=0, column=2, padx=6, pady=8)
        ctk.CTkButton(footer, text=self.t("app.generate_file"), command=self._generate_document).grid(row=0, column=3, padx=6, pady=8)

    def _on_tab_changed(self) -> None:
        """Refresh calculated views when their tab becomes visible."""
        current = self.tabs.get()
        if current == self._tab_names.get("preview"):
            self._update_preview()
        if current == self._tab_names.get("layout") and hasattr(self, "layout_sketch"):
            self.layout_sketch.draw()

    def _form_entry(self, parent, row: int, label: str, var: tk.StringVar, col: int = 0, width: int = 180) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=col, sticky="w", padx=8, pady=6)
        entry = ctk.CTkEntry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=col + 1, sticky="ew", padx=8, pady=6)
        return entry

    def _build_game_tab(self, tab) -> None:
        """Create the main game tab.

        The previous compact four-column layout could become visually cramped on
        some Windows scaling settings. This version uses full-width section
        panels and one setting per row, so the available height and width are
        used predictably and every label remains readable.
        """
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkScrollableFrame(tab)
        outer.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        outer.grid_columnconfigure(0, weight=1)

        parameters = self._game_section_frame(outer, 0, self.t("game.parameters"))
        row = 0
        self._game_option_row(parameters, row, self.t("game.language"), self.vars["language"], list(self._language_display_map().keys()), self._change_language)
        row += 1
        self._game_entry_row(parameters, row, self.t("game.cards"), self.vars["number_of_cards"])
        row += 1
        self._game_entry_row(parameters, row, self.t("game.rows"), self.vars["rows"])
        row += 1
        self._game_entry_row(parameters, row, self.t("game.cols"), self.vars["cols"])
        row += 1
        seed_entry = self._game_entry_row(parameters, row, self.t("game.seed"), self.vars["random_seed"])
        ToolTip(seed_entry, self.t("game.seed_tooltip"))

        texts = self._game_section_frame(outer, 1, self.t("game.texts"))
        row = 0
        self._game_entry_row(texts, row, self.t("game.title"), self.vars["title"])
        row += 1
        self._game_entry_row(texts, row, self.t("game.subtitle"), self.vars["subtitle"])
        row += 1
        self._game_entry_row(texts, row, self.t("game.date"), self.vars["date"])
        row += 1
        self._game_entry_row(texts, row, self.t("game.intro"), self.vars["intro_text"])

        output = self._game_section_frame(outer, 2, self.t("game.output"))
        row = 0
        self._game_option_row(output, row, self.t("game.output_format"), self.vars["output_format"], ["docx", "pdf"], lambda *_: self._update_output_extension())
        row += 1
        ctk.CTkLabel(output, text=self.t("game.output_path"), anchor="w").grid(row=row, column=0, sticky="w", padx=12, pady=8)
        out_entry = ctk.CTkEntry(output, textvariable=self.vars["output_path"])
        out_entry.grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        ctk.CTkButton(output, text=self.t("game.browse"), command=self._browse_output, width=140).grid(row=row, column=2, sticky="e", padx=12, pady=8)

    def _game_section_frame(self, parent, row: int, title: str):
        """Create a labeled section on the game tab."""
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=0, sticky="ew", padx=8, pady=(8, 14))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))
        return frame

    def _game_entry_row(self, parent, row: int, label: str, var: tk.StringVar):
        """Add one full-width label/entry row to the game tab."""
        grid_row = row + 1
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=grid_row, column=0, sticky="w", padx=12, pady=8)
        entry = ctk.CTkEntry(parent, textvariable=var)
        entry.grid(row=grid_row, column=1, columnspan=2, sticky="ew", padx=12, pady=8)
        return entry

    def _game_option_row(self, parent, row: int, label: str, var: tk.StringVar, values: list[str], command=None):
        """Add one full-width label/dropdown row to the game tab."""
        grid_row = row + 1
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=grid_row, column=0, sticky="w", padx=12, pady=8)
        menu = ctk.CTkOptionMenu(parent, variable=var, values=values, command=command)
        menu.grid(row=grid_row, column=1, columnspan=2, sticky="ew", padx=12, pady=8)
        return menu

    def _build_layout_tab(self, tab) -> None:
        """Create the layout editor with a draggable sketch pane."""
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        paned = tk.PanedWindow(tab, orient=tk.HORIZONTAL, sashwidth=8, sashrelief="raised", bg="#E5E5E5", bd=0)
        paned.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        left_frame = ctk.CTkFrame(paned)
        right_frame = ctk.CTkFrame(paned)
        paned.add(left_frame, minsize=640, stretch="always")
        paned.add(right_frame, minsize=330, stretch="always")

        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(left_frame)
        scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        scroll.grid_columnconfigure(1, weight=1)

        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(right_frame, text=self.t("layout.sketch_title"), font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.layout_sketch = LayoutSketch(right_frame, self._current_settings_from_ui, self.t)
        self.layout_sketch.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        ctk.CTkLabel(right_frame, text=self.t("layout.sketch_hint"), wraplength=420, justify="left").grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        row = 0
        row = self._section_label(scroll, row, self.t("layout.fonts"))
        row = self._font_row(scroll, row, self.t("layout.title_font"), "title_font", self.t("layout.title_size"), "title_size_pt")
        row = self._font_row(scroll, row, self.t("layout.subtitle_font"), "subtitle_font", self.t("layout.subtitle_size"), "subtitle_size_pt")
        row = self._font_row(scroll, row, self.t("layout.date_font"), "date_font", self.t("layout.date_size"), "date_size_pt")
        row = self._font_row(scroll, row, self.t("layout.intro_font"), "intro_font", self.t("layout.intro_size"), "intro_size_pt")
        row = self._font_row(scroll, row, self.t("layout.cell_font"), "cell_font", self.t("layout.cell_size_font"), "cell_font_size_pt")

        row = self._section_label(scroll, row, self.t("layout.colors"))
        for label, key in [
            (self.t("layout.title_color"), "title_color"),
            (self.t("layout.subtitle_color"), "subtitle_color"),
            (self.t("layout.date_color"), "date_color"),
            (self.t("layout.intro_color"), "intro_color"),
            (self.t("layout.cell_text"), "cell_text_color"),
            (self.t("layout.border"), "grid_border_color"),
            (self.t("layout.cell_light"), "cell_bg_light"),
            (self.t("layout.cell_dark"), "cell_bg_dark"),
        ]:
            row = self._color_single_row(scroll, row, label, key)

        row = self._section_label(scroll, row, self.t("layout.page_grid"))
        for label, key in [
            (self.t("layout.margin_top"), "margin_top"),
            (self.t("layout.margin_bottom"), "margin_bottom"),
            (self.t("layout.margin_left"), "margin_left"),
            (self.t("layout.margin_right"), "margin_right"),
            (self.t("layout.footer_distance"), "footer_distance"),
            (self.t("layout.max_cell_size"), "cell_size_inch"),
            (self.t("layout.cell_padding"), "cell_padding_twips"),
            (self.t("layout.border_width"), "grid_border_width_pt"),
            (self.t("layout.title_top_spacing"), "title_top_spacing_pt"),
            (self.t("layout.grid_top_gap"), "grid_top_gap_inch"),
        ]:
            row = self._single_entry_row(scroll, row, label, key)
        ctk.CTkCheckBox(scroll, text=self.t("layout.auto_cell_size"), variable=self.vars["auto_cell_size"], command=self._update_layout_helpers).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=7)
        row += 1
        ctk.CTkLabel(scroll, text=self.t("layout.intro_alignment")).grid(row=row, column=0, sticky="w", padx=8, pady=7)
        ctk.CTkOptionMenu(scroll, variable=self.vars["intro_alignment"], values=["left", "center", "right"], command=lambda *_: self._update_layout_helpers()).grid(row=row, column=1, sticky="ew", padx=8, pady=7)
        row += 1

        row = self._section_label(scroll, row, self.t("layout.corner_images"))
        row = self._image_row(scroll, row, self.t("layout.top_left"), "top_left_image", "top_left_width")
        row = self._image_row(scroll, row, self.t("layout.top_right"), "top_right_image", "top_right_width")
        row = self._image_row(scroll, row, self.t("layout.bottom_left"), "bottom_left_image", "bottom_left_width")
        row = self._image_row(scroll, row, self.t("layout.bottom_right"), "bottom_right_image", "bottom_right_width")

    def _section_label(self, parent, row: int, text: str) -> int:
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=18, weight="bold")).grid(row=row, column=0, columnspan=4, sticky="w", padx=8, pady=(18, 6))
        return row + 1

    def _single_entry_row(self, parent, row: int, label: str, key: str) -> int:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=7)
        entry = ctk.CTkEntry(parent, textvariable=self.vars[key], width=150)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=7)
        entry.bind("<FocusOut>", lambda _e: self._update_layout_helpers())
        return row + 1

    def _font_row(self, parent, row: int, label_font: str, key_font: str, label_size: str, key_size: str) -> int:
        ctk.CTkLabel(parent, text=label_font).grid(row=row, column=0, sticky="w", padx=8, pady=7)
        ctk.CTkOptionMenu(parent, variable=self.vars[key_font], values=self._available_fonts, command=lambda *_: self._update_layout_helpers()).grid(row=row, column=1, sticky="ew", padx=8, pady=7)
        ctk.CTkLabel(parent, text=label_size).grid(row=row, column=2, sticky="w", padx=8, pady=7)
        size_entry = ctk.CTkEntry(parent, textvariable=self.vars[key_size], width=90)
        size_entry.grid(row=row, column=3, sticky="ew", padx=8, pady=7)
        size_entry.bind("<FocusOut>", lambda _e: self._update_layout_helpers())
        return row + 1

    def _color_single_row(self, parent, row: int, label: str, key: str) -> int:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=7)
        swatch = ctk.CTkButton(parent, text=f"#{normalize_hex(str(self.vars[key].get()))}", width=130, fg_color=f"#{normalize_hex(str(self.vars[key].get()))}", command=lambda: self._choose_color(key, swatch))
        swatch.grid(row=row, column=1, sticky="w", padx=8, pady=7)
        return row + 1

    def _image_row(self, parent, row: int, label: str, path_key: str, width_key: str) -> int:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=7)
        ctk.CTkEntry(parent, textvariable=self.vars[path_key]).grid(row=row, column=1, sticky="ew", padx=8, pady=7)
        ctk.CTkEntry(parent, textvariable=self.vars[width_key], width=80).grid(row=row, column=2, sticky="ew", padx=8, pady=7)
        ctk.CTkButton(parent, text=self.t("layout.image_choose"), command=lambda: self._browse_image(path_key)).grid(row=row, column=3, sticky="ew", padx=8, pady=7)
        return row + 1

    def _build_categories_tab(self, tab) -> None:
        """Create the category editor tab."""
        tab.grid_columnconfigure(0, weight=1, minsize=380)
        tab.grid_columnconfigure(1, weight=3)
        tab.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(tab)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left, text=self.t("categories.title"), font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=12)
        self.category_listbox = tk.Listbox(left, font=("Arial", 16), activestyle="dotbox", height=18)
        self.category_listbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        self.category_listbox.bind("<<ListboxSelect>>", self._on_category_selected)
        ctk.CTkButton(left, text=self.t("categories.new"), command=self._new_category).grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        ctk.CTkButton(left, text=self.t("categories.delete"), command=self._delete_category).grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))

        right = ctk.CTkFrame(tab)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right.grid_columnconfigure(1, weight=1)
        right.grid_rowconfigure(6, weight=1)
        ctk.CTkLabel(right, text=self.t("categories.edit"), font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=12)
        ctk.CTkLabel(right, text=self.t("categories.name")).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        name_entry = ctk.CTkEntry(right, textvariable=self.cat_name)
        name_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        name_entry.bind("<FocusOut>", lambda _e: self._commit_category_editor_to_memory(refresh_list=True, strict=False))
        ctk.CTkLabel(right, text=self.t("categories.min")).grid(row=2, column=0, sticky="w", padx=12, pady=6)
        min_entry = ctk.CTkEntry(right, textvariable=self.cat_min)
        min_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=6)
        min_entry.bind("<FocusOut>", lambda _e: self._commit_category_editor_to_memory(refresh_list=True, strict=False))
        ctk.CTkLabel(right, text=self.t("categories.max")).grid(row=3, column=0, sticky="w", padx=12, pady=6)
        max_entry = ctk.CTkEntry(right, textvariable=self.cat_max)
        max_entry.grid(row=3, column=1, sticky="ew", padx=12, pady=6)
        max_entry.bind("<FocusOut>", lambda _e: self._commit_category_editor_to_memory(refresh_list=True, strict=False))
        ctk.CTkCheckBox(right, text=self.t("categories.enabled"), variable=self.cat_enabled, command=lambda: self._commit_category_editor_to_memory(refresh_list=True)).grid(row=4, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkCheckBox(right, text=self.t("categories.filler"), variable=self.cat_filler, command=lambda: self._commit_category_editor_to_memory(refresh_list=True)).grid(row=4, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkLabel(right, text=self.t("categories.questions")).grid(row=5, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 4))
        self.questions_text = ctk.CTkTextbox(right, height=320)
        self.questions_text.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=12, pady=6)
        self.questions_text.bind("<KeyRelease>", lambda _e: self._commit_category_editor_to_memory(refresh_list=False, strict=False))
        ctk.CTkButton(right, text=self.t("categories.save"), command=self._save_category_from_editor).grid(row=7, column=2, sticky="e", padx=12, pady=12)

    def _build_preview_tab(self, tab) -> None:
        """Create a zoomable, scrollable preview tab."""
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        toolbar.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(toolbar, text=self.t("preview.zoom")).grid(row=0, column=0, padx=(12, 6), pady=8)
        ctk.CTkButton(toolbar, text="-", width=38, command=lambda: self._change_zoom(-0.1)).grid(row=0, column=1, padx=4, pady=8)
        self.zoom_slider = ctk.CTkSlider(toolbar, from_=0.45, to=2.0, variable=self.preview_zoom, command=lambda _v: self._update_preview())
        self.zoom_slider.grid(row=0, column=2, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(toolbar, text="+", width=38, command=lambda: self._change_zoom(0.1)).grid(row=0, column=3, sticky="w", padx=4, pady=8)
        ctk.CTkButton(toolbar, text=self.t("app.update_preview"), command=self._update_preview).grid(row=0, column=4, padx=8, pady=8)

        container = ctk.CTkFrame(tab)
        container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(container, bg="#DADADA", highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll = ctk.CTkScrollbar(container, orientation="vertical", command=self.preview_canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ctk.CTkScrollbar(container, orientation="horizontal", command=self.preview_canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.preview_canvas.bind("<Configure>", lambda _e: self._center_preview_image())

        ctk.CTkLabel(tab, text=self.t("app.preview_hint"), wraplength=1050, justify="left").grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

    def _build_help_tab(self, tab) -> None:
        """Show the README file inside the app."""
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        textbox = ctk.CTkTextbox(tab, wrap="word")
        textbox.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        readme_path = self.root_dir / "README.md"
        text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else self.t("help.no_readme")
        textbox.insert("1.0", text)
        textbox.configure(state="disabled")

    # ---------------------------------------------------------------------
    # Category editing
    # ---------------------------------------------------------------------
    def _refresh_category_list(self) -> None:
        """Rebuild the category list without discarding unsaved edits."""
        if not hasattr(self, "category_listbox"):
            return
        previous_index = self.selected_category_index
        self._suppress_category_select = True
        try:
            self.category_listbox.delete(0, tk.END)
            for category in self.categories:
                label = f"{'✓' if category.enabled else 'x'} {category.name}"
                self.category_listbox.insert(tk.END, label)

            if self.categories:
                if previous_index is None:
                    previous_index = 0
                previous_index = max(0, min(previous_index, len(self.categories) - 1))
                self.category_listbox.select_clear(0, tk.END)
                self.category_listbox.select_set(previous_index)
                self.category_listbox.activate(previous_index)
                self.selected_category_index = previous_index
            else:
                self.selected_category_index = None
        finally:
            self._suppress_category_select = False

        if self.categories and previous_index is not None and not self.cat_name.get():
            self._load_category_into_editor(previous_index)

    def _on_category_selected(self, _event=None) -> None:
        """Switch categories without losing unsaved editor changes."""
        if self._suppress_category_select:
            return
        selection = self.category_listbox.curselection()
        if not selection:
            return
        new_index = int(selection[0])
        if self.selected_category_index == new_index:
            return
        # Commit the currently visible editor to RAM first. This is not a disk
        # save; it only prevents edits from disappearing when the list selection
        # changes.
        self._commit_category_editor_to_memory(refresh_list=False, strict=False)
        self.selected_category_index = new_index
        self._load_category_into_editor(self.selected_category_index)

    def _load_category_into_editor(self, index: int) -> None:
        """Load one category into the editor without marking it as changed."""
        category = self.categories[index]
        was_tracking = self._tracking_enabled
        self._tracking_enabled = False
        try:
            self.cat_name.set(category.name)
            self.cat_min.set(str(category.min_per_card))
            self.cat_max.set("" if category.max_per_card is None else str(category.max_per_card))
            self.cat_enabled.set(category.enabled)
            self.cat_filler.set(category.use_as_filler)
            self.questions_text.delete("1.0", tk.END)
            self.questions_text.insert("1.0", "\n".join(category.questions))
        finally:
            self._tracking_enabled = was_tracking

    def _new_category(self) -> None:
        """Create a new unsaved category in memory and select it immediately."""
        self._commit_category_editor_to_memory(refresh_list=False, strict=False)
        base_name = self.t("categories.new")
        existing = {category.name for category in self.categories}
        name = base_name
        counter = 2
        while name in existing:
            name = f"{base_name} {counter}"
            counter += 1
        self.categories.append(CategoryConfig(name=name, questions=[], min_per_card=0, max_per_card=None, use_as_filler=True, enabled=True))
        self.selected_category_index = len(self.categories) - 1
        self._refresh_category_list()
        self.category_listbox.select_clear(0, tk.END)
        self.category_listbox.select_set(self.selected_category_index)
        self._load_category_into_editor(self.selected_category_index)
        self._mark_dirty()

    def _commit_category_editor_to_memory(self, refresh_list: bool = False, strict: bool = False) -> bool:
        """Copy the visible category editor into the in-memory category list.

        This is deliberately separate from writing JSON files. It allows users
        to switch between categories freely and keeps every unsaved edit alive
        until the global Save button is pressed.
        """
        if self.selected_category_index is None or not hasattr(self, "questions_text"):
            return True
        try:
            category = self._category_from_editor(validate=strict)
        except Exception as exc:
            if strict:
                messagebox.showerror(self.t("categories.invalid_title"), str(exc))
                return False
            # During normal typing we keep the previous numeric limits if the
            # user is halfway through an invalid value. Text and checkboxes are
            # still preserved.
            old = self.categories[self.selected_category_index]
            category = CategoryConfig(
                name=self.cat_name.get().strip() or old.name,
                questions=[line.strip() for line in self.questions_text.get("1.0", tk.END).splitlines() if line.strip()],
                min_per_card=old.min_per_card,
                max_per_card=old.max_per_card,
                use_as_filler=bool(self.cat_filler.get()),
                enabled=bool(self.cat_enabled.get()),
            )
        previous = self.categories[self.selected_category_index]
        self.categories[self.selected_category_index] = category
        if category != previous:
            self._mark_dirty()
        if refresh_list and hasattr(self, "category_listbox"):
            selected = self.selected_category_index
            self._refresh_category_list()
            self.category_listbox.select_clear(0, tk.END)
            self.category_listbox.select_set(selected)
            self.selected_category_index = selected
        return True

    def _category_from_editor(self, validate: bool = True) -> CategoryConfig:
        max_text = self.cat_max.get().strip()
        category = CategoryConfig(
            name=self.cat_name.get().strip(),
            questions=[line.strip() for line in self.questions_text.get("1.0", tk.END).splitlines() if line.strip()],
            min_per_card=int(float(self.cat_min.get().strip() or 0)),
            max_per_card=None if max_text == "" else int(float(max_text)),
            use_as_filler=bool(self.cat_filler.get()),
            enabled=bool(self.cat_enabled.get()),
        )
        if validate:
            category.validate(self._current_settings_from_ui().grid_cells)
        return category

    def _save_category_from_editor(self) -> None:
        """Validate and store the current category in memory.

        The global Save button writes all category JSON files. This button is a
        convenience for validating the current category without leaving the tab.
        """
        if not self._commit_category_editor_to_memory(refresh_list=True, strict=True):
            return
        category = self.categories[self.selected_category_index]
        self.status_label.configure(text=self.t("categories.saved", name=category.name))
        self._update_preview()

    def _delete_category(self) -> None:
        if self.selected_category_index is None:
            return
        category = self.categories[self.selected_category_index]
        if not messagebox.askyesno(self.t("categories.delete_title"), self.t("categories.delete_confirm", name=category.name)):
            return
        del self.categories[self.selected_category_index]
        self.selected_category_index = None
        self._refresh_category_list()
        self._new_category()
        self._mark_dirty()
        self._update_preview()

    # ---------------------------------------------------------------------
    # Files, preview, language, save and generation
    # ---------------------------------------------------------------------
    def _choose_color(self, key: str, swatch=None) -> None:
        initial = f"#{normalize_hex(str(self.vars[key].get()))}"
        chosen = colorchooser.askcolor(color=initial, title=self.t("layout.choose_color"))
        if chosen and chosen[1]:
            value = chosen[1].replace("#", "").upper()
            self.vars[key].set(value)
            if swatch is not None:
                swatch.configure(text=f"#{value}", fg_color=f"#{value}")
            self._update_layout_helpers()

    def _browse_image(self, key: str) -> None:
        path = filedialog.askopenfilename(
            title=self.t("dialogs.image_title"),
            filetypes=[(self.t("dialogs.image_files"), "*.png *.jpg *.jpeg *.webp *.ico"), (self.t("dialogs.all_files"), "*.*")],
        )
        if path:
            self.vars[key].set(path)
            self._update_layout_helpers()

    def _update_output_extension(self) -> None:
        """Adjust output suffix when the user changes DOCX/PDF format."""
        path = Path(str(self.vars["output_path"].get()) or "bingo_cards")
        fmt = str(self.vars["output_format"].get()).lower()
        suffix = ".pdf" if fmt == "pdf" else ".docx"
        if path.suffix.lower() not in {".pdf", ".docx"} or path.suffix.lower() != suffix:
            self.vars["output_path"].set(str(path.with_suffix(suffix)))

    def _browse_output(self) -> None:
        fmt = str(self.vars["output_format"].get()).lower()
        default_ext = ".pdf" if fmt == "pdf" else ".docx"
        filetypes = [(self.t("dialogs.pdf_doc"), "*.pdf"), (self.t("dialogs.word_doc"), "*.docx"), (self.t("dialogs.all_files"), "*.*")]
        path = filedialog.asksaveasfilename(title=self.t("dialogs.output_title"), defaultextension=default_ext, filetypes=filetypes)
        if path:
            self.vars["output_path"].set(path)
            suffix = Path(path).suffix.lower()
            if suffix == ".pdf":
                self.vars["output_format"].set("pdf")
            elif suffix == ".docx":
                self.vars["output_format"].set("docx")

    def _change_language(self, selected_display_name: str) -> None:
        display_to_code = self._language_display_map()
        lang_code = display_to_code.get(selected_display_name)
        if not lang_code:
            return
        self._commit_category_editor_to_memory(refresh_list=False, strict=False)
        try:
            self.settings = self._current_settings_from_ui()
        except Exception:
            pass
        self.settings.language = lang_code
        self.i18n.set_language(lang_code)
        self.config_manager.save_settings(self.settings)

        # Rebuild all tabs so every label switches language immediately.
        self._tracking_enabled = False
        for child in self.winfo_children():
            child.destroy()
        self._create_variables()
        self._build_ui()
        self._attach_dirty_tracking()
        self._refresh_category_list()
        self._update_preview()

    def _update_layout_helpers(self) -> None:
        if hasattr(self, "layout_sketch"):
            self.layout_sketch.draw()
        if hasattr(self, "tabs") and self.tabs.get() == self._tab_names.get("preview"):
            self._update_preview()

    def _save_all(self) -> bool:
        """Save settings and category JSON files. Returns True on success."""
        try:
            # If the category editor currently contains an existing category, keep
            # its in-memory value in sync before writing all JSON files.
            if not self._commit_category_editor_to_memory(refresh_list=True, strict=True):
                return False

            self.settings = self._current_settings_from_ui()
            self.settings.validate()
            for category in self.categories:
                category.validate(self.settings.grid_cells)
            self.config_manager.save_settings(self.settings)
            self.config_manager.save_all_categories(self.categories)
            self._dirty = False
            self.status_label.configure(text=self.t("app.saved"))
            return True
        except Exception as exc:
            messagebox.showerror(self.t("dialogs.save_error"), str(exc))
            return False

    def _change_zoom(self, delta: float) -> None:
        value = max(0.45, min(2.0, float(self.preview_zoom.get()) + delta))
        self.preview_zoom.set(value)
        self._update_preview()

    def _update_preview(self) -> None:
        """Render a fresh preview image and place it on the scrollable canvas."""
        self._commit_category_editor_to_memory(refresh_list=False, strict=False)
        try:
            settings = self._current_settings_from_ui()
            settings.validate()
            preview_settings = GameSettings.from_dict(settings.to_dict())
            preview_settings.number_of_cards = 1
            sample = generate_cards(self.categories, preview_settings, seed=42)[0]
        except Exception:
            settings = self.settings
            sample = [f"Frage {i + 1}" for i in range(settings.grid_cells)]

        width_px = int(794 * float(self.preview_zoom.get()))
        img = PreviewRenderer(settings).render(sample_card=sample, width_px=max(320, width_px))
        self.preview_photo = ImageTk.PhotoImage(img)
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.delete("all")
            self.preview_image_id = self.preview_canvas.create_image(0, 0, image=self.preview_photo, anchor="nw")
            self.preview_canvas.configure(scrollregion=(0, 0, img.width, img.height))
            self._center_preview_image()
        self._update_layout_helpers_safely()

    def _center_preview_image(self) -> None:
        """Center the preview image if it is smaller than the visible canvas."""
        if not hasattr(self, "preview_canvas") or self.preview_photo is None or self.preview_image_id is None:
            return
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        iw = self.preview_photo.width()
        ih = self.preview_photo.height()
        x = max(0, (cw - iw) // 2)
        y = max(0, (ch - ih) // 2)
        self.preview_canvas.coords(self.preview_image_id, x, y)
        self.preview_canvas.configure(scrollregion=(0, 0, max(iw, cw), max(ih, ch)))

    def _update_layout_helpers_safely(self) -> None:
        if hasattr(self, "layout_sketch"):
            try:
                self.layout_sketch.draw()
            except Exception:
                pass

    def _generate_document(self) -> None:
        try:
            if not self._commit_category_editor_to_memory(refresh_list=True, strict=True):
                return
            self.settings = self._current_settings_from_ui()
            self.settings.validate()
            self.config_manager.save_settings(self.settings)
            self.config_manager.save_all_categories(self.categories)
            cards = generate_cards(self.categories, self.settings)
            output = export_cards(cards, self.settings)
            self._dirty = False
        except DeckGenerationError as exc:
            messagebox.showerror(self.t("dialogs.generation_error"), str(exc))
            return
        except ExportError as exc:
            messagebox.showerror(self.t("dialogs.export_error"), str(exc))
            return
        except Exception as exc:
            messagebox.showerror(self.t("dialogs.create_error"), str(exc))
            return

        self.status_label.configure(text=self.t("app.done", output=output))
        messagebox.showinfo(self.t("app.done_title"), self.t("app.done_message", output=output))

    def _on_close(self) -> None:
        """Ask whether unsaved changes should be saved before closing."""
        if self._dirty:
            result = messagebox.askyesnocancel(self.t("dialogs.unsaved_title"), self.t("dialogs.unsaved_message"))
            if result is None:
                return
            if result is True and not self._save_all():
                return
        self.destroy()

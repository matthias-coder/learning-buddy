"""Kessler-Family-Design-System: zentrale Token für Farben, Typografie, Spacing.

Quelle: kessler-family-design-system/project/colors_and_type.css (Anthropic-inspirierte
paper-and-ink Wärme mit Clay-Terracotta-Primary und Tea-Green-Accent).
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

from ..resources import assets_dir

FONTS_DIR = assets_dir() / "fonts"


class Color:
    # Paper — warm neutral spine
    PAPER_50  = "#faf7f2"
    PAPER_100 = "#f4efe6"
    PAPER_200 = "#ebe3d5"
    PAPER_300 = "#d8cdb8"
    PAPER_400 = "#a89e89"
    PAPER_500 = "#6f6757"
    PAPER_600 = "#4a4538"
    PAPER_700 = "#2f2b22"
    PAPER_800 = "#1e1b15"
    PAPER_900 = "#13110c"
    BG_ELEVATED = "#fffdf8"

    # Clay — primary (terracotta)
    CLAY_50  = "#fbf1ea"
    CLAY_100 = "#f6ddc9"
    CLAY_200 = "#eebf9c"
    CLAY_300 = "#e29f6e"
    CLAY_400 = "#d58151"
    CLAY_500 = "#c26a3d"
    CLAY_600 = "#a25431"
    CLAY_700 = "#7e4025"

    # Tea — secondary (matcha)
    TEA_50  = "#eef3e8"
    TEA_100 = "#dde8d0"
    TEA_200 = "#bdd1a4"
    TEA_300 = "#9bba7b"
    TEA_400 = "#7ea25d"
    TEA_500 = "#658a47"
    TEA_600 = "#506f39"
    TEA_700 = "#3e552d"

    # Supporting
    SKY_400  = "#7ea8b8"
    SKY_500  = "#5f8b9d"
    ROSE_400 = "#c77270"
    ROSE_500 = "#a8524f"
    HONEY_400 = "#dfb968"
    HONEY_500 = "#c79d44"


# Semantic mapping
class Semantic:
    BG          = Color.PAPER_50
    BG_ELEVATED = Color.BG_ELEVATED
    BG_SUNKEN   = Color.PAPER_100
    FG          = Color.PAPER_800
    FG_MUTED    = Color.PAPER_500
    FG_SUBTLE   = Color.PAPER_400
    FG_STRONG   = Color.PAPER_900
    BORDER      = Color.PAPER_300
    BORDER_SUBTLE = Color.PAPER_200
    BORDER_STRONG = Color.PAPER_400
    ACCENT      = Color.CLAY_500
    ACCENT_HOVER = Color.CLAY_600
    ACCENT_2    = Color.TEA_500
    ACCENT_2_HOVER = Color.TEA_600
    SUCCESS     = Color.TEA_500
    WARNING     = Color.HONEY_500
    DANGER      = Color.ROSE_500
    INFO        = Color.SKY_500
    LINK        = Color.CLAY_600


class Radius:
    XS = 4
    SM = 6
    MD = 10
    LG = 16
    XL = 24
    PILL = 999


class Spacing:
    """4px base scale."""
    S1 = 4
    S2 = 8
    S3 = 12
    S4 = 16
    S5 = 24
    S6 = 32
    S7 = 40
    S8 = 48
    S9 = 64
    S10 = 96


class FontFamily:
    DISPLAY = "Fraunces"
    BODY = "Inter"
    MONO = "IBM Plex Mono"


class FontSize:
    """Modular scale, in pt for Qt (Qt uses pt by default)."""
    XS   = 9
    SM   = 10
    BASE = 11
    MD   = 12
    LG   = 14
    XL   = 17
    XXL  = 22
    XXXL = 28
    XXXXL = 40


def load_fonts() -> dict[str, int]:
    """Lade alle Kessler-Fonts in QFontDatabase. Aufrufen NACH QApplication-Erstellung.
    Gibt zurück: dict mit family-Namen → erster gefundener font_id."""
    loaded: dict[str, int] = {}
    if not FONTS_DIR.exists():
        return loaded
    for path in sorted(FONTS_DIR.glob("*.woff2")):
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid < 0:
            continue
        for fam in QFontDatabase.applicationFontFamilies(fid):
            loaded.setdefault(fam, fid)
    return loaded


def display_font(size: int, *, weight: int = QFont.Weight.Normal, italic: bool = False) -> QFont:
    f = QFont(FontFamily.DISPLAY)
    f.setPointSize(size)
    f.setWeight(weight)
    f.setItalic(italic)
    return f


def body_font(size: int = FontSize.BASE, *, weight: int = QFont.Weight.Normal) -> QFont:
    f = QFont(FontFamily.BODY)
    f.setPointSize(size)
    f.setWeight(weight)
    return f


def mono_font(size: int = FontSize.SM) -> QFont:
    f = QFont(FontFamily.MONO)
    f.setPointSize(size)
    return f


def qcolor(hex_str: str) -> QColor:
    return QColor(hex_str)

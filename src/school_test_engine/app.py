from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from .storage import connect, run_migrations
from .ui.design import FontFamily, FontSize, load_fonts
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("School Test Engine")
    app.setApplicationDisplayName("Übungstests")

    icon_path = Path(__file__).resolve().parents[2] / "assets" / "logomark.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Kessler-Fonts laden (Fraunces / Inter / IBM Plex Mono) und Inter als Default setzen
    load_fonts()
    default_font = QFont(FontFamily.BODY)
    default_font.setPointSize(FontSize.BASE)
    app.setFont(default_font)

    conn = connect()
    run_migrations(conn)

    window = MainWindow(conn)
    window.resize(960, 720)
    window.show_profile_picker()
    window.show()
    return app.exec()

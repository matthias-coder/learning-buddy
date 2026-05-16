from __future__ import annotations

import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from .storage import connect, run_migrations
from .ui.design import FontFamily, FontSize, load_fonts
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Learning Buddy")
    app.setApplicationDisplayName("Learning Buddy")
    app.setOrganizationName("Matthias Kessler")

    from .resources import assets_dir
    icon_path = assets_dir() / "logomark.svg"
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
    window.setMinimumSize(QSize(1024, 600))
    window.resize(QSize(1280, 800))
    window.show_profile_picker()
    window.show()
    return app.exec()

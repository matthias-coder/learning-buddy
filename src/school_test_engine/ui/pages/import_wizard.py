from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...importer.json_import import ImportError as TestImportError
from ...importer.json_import import import_from_file
from ..design import FontFamily
from ..widgets.eyebrow import Eyebrow


class ImportPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        outer_wrap = QVBoxLayout(self)
        outer_wrap.setContentsMargins(0, 0, 0, 0)
        outer_wrap.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_wrap.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        layout.addWidget(Eyebrow("Aufgaben"))
        title = QLabel("Test einlesen")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 30, QFont.Weight.Normal))
        layout.addWidget(title)

        info = QLabel(
            "Wähle eine JSON-Datei, die du dir z.B. mit Claude, ChatGPT oder Gemini "
            "erzeugen lässt. Die Vorlage für den KI-Prompt findest du in "
            "<i>examples/PROMPT-FOR-AI.md</i>."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #4a4538;")
        layout.addWidget(info)

        choose = QPushButton("Datei auswählen …")
        choose.setObjectName("primary")
        choose.clicked.connect(self._pick_file)
        layout.addWidget(choose)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: monospace; font-size: 11pt;")
        layout.addWidget(self.log, stretch=1)

        bottom = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.clicked.connect(window.show_menu)
        bottom.addWidget(back)
        bottom.addStretch(1)
        layout.addLayout(bottom)

    def _pick_file(self) -> None:
        examples = Path(__file__).resolve().parents[3] / "examples"
        start_dir = str(examples) if examples.exists() else str(Path.home())
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Test-JSON wählen", start_dir, "JSON-Dateien (*.json)"
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            test_id = import_from_file(self.conn, path, self.window.active_user_id)
        except TestImportError as e:
            self.log.append(f"❌ {path.name}\n{e}\n")
            QMessageBox.warning(self, "Import fehlgeschlagen", str(e))
            return
        self.log.append(f"✅ {path.name} eingelesen (test_id={test_id})\n")
        QMessageBox.information(
            self,
            "Eingelesen",
            f"'{path.name}' liegt jetzt in der Übungs-Bibliothek — "
            "starte ihn über 'Üben' im Hauptmenü.",
        )

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

from PySide6.QtWidgets import QApplication, QPlainTextEdit

from ...importer.json_import import ImportError as TestImportError
from ...importer.json_import import import_from_file, import_from_string
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
            "Erzeuge dir den Test mit Claude, ChatGPT oder Gemini. "
            "Die Vorlage für den KI-Prompt findest du in <i>examples/PROMPT-FOR-AI.md</i>."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #4a4538;")
        layout.addWidget(info)

        # Option 1: JSON-Datei
        layout.addWidget(Eyebrow("AUS DATEI"))
        choose = QPushButton("Datei auswählen …")
        choose.setObjectName("primary")
        choose.clicked.connect(self._pick_file)
        layout.addWidget(choose)

        # Option 2: JSON aus Zwischenablage einfügen
        layout.addWidget(Eyebrow("ODER AUS ZWISCHENABLAGE"))
        self.paste_edit = QPlainTextEdit()
        self.paste_edit.setPlaceholderText("JSON hier einfügen (Strg+V) …")
        self.paste_edit.setStyleSheet("font-family: monospace; font-size: 10pt;")
        self.paste_edit.setMinimumHeight(160)
        layout.addWidget(self.paste_edit)

        paste_row = QHBoxLayout()
        paste_from_clipboard = QPushButton("Aus Zwischenablage einfügen")
        paste_from_clipboard.setObjectName("text")
        paste_from_clipboard.clicked.connect(self._paste_from_clipboard)
        paste_row.addWidget(paste_from_clipboard)
        paste_row.addStretch(1)
        import_text_btn = QPushButton("Importieren")
        import_text_btn.setObjectName("primary")
        import_text_btn.clicked.connect(self._import_text)
        paste_row.addWidget(import_text_btn)
        layout.addLayout(paste_row)

        layout.addWidget(Eyebrow("STATUS"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: monospace; font-size: 11pt;")
        self.log.setMinimumHeight(80)
        layout.addWidget(self.log, stretch=1)

        bottom = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
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

    def _paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            QMessageBox.information(
                self, "Zwischenablage leer",
                "Es ist kein Text in der Zwischenablage.",
            )
            return
        self.paste_edit.setPlainText(text)

    def _import_text(self) -> None:
        source = self.paste_edit.toPlainText().strip()
        if not source:
            QMessageBox.information(
                self, "Kein JSON",
                "Füge erst ein JSON in das Textfeld ein.",
            )
            return
        try:
            test_id = import_from_string(self.conn, source, self.window.active_user_id)
        except TestImportError as e:
            self.log.append(f"❌ Eingefügtes JSON\n{e}\n")
            QMessageBox.warning(self, "Import fehlgeschlagen", str(e))
            return
        self.log.append(f"✅ Eingefügtes JSON eingelesen (test_id={test_id})\n")
        self.paste_edit.clear()
        QMessageBox.information(
            self,
            "Eingelesen",
            "Der Test liegt jetzt in der Übungs-Bibliothek — "
            "starte ihn über 'Üben' im Hauptmenü.",
        )

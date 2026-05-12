from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..design import FontFamily
from ..widgets.eyebrow import Eyebrow


class ReviewPage(QWidget):
    """Übersichts-Screen vor dem endgültigen Abgeben."""

    COLUMNS = 4

    def __init__(self, window):
        super().__init__()
        self.window = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        layout.addWidget(Eyebrow("Übersicht"))
        title = QLabel("Bereit zum Abgeben?")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(title)

        self.summary = QLabel()
        self.summary.setStyleSheet("color: #4a4538; font-size: 12pt;")
        layout.addWidget(self.summary)

        legend = QLabel("🟢  beantwortet  ·  ⚪  noch offen  ·  🚩  markiert")
        legend.setStyleSheet("color: #6f6757; font-size: 10pt;")
        layout.addWidget(legend)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll, stretch=1)

        bottom = QHBoxLayout()
        back = QPushButton("← Weiter üben")
        back.clicked.connect(self._back_to_runner)
        bottom.addWidget(back)
        bottom.addStretch(1)
        submit = QPushButton("Abgeben ✓")
        submit.setObjectName("primary")
        submit.clicked.connect(self._submit)
        bottom.addWidget(submit)
        layout.addLayout(bottom)

    def show_for_attempt(self) -> None:
        items = self.window.runner_page.get_status_overview()
        answered = sum(1 for it in items if it["answered"])
        marked = sum(1 for it in items if it["marked"])
        open_count = len(items) - answered
        self.summary.setText(
            f"{answered} beantwortet · {open_count} offen · {marked} markiert"
        )
        self._render_grid(items)

    def _render_grid(self, items: list[dict]) -> None:
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

        for pos, it in enumerate(items):
            tile = self._make_tile(it)
            row, col = divmod(pos, self.COLUMNS)
            self.grid.addWidget(tile, row, col)

    def _make_tile(self, item: dict) -> QPushButton:
        # Status-Icon: rotes ⚪ wenn nicht beantwortet, 🟢 wenn beantwortet.
        # 🚩 zusätzlich wenn markiert.
        status = "🟢" if item["answered"] else "⚪"
        marker = " 🚩" if item["marked"] else ""
        topic_short = item["topic"]
        if len(topic_short) > 30:
            topic_short = topic_short[:27] + "…"
        text = f"{status}{marker}\n#{item['index'] + 1}  {topic_short}\n{item['points']} P."
        btn = QPushButton(text)
        btn.setMinimumHeight(90)
        # Kessler: tea (beantwortet) / honey (markiert) / paper (offen)
        if item["answered"]:
            color = "#dde8d0" if not item["marked"] else "#f6ddc9"
            border = "#658a47" if not item["marked"] else "#c79d44"
        else:
            color = "#f4efe6" if not item["marked"] else "#f6ddc9"
            border = "#a89e89" if not item["marked"] else "#c79d44"
        btn.setStyleSheet(
            f"text-align: left; padding: 8px; background: {color}; "
            f"border: 2px solid {border}; border-radius: 6px;"
        )
        btn.clicked.connect(lambda _=False, idx=item["index"]: self._jump(idx))
        return btn

    def _jump(self, index: int) -> None:
        self.window.jump_to_question(index)

    def _back_to_runner(self) -> None:
        self.window.back_to_runner()

    def _submit(self) -> None:
        items = self.window.runner_page.get_status_overview()
        open_count = sum(1 for it in items if not it["answered"])
        if open_count > 0:
            reply = QMessageBox.question(
                self,
                "Test abgeben?",
                f"Noch {open_count} Frage(n) offen — trotzdem abgeben?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.window.runner_page.submit_final()

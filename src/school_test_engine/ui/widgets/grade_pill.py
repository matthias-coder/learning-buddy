from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ...grading.grade_labels import grade_label
from .._subjects import note_color


def GradePill(grade: float, *, size: int = 56, parent=None) -> QLabel:
    """Circular note display. Color follows _subjects.note_color() based on rounded grade.

    `grade` may be fractional (e.g. 2.5). Display formats:
      - tendencies: "2+", "2" , "2−" (see grading.grade_labels)
      - legacy half step: "2–3"
    """
    rounded = max(1, min(6, int(round(grade))))
    bg = note_color(rounded)
    text = grade_label(grade)
    lbl = QLabel(text, parent)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background: {bg}; color: #f6f1e6; "
        f"font-family: 'Fraunces'; font-size: {int(size * 0.45)}pt; "
        f"font-weight: 500; border-radius: {size // 2}px;"
    )
    return lbl

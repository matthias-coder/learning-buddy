"""Pure mapping between German grade labels (with tendencies) and decimal values.

"+" = -0.25, "−" (real minus sign) = +0.25. Legacy half steps (x.5) are
displayed as "2–3" (en dash).
"""
from __future__ import annotations

MINUS = "−"
EN_DASH = "–"


def _build_options() -> list[tuple[str, float]]:
    opts: list[tuple[str, float]] = []
    for n in range(1, 7):
        if n > 1:
            opts.append((f"{n}+", n - 0.25))
        opts.append((str(n), float(n)))
        if n < 6:
            opts.append((f"{n}{MINUS}", n + 0.25))
    return opts


GRADE_OPTIONS: list[tuple[str, float]] = _build_options()
# 1+ and 6− do not exist, but 1− and 6+ do; _build_options yields exactly 16.
_BY_LABEL = {label: value for label, value in GRADE_OPTIONS}


def clamp_grade(value: float) -> float:
    return max(1.0, min(6.0, float(value)))


def grade_label(value: float) -> str:
    """Display label for a stored grade value."""
    v = clamp_grade(value)
    for label, val in GRADE_OPTIONS:
        if abs(val - v) < 0.01:
            return label
    base = int(v)
    if abs(v - base - 0.5) < 0.01 and base < 6:
        return f"{base}{EN_DASH}{base + 1}"
    return f"{v:.2f}".replace(".", ",")


def label_to_value(label: str) -> float:
    if label in _BY_LABEL:
        return _BY_LABEL[label]
    if EN_DASH in label:
        return int(label.split(EN_DASH)[0]) + 0.5
    raise ValueError(f"unknown grade label: {label!r}")

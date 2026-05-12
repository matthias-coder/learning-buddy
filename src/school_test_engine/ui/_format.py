"""Formatier-Helpers für die UI (Zahlen + Daten).

Drei Pages hatten kopierte `_fmt`/`_fmt_dt`-Varianten — hier zentralisiert.
"""
from __future__ import annotations

from datetime import datetime


def fmt_num(x: float | int | None) -> str:
    if x is None:
        return "0"
    f = float(x)
    return str(int(f)) if f.is_integer() else f"{f:.2f}"


def fmt_dt(iso: str | None, *, with_time: bool = False, fallback: str = "—") -> str:
    if not iso:
        return fallback
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return iso
    return dt.strftime("%d.%m.%Y · %H:%M") if with_time else dt.strftime("%d.%m.%Y")

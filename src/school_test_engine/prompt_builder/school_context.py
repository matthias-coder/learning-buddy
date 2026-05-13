from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ui._layouts import row_get


BUNDESLAENDER = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen",
]


SCHOOL_TYPES = ["Hauptschule", "Realschule", "Gymnasium"]


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SchoolContext:
    grade: int | None
    school_type: str | None
    bundesland: str | None
    school_name: str | None
    school_year: str | None

    @classmethod
    def from_user_row(cls, row: Any | None) -> "SchoolContext":
        if row is None:
            return cls(None, None, None, None, None)
        return cls(
            grade=_coerce_int(row_get(row, "grade")),
            school_type=row_get(row, "school_type"),
            bundesland=row_get(row, "bundesland"),
            school_name=row_get(row, "school_name"),
            school_year=row_get(row, "school_year"),
        )

    def is_minimally_complete(self) -> bool:
        """True when both grade and school_type are set — the pair required to
        produce a sensible AI prompt."""
        return self.grade is not None and bool(self.school_type)

"""Phase 14 Track D: Render a current grade report PDF for one user."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import date
from html import escape

from ..cockpit import service as cockpit
from ..storage import assessments_repo, users_repo
from ._common import html_header, html_footer


CATEGORY_LABEL = {
    "schriftlich": "schriftlich",
    "muendlich": "mündlich",
    "sonstige": "sonstige",
}


def _row_get(row, key, default=None):
    if row is None:
        return default
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def _fmt_avg(val) -> str:
    if val is None:
        return "—"
    return f"{val:.2f}".replace(".", ",")


def _render_chart_png(rows) -> str | None:
    """Render a GradeChart with this subject's data to a temp PNG file.
    Returns the file path or None if no chart could be rendered."""
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return None
        from ..ui.widgets.grade_chart import GradeChart
        from datetime import date as _date
        schriftlich = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "schriftlich"
        ]
        muendlich = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "muendlich"
        ]
        if len(schriftlich) + len(muendlich) < 2:
            return None
        chart = GradeChart()
        chart.resize(600, 220)
        chart.set_data(schriftlich=schriftlich, muendlich=muendlich)
        pixmap = chart.grab()
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        pixmap.save(tmp.name, "PNG")
        return tmp.name
    except Exception:
        return None


def export_grade_report(conn: sqlite3.Connection, user_id: int) -> str:
    user = users_repo.get_user(conn, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    name = user["name"]
    school_name = _row_get(user, "school_name", "")
    grade_klass = _row_get(user, "grade")
    school_year = _row_get(user, "school_year", "")
    school_line_parts: list[str] = []
    if school_name:
        school_line_parts.append(escape(school_name))
    if grade_klass:
        school_line_parts.append(f"Klasse {int(grade_klass)}")
    if school_year:
        school_line_parts.append(f"Schuljahr {escape(school_year)}")
    school_line = " · ".join(school_line_parts)

    today_str = date.today().strftime("%d.%m.%Y")
    parts = [
        html_header(f"{escape(name)} — Notenübersicht"),
        f"<div class='eyebrow'>STAND: {escape(today_str)}</div>",
    ]
    if school_line:
        parts.append(f"<p>{school_line}</p>")

    # Fetch all subjects with at least one assessment
    subjects = [
        row["subject"]
        for row in conn.execute(
            "SELECT DISTINCT subject FROM assessments WHERE user_id = ? ORDER BY subject",
            (user_id,),
        ).fetchall()
    ]

    if not subjects:
        parts.append("<p>Noch keine Noten erfasst.</p>")
        parts.append(html_footer())
        return "".join(parts)

    for subject in subjects:
        rows = assessments_repo.list_by_subject(conn, user_id, subject)
        if not rows:
            continue
        avg = cockpit.subject_grade_average(conn, user_id, subject)
        zeugnis = "—" if avg.zeugnis_estimate is None else f"{avg.zeugnis_estimate:.2f}".replace(".", ",")
        breakdown = (
            f"schriftlich {_fmt_avg(avg.schriftlich_avg)} · "
            f"mündlich {_fmt_avg(avg.muendlich_avg)}"
        )
        parts.append(f"<h2>{escape(subject)}</h2>")
        parts.append(
            f"<p><span style='font-family:Fraunces;font-size:28pt'>{zeugnis}</span><br/>"
            f"<span class='eyebrow'>ZEUGNIS-SCHÄTZUNG</span> &nbsp; {breakdown}</p>"
        )
        chart_path = _render_chart_png(rows)
        if chart_path:
            parts.append(f"<p><img src='file://{chart_path}' width='480' /></p>")
        parts.append("<table>")
        parts.append("<tr><th>Datum</th><th>Art</th><th>Note</th><th>Notiz</th></tr>")
        for r in rows:
            cat = CATEGORY_LABEL.get(r["category"], r["category"])
            grade_str = f"{r['grade']:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            note = r["note"] or ""
            parts.append(
                f"<tr><td>{r['assessment_date']}</td><td>{escape(cat)}</td>"
                f"<td>{grade_str}</td><td>{escape(note)}</td></tr>"
            )
        parts.append("</table>")

    parts.append(html_footer())
    return "".join(parts)

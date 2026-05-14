"""Phase 14 Track D: Render a test as a printable worksheet + solutions page."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from html import escape

from ._common import html_footer, html_header


def export_test_sheet(conn: sqlite3.Connection, test_id: int) -> str:
    """Render a test as a printable worksheet HTML.

    Two-section layout: questions on page 1+, solutions on a separate page.
    The questions table stores choices and correct answers in a JSON ``payload``
    column, and question type in the ``type`` column
    (``single_choice`` | ``multi_choice`` | ``short_answer``).
    """
    test_row = conn.execute(
        "SELECT * FROM tests WHERE id = ?", (test_id,)
    ).fetchone()
    if test_row is None:
        raise ValueError(f"Test {test_id} not found")

    subject = test_row["subject"]
    today_str = date.today().strftime("%d.%m.%Y")

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position ASC",
        (test_id,),
    ).fetchall()

    parts = [
        html_header(f"{escape(subject)} · Übungs-Test"),
        f"<div class='eyebrow'>{escape(today_str)}</div>",
        "<p>Name: <span class='answer-line'></span> &nbsp;&nbsp; "
        "Klasse: <span class='answer-line'></span></p>",
    ]

    # Page 1+: questions
    for i, q in enumerate(questions, start=1):
        q_type = q["type"]
        payload = json.loads(q["payload"])

        parts.append("<div class='question'>")
        parts.append(f"<span class='num'>{i}.</span> {escape(q['prompt'])}<br/>")

        if q_type in ("single_choice", "multi_choice"):
            for choice in payload.get("choices", []):
                parts.append(
                    f"<span class='option-bullet'>○</span> {escape(choice['text'])}<br/>"
                )
        else:  # short_answer
            parts.append("<span class='answer-line'></span><br/><br/>")
            parts.append("<span class='answer-line'></span>")

        parts.append("</div>")

    # Page break → solutions
    parts.append("<div style='page-break-before: always;'>")
    parts.append("<h2>Lösungen</h2>")

    for i, q in enumerate(questions, start=1):
        q_type = q["type"]
        payload = json.loads(q["payload"])

        if q_type in ("single_choice", "multi_choice"):
            correct_ids = set(payload.get("correct", []))
            choices_by_id = {c["id"]: c["text"] for c in payload.get("choices", [])}
            answer = ", ".join(
                escape(choices_by_id[cid])
                for cid in payload.get("correct", [])
                if cid in choices_by_id
            )
        else:  # short_answer
            accepted = payload.get("accepted_answers", [])
            answer = escape(accepted[0]) if accepted else ""

        parts.append(f"<p><span class='num'>{i}.</span> {answer}</p>")

    parts.append("</div>")
    parts.append(html_footer())
    return "".join(parts)

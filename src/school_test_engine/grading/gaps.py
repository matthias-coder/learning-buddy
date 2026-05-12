from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

Trend = Literal["up", "down", "flat", "none"]


@dataclass
class TopicStat:
    topic: str
    earned: float
    possible: float
    percent: float
    n_answers: int
    subject: str = ""
    trend: Trend = "none"
    history: list[float] = field(default_factory=list)


def topic_stats_from_rows(rows: Iterable) -> list[TopicStat]:
    out: list[TopicStat] = []
    for r in rows:
        possible = float(r["possible"] or 0)
        earned = float(r["earned"] or 0)
        percent = (earned / possible * 100.0) if possible > 0 else 0.0
        try:
            subject = r["subject"]
        except (IndexError, KeyError):
            subject = ""
        out.append(
            TopicStat(
                topic=r["topic"],
                earned=earned,
                possible=possible,
                percent=percent,
                n_answers=int(r["n_answers"]),
                subject=subject or "",
            )
        )
    return out


def apply_trend(stats: list[TopicStat], history_rows: Iterable) -> list[TopicStat]:
    """Reichere stats mit Trend-Info aus per-Versuch-Verlauf an."""
    per_topic: dict[str, list[float]] = {}
    for r in history_rows:
        topic = r["topic"]
        possible = float(r["possible"] or 0)
        earned = float(r["earned"] or 0)
        if possible <= 0:
            continue
        per_topic.setdefault(topic, []).append(earned / possible * 100.0)

    by_topic = {s.topic: s for s in stats}
    for topic, history in per_topic.items():
        if topic not in by_topic:
            continue
        s = by_topic[topic]
        s.history = history
        s.trend = _trend_from_history(history)
    return stats


def _trend_from_history(history: list[float]) -> Trend:
    if len(history) < 2:
        return "none"
    latest = history[-1]
    previous = history[-2]
    diff = latest - previous
    if diff > 5:
        return "up"
    if diff < -5:
        return "down"
    return "flat"


TREND_ARROW: dict[Trend, str] = {
    "up": "↑",
    "down": "↓",
    "flat": "→",
    "none": "",
}

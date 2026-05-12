from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnswerResult:
    question_id: int
    ext_id: str
    response: list[str] | str
    points_earned: float
    points_possible: int
    is_correct: bool


@dataclass
class AttemptResult:
    attempt_id: int
    test_id: int
    title: str
    points_earned: float
    points_possible: int
    percent: float
    note: int
    answers: list[AnswerResult]

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    points_earned: float
    is_correct: bool


def score_single(correct_ids: list[str], response: list[str], points: int) -> ScoreResult:
    if len(response) != 1:
        return ScoreResult(0.0, False)
    is_correct = response[0] == correct_ids[0]
    return ScoreResult(float(points) if is_correct else 0.0, is_correct)


def score_multi(
    correct_ids: list[str],
    response: list[str],
    points: int,
    scoring: str = "partial",
) -> ScoreResult:
    correct_set = set(correct_ids)
    response_set = set(response)

    if scoring == "all_or_nothing":
        is_correct = correct_set == response_set
        return ScoreResult(float(points) if is_correct else 0.0, is_correct)

    total_correct = len(correct_set)
    selected_correct = len(response_set & correct_set)
    selected_incorrect = len(response_set - correct_set)

    fraction = max(0.0, (selected_correct - selected_incorrect) / total_correct)
    earned = round(points * fraction, 2)
    is_fully_correct = correct_set == response_set
    return ScoreResult(earned, is_fully_correct)


def score_short(
    accepted_answers: list[str],
    response: str,
    points: int,
    case_sensitive: bool = False,
    trim_whitespace: bool = True,
) -> ScoreResult:
    candidate = response
    if trim_whitespace:
        candidate = candidate.strip()
    if not case_sensitive:
        candidate = candidate.lower()

    for accepted in accepted_answers:
        target = accepted
        if trim_whitespace:
            target = target.strip()
        if not case_sensitive:
            target = target.lower()
        if candidate == target:
            return ScoreResult(float(points), True)
    return ScoreResult(0.0, False)

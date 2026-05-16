from school_test_engine.error_book.queries import (
    _is_resolved, _consecutive_correct,
)


class _Row:
    def __init__(self, is_correct: int):
        self.is_correct = is_correct


def test_is_resolved_needs_two_recent_correct():
    assert _is_resolved([_Row(1), _Row(1)]) is True
    assert _is_resolved([_Row(1), _Row(0)]) is False
    assert _is_resolved([_Row(0), _Row(1)]) is False
    assert _is_resolved([_Row(1)]) is False  # zu wenige
    assert _is_resolved([]) is False


def test_consecutive_correct_stops_at_first_wrong():
    assert _consecutive_correct([_Row(1), _Row(1), _Row(0), _Row(1)]) == 2
    assert _consecutive_correct([_Row(1), _Row(0)]) == 1
    assert _consecutive_correct([_Row(0), _Row(1)]) == 0
    assert _consecutive_correct([]) == 0

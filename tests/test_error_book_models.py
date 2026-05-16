from school_test_engine.error_book.models import ErrorBookEntry


def test_error_book_entry_is_frozen():
    entry = ErrorBookEntry(
        question_id=42,
        subject="Mathe",
        topic="Bruchrechnung",
        prompt_excerpt="Was ist 1/2 + 1/3?",
        wrong_count=3,
        last_wrong_at="2026-05-12T10:00:00Z",
        consecutive_correct=1,
    )
    import dataclasses
    assert dataclasses.is_dataclass(entry)
    # frozen → AttributeError on mutation
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.wrong_count = 5  # type: ignore

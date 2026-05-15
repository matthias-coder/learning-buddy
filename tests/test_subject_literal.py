"""Phase 15 follow-up: Test.subject Literal must accept the 11 SUBJECTS_ALL entries."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from school_test_engine.models.test import Test
from school_test_engine.ui._subjects import SUBJECTS_ALL


def _minimal_test_payload(subject: str) -> dict:
    return {
        "schema_version": 1,
        "title": "Probe",
        "subject": subject,
        "grade": 8,
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": "X",
                "difficulty": "leicht",
                "points": 1,
                "prompt": "Was?",
                "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correct": ["a"],
            }
        ],
    }


@pytest.mark.parametrize("subject", SUBJECTS_ALL)
def test_subject_literal_accepts_all_subjects_all(subject):
    Test.model_validate(_minimal_test_payload(subject))


def test_subject_literal_rejects_unknown_subject():
    with pytest.raises(ValidationError):
        Test.model_validate(_minimal_test_payload("NichtExistierendesFach"))

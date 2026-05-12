from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Subject = Literal["Mathe", "Englisch", "Bio", "Physik", "Chemie", "Geschichte"]
Difficulty = Literal["leicht", "mittel", "schwer"]
QuestionType = Literal["single_choice", "multi_choice", "short_answer"]


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class _BaseQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    difficulty: Difficulty
    points: int = Field(gt=0)
    prompt: str = Field(min_length=1)
    prompt_math: str | None = None
    explanation: str | None = None


class SingleChoiceQuestion(_BaseQuestion):
    type: Literal["single_choice"]
    choices: list[Choice] = Field(min_length=2)
    correct: list[str] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def _check_correct_ids(self) -> "SingleChoiceQuestion":
        ids = {c.id for c in self.choices}
        if duplicates := _find_duplicate_choice_ids(self.choices):
            raise ValueError(f"choices haben doppelte ids: {duplicates}")
        for ref in self.correct:
            if ref not in ids:
                raise ValueError(f"correct enthält id '{ref}', die nicht in choices vorkommt")
        return self


class MultiChoiceQuestion(_BaseQuestion):
    type: Literal["multi_choice"]
    choices: list[Choice] = Field(min_length=2)
    correct: list[str] = Field(min_length=1)
    scoring: Literal["partial", "all_or_nothing"] = "partial"

    @model_validator(mode="after")
    def _check_correct_ids(self) -> "MultiChoiceQuestion":
        ids = {c.id for c in self.choices}
        if duplicates := _find_duplicate_choice_ids(self.choices):
            raise ValueError(f"choices haben doppelte ids: {duplicates}")
        if len(set(self.correct)) != len(self.correct):
            raise ValueError("correct enthält Duplikate")
        for ref in self.correct:
            if ref not in ids:
                raise ValueError(f"correct enthält id '{ref}', die nicht in choices vorkommt")
        return self


class ShortAnswerQuestion(_BaseQuestion):
    type: Literal["short_answer"]
    accepted_answers: list[str] = Field(min_length=1)
    case_sensitive: bool = False
    trim_whitespace: bool = True


Question = Annotated[
    Union[SingleChoiceQuestion, MultiChoiceQuestion, ShortAnswerQuestion],
    Field(discriminator="type"),
]


def _find_duplicate_choice_ids(choices: list[Choice]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for c in choices:
        if c.id in seen:
            dupes.append(c.id)
        seen.add(c.id)
    return dupes


REALSCHULE_DEFAULT_NOTENSCHLUESSEL: dict[int, int] = {
    1: 92,
    2: 81,
    3: 67,
    4: 50,
    5: 25,
    6: 0,
}


class Test(BaseModel):
    model_config = ConfigDict(extra="forbid")
    __test__ = False  # silence pytest collection warning

    schema_version: Literal[1]
    title: str = Field(min_length=1)
    subject: Subject
    grade: int = Field(ge=1, le=13)
    school_type: str = "Realschule"
    description: str | None = None
    time_limit_minutes: int | None = Field(default=None, gt=0)
    notenschluessel: dict[int, int] | None = None
    questions: list[Question] = Field(min_length=1)

    @field_validator("notenschluessel", mode="before")
    @classmethod
    def _coerce_string_keys(cls, v: object) -> object:
        if isinstance(v, dict):
            return {int(k): val for k, val in v.items()}
        return v

    @model_validator(mode="after")
    def _check_notenschluessel(self) -> "Test":
        if self.notenschluessel is None:
            return self
        for note in (1, 2, 3, 4, 5, 6):
            if note not in self.notenschluessel:
                raise ValueError(f"notenschluessel fehlt Eintrag für Note {note}")
        cutoffs = [self.notenschluessel[n] for n in (1, 2, 3, 4, 5, 6)]
        for cutoff in cutoffs:
            if not 0 <= cutoff <= 100:
                raise ValueError(f"notenschluessel-Cutoff {cutoff} liegt außerhalb 0..100")
        for a, b in zip(cutoffs, cutoffs[1:]):
            if a < b:
                raise ValueError(
                    "notenschluessel: Cutoffs müssen monoton fallend sein (Note 1 > Note 2 > ...)"
                )
        return self

    @model_validator(mode="after")
    def _check_unique_question_ids(self) -> "Test":
        seen: set[str] = set()
        for q in self.questions:
            if q.id in seen:
                raise ValueError(f"question id '{q.id}' kommt mehrfach vor")
            seen.add(q.id)
        return self

    @property
    def total_points(self) -> int:
        return sum(q.points for q in self.questions)

    def effective_notenschluessel(self) -> dict[int, int]:
        return self.notenschluessel or dict(REALSCHULE_DEFAULT_NOTENSCHLUESSEL)

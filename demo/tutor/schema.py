"""The typed contracts. Everything the model returns is parsed through these,
so a malformed lesson fails here rather than three steps later."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Option(BaseModel):
    text: str
    # A distractor is written to represent ONE specific wrong belief. Picking it
    # tells us which belief, which is more than "wrong" ever could. None = the
    # correct option.
    misconception: str | None = None


_POINTS_AT_CODE = re.compile(
    r"\b(following|below|above|given|this|these|shown)\b[^.?]{0,20}\b(code|snippet|program|script)\b",
    re.I)


class Quiz(BaseModel):
    question: str
    code: str | None = None     # shown between the question and the options
    options: list[Option] = Field(min_length=2, max_length=5)
    correct: int
    why: str                    # shown after answering; the quiz teaches too

    @model_validator(mode="after")
    def _one_right_answer_and_tagged_distractors(self):
        # A question that points at code the student cannot see is unanswerable.
        # Rejecting it here sends it through the schema-repair pass.
        if _POINTS_AT_CODE.search(self.question) and not (self.code or "").strip():
            raise ValueError("the question refers to code but `code` is empty")
        if not 0 <= self.correct < len(self.options):
            raise ValueError("correct is not an index into options")
        for i, o in enumerate(self.options):
            if i == self.correct and o.misconception:
                raise ValueError("the correct option must not carry a misconception")
            if i != self.correct and not o.misconception:
                raise ValueError(f"distractor {i} names no misconception")
        return self


class Lesson(BaseModel):
    explanation: str
    citations: list[str]        # must be chunk cites the code handed the model
    diagram: str | None = None  # Mermaid source, rendered by the page
    quiz: Quiz


class Grade(BaseModel):
    """Free-text answers only. MCQ needs no model call: the option chosen IS
    the classification."""
    correct: bool
    misconception: str | None = None
    feedback: str


AnswerMode = Literal["mcq", "text"]


class LearnerModel(BaseModel):
    student_id: str
    mastery: dict[str, float] = {}          # concept -> 0..1
    misconceptions: dict[str, int] = {}     # tag -> times seen
    interests: list[str] = []
    answer_mode: AnswerMode = "mcq"         # the default; free text is opt-in

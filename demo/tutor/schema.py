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


def _code_present(question: str, code: str | None) -> None:
    """A question that points at code the student cannot see is unanswerable.
    Rejecting it here sends it through the schema-repair pass."""
    if _POINTS_AT_CODE.search(question) and not (code or "").strip():
        raise ValueError("the question refers to code but `code` is empty")


class Quiz(BaseModel):
    question: str
    code: str | None = None     # shown between the question and the options
    options: list[Option] = Field(min_length=2, max_length=5)
    correct: int
    why: str                    # shown after answering; the quiz teaches too

    @model_validator(mode="after")
    def _one_right_answer_and_tagged_distractors(self):
        _code_present(self.question, self.code)
        if not 0 <= self.correct < len(self.options):
            raise ValueError("correct is not an index into options")
        for i, o in enumerate(self.options):
            if i == self.correct and o.misconception:
                raise ValueError("the correct option must not carry a misconception")
            if i != self.correct and not o.misconception:
                raise ValueError(f"distractor {i} names no misconception")
        return self


class Mistake(BaseModel):
    belief: str                 # kebab-case tag; the grader picks from these
    sign: str                   # what an answer holding it tends to say


class OpenQuestion(BaseModel):
    """A question answered in the student's own words. Everything but the
    question and code stays on the server: the rubric is how it gets graded."""
    question: str
    code: str | None = None
    rubric: list[str] = Field(min_length=1)     # what a correct answer must contain
    model_answer: str
    common_mistakes: list[Mistake] = []

    @model_validator(mode="after")
    def _self_contained(self):
        _code_present(self.question, self.code)
        return self


class CodeTest(BaseModel):
    """One hidden check on a submitted program. `belief` names the wrong idea a
    failure of THIS test exposes, so failing it is a diagnosis, like a tagged
    distractor."""
    call: str                   # a Python expression using the student's code, e.g. add(2, 3)
    expected: str               # repr() of the right result
    belief: str


class CodeTask(BaseModel):
    """A question answered by writing a program. Only `question` and `starter` reach
    the browser; the tests and the solution stay on the server."""
    question: str
    starter: str = ""
    tests: list[CodeTest] = Field(min_length=1, max_length=6)
    model_solution: str


class Lesson(BaseModel):
    covered: bool = True        # documents mode: the notes really cover the topic
    explanation: str
    citations: list[str] = []   # documents mode: must be chunks the code handed the model
    diagram: str | None = None  # Mermaid source, rendered by the page
    quiz: Quiz | None = None    # exactly one of these two, matching the mode asked for
    open: OpenQuestion | None = None
    code_task: CodeTask | None = None

    @model_validator(mode="after")
    def _one_check(self):
        if sum(x is not None for x in (self.quiz, self.open, self.code_task)) != 1:
            raise ValueError("give exactly one of `quiz`, `open` and `code_task`")
        return self

    @property
    def kind(self) -> str:
        return "mcq" if self.quiz else "text" if self.open else "code"


class Grade(BaseModel):
    """Free-text answers only. MCQ needs no model call: the option chosen IS
    the classification."""
    correct: bool
    misconception: str | None = None
    feedback: str


class PlanDraft(BaseModel):
    """What a topic builds on and what it contains. Ids only, kebab-case: labels are derived
    in code, so a small model has almost nothing to get wrong. Every field is lenient;
    curriculum.clean_plan truncates and canonicalises."""
    target: str = ""            # used only for a pasted exam question: the topic it tests
    prereqs: list[str] = []
    subtopics: list[str] = []


class Probe(BaseModel):
    """A bare check on a prerequisite, asked BEFORE anything is explained."""
    quiz: Quiz


AnswerMode = Literal["mcq", "text", "code"]


class LearnerModel(BaseModel):
    student_id: str
    mastery: dict[str, float] = {}          # concept -> 0..1
    misconceptions: dict[str, int] = {}     # tag -> times seen
    # The same tags, kept per concept, so a new session can start where the last
    # one stumbled instead of at the beginning.
    concept_misconceptions: dict[str, dict[str, int]] = {}
    wrong_answers: dict[str, int] = {}      # every wrong answer, tagged or not
    last_seen: dict[str, float] = {}        # concept -> epoch seconds of last check
    interests: list[str] = []
    # The TYPE of the next question: "mcq" by default, "text" for open questions.
    answer_mode: AnswerMode = "mcq"
    use_docs: bool = False                  # teach from the student's own documents
    recent_questions: dict[str, list[str]] = {}   # concept -> last few stems, so none repeat
    plans: dict[str, dict] = {}             # curriculum.key(topic) -> {"prereqs": [...], "subtopics": [...]}

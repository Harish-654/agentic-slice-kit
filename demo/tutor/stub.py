"""Canned responses, so the whole loop can be proven with no key, no network and
no tokens. Payloads go through the real schemas, so a schema mistake fails here."""
from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel

CITE = "python-notes.md#0"


def lesson(text: str, *, diagram: str | None = None, cites=(CITE,), covered: bool = True) -> str:
    """A lesson whose quiz has one right answer (index 1) and two tagged wrong
    ones: 0 = default-is-copied, 2 = default-is-global."""
    return json.dumps({
        "covered": covered, "explanation": text, "citations": list(cites), "diagram": diagram,
        "open": None,
        "quiz": {"question": "What does f() return the second time it is called?",
                 "options": [{"text": "[1]", "misconception": "default-is-copied"},
                             {"text": "[1, 1]"},
                             {"text": "an error", "misconception": "default-is-global"}],
                 "correct": 1,
                 "why": "The default list is created once, when def runs, and shared."},
    })


def open_lesson(text: str, *, cites=(CITE,), covered: bool = True) -> str:
    """The same topic asked as a written question, graded against a rubric."""
    return json.dumps({
        "covered": covered, "explanation": text, "citations": list(cites), "diagram": None,
        "quiz": None,
        "open": {"question": "Why does f() remember earlier calls?", "code": None,
                 "rubric": ["the default list is created once", "later calls share it"],
                 "model_answer": "The default is built when def runs, so every call reuses it.",
                 "common_mistakes": [{"belief": "default-is-copied",
                                      "sign": "says each call gets a fresh list"}]},
    })


def grade(correct: bool, misconception: str | None, feedback: str = "ok") -> str:
    return json.dumps({"correct": correct, "misconception": misconception, "feedback": feedback})


class Stub:
    """A drop-in for slice.llm.complete. Same keyword signature, no network."""

    def __init__(self, script: dict[str, list[str]]) -> None:
        self.script, self.calls, self.messages, self._n = script, [], [], {}
        self.reasoning: list = []               # what each call asked of the model

    def __call__(self, *, settings, budget, messages, schema: Type[BaseModel] | None = None,
                 model: str | None = None, step: str = "call", timeout: float = 120.0,
                 reasoning: bool | None = None) -> Any:
        base = step.split(":")[0]
        i = self._n.get(base, 0)
        self._n[base] = i + 1
        self.calls.append(step)
        self.messages.append(messages)
        self.reasoning.append(reasoning)
        try:
            raw = self.script[base][i]
        except (KeyError, IndexError):
            raise AssertionError(
                f"stub has no scripted reply {i} for step {step!r}. The flow made a call "
                "the script did not expect - usually the finding, not a stub problem.")
        budget.record_tokens(len(raw) // 4)
        return schema.model_validate_json(raw) if schema else raw

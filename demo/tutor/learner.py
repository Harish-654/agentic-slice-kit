"""The learner model's rules. Pure functions, no model and no database, so every
decision about what a student is taught next can be tested in microseconds."""
from __future__ import annotations

import re

from .schema import LearnerModel

MASTERY = 0.75
START = 0.3                     # unknown is not zero: they may know a little
MAX_CHECKS = 8                  # quiz items per session
# Explanation styles, tried in order per concept. A wrong answer means the last
# explanation did not land, and repeating it louder is the failure to avoid.
STYLES = ("plain", "analogy", "worked_example", "diagram")


def slug(tag: str | None) -> str | None:
    """Free-text graders phrase the same wrong belief many ways; keep the tag
    stable enough to count."""
    if not tag:
        return None
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-") or None


def pick_concept(m: LearnerModel, concepts: list[str]) -> str | None:
    """Weakest unmastered concept first; ties go to the one whose
    misconceptions we have seen most. None means everything is mastered."""
    todo = [c for c in concepts if m.mastery.get(c, START) < MASTERY]
    if not todo:
        return None
    return min(todo, key=lambda c: (m.mastery.get(c, START), concepts.index(c)))


def style_for(wrong_so_far: int) -> str:
    return STYLES[min(wrong_so_far, len(STYLES) - 1)]


def apply_check(m: LearnerModel, concept: str, correct: bool,
                misconception: str | None) -> LearnerModel:
    """Right answers move mastery toward 1, wrong ones halve it - forgetting is
    faster than learning, which is what a bad explanation costs."""
    old = m.mastery.get(concept, START)
    new = old + (1 - old) * 0.5 if correct else old * 0.5
    mis = dict(m.misconceptions)
    tag = slug(misconception)
    if not correct and tag:
        mis[tag] = mis.get(tag, 0) + 1
    return m.model_copy(update={"mastery": {**m.mastery, concept: round(new, 4)},
                                "misconceptions": mis})

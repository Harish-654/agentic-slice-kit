"""The learner model's rules. Pure functions, no model and no database, so every
decision about what a student is taught next can be tested in microseconds."""
from __future__ import annotations

import re
import time

from .schema import LearnerModel

MASTERY = 0.75
START = 0.3                     # unknown is not zero: they may know a little
MAX_CHECKS = 8                  # quiz items per session
HALF_LIFE_DAYS = 14             # how fast an unpractised concept slides back to START
# Explanation styles, tried in order per concept. A wrong answer means the last
# explanation did not land, and repeating it louder is the failure to avoid.
RECENT = 8                      # question stems remembered per concept
STYLES = ("plain", "analogy", "worked_example", "diagram")


def slug(tag: str | None) -> str | None:
    """Free-text graders phrase the same wrong belief many ways; keep the tag
    stable enough to count."""
    if not tag:
        return None
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-") or None


def effective_mastery(m: LearnerModel, concept: str, now: float | None = None) -> float:
    """What the student probably still knows. Stored mastery is what they showed
    on the day; this slides back toward START the longer they go without
    practice, so an old success comes due for review. Read-time only: nothing
    stored is ever rewritten."""
    stored = m.mastery.get(concept, START)
    seen = m.last_seen.get(concept)
    if seen is None:
        return stored
    days = max(0.0, ((time.time() if now is None else now) - seen) / 86400)
    return START + (stored - START) * 0.5 ** (days / HALF_LIFE_DAYS)


def pick_concept(m: LearnerModel, concepts: list[str], now: float | None = None) -> str | None:
    """Weakest unmastered concept first, in the order given on a tie. None means
    everything is mastered and nothing is due for review."""
    eff = {c: effective_mastery(m, c, now) for c in concepts}
    todo = [c for c in concepts if eff[c] < MASTERY]
    if not todo:
        return None
    return min(todo, key=lambda c: (eff[c], concepts.index(c)))


def carried(m: LearnerModel, concept: str) -> tuple[int, str | None]:
    """How many wrong answers this student has ever given on the concept, and the
    belief they held most often. Untagged wrong answers count towards the first
    number: a grader that could not name the belief still saw a wrong answer."""
    tags = m.concept_misconceptions.get(concept, {})
    return m.wrong_answers.get(concept, 0), (max(tags, key=tags.get) if tags else None)


def level_for(mastery: float) -> str:
    return "beginner" if mastery < 0.4 else "intermediate" if mastery < MASTERY else "advanced"


def profile(m: LearnerModel, concept: str, now: float | None = None) -> str:
    """What the tutor knows about this student on this topic, as prompt text.
    This is what makes questions curated rather than predefined."""
    eff = effective_mastery(m, concept, now)
    wrong, _ = carried(m, concept)
    lines = [f"LEVEL: {level_for(eff)} ({round(eff * 100)}% on this topic)",
             f"WRONG ANSWERS ON THIS TOPIC SO FAR: {wrong}",
             f"INTERESTS: {', '.join(m.interests) or 'none known'}"]
    recent = m.recent_questions.get(concept, [])
    if recent:
        lines.append("QUESTIONS ALREADY ASKED (ask something different):\n"
                     + "\n".join(f"- {q}" for q in recent))
    return "\n".join(lines)


def style_for(wrong_so_far: int) -> str:
    return STYLES[min(wrong_so_far, len(STYLES) - 1)]


def apply_check(m: LearnerModel, concept: str, correct: bool,
                misconception: str | None, now: float | None = None,
                question: str | None = None) -> LearnerModel:
    """Right answers move mastery toward 1, wrong ones halve it - forgetting is
    faster than learning, which is what a bad explanation costs."""
    old = effective_mastery(m, concept, now)     # from what they know now, not their peak
    new = old + (1 - old) * 0.5 if correct else old * 0.5
    wrong = dict(m.wrong_answers)
    if not correct:
        wrong[concept] = wrong.get(concept, 0) + 1
    mis, per = dict(m.misconceptions), {k: dict(v) for k, v in m.concept_misconceptions.items()}
    tag = slug(misconception)
    if not correct and tag:
        mis[tag] = mis.get(tag, 0) + 1
        per.setdefault(concept, {})[tag] = per.get(concept, {}).get(tag, 0) + 1
    recent = m.recent_questions
    if question:
        recent = {**recent, concept: [*recent.get(concept, []), question[:140]][-RECENT:]}
    return m.model_copy(update={"mastery": {**m.mastery, concept: round(new, 4)},
                                "recent_questions": recent,
                                "misconceptions": mis, "concept_misconceptions": per,
                                "wrong_answers": wrong,
                                "last_seen": {**m.last_seen,
                                              concept: time.time() if now is None else now}})

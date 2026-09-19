"""Turning what a student typed and what the model proposed into stable concept ids.
Pure functions, no model: the same topic must land on the same id every time, or a
student's progress splits across "classes and objects", "class-objects" and "objects"."""
from __future__ import annotations

import difflib

from . import learner
from .schema import PlanDraft

MAX_PREREQS, MAX_SUBTOPICS = 3, 4
SIMILAR = 0.85                  # difflib ratio on canonical keys that counts as the same concept
_STOP = {"a", "an", "the", "of", "in", "and", "to", "for", "with", "on", "basics", "basic",
         "introduction", "intro", "python"}


def key(name: str) -> str:
    """Lowercase, drop filler words, strip plurals, sort the words: "Classes and objects"
    and "object-classes" give the same key."""
    words = [w for w in (learner.slug(name) or "").split("-") if w and w not in _STOP]
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words]
    return " ".join(sorted(words))


def resolve(name: str, known: list[str]) -> str | None:
    """The id to use for `name`: an id the student already has if it means the same, else a
    fresh kebab-case one. None when there is nothing usable."""
    k = key(name)
    if not k:
        return None
    for c in known:
        if key(c) == k:
            return c
    close = [(difflib.SequenceMatcher(None, k, key(c)).ratio(), c) for c in known]
    best = max(close, default=(0.0, None))
    return best[1] if best[0] >= SIMILAR else learner.slug(name)


def clean_plan(draft: PlanDraft, target: str, known: list[str]) -> dict:
    """The model's draft made safe to run on: canonical ids, no repeats, the target never its
    own prerequisite, and capped in code because a prompt is not a limit."""
    seen = {key(target)}

    def take(names: list[str], cap: int) -> list[str]:
        out: list[str] = []
        for n in names:
            c = resolve(n, known)
            if c and key(c) not in seen and len(out) < cap:
                seen.add(key(c))
                out.append(c)
        return out

    prereqs = take(draft.prereqs, MAX_PREREQS)
    return {"prereqs": prereqs, "subtopics": take(draft.subtopics, MAX_SUBTOPICS)}

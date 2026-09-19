"""What a guided session does next. Pure functions over the plan, the learner model and
this session's checks, so the whole prerequisite policy is testable in microseconds and
never left to a prompt."""
from __future__ import annotations

import time

from . import learner
from .schema import LearnerModel

TRUST = 0.85                    # a prerequisite this well known, this recently, is not probed
TRUST_DAYS = 3
MAX_TAUGHT = 2                  # tries at teaching a prerequisite before moving on
MAX_CHECKS = 12                 # every check in one guided session, probes included


def _trusted(m: LearnerModel, concept: str, now: float) -> bool:
    seen = m.last_seen.get(concept)
    return (seen is not None and now - seen <= TRUST_DAYS * 86400
            and learner.effective_mastery(m, concept, now) >= TRUST)


def decide(order: list[str], m: LearnerModel, checks: list[dict], skipped=frozenset(),
           probing: bool = True, unprobed=frozenset(),
           now: float | None = None) -> tuple[str, str | None]:
    """`order` is the prerequisites then the target. Returns ("probe" | "teach", concept), or
    ("done", reason). A prerequisite is checked once BEFORE it is explained: right means the
    student knew it and it is skipped; wrong or "I don't know" means it is taught until one
    check is right, at most MAX_TAUGHT times. `probing=False` (the student's documents are the
    source of truth) skips the probe, because a probe question would come from outside them.
    `unprobed` are prerequisites whose probe could not be made trustworthy: taught instead."""
    now = time.time() if now is None else now
    *prereqs, target = order
    if target in skipped:
        return "done", "skipped"
    if learner.effective_mastery(m, target, now) >= learner.MASTERY:
        return "done", "mastery"
    for p in prereqs:
        if p in skipped or _trusted(m, p, now):
            continue
        mine = [c for c in checks if c["concept"] == p]
        probed = [c for c in mine if c.get("probe")]
        taught = [c for c in mine if not c.get("probe")]
        if probing and p not in unprobed and not probed:
            return "probe", p
        if any(c["correct"] for c in probed + taught) or len(taught) >= MAX_TAUGHT:
            continue
        return "teach", p
    return "teach", target

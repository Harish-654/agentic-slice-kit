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
MAX_CHECKS = 16                 # every check in one guided session, probes and finals included
MAX_STEPS = 30                  # every lesson, probe and final: a cap on how long one topic can run
MAX_EXPLAINS = 2                # explanations in a row before the tutor must offer the quiz
COVER_CORRECT = 2               # right answers a part of the topic needs, this session, to count as covered
MAX_REVISIONS = 2               # after a failed final: re-teach the weakest part and try again, twice at most
# What a student can ask for after an explanation. "quiz" shows the check that was held back.
CHOICES = ("quiz", "example", "more_detail", "deeper", "skip", "stop")


def choices(explains_in_row: int) -> list[str]:
    """The menu after an explanation. After MAX_EXPLAINS in a row the ways to keep explaining
    are withdrawn, so a session cannot circle forever without the student being asked anything."""
    if explains_in_row < MAX_EXPLAINS:
        return list(CHOICES)
    return [c for c in CHOICES if c in ("quiz", "skip", "stop")]


def _trusted(m: LearnerModel, concept: str, now: float) -> bool:
    seen = m.last_seen.get(concept)
    return (seen is not None and now - seen <= TRUST_DAYS * 86400
            and learner.effective_mastery(m, concept, now) >= TRUST)


def decide(order: list[str], m: LearnerModel, checks: list[dict], skipped=frozenset(),
           probing: bool = True, unprobed=frozenset(), subtopics=(),
           now: float | None = None) -> tuple[str, str | None]:
    """`order` is the prerequisites, the parts of the topic, then the target; `subtopics` names
    the parts. Returns ("probe" | "teach" | "final", concept), or ("done", reason).

    Prerequisites come first. Each is checked once BEFORE it is explained: right means the student
    knew it and it is skipped; wrong or "I don't know" means it is taught until one check is
    right, at most MAX_TAUGHT times. `probing=False` (the student's documents are the source of
    truth) skips the probe, because a probe question would come from outside them. `unprobed` are
    prerequisites whose probe could not be made trustworthy: taught instead.

    Then every part of the topic must be COVERED: mastery of it at the bar and COVER_CORRECT right
    answers this session (a part known well and recently is skipped). With no parts the topic is
    its own single part. Only then the FINAL, a written question on the whole topic. Fail it and
    the weakest part (recorded on the failed check) is taught again before the next try, at most
    MAX_REVISIONS times, then the session ends as "revision_limit"."""
    now = time.time() if now is None else now
    *rest, target = order
    subs = [c for c in rest if c in subtopics]
    prereqs = [c for c in rest if c not in subtopics]
    if target in skipped:
        return "done", "skipped"
    finals = [c for c in checks if c.get("final")]
    if finals and finals[-1]["correct"]:
        return "done", "mastery"
    if len(finals) > MAX_REVISIONS:
        return "done", "revision_limit"
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
    parts = [s for s in subs if s not in skipped] if subs else [target]
    if not parts:
        return "done", "skipped"                      # every part was skipped: there is nothing to test
    revisit = finals[-1].get("revisit") if finals else None
    last_final = max((i for i, c in enumerate(checks) if c.get("final")), default=-1)
    for s in parts:
        if s == revisit:                              # the weak part: needs a fresh right answer
            if not any(c["concept"] == s and c["correct"] for c in checks[last_final + 1:]):
                return "teach", s
            continue
        if _trusted(m, s, now):
            continue
        right = sum(1 for c in checks if c["concept"] == s and c["correct"])
        if learner.effective_mastery(m, s, now) < learner.MASTERY or right < COVER_CORRECT:
            return "teach", s
    return "final", target

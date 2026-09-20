"""What a student has learnt, across every session they have ever had.

Nothing is stored for this. The twin already holds how well the student knows each idea and when they last
practised it (with forgetting built in), and every session already records its topic and, for a guided one, its
plan: the prerequisites and the parts. The dashboard is those two put side by side.

"Completed" is the twin's word, not a certificate. A part counts as completed once the student reached the bar on
it, and reads "got-it" while they are still there. Ideas fade, so one learnt weeks ago reads "review" until it is
practised again: still completed, but due. A topic whose final check was passed stays "learnt" however long ago;
how many of its ideas have faded is reported separately as `due`.
"""
from __future__ import annotations

import time

from slice.store import Store

from . import curriculum, learner, learners
from .schema import LearnerModel

MAX_RUNS = 200                  # the newest sessions read
MAX_TOPICS = 30                 # the newest topics shown


def band(standing: dict) -> str:
    """The same four words the page uses for an idea: new, learning, review, got-it."""
    return ("review" if standing["review_due"] else "got-it" if standing["mastered"]
            else "learning" if standing["seen"] else "new")


def _idea(model: LearnerModel, concept: str, now: float) -> dict:
    s = learner.standing(model, concept, now)
    return {"concept": concept, "mastery": s["mastery"], "band": band(s)}


def _student_runs(store: Store, student: str) -> list[tuple[str, float]]:
    """(run id, when it began) for this student's tutor sessions, newest first."""
    rows = store.db.execute(
        "SELECT id, created_at FROM runs WHERE domain = 'tutor' AND json_extract(meta_json, '$.student_id') = ? "
        "ORDER BY created_at DESC LIMIT ?", (student, MAX_RUNS))
    return [(r["id"], r["created_at"]) for r in rows]


def _topics_in(inp: dict) -> list[tuple[str, dict | None]]:
    """(the student's own words for it, its plan or None) for each topic a session was about. A guided session
    is one topic with parts; quick practice is one topic per thing typed, with no parts."""
    plan = inp.get("plan")
    if inp.get("mode") == "guided":
        if plan:
            return [(plan["target"], plan)]
        typed = inp["concepts"][0] if inp.get("concepts") else ""
        return [] if inp.get("exam_question") or not typed else [(typed, None)]     # no plan was ever made
    return [(c, None) for c in inp.get("concepts", []) if c]


def report(store: Store, student: str, now: float | None = None) -> dict:
    """What GET /api/me/learning returns: one entry per topic the student has studied, newest first, with the
    standing of the topic itself, its prerequisites and each of its parts, and totals over all of them."""
    now = time.time() if now is None else now
    model = learners.load(store, student) or LearnerModel(student_id=student)
    topics: dict[str, dict] = {}
    sessions = 0
    for run_id, began in _student_runs(store, student):
        inp = store.latest(run_id, "input")
        if inp is None:
            continue
        end = store.latest(run_id, "session_end")
        passed = bool(end) and end.get("reason") == "mastery"           # the final check was passed
        for name, plan in _topics_in(inp):
            key = curriculum.key(name, keep_language=True) or name.lower()
            t = topics.setdefault(key, {"name": name, "last": began, "sessions": 0, "passed": False, "plan": None})
            t["sessions"] += 1
            t["passed"] = t["passed"] or passed
            if t["plan"] is None and plan:                             # the newest plan wins
                t["plan"] = plan
        sessions += 1

    out, parts_done, review = [], set(), set()
    for t in list(topics.values())[:MAX_TOPICS]:
        plan = t["plan"] or {}
        target = _idea(model, t["name"], now)
        parts = [_idea(model, c, now) for c in plan.get("subtopics", [])]
        prereqs = [_idea(model, c, now) for c in plan.get("prereqs", [])]
        ideas = [target, *parts, *prereqs]
        state = ("learnt" if t["passed"] or target["band"] == "got-it"        # passing the final check is learning it
                 else "review" if target["band"] == "review"
                 else "learning" if any(i["band"] != "new" for i in ideas) else "new")
        due = {i["concept"] for i in ideas if i["band"] == "review"}          # learnt before, since faded
        done = {i["concept"] for i in parts if i["band"] in ("got-it", "review")}     # reached the bar, faded or not
        parts_done |= done
        review |= due
        out.append({"name": t["name"], "state": state, "last_studied": t["last"], "sessions": t["sessions"],
                    "due": len(due), "mastery": target["mastery"], "parts_done": len(done),
                    "parts_total": len(parts), "parts": parts, "prereqs": prereqs})
    return {"totals": {"topics": len(out), "learnt": sum(t["state"] == "learnt" for t in out),
                       "parts_done": len(parts_done), "to_review": len(review), "sessions": sessions},
            "topics": out}

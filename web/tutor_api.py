"""
The JSON API behind the tutor's chat page.

A session is a run. This module turns its history into chat messages and lets the
page drive it: start, answer, toggle, resume. Lesson generation takes seconds, so
it runs on a background thread and the page polls. The student sees whether they
were right the moment the answer lands, while the next lesson is still being written.

Two rules worth knowing:
- The correct option is never sent until the student has answered. The page could
  hide it, but "hidden by CSS" is not hidden.
- One run has at most one thread advancing it. A second request while one is
  running is a no-op, not a second concurrent lesson.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from demo.tutor import learner, session
from demo.tutor.flow import KIND_TEACHER, build_flow
from demo.tutor.schema import LearnerModel
from slice import runner
from slice.config import settings
from slice.records import RunState
from slice.store import Store

router = APIRouter(prefix="/api")

# Set by web.student, overridable in tests.
DB = "run.db"
flow_factory = build_flow
get_settings = settings

_running: set[str] = set()
_lock = threading.Lock()


def _store() -> Store:
    return Store(Path(DB))


# ------------------------------------------------------------------ running

def _advance(run_id: str) -> None:
    """Runs on its own thread with its own connection: SQLite connections belong
    to the thread that made them."""
    s = Store(Path(DB))
    try:
        runner.advance(s, run_id, flow_factory(), get_settings())
    except Exception as e:                       # a bug must end the run visibly, not hang it
        s.append(run_id, "failure",
                 {"kind": "internal", "detail": f"{type(e).__name__}: {str(e)[:200]}"}, "system")
        s.set_state(run_id, RunState.FAILED)
    finally:
        with _lock:
            _running.discard(run_id)
        s.close()


def _kick(run_id: str) -> None:
    with _lock:
        if run_id in _running:
            return
        _running.add(run_id)
    threading.Thread(target=_advance, args=(run_id,), daemon=True).start()


def is_running(run_id: str) -> bool:
    with _lock:
        return run_id in _running


# ---------------------------------------------------------------- snapshots

def _status(s: Store, run_id: str) -> str:
    if is_running(run_id):
        return "working"
    state = s.get_state(run_id)
    if state is RunState.COMPLETE:
        return "complete"
    if state is RunState.FAILED:
        return "failed"
    if state.is_suspended:
        return "waiting_student" if session.open_quiz(s, run_id) else "waiting_teacher"
    return "stalled"          # mid-step with nothing driving it, e.g. the server restarted


def _lesson_message(v) -> dict:
    p = v.payload
    q = p["quiz"]
    return {
        "id": f"{v.seq}-lesson", "role": "assistant", "kind": "lesson",
        "concept": p["concept"], "style": p["style"], "citations": p["citations"],
        "explanation": p["explanation"], "diagram": p.get("diagram"),
        "quiz": {"question": q["question"], "code": q.get("code"),
                 "options": [{"text": o["text"]} for o in q["options"]],   # no answer key
                 "answered": None},
    }


def _messages(versions) -> list[dict]:
    out: list[dict] = []
    lesson_msg: dict | None = None
    lesson_payload: dict | None = None
    reply: dict | None = None
    for v in versions:
        p = v.payload
        if v.kind == "lesson":
            lesson_payload, reply = p, None
            lesson_msg = _lesson_message(v)
            out.append(lesson_msg)
        elif v.kind == "expert_answer" and p.get("who") == "student" and p.get("answer"):
            reply = json.loads(p["answer"])
        elif v.kind == "check" and lesson_payload and lesson_msg:
            quiz = lesson_payload["quiz"]
            given = reply or {}
            if given.get("mode") == "mcq":
                said = quiz["options"][given["choice"]]["text"]
                lesson_msg["quiz"]["answered"] = {"chosen": given["choice"],
                                                  "correct_index": quiz["correct"],
                                                  "correct": p["correct"]}
            else:
                said = given.get("text", "")
                lesson_msg["quiz"]["answered"] = {"chosen": None, "correct_index": None,
                                                  "correct": p["correct"]}
            out.append({"id": f"{v.seq}-answer", "role": "user", "kind": "answer", "text": said})
            out.append({"id": f"{v.seq}-feedback", "role": "assistant", "kind": "feedback",
                        "correct": p["correct"], "text": p["feedback"],
                        "misconception": p.get("misconception"),
                        "via": given.get("mode", "mcq")})
            lesson_msg = lesson_payload = reply = None
        elif v.kind == "session_end":
            out.append({"id": f"{v.seq}-end", "role": "assistant", "kind": "end",
                        "reason": p["reason"]})
        elif v.kind == "failure":
            out.append({"id": f"{v.seq}-failure", "role": "assistant", "kind": "notice",
                        "text": p.get("detail", "The session stopped."), "problem": True})
        elif v.kind == "question" and p["context"].get("kind") == KIND_TEACHER:
            out.append({"id": f"{v.seq}-teacher", "role": "assistant", "kind": "notice",
                        "text": f"Your notes do not cover “{p['context']['concept']}” yet, so "
                                "your teacher has been asked. This page continues on its own "
                                "when they answer.", "problem": False})
    return out


def _progress(s: Store, run_id: str) -> dict:
    model = LearnerModel.model_validate(s.latest(run_id, "learner_model"))
    concepts = s.latest(run_id, "input")["concepts"]
    rows = []
    for c in concepts:
        eff = learner.effective_mastery(model, c)
        rows.append({
            "concept": c,
            "mastery": round(eff, 3),
            "mastered": eff >= learner.MASTERY,
            "seen": c in model.mastery,
            # learnt before, since slid back below the bar: a review, not a first pass
            "review_due": c in model.mastery and eff < learner.MASTERY
                          and model.mastery[c] >= learner.MASTERY,
            "beliefs": sorted(model.concept_misconceptions.get(c, {}).items(),
                              key=lambda kv: -kv[1]),
        })
    return {"concepts": rows, "threshold": learner.MASTERY,
            "answer_mode": model.answer_mode, "interests": model.interests}


def snapshot(s: Store, run_id: str) -> dict:
    try:
        status = _status(s, run_id)
    except KeyError:
        raise HTTPException(404, "No such session.")
    meta = s.meta(run_id)
    return {"id": run_id, "student": meta.get("student_id", ""), "status": status,
            "messages": _messages(s.replay(run_id)), "progress": _progress(s, run_id)}


# --------------------------------------------------------------------- routes

class StartRequest(BaseModel):
    student: str = Field(min_length=1, max_length=60)
    concepts: list[str] = Field(min_length=1, max_length=12)
    interests: list[str] = []


class AnswerRequest(BaseModel):
    choice: int | None = None
    text: str | None = Field(default=None, max_length=4000)


class ModeRequest(BaseModel):
    mode: str


def _concept_name(doc: str) -> str:
    """mutable-defaults.md -> mutable-defaults; week3.pdf.md (a converted PDF) -> week3."""
    name = doc.rsplit(".", 1)[0] if doc.endswith((".md", ".txt")) else doc
    return name.rsplit(".", 1)[0] if name.endswith((".pdf", ".docx")) else name


@router.get("/notes")
def notes_available():
    """What the teacher's notes cover, so the page can offer topics instead of
    asking a student to guess what to type."""
    try:
        rows = _store().db.execute("SELECT DISTINCT doc FROM chunks ORDER BY doc").fetchall()
    except Exception:                       # nothing ingested yet
        return {"concepts": []}
    return {"concepts": sorted({_concept_name(r["doc"]) for r in rows})}


@router.post("/sessions")
def start(req: StartRequest):
    s = _store()
    concepts = [c.strip() for c in req.concepts if c.strip()]
    if not concepts:
        raise HTTPException(422, "Give at least one concept to learn.")
    interests = [i.strip() for i in req.interests if i.strip()] or None
    run = session.start_session(s, req.student.strip(), concepts, interests)
    _kick(run)
    return {"id": run}


@router.get("/sessions/{run_id}")
def get(run_id: str):
    return snapshot(_store(), run_id)


@router.post("/sessions/{run_id}/answer")
def answer(run_id: str, req: AnswerRequest):
    s = _store()
    snapshot(s, run_id)                                  # 404 if unknown
    q = session.open_quiz(s, run_id)
    if q is None or is_running(run_id):
        raise HTTPException(409, "This session is not waiting for an answer.")
    lesson = s.latest(run_id, "lesson")
    if req.choice is not None:
        if not 0 <= req.choice < len(lesson["quiz"]["options"]):
            raise HTTPException(422, "That option does not exist.")
        session.submit_mcq(s, q.id, req.choice)
    elif (req.text or "").strip():
        session.submit_text(s, q.id, req.text.strip())
    else:
        raise HTTPException(422, "Send a choice or some text.")
    _kick(run_id)
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/mode")
def mode(run_id: str, req: ModeRequest):
    if req.mode not in ("mcq", "text"):
        raise HTTPException(422, "mode must be 'mcq' or 'text'.")
    s = _store()
    snapshot(s, run_id)
    if is_running(run_id):        # the run is about to write the learner model itself
        raise HTTPException(409, "Wait for the next lesson before switching.")
    session.set_answer_mode(s, run_id, req.mode)
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/resume")
def resume(run_id: str):
    """For a run left mid-step (server restarted) or one a teacher just answered."""
    s = _store()
    if _status(s, run_id) == "stalled":
        _kick(run_id)
    return snapshot(s, run_id)

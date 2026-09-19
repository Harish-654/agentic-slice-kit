"""
The JSON API behind the tutor's chat page.

A session is a run. This module turns its history into chat messages and lets the
page drive it: start, answer, toggle, resume. Lesson generation takes seconds, so
it runs on a background thread and the page polls. The student sees whether they
were right the moment the answer lands, while the next lesson is still being written.

Rules worth knowing:
- The correct option, the misconception tags, and everything a written answer is
  graded against (rubric, model answer, common mistakes) never leave the server
  before the student has answered. "Hidden by CSS" is not hidden.
- One run has at most one thread advancing it. A second request while one is
  running is a no-op, not a second concurrent lesson.
- A student's documents are theirs. Every document route takes the student's name
  and only ever touches that student's folder and index.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from demo.tutor import learner, library, session
from demo.tutor.flow import build_flow
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


def get_store():
    """One connection per request, closed when it ends."""
    s = _store()
    try:
        yield s
    finally:
        s.close()


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
        if session.open_quiz(s, run_id):
            return "waiting_student"
        return "waiting_choice" if session.open_gap(s, run_id) else "stalled"
    return "stalled"          # mid-step with nothing driving it, e.g. the server restarted


def _lesson_message(v) -> dict:
    """Only what the student may see. Everything else stays in the database."""
    p = v.payload
    msg = {"id": f"{v.seq}-lesson", "role": "assistant", "kind": "lesson",
           "concept": p["concept"], "style": p["style"], "source": p.get("source", "docs"),
           # Stored as <student>__<file>#n; the student only ever knows their own file name.
           "citations": [c.split("__", 1)[-1] for c in p["citations"]],
           "explanation": p["explanation"],
           "diagram": p.get("diagram"), "quiz": None, "open": None}
    if p["quiz"]:
        q = p["quiz"]
        msg["quiz"] = {"question": q["question"], "code": q.get("code"),
                       "options": [{"text": o["text"]} for o in q["options"]],   # no answer key
                       "answered": None}
    else:
        o = p["open"]
        msg["open"] = {"question": o["question"], "code": o.get("code"), "answered": None}
    return msg


def _messages(versions) -> list[dict]:
    gaps = {v.payload["question_id"]: v.payload["answer"]
            for v in versions if v.kind == "expert_answer" and v.payload.get("who") == "student_gap"}
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
            given = reply or {}
            card = lesson_msg["quiz"] or lesson_msg["open"]
            key = lesson_payload["quiz"]["correct"] if lesson_payload["quiz"] else None
            if given.get("mode") == "dont_know":
                said = "I don't know"
                # The answer is shown now: they have given up on it, and learning is the point.
                card["answered"] = {"chosen": None, "correct_index": key, "correct": False,
                                    "dont_know": True}
            elif given.get("mode") == "mcq":
                said = lesson_payload["quiz"]["options"][given["choice"]]["text"]
                card["answered"] = {"chosen": given["choice"],
                                    "correct_index": lesson_payload["quiz"]["correct"],
                                    "correct": p["correct"]}
            else:
                said = given.get("text", "")
                card["answered"] = {"chosen": None, "correct_index": None, "correct": p["correct"]}
            out.append({"id": f"{v.seq}-answer", "role": "user", "kind": "answer", "text": said})
            out.append({"id": f"{v.seq}-feedback", "role": "assistant", "kind": "feedback",
                        "correct": p["correct"], "text": p["feedback"],
                        "misconception": p.get("misconception"),
                        "via": "mcq" if lesson_payload["quiz"] else "text",
                        "confidence": p.get("confidence"), "dont_know": p.get("dont_know", False)})
            lesson_msg = lesson_payload = reply = None
        elif v.kind == "session_end":
            out.append({"id": f"{v.seq}-end", "role": "assistant", "kind": "end",
                        "reason": p["reason"]})
        elif v.kind == "failure":
            out.append({"id": f"{v.seq}-failure", "role": "assistant", "kind": "notice",
                        "text": p.get("detail", "The session stopped."), "problem": True,
                        "gap": None})
        elif v.kind == "question" and p["context"].get("kind") == "doc_gap":
            out.append({"id": f"{v.seq}-gap", "role": "assistant", "kind": "notice", "problem": False,
                        "text": f"“{p['context']['concept']}” is not in your documents.",
                        "gap": {"concept": p["context"]["concept"], "answer": gaps.get(p["id"])}})
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
            "answer_mode": model.answer_mode, "interests": model.interests,
            "use_docs": model.use_docs, "docs": library.docs(s.meta(run_id)["student_id"])}


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
    use_docs: bool = False


class AnswerRequest(BaseModel):
    choice: int | None = None
    text: str | None = Field(default=None, max_length=4000)
    # How sure the student is. It changes how far the answer moves their mastery.
    confidence: Literal["low", "medium", "high"] | None = None
    dont_know: bool = False


class ModeRequest(BaseModel):
    mode: str


class SourceRequest(BaseModel):
    use_docs: bool


class GapRequest(BaseModel):
    choice: str


def _need_docs(student: str, on: bool) -> None:
    if on and not library.has_docs(student):
        raise HTTPException(422, "Add a document first, then switch this on.")


@router.post("/sessions")
def start(req: StartRequest, s: Store = Depends(get_store)):
    concepts = [c.strip() for c in req.concepts if c.strip()]
    if not concepts:
        raise HTTPException(422, "Say what you want to learn.")
    student = req.student.strip()
    _need_docs(student, req.use_docs)
    interests = [i.strip() for i in req.interests if i.strip()] or None
    run = session.start_session(s, student, concepts, interests, use_docs=req.use_docs)
    _kick(run)
    return {"id": run}


@router.get("/sessions/{run_id}")
def get(run_id: str, s: Store = Depends(get_store)):
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/answer")
def answer(run_id: str, req: AnswerRequest, s: Store = Depends(get_store)):
    snapshot(s, run_id)                                  # 404 if unknown
    q = session.open_quiz(s, run_id)
    if q is None or is_running(run_id):
        raise HTTPException(409, "This session is not waiting for an answer.")
    lesson = s.latest(run_id, "lesson")
    typed = (req.text or "").strip()
    if req.dont_know:
        if req.choice is not None or typed:
            raise HTTPException(422, "Give an answer, or say you do not know, not both.")
        session.submit_unknown(s, q.id)
    elif req.choice is not None and lesson["quiz"]:
        if not 0 <= req.choice < len(lesson["quiz"]["options"]):
            raise HTTPException(422, "That option does not exist.")
        session.submit_mcq(s, q.id, req.choice, req.confidence)
    elif typed and lesson["open"]:
        session.submit_text(s, q.id, typed, req.confidence)
    else:
        raise HTTPException(422, "Choose an option." if lesson["quiz"] else "Write your answer.")
    _kick(run_id)
    return snapshot(s, run_id)


def _toggle(run_id: str, s: Store, apply) -> dict:
    snapshot(s, run_id)
    if is_running(run_id):        # the run is about to write the learner model itself
        raise HTTPException(409, "Wait for the next lesson before changing this.")
    apply()
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/mode")
def mode(run_id: str, req: ModeRequest, s: Store = Depends(get_store)):
    """The type of the NEXT question. The one on screen stays as it is."""
    if req.mode not in ("mcq", "text"):
        raise HTTPException(422, "mode must be 'mcq' or 'text'.")
    return _toggle(run_id, s, lambda: session.set_answer_mode(s, run_id, req.mode))


@router.post("/sessions/{run_id}/source")
def source(run_id: str, req: SourceRequest, s: Store = Depends(get_store)):
    """Teach from the student's documents (on) or from general knowledge (off)."""
    snapshot(s, run_id)
    _need_docs(s.meta(run_id)["student_id"], req.use_docs)
    return _toggle(run_id, s, lambda: session.set_use_docs(s, run_id, req.use_docs))


@router.post("/sessions/{run_id}/fallback")
def fallback(run_id: str, req: GapRequest, s: Store = Depends(get_store)):
    """The student's answer to "that is not in your documents"."""
    if req.choice not in ("general", "skip"):
        raise HTTPException(422, "choice must be 'general' or 'skip'.")
    snapshot(s, run_id)
    gap = session.open_gap(s, run_id)
    if gap is None or is_running(run_id):
        raise HTTPException(409, "There is nothing to decide right now.")
    session.submit_gap(s, gap.id, req.choice)
    _kick(run_id)
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/resume")
def resume(run_id: str, s: Store = Depends(get_store)):
    """For a run left mid-step (the server restarted)."""
    if _status(s, run_id) == "stalled":
        _kick(run_id)
    return snapshot(s, run_id)


# ------------------------------------------------------------------ documents

@router.get("/students/{student}/docs")
def list_docs(student: str):
    return {"docs": library.docs(student)}


@router.post("/students/{student}/docs")
def upload_docs(student: str, files: list[UploadFile], s: Store = Depends(get_store)):
    """Sync on purpose: reading, converting and embedding a file is slow, and a plain
    `def` route runs on a worker thread instead of blocking the server."""
    try:
        for f in files:
            # Read one byte past the limit so an oversize file is seen, not truncated.
            library.save(s, student, f.filename or "document", f.file.read(library.MAX_BYTES + 1))
    except library.Rejected as e:
        raise HTTPException(422, str(e))
    return {"docs": library.docs(student)}


@router.post("/students/{student}/docs/sample")
def sample_docs(student: str, s: Store = Depends(get_store)):
    return {"docs": library.add_sample(s, student)}


@router.delete("/students/{student}/docs/{name}")
def remove_doc(student: str, name: str, s: Store = Depends(get_store)):
    if name not in library.docs(student):
        raise HTTPException(404, "No such document.")
    library.delete(s, student, name)
    return {"docs": library.docs(student)}

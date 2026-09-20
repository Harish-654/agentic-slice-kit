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
import sqlite3
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from demo.tutor import activity, coach, dashboard, languages, learner, learners, library, sandbox, session, visuals
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from slice import runner
from slice.budget import Budget
from slice.llm import complete
from slice.config import settings
from slice.records import RunState
from slice.store import Store
from web import auth

# Set by web.student, overridable in tests.
DB = "run.db"
flow_factory = build_flow
get_settings = settings
sandbox_run, sandbox_ready = sandbox.run, sandbox.available     # overridable in tests
sandbox_installed = sandbox.installed                            # overridable in tests
suggest_call = complete                                          # overridable in tests

_running: set[str] = set()
_lock = threading.Lock()


class _RequestStore(Store):
    """A store whose connection may be used and closed from a different thread than the one that opened it.

    FastAPI runs a request's dependencies and its route on a thread pool, so the thread that opens a
    request's store is not always the one that closes it, and SQLite's default refuses that with
    "objects created in a thread can only be used in that same thread". It showed up as random 500s once
    routes had several dependencies. This is safe here because every request has its own connection and
    uses it one step at a time, never from two threads at once."""

    def __init__(self, path):
        super().__init__(path)                      # creates the schema; this connection is tied to this thread
        self.db.close()
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")


def _store() -> Store:
    return _RequestStore(Path(DB))


def get_store():
    """One connection per request, closed when it ends."""
    s = _store()
    try:
        yield s
    finally:
        s.close()


# Every route below needs a signed-in student (web/auth.py); each then checks the run or the documents are theirs.
current_student = auth.guard(get_store)
router = APIRouter(prefix="/api", dependencies=[Depends(current_student)])


def _own(s: Store, run_id: str, user: str | None) -> None:
    """A run belongs to the student who started it. Anyone else is told it does not exist, not that it is
    someone else's. `user` is None only when login is switched off (tests)."""
    if user is None:
        return
    try:
        owner = s.meta(run_id).get("student_id")
    except KeyError:
        raise HTTPException(404, "No such session.")
    if owner != user:
        raise HTTPException(404, "No such session.")


def _mine(student: str, user: str | None) -> None:
    if user is not None and student != user:
        raise HTTPException(403, "Those are not your documents.")


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
        return "waiting_choice" if session.open_gap(s, run_id) or session.open_choice(s, run_id) else "stalled"
    return "stalled"          # mid-step with nothing driving it, e.g. the server restarted


def _card(p: dict) -> dict:
    """The check as the student may see it: the question, and nothing that grades it."""
    card = {"quiz": None, "open": None, "code_task": None}
    if p["quiz"]:
        q = p["quiz"]
        card["quiz"] = {"question": q["question"], "code": q.get("code"),
                        "options": [{"text": o["text"]} for o in q["options"]],   # no answer key
                        "answered": None}
    elif p.get("code_task"):
        t = p["code_task"]                     # the tests, beliefs and solution stay on the server
        card["code_task"] = {"question": t["question"], "starter": t["starter"],
                             "style": t.get("style", "function"), "answered": None,
                             "language": _language_info(p.get("language"), p.get("version"))}
    else:
        o = p["open"]
        card["open"] = {"question": o["question"], "code": o.get("code"), "answered": None}
    return card


def _lesson_message(v) -> dict:
    """Only what the student may see. Everything else stays in the database. A held lesson
    (guided mode) shows its explanation now and its check only once they ask for it."""
    p = v.payload
    msg = {"id": f"{v.seq}-lesson", "role": "assistant", "kind": "lesson",
           "concept": p["concept"], "style": p["style"], "source": p.get("source", "docs"),
           # Stored as <student>__<file>#n; the student only ever knows their own file name.
           "citations": [c.split("__", 1)[-1] for c in p["citations"]],
           "explanation": p["explanation"],
           "diagram": visuals.safe_diagram(p.get("diagram"))}
    return msg | ({"quiz": None, "open": None, "code_task": None} if p.get("held") else _card(p))


def _messages(versions) -> list[dict]:
    gaps = {v.payload["question_id"]: v.payload["answer"]
            for v in versions if v.kind == "expert_answer" and v.payload.get("who") == "student_gap"}
    out: list[dict] = []
    choice_msgs: dict[str, dict] = {}
    model: LearnerModel | None = None                        # the learner model as of this point in the history
    lesson_msg: dict | None = None
    lesson_payload: dict | None = None
    reply: dict | None = None
    for v in versions:
        p = v.payload
        if v.kind == "learner_model":
            model = LearnerModel.model_validate(p)
        elif v.kind == "input" and p.get("plan") and model is not None:      # the plan was just made: show it
            out.append({"id": f"{v.seq}-map", "role": "assistant", "kind": "map",
                        **visuals.concept_map(p["plan"], model)})
        elif v.kind == "lesson":
            lesson_payload, reply = p, None
            lesson_msg = _lesson_message(v)
            out.append(lesson_msg)
        elif v.kind == "reveal" and lesson_payload:          # "quiz me": the held check appears
            lesson_msg = {"id": f"{v.seq}-card", "role": "assistant", "kind": "card",
                          "concept": lesson_payload["concept"], **_card(lesson_payload)}
            out.append(lesson_msg)
        elif v.kind == "expert_answer" and p.get("who") == "student_choice":
            if p["question_id"] in choice_msgs:
                choice_msgs[p["question_id"]]["chosen"] = p["answer"]
        elif v.kind == "expert_answer" and p.get("who") == "student" and p.get("answer"):
            reply = json.loads(p["answer"])
        elif v.kind == "check" and lesson_payload and lesson_msg:
            given = reply or {}
            card = lesson_msg["quiz"] or lesson_msg["open"] or lesson_msg["code_task"]
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
            elif given.get("mode") == "code":
                said = given.get("code", "")
                card["answered"] = {"chosen": None, "correct_index": None, "correct": p["correct"]}
            else:
                said = given.get("text", "")
                card["answered"] = {"chosen": None, "correct_index": None, "correct": p["correct"]}
            out.append({"id": f"{v.seq}-answer", "role": "user", "kind": "answer", "text": said})
            out.append({"id": f"{v.seq}-feedback", "role": "assistant", "kind": "feedback",
                        "correct": p["correct"], "text": p["feedback"],
                        "misconception": p.get("misconception"),
                        "via": "mcq" if lesson_payload["quiz"] else "code" if lesson_payload.get("code_task") else "text",
                        "confidence": p.get("confidence"), "dont_know": p.get("dont_know", False)})
            lesson_msg = lesson_payload = reply = None
        elif v.kind == "session_end":
            out.append({"id": f"{v.seq}-end", "role": "assistant", "kind": "end",
                        "reason": p["reason"]})
        elif v.kind == "failure":
            out.append({"id": f"{v.seq}-failure", "role": "assistant", "kind": "notice",
                        "text": p.get("detail", "The session stopped."), "problem": True,
                        "gap": None})
        elif v.kind == "question" and p["context"].get("kind") == "step_choice":
            choice_msgs[p["id"]] = {"id": f"{v.seq}-choices", "role": "assistant", "kind": "choices",
                                    "options": p["context"]["options"], "chosen": None}
            out.append(choice_msgs[p["id"]])
        elif v.kind == "question" and p["context"].get("kind") == "doc_gap":
            out.append({"id": f"{v.seq}-gap", "role": "assistant", "kind": "notice", "problem": False,
                        "text": f"“{p['context']['concept']}” is not in your documents.",
                        "gap": {"concept": p["context"]["concept"], "answer": gaps.get(p["id"])}})
    return out


def _language_info(language: str | None, version: str | None) -> dict | None:
    """{id, name, version, label} for the page, or None when there is nothing to say (a question with no program)."""
    if not language:
        return None
    lang, v = languages.resolve(language, version)
    return {"id": lang.id, "name": lang.name, "version": v, "label": lang.label(v)}


def _sandbox_language(s: Store, run_id: str):
    """(language, version) of this student's code sandbox. It is chosen in the sandbox and remembered; lessons ignore it."""
    model = LearnerModel.model_validate(s.latest(run_id, "learner_model"))
    return languages.resolve(model.language, model.version)


def _language_for(s: Store, run_id: str, language: str | None, version: str | None):
    """What a request runs in: the language it names (a program question keeps its own), else the sandbox's."""
    try:
        return languages.resolve(language, version) if language else _sandbox_language(s, run_id)
    except languages.UnknownLanguage as e:
        raise HTTPException(422, str(e))


def _progress(s: Store, run_id: str) -> dict:
    model = LearnerModel.model_validate(s.latest(run_id, "learner_model"))
    inp = s.latest(run_id, "input")
    lang, version = _sandbox_language(s, run_id)
    concepts = inp["concepts"]
    plan = inp.get("plan")
    rows = []
    for c in concepts:
        rows.append({
            "concept": c,
            **learner.standing(model, c),
            "beliefs": sorted(model.concept_misconceptions.get(c, {}).items(),
                              key=lambda kv: -kv[1]),
        })
    latest = s.latest(run_id, "lesson")
    current = latest["concept"] if latest and not s.get_state(run_id).is_terminal else None
    return {"concepts": rows, "threshold": learner.MASTERY, "mode": inp.get("mode", "quick"),
            "language": _language_info(lang.id, version),
            "map": visuals.concept_map(plan, model, current) if plan else None,
            "plan": ({"target": plan["target"], "prereqs": plan["prereqs"],
                      "subtopics": plan.get("subtopics", [])} if plan else None),
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
    concepts: list[str] = Field(default=[], max_length=12)
    interests: list[str] = []
    use_docs: bool = False
    # "guided" checks what the topic builds on before teaching it. "quick" is the original loop.
    mode: Literal["quick", "guided"] = "quick"
    exam_question: str | None = Field(default=None, max_length=2000)


class AnswerRequest(BaseModel):
    choice: int | None = None
    text: str | None = Field(default=None, max_length=4000)
    code: str | None = Field(default=None, max_length=8000)     # a program, for a code question
    assisted: bool = False                                      # a suggestion chip helped write it
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
def start(req: StartRequest, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    concepts = [c.strip() for c in req.concepts if c.strip()]
    exam = (req.exam_question or "").strip() or None
    if exam and req.mode != "guided":
        raise HTTPException(422, "An exam question needs guided mode.")
    if req.mode == "guided":
        if len(concepts) > 1:
            raise HTTPException(422, "Guided mode takes one topic at a time.")
        if not concepts and exam:
            concepts = ["exam-question"]       # replaced by the topic the plan finds in the question
    if not concepts:
        raise HTTPException(422, "Say what you want to learn.")
    student = user or req.student.strip()             # signed in: the account's name, whatever the body says
    _need_docs(student, req.use_docs)
    interests = [i.strip() for i in req.interests if i.strip()] or None
    run = session.start_session(s, student, concepts, interests, use_docs=req.use_docs,
                                mode=req.mode, exam_question=exam)
    _kick(run)
    return {"id": run}


@router.get("/sessions/{run_id}")
def get(run_id: str, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    _own(s, run_id, user)
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/answer")
def answer(run_id: str, req: AnswerRequest, s: Store = Depends(get_store),
           user: str | None = Depends(current_student)):
    _own(s, run_id, user)
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
    elif (req.code or "").strip() and lesson.get("code_task"):
        session.submit_code(s, q.id, req.code, req.confidence, req.assisted)
    else:
        raise HTTPException(422, "Choose an option." if lesson["quiz"]
                            else "Write your program." if lesson.get("code_task") else "Write your answer.")
    _kick(run_id)
    return snapshot(s, run_id)


def _toggle(run_id: str, s: Store, apply) -> dict:
    snapshot(s, run_id)
    if is_running(run_id):        # the run is about to write the learner model itself
        raise HTTPException(409, "Wait for the next lesson before changing this.")
    apply()
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/mode")
def mode(run_id: str, req: ModeRequest, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    """The type of the NEXT question. The one on screen stays as it is."""
    _own(s, run_id, user)
    if req.mode not in ("mcq", "text", "code"):
        raise HTTPException(422, "mode must be 'mcq', 'text' or 'code'.")
    if req.mode == "code":
        lang, version = _sandbox_language(s, run_id)
        ok, why = sandbox_ready(lang.id, version)
        if not ok:
            raise HTTPException(422, "Program questions need the code sandbox. " + why)
    return _toggle(run_id, s, lambda: session.set_answer_mode(s, run_id, req.mode))


class LanguageRequest(BaseModel):
    language: str = Field(max_length=20)
    version: str | None = Field(default=None, max_length=10)       # None: that language's default


@router.post("/sessions/{run_id}/language")
def language(run_id: str, req: LanguageRequest, s: Store = Depends(get_store),
             user: str | None = Depends(current_student)):
    """The code sandbox's language and version, picked in the sandbox. Applies to the editor and to the NEXT program
    question; it never changes what a lesson is about, and a question already asked keeps the language it was written in."""
    _own(s, run_id, user)
    snapshot(s, run_id)
    try:
        languages.resolve(req.language, req.version)
    except languages.UnknownLanguage as e:
        raise HTTPException(422, str(e))
    return _toggle(run_id, s, lambda: session.set_language(s, run_id, req.language, req.version))


@router.post("/sessions/{run_id}/source")
def source(run_id: str, req: SourceRequest, s: Store = Depends(get_store),
           user: str | None = Depends(current_student)):
    """Teach from the student's documents (on) or from general knowledge (off)."""
    _own(s, run_id, user)
    snapshot(s, run_id)
    _need_docs(s.meta(run_id)["student_id"], req.use_docs)
    return _toggle(run_id, s, lambda: session.set_use_docs(s, run_id, req.use_docs))


class ChoiceRequest(BaseModel):
    choice: str


@router.post("/sessions/{run_id}/choice")
def choice(run_id: str, req: ChoiceRequest, s: Store = Depends(get_store),
           user: str | None = Depends(current_student)):
    """The student's pick from the "what next?" menu after an explanation."""
    _own(s, run_id, user)
    snapshot(s, run_id)
    q = session.open_choice(s, run_id)
    if q is None or is_running(run_id):
        raise HTTPException(409, "There is nothing to choose right now.")
    if req.choice not in q.context["options"]:
        raise HTTPException(422, "That is not one of the options.")
    session.submit_choice(s, q.id, req.choice)
    _kick(run_id)
    return snapshot(s, run_id)


@router.post("/sessions/{run_id}/fallback")
def fallback(run_id: str, req: GapRequest, s: Store = Depends(get_store),
             user: str | None = Depends(current_student)):
    """The student's answer to "that is not in your documents"."""
    _own(s, run_id, user)
    if req.choice not in ("general", "skip"):
        raise HTTPException(422, "choice must be 'general' or 'skip'.")
    snapshot(s, run_id)
    gap = session.open_gap(s, run_id)
    if gap is None or is_running(run_id):
        raise HTTPException(409, "There is nothing to decide right now.")
    session.submit_gap(s, gap.id, req.choice)
    _kick(run_id)
    return snapshot(s, run_id)


class CodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=8000)
    concept: str | None = None                       # defaults to the topic of the latest lesson
    expected: str | None = Field(default=None, max_length=2000)   # what a correct run prints
    assisted: bool = False          # a suggestion chip helped, so a match proves nothing
    stdin: str = Field(default="", max_length=2000)   # what the program reads, for a program that reads input
    language: str | None = Field(default=None, max_length=20)      # a program question's own; else the sandbox's
    version: str | None = Field(default=None, max_length=10)


@router.get("/me/activity")
def my_activity(tz: int = 0, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    """The signed-in student's day-by-day activity and streak. `tz` is the browser's
    Date.getTimezoneOffset(), so a day is the student's own day."""
    if user is None:                                     # login off (tests): there is nobody to report on
        return activity.report(s, "", tz)
    return activity.report(s, user, tz)


@router.get("/me/learning")
def my_learning(s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    """What the signed-in student has learnt: each topic they have studied, and which of its parts they have
    completed. Worked out from their twin and past sessions; nothing is stored for it."""
    return dashboard.report(s, user or "")            # login off (tests): nobody's, so empty


@router.get("/languages")
def language_list():
    """What the code sandbox can run, and which runtimes this machine has, so its picker offers only real choices."""
    have = sandbox_installed()                         # None when Docker cannot be asked
    out = languages.catalogue()
    for lang in out:
        lang["installed"] = {v: have is not None and image in have for v, image in lang.pop("images").items()}
    return {"languages": out, "docker": have is not None}


@router.get("/code/status")
def code_status(language: str | None = None, version: str | None = None):
    """Whether code can run at all here, in this language. False until the isolation self-test passes."""
    try:
        lang, v = languages.resolve(language, version)
    except languages.UnknownLanguage as e:
        raise HTTPException(422, str(e))
    ok, why = sandbox_ready(lang.id, v)
    return {"available": ok, "reason": why, "language": lang.id, "version": v}


def _coach_concept(s: Store, run_id: str, asked: str | None) -> str:
    """The topic a piece of code is about: the one asked for, else the latest lesson's."""
    concepts = s.latest(run_id, "input")["concepts"]
    lesson = s.latest(run_id, "lesson")
    concept = asked or (lesson["concept"] if lesson else concepts[0])
    if concept not in concepts:
        raise HTTPException(422, "That topic is not part of this session.")
    return concept


class SuggestRequest(BaseModel):
    code: str = Field(max_length=8000)
    concept: str | None = None
    language: str | None = Field(default=None, max_length=20)      # a program question's own; else the sandbox's
    version: str | None = Field(default=None, max_length=10)


@router.post("/sessions/{run_id}/suggest")
def suggest(run_id: str, req: SuggestRequest, s: Store = Depends(get_store),
            user: str | None = Depends(current_student)):
    """Suggestion chips while the student types. The twin decides whether to help: a topic
    the student has not mastered gets no chips and no model call."""
    _own(s, run_id, user)
    snapshot(s, run_id)
    if is_running(run_id):
        raise HTTPException(409, "Wait for the next lesson.")
    concept = _coach_concept(s, run_id, req.concept)
    model = LearnerModel.model_validate(s.latest(run_id, "learner_model"))
    if coach.help_level(model, concept) == "withhold" or not req.code.strip():
        return {"enabled": False, "reason": "Try it yourself first: suggestions unlock when this topic is solid.",
                "suggestions": []}
    level = learner.level_for(learner.effective_mastery(model, concept))
    lang, version = _language_for(s, run_id, req.language, req.version)
    chips = coach.suggest(suggest_call, get_settings(), Budget(s, run_id, get_settings()),
                          concept, level, req.code, lang.prompt_line(version))
    return {"enabled": True, "reason": "You know this topic well, so suggestions are on.",
            "suggestions": chips}


@router.post("/sessions/{run_id}/code")
def run_code(run_id: str, req: CodeRequest, s: Store = Depends(get_store),
             user: str | None = Depends(current_student)):
    """The editor coach: run the student's code in the sandbox and turn the outcome into
    evidence on the same learner model the quizzes feed. Nothing about the tutoring
    loop changes; this only appends a `code_run` record and, when the run proves
    something, a new `learner_model`."""
    _own(s, run_id, user)
    snapshot(s, run_id)
    lang, version = _language_for(s, run_id, req.language, req.version)
    ok, why = sandbox_ready(lang.id, version)
    if not ok:
        raise HTTPException(503, "Running code is switched off here. " + why)
    if is_running(run_id):
        raise HTTPException(409, "Wait for the next lesson before running code.")
    concept = _coach_concept(s, run_id, req.concept)

    res = sandbox_run(req.code, language=lang.id, version=version, stdin=req.stdin)
    correct, tag = coach.evidence(res, req.expected, lang.id)
    if req.assisted and correct:
        correct = None
    s.append(run_id, "code_run", {"concept": concept, "code": req.code, "expected": req.expected,
                                  "language": lang.id, "version": version, "stdin": req.stdin,
                                  "stdout": res.stdout, "stderr": res.stderr, "exit_code": res.exit_code,
                                  "timed_out": res.timed_out, "correct": correct, "misconception": tag},
             "student")
    if correct is not None:
        # Read the model only now: an answer may have landed while the code ran.
        model = learner.apply_check(LearnerModel.model_validate(s.latest(run_id, "learner_model")),
                                    concept, correct, tag)
        s.append(run_id, "learner_model", model.model_dump(), "system")
        learners.save(s, model)
    return {"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.exit_code,
            "timed_out": res.timed_out, "correct": correct, "misconception": tag,
            "hint": coach.hint(res, correct, lang.id), "progress": _progress(s, run_id)}


@router.post("/sessions/{run_id}/resume")
def resume(run_id: str, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    """For a run left mid-step (the server restarted)."""
    _own(s, run_id, user)
    if _status(s, run_id) == "stalled":
        _kick(run_id)
    return snapshot(s, run_id)


# ------------------------------------------------------------------ documents

@router.get("/students/{student}/docs")
def list_docs(student: str, user: str | None = Depends(current_student)):
    _mine(student, user)
    return {"docs": library.docs(student)}


@router.post("/students/{student}/docs")
def upload_docs(student: str, files: list[UploadFile], s: Store = Depends(get_store),
                user: str | None = Depends(current_student)):
    """Sync on purpose: reading, converting and embedding a file is slow, and a plain
    `def` route runs on a worker thread instead of blocking the server."""
    _mine(student, user)
    try:
        for f in files:
            # Read one byte past the limit so an oversize file is seen, not truncated.
            library.save(s, student, f.filename or "document", f.file.read(library.MAX_BYTES + 1))
    except library.Rejected as e:
        raise HTTPException(422, str(e))
    return {"docs": library.docs(student)}


@router.post("/students/{student}/docs/sample")
def sample_docs(student: str, s: Store = Depends(get_store), user: str | None = Depends(current_student)):
    _mine(student, user)
    return {"docs": library.add_sample(s, student)}


@router.delete("/students/{student}/docs/{name}")
def remove_doc(student: str, name: str, s: Store = Depends(get_store),
               user: str | None = Depends(current_student)):
    _mine(student, user)
    if name not in library.docs(student):
        raise HTTPException(404, "No such document.")
    library.delete(s, student, name)
    return {"docs": library.docs(student)}

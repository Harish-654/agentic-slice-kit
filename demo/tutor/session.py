"""The edges of the loop: starting a session, carrying the learner model over
from the student's last one, and delivering an answer. The web page and the
tests both go through here, so neither reimplements the protocol."""
from __future__ import annotations

import json

from slice import callback
from slice.store import Store

from . import learners
from .schema import LearnerModel

DOMAIN = "tutor"


def previous_model(store: Store, student_id: str) -> LearnerModel | None:
    """The student's current learner model. The learners table is the fast path;
    a database from before it existed falls back to the newest run that has a
    model for this student."""
    saved = learners.load(store, student_id)
    if saved:
        return saved
    for r in store.list_runs(limit=200):           # newest first
        if r["domain"] != DOMAIN or store.meta(r["id"]).get("student_id") != student_id:
            continue
        found = store.latest(r["id"], "learner_model")
        if found:
            return LearnerModel.model_validate(found)
    return None


def start_session(store: Store, student_id: str, concepts: list[str],
                  interests: list[str] | None = None, use_docs: bool | None = None) -> str:
    model = previous_model(store, student_id) or LearnerModel(student_id=student_id)
    if interests is not None:
        model = model.model_copy(update={"interests": interests})
    if use_docs is not None:
        model = model.model_copy(update={"use_docs": use_docs})
    run = store.create_run(DOMAIN, {"student_id": student_id})
    store.append(run, "input", {"student_id": student_id, "concepts": concepts}, "student")
    store.append(run, "learner_model", model.model_dump(), "system")
    learners.save(store, model)
    return run


def _set(store: Store, run_id: str, **fields) -> None:
    """A toggle. Stored on the model, so it is still there next session."""
    m = LearnerModel.model_validate(store.latest(run_id, "learner_model"))
    m = m.model_copy(update=fields)
    store.append(run_id, "learner_model", m.model_dump(), "student")
    learners.save(store, m)


def set_answer_mode(store: Store, run_id: str, mode: str) -> None:
    """The type of the NEXT question: "mcq" or "text". The one being asked stays as it is."""
    _set(store, run_id, answer_mode=mode)


def set_use_docs(store: Store, run_id: str, on: bool) -> None:
    _set(store, run_id, use_docs=on)


def open_question(store: Store, run_id: str, kind: str):
    """What the student is being asked right now, of the given kind, or None."""
    for q in callback.pending(store, run_id):
        if q.context.get("kind") == kind:
            return q
    return None


def open_quiz(store: Store, run_id: str):
    return open_question(store, run_id, "student_quiz")


def open_gap(store: Store, run_id: str):
    """The "your documents do not cover this" question, if that is what is open."""
    return open_question(store, run_id, "doc_gap")


def submit_gap(store: Store, qid: str, choice: str) -> str | None:
    """`choice` is "general" (teach it without the documents) or "skip". Recorded under
    its own `who` so it is never mistaken for an answer to a quiz."""
    return callback.answer(store, qid, choice, who="student_gap")


def submit_mcq(store: Store, qid: str, choice: int, confidence: str | None = None) -> str | None:
    given = {"mode": "mcq", "choice": choice, "confidence": confidence}
    return callback.answer(store, qid, json.dumps(given), who="student")


def submit_text(store: Store, qid: str, text: str, confidence: str | None = None) -> str | None:
    given = {"mode": "text", "text": text, "confidence": confidence}
    return callback.answer(store, qid, json.dumps(given), who="student")


def submit_unknown(store: Store, qid: str) -> str | None:
    """"I don't know", for either kind of question. Honest, so it is never graded."""
    return callback.answer(store, qid, json.dumps({"mode": "dont_know"}), who="student")


def is_finished(store: Store, run_id: str) -> bool:
    return store.get_state(run_id).is_terminal

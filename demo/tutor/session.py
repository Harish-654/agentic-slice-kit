"""The edges of the loop: starting a session, carrying the learner model over
from the student's last one, and delivering an answer. The web page and the
tests both go through here, so neither reimplements the protocol."""
from __future__ import annotations

import json

from slice import callback
from slice.store import Store

from .schema import LearnerModel

DOMAIN = "tutor"


def previous_model(store: Store, student_id: str) -> LearnerModel | None:
    """The student's latest learner model from any earlier session. No table of
    its own: a session is a run, and the model is a version inside it."""
    for r in store.list_runs(limit=200):           # newest first
        if r["domain"] != DOMAIN or store.meta(r["id"]).get("student_id") != student_id:
            continue
        found = store.latest(r["id"], "learner_model")
        if found:
            return LearnerModel.model_validate(found)
    return None


def start_session(store: Store, student_id: str, concepts: list[str],
                  interests: list[str] | None = None) -> str:
    model = previous_model(store, student_id) or LearnerModel(student_id=student_id)
    if interests is not None:
        model = model.model_copy(update={"interests": interests})
    run = store.create_run(DOMAIN, {"student_id": student_id})
    store.append(run, "input", {"student_id": student_id, "concepts": concepts}, "student")
    store.append(run, "learner_model", model.model_dump(), "system")
    return run


def set_answer_mode(store: Store, run_id: str, mode: str) -> None:
    """The toggle. Stored on the model, so it is still there next session."""
    m = LearnerModel.model_validate(store.latest(run_id, "learner_model"))
    store.append(run_id, "learner_model",
                 m.model_copy(update={"answer_mode": mode}).model_dump(), "student")


def open_quiz(store: Store, run_id: str):
    """The question the student is being asked right now, or None."""
    for q in callback.pending(store, run_id):
        if q.context.get("kind") == "student_quiz":
            return q
    return None


def submit_mcq(store: Store, qid: str, choice: int) -> str | None:
    return callback.answer(store, qid, json.dumps({"mode": "mcq", "choice": choice}), who="student")


def submit_text(store: Store, qid: str, text: str) -> str | None:
    return callback.answer(store, qid, json.dumps({"mode": "text", "text": text}), who="student")


def is_finished(store: Store, run_id: str) -> bool:
    return store.get_state(run_id).is_terminal

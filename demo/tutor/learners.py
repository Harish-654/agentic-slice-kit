"""One row per student: their current learner model.

The versions in a run are the audit trail - every check, in order, immutable.
This table is the fast path: "who is this student" without replaying anything.
It is created here, on the run database, the way slice/retrieve.py creates its
own tables, so nothing in slice/ changes."""
from __future__ import annotations

import time

from slice.store import Store

from .schema import LearnerModel

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
    student_id TEXT PRIMARY KEY,
    model_json TEXT NOT NULL,
    updated_at REAL NOT NULL
)"""


def _ready(store: Store) -> None:
    store.db.execute(_SCHEMA)


def load(store: Store, student_id: str) -> LearnerModel | None:
    _ready(store)
    row = store.db.execute("SELECT model_json FROM learners WHERE student_id=?",
                           (student_id,)).fetchone()
    return LearnerModel.model_validate_json(row["model_json"]) if row else None


def save(store: Store, model: LearnerModel) -> None:
    _ready(store)
    store.db.execute(
        "INSERT INTO learners(student_id, model_json, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(student_id) DO UPDATE SET model_json=excluded.model_json, "
        "updated_at=excluded.updated_at",
        (model.student_id, model.model_dump_json(), time.time()))

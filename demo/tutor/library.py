"""A student's own documents, and searching only them.

Files are saved as uploads/<student>/<student>__<name>, converted if PDF or Word,
and ingested by the kit's retriever unchanged. The prefix is what scopes them: a
search keeps only chunks whose document carries the asking student's prefix, so
one student's notes never reach another student's lesson.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from slice import retrieve
from slice.retrieve import Chunk
from slice.store import Store

from . import notes

ROOT = Path("uploads")
SAMPLE = Path("corpus/python")
ALLOWED = {".md", ".txt", ".pdf", ".docx"}
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 10
# Measured on the sample notes: covered topics score 0.59-0.71, unrelated ones
# 0.96+, and same-subject-but-not-covered sits between (0.76-1.00). This cutoff
# only removes the clear misses; the model's own `covered` flag handles the rest.
THRESHOLD = 0.80


class Rejected(ValueError):
    """The upload is not acceptable; the message is safe to show the student."""


def slug(student: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", student.lower()).strip("-")[:40] or "student"


def _prefix(student: str) -> str:
    return f"{slug(student)}__"


def _folder(student: str) -> Path:
    return ROOT / slug(student)


def docs(student: str) -> list[str]:
    """The student's documents, by the name they uploaded them under."""
    folder, p = _folder(student), _prefix(student)
    return sorted(f.name[len(p):] for f in folder.glob(f"{p}*") if f.is_file()) if folder.is_dir() else []


def save(store: Store, student: str, name: str, data: bytes) -> str:
    """Validate, store and index one file. Returns the name it is listed under."""
    safe = re.sub(r"[^\w.\-]+", "_", Path(name).name).lstrip(".")   # no folders, no dotfiles
    if Path(safe).suffix.lower() not in ALLOWED:
        raise Rejected(f"{name!r}: only {', '.join(sorted(ALLOWED))} files can be added.")
    if len(data) > MAX_BYTES:
        raise Rejected(f"{name!r} is over {MAX_BYTES // 2**20} MB.")
    if safe not in docs(student) and len(docs(student)) >= MAX_FILES:
        raise Rejected(f"You can keep up to {MAX_FILES} documents. Remove one first.")
    folder = _folder(student)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (_prefix(student) + safe)).write_bytes(data)
    report = notes.prepare(folder)
    if safe in {k.removeprefix(_prefix(student)) for k in report["unreadable"]}:
        delete(store, student, safe)
        raise Rejected(f"{name!r} could not be read: {report['unreadable'][_prefix(student) + safe]}")
    retrieve.ingest(store, folder)
    return safe


def add_sample(store: Store, student: str) -> list[str]:
    """One click to try the tutor with the sample teacher notes."""
    for f in sorted(SAMPLE.glob("*.md")):
        save(store, student, f.name, f.read_bytes())
    return docs(student)


def delete(store: Store, student: str, name: str) -> None:
    """Remove the file, its converted copy, and every chunk indexed from it."""
    src = _prefix(student) + name
    folder = _folder(student)
    for f in (folder / src, folder / notes.CONVERTED / f"{src}.md"):
        f.unlink(missing_ok=True)
    retrieve._prepare(store)                    # loads sqlite-vec so chunk_vec can be edited
    ids = "SELECT chunk_id FROM chunks WHERE doc IN (?, ?)"
    args = (src, f"{src}.md")
    store.db.execute(f"DELETE FROM chunk_vec WHERE chunk_id IN ({ids})", args)
    store.db.execute("DELETE FROM chunks WHERE doc IN (?, ?)", args)


def search(store: Store, student: str, query: str, k: int = 4) -> list[Chunk]:
    """The student's own chunks that are close enough to the query, best first."""
    p = _prefix(student)
    # ponytail: fetches the 50 nearest overall then filters; a very large shared
    # index would want the filter inside the query.
    hits = retrieve.search(store, query, k=50)
    return [c for c in hits if c.doc.startswith(p) and c.distance <= THRESHOLD][:k]


def has_docs(student: str) -> bool:
    return bool(docs(student))

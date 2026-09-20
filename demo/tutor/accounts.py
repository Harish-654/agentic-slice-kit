"""Student accounts and sign-in sessions.

Until now a student was whatever name they typed, which was also the key for their learner model, their runs
and their document folder, so anyone typing the same name got that student's data. An account makes a name
belong to one person.

Nothing here is clever, on purpose:
- passwords are hashed with the standard library's scrypt and a random salt per account, and compared in
  constant time; nothing else about a password is ever stored;
- a sign-in is a random token; only its SHA-256 is kept, so a copy of the database cannot be used to sign in;
- a name that already has history (from before accounts existed) is LOCKED, not claimable, so nobody can take
  over someone else's progress by signing up first. `scripts/manage_accounts.py claim` attaches one deliberately.

The tables are created here on the run database, the way learners.py creates its own, so nothing in slice/
changes.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from slice.store import Store

from . import learners

SESSION_DAYS = 30
MIN_PASSWORD, MAX_PASSWORD = 8, 200
SCRYPT_N = 2 ** 14              # stored per account, so raising it later never breaks an old password
_NAME = re.compile(r"^[A-Za-z0-9 ._-]{2,40}$")

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS accounts (
        name_key   TEXT PRIMARY KEY,
        folder_key TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL,
        salt       BLOB NOT NULL,
        hash       BLOB NOT NULL,
        n          INTEGER NOT NULL,
        created_at REAL NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS auth_sessions (
        token_hash TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL)""",
)


class AccountError(ValueError):
    """The request cannot be honoured; the message is safe to show the student."""


def _ready(store: Store) -> None:
    for sql in _SCHEMA:
        store.db.execute(sql)


# ------------------------------------------------------------------ names and passwords

def clean_name(name: str) -> str:
    """The name as it will be kept: spaces collapsed, then checked. Raises AccountError."""
    name = " ".join((name or "").split())
    if not _NAME.match(name) or sum(c.isalnum() for c in name) < 2:
        raise AccountError("Use 2 to 40 letters, numbers, spaces, dots, dashes or underscores.")
    return name


def name_key(name: str) -> str:
    return name.casefold()


def folder_key(name: str) -> str:
    """The same key demo/tutor/library.py uses for a student's document folder. Two accounts must never
    share one, or they would share documents (a test pins that this matches library.slug)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "student"


def check_password(password: str) -> None:
    if not MIN_PASSWORD <= len(password or "") <= MAX_PASSWORD:
        raise AccountError(f"Use a password of {MIN_PASSWORD} to {MAX_PASSWORD} characters.")


def _hash(password: str, salt: bytes, n: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=8, p=1, dklen=32)


# ------------------------------------------------------------------ accounts

def has_history(store: Store, name: str) -> bool:
    """Does this name already belong to sessions from before accounts existed? Compared without regard to
    case, so "mithran" cannot be used to reach "Mithran"'s progress."""
    learners._ready(store)
    key = name_key(name)
    seen = [r["student_id"] for r in store.db.execute("SELECT student_id FROM learners")]
    seen += [r["sid"] for r in store.db.execute(
        "SELECT DISTINCT json_extract(meta_json, '$.student_id') AS sid FROM runs WHERE domain = 'tutor'")]
    return any(s and name_key(s) == key for s in seen)


def create(store: Store, name: str, password: str, claim_history: bool = False) -> str:
    """Make an account and return its name as kept. `claim_history` is for the admin script only: it lets
    a name that already has sessions be attached to a new password on purpose."""
    _ready(store)
    name = clean_name(name)
    check_password(password)
    if store.db.execute("SELECT 1 FROM accounts WHERE name_key=? OR folder_key=?",
                        (name_key(name), folder_key(name))).fetchone():
        raise AccountError("That name is taken, or too close to one that is. Please choose another.")
    if not claim_history and has_history(store, name):
        raise AccountError("That name has earlier sessions and is locked. Please choose a different name.")
    salt = secrets.token_bytes(16)
    store.db.execute(
        "INSERT INTO accounts(name_key, folder_key, name, salt, hash, n, created_at) VALUES (?,?,?,?,?,?,?)",
        (name_key(name), folder_key(name), name, salt, _hash(password, salt, SCRYPT_N), SCRYPT_N, time.time()))
    return name


def verify(store: Store, name: str, password: str) -> str | None:
    """The account's name if the password is right, else None. An unknown name costs the same time as a
    wrong password, so the delay does not reveal which names exist."""
    _ready(store)
    row = store.db.execute("SELECT name, salt, hash, n FROM accounts WHERE name_key=?",
                           (name_key(" ".join((name or "").split())),)).fetchone()
    if row is None:
        _hash(password or "", b"\0" * 16, SCRYPT_N)
        return None
    ok = hmac.compare_digest(_hash(password or "", row["salt"], row["n"]), row["hash"])
    return row["name"] if ok else None


def set_password(store: Store, name: str, password: str) -> None:
    """Admin recovery: a new password for an existing account, and every sign-in of theirs is ended."""
    _ready(store)
    check_password(password)
    row = store.db.execute("SELECT name FROM accounts WHERE name_key=?", (name_key(name),)).fetchone()
    if row is None:
        raise AccountError("There is no such account.")
    salt = secrets.token_bytes(16)
    store.db.execute("UPDATE accounts SET salt=?, hash=?, n=? WHERE name_key=?",
                     (salt, _hash(password, salt, SCRYPT_N), SCRYPT_N, name_key(name)))
    store.db.execute("DELETE FROM auth_sessions WHERE name=?", (row["name"],))


# ------------------------------------------------------------------ sign-ins

def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def open_session(store: Store, name: str, now: float | None = None) -> str:
    """A new sign-in for `name`. Returns the token to put in the cookie; the database keeps only its hash."""
    _ready(store)
    now = time.time() if now is None else now
    store.db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
    token = secrets.token_urlsafe(32)
    store.db.execute("INSERT INTO auth_sessions(token_hash, name, created_at, expires_at) VALUES (?,?,?,?)",
                     (_digest(token), name, now, now + SESSION_DAYS * 86400))
    return token


def who(store: Store, token: str | None, now: float | None = None) -> str | None:
    """The signed-in name for a cookie token, or None if it is unknown or has expired."""
    if not token:
        return None
    _ready(store)
    row = store.db.execute("SELECT name, expires_at FROM auth_sessions WHERE token_hash=?",
                           (_digest(token),)).fetchone()
    if row is None or row["expires_at"] < (time.time() if now is None else now):
        return None
    return row["name"]


def close_session(store: Store, token: str | None) -> None:
    if token:
        _ready(store)
        store.db.execute("DELETE FROM auth_sessions WHERE token_hash=?", (_digest(token),))

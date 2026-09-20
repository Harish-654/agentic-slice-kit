"""Accounts and sign-in: who a student is, and that everything they own is theirs alone.

Login is ON in these tests (the shared helpers switch it off so the other suites can test the tutor itself)."""
import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo.tutor import accounts, learners, library, session
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, lesson
from slice.store import Store
from tests.test_tutor import S
from tests.test_tutor_api import settle
from web import auth, student, tutor_api

PASSWORD = "correct horse battery"


@pytest.fixture
def app(tmp_path, monkeypatch):
    db = str(tmp_path / "auth.db")
    monkeypatch.setattr(student, "DB", db)
    monkeypatch.setattr(tutor_api, "DB", db)
    monkeypatch.setattr(library, "ROOT", tmp_path / "uploads")
    monkeypatch.setattr(accounts, "SCRYPT_N", 2 ** 4)              # cheap hashing: these tests make many accounts
    monkeypatch.setattr(auth, "limiter", auth.Limiter())
    monkeypatch.setattr(auth, "REQUIRED", True)
    stub = Stub({"teach": [lesson("T")] * 20})
    monkeypatch.setattr(tutor_api, "flow_factory", lambda: build_flow(call=stub, find=lambda *a, **k: []))
    monkeypatch.setattr(tutor_api, "get_settings", lambda: S)
    tutor_api._running.clear()
    return SimpleApp(db)


class SimpleApp:
    """One database and any number of browsers, each with its own cookies."""

    def __init__(self, db):
        self.db = db

    def browser(self):
        return TestClient(student.app)

    def store(self):
        return Store(Path(self.db))

    def signed_in(self, name="Asha", password=PASSWORD):
        c = self.browser()
        r = c.post("/api/auth/signup", json={"name": name, "password": password})
        assert r.status_code == 200, r.text
        return c


def start(c, topic="mutable-defaults", student_name="whoever"):
    r = c.post("/api/sessions", json={"student": student_name, "concepts": [topic]})
    assert r.status_code == 200, r.text
    run = r.json()["id"]
    settle(c, run)
    return run


# ------------------------------------------------------------------ signing up and in

def test_signing_up_signs_you_in_with_a_cookie_the_page_script_cannot_read(app):
    c = app.browser()
    r = c.post("/api/auth/signup", json={"name": "  Asha   K  ", "password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"student": "Asha K"}       # spaces tidied
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie and "max-age=" in cookie
    assert c.get("/api/auth/me").json() == {"student": "Asha K", "login_required": True}


def test_logging_out_ends_the_sign_in_for_good(app):
    c = app.signed_in()
    token = c.cookies.get(auth.COOKIE)
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    c.cookies.set(auth.COOKIE, token)                                       # replaying the old cookie must not work either
    assert c.get("/api/auth/me").status_code == 401


def test_a_wrong_password_and_an_unknown_name_get_the_same_answer(app):
    app.signed_in("Asha")
    c = app.browser()
    wrong = c.post("/api/auth/login", json={"name": "Asha", "password": "not the password"})
    nobody = c.post("/api/auth/login", json={"name": "Nobody", "password": "not the password"})
    assert wrong.status_code == nobody.status_code == 401 and wrong.json() == nobody.json()
    assert c.post("/api/auth/login", json={"name": "asha", "password": PASSWORD}).status_code == 200   # any case


def test_names_are_unique_however_they_are_typed(app):
    app.signed_in("Asha")
    for clash in ("asha", "ASHA", " asha "):
        assert app.browser().post("/api/auth/signup", json={"name": clash, "password": PASSWORD}).status_code == 422
    app.signed_in("asha.k")
    # "asha k" would share asha.k's DOCUMENT folder (library.slug drops punctuation), so it is refused too
    assert app.browser().post("/api/auth/signup", json={"name": "asha k", "password": PASSWORD}).status_code == 422


@pytest.mark.parametrize("name,password", [("a", PASSWORD), ("<script>", PASSWORD), ("x" * 41, PASSWORD),
                                           ("!!", PASSWORD), ("Asha", "short"), ("Asha", "x" * 201)])
def test_a_bad_name_or_password_is_refused_with_a_reason(app, name, password):
    r = app.browser().post("/api/auth/signup", json={"name": name, "password": password})
    assert r.status_code == 422 and r.json()["detail"]


def test_names_that_already_have_history_are_locked(app):
    store = app.store()
    learners.save(store, LearnerModel(student_id="Mithran"))
    session.start_session(store, "Hari", ["a"])                              # a run, and so a learner row
    store.close()
    for locked in ("Mithran", "mithran", "MITHRAN", "hari"):
        r = app.browser().post("/api/auth/signup", json={"name": locked, "password": PASSWORD})
        assert r.status_code == 422 and "earlier sessions" in r.json()["detail"], locked
    assert app.browser().post("/api/auth/signup", json={"name": "Mithran K", "password": PASSWORD}).status_code == 200


def test_the_admin_can_attach_a_locked_name_on_purpose_and_reset_a_password(app):
    store = app.store()
    learners.save(store, LearnerModel(student_id="Mithran"))
    accounts.create(store, "Mithran", PASSWORD, claim_history=True)
    c = app.browser()
    assert c.post("/api/auth/login", json={"name": "Mithran", "password": PASSWORD}).status_code == 200
    accounts.set_password(store, "mithran", "a brand new secret")
    store.close()
    assert c.get("/api/auth/me").status_code == 401                          # the reset ended their sign-in
    assert c.post("/api/auth/login", json={"name": "Mithran", "password": PASSWORD}).status_code == 401
    assert c.post("/api/auth/login", json={"name": "Mithran", "password": "a brand new secret"}).status_code == 200


# ------------------------------------------------------------------ what is stored

def test_neither_the_password_nor_the_sign_in_token_is_stored(app):
    c = app.signed_in("Asha")
    token = c.cookies.get(auth.COOKIE)
    store = app.store()
    row = store.db.execute("SELECT * FROM accounts").fetchone()
    assert row["hash"] != PASSWORD.encode() and len(row["hash"]) == 32 and len(row["salt"]) == 16
    sess = store.db.execute("SELECT token_hash FROM auth_sessions").fetchone()
    assert sess["token_hash"] == hashlib.sha256(token.encode()).hexdigest() and token not in sess["token_hash"]
    store.close()
    raw = b"".join(p.read_bytes() for p in Path(app.db).parent.glob("auth.db*"))
    assert PASSWORD.encode() not in raw and token.encode() not in raw


def test_two_accounts_with_the_same_password_get_different_hashes(app):
    app.signed_in("Asha")
    app.signed_in("Ben")
    hashes = {r["hash"] for r in app.store().db.execute("SELECT hash FROM accounts")}
    assert len(hashes) == 2


def test_an_old_password_still_works_after_the_hashing_cost_is_raised(app, monkeypatch):
    app.signed_in("Asha")
    monkeypatch.setattr(accounts, "SCRYPT_N", 2 ** 5)                        # the cost is kept per account
    assert app.browser().post("/api/auth/login", json={"name": "Asha", "password": PASSWORD}).status_code == 200


def test_the_folder_key_matches_the_one_the_document_library_uses():
    for name in ("Asha", "asha.k", "Asha K", "A-b_c", "x" * 40, "Ab 12"):
        assert accounts.folder_key(name) == library.slug(name)


def test_a_sign_in_expires_after_thirty_days(app):
    store = app.store()
    accounts.create(store, "Asha", PASSWORD)
    now = time.time()
    token = accounts.open_session(store, "Asha", now=now)
    assert accounts.who(store, token, now=now + 29 * 86400) == "Asha"
    assert accounts.who(store, token, now=now + 31 * 86400) is None
    accounts.open_session(store, "Asha", now=now + 32 * 86400)               # opening another sweeps the dead one
    assert store.db.execute("SELECT COUNT(*) AS n FROM auth_sessions").fetchone()["n"] == 1
    store.close()


def test_an_unknown_name_still_costs_a_password_hash(app, monkeypatch):
    calls = []
    real = accounts._hash
    monkeypatch.setattr(accounts, "_hash", lambda *a, **k: calls.append(1) or real(*a, **k))
    store = app.store()
    assert accounts.verify(store, "Nobody", "whatever") is None and calls == [1]   # so the delay does not reveal names
    store.close()


# ------------------------------------------------------------------ guessing passwords

def test_five_wrong_passwords_lock_that_name_for_a_minute_then_it_clears(app, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth, "limiter", auth.Limiter(clock=lambda: now[0]))
    app.signed_in("Asha")
    c = app.browser()
    for _ in range(5):
        assert c.post("/api/auth/login", json={"name": "Asha", "password": "guess"}).status_code == 401
    locked = c.post("/api/auth/login", json={"name": "Asha", "password": PASSWORD})   # even the RIGHT password waits
    assert locked.status_code == 429 and 0 < int(locked.headers["retry-after"]) <= 60
    now[0] += 61
    assert c.post("/api/auth/login", json={"name": "Asha", "password": PASSWORD}).status_code == 200


def test_a_lockout_is_per_name_so_one_person_cannot_lock_everyone_out(app, monkeypatch):
    app.signed_in("Asha")
    app.signed_in("Ben")
    c = app.browser()
    for _ in range(5):
        c.post("/api/auth/login", json={"name": "Asha", "password": "guess"})
    assert c.post("/api/auth/login", json={"name": "Ben", "password": PASSWORD}).status_code == 200


# ------------------------------------------------------------------ everything needs a sign-in

def test_nothing_is_reachable_without_signing_in(app):
    c = app.browser()
    for method, path, body in (("get", "/api/sessions/run_x", None), ("post", "/api/sessions", {"student": "a", "concepts": ["x"]}),
                               ("post", "/api/sessions/run_x/answer", {"choice": 0}), ("post", "/api/sessions/run_x/choice", {"choice": "quiz"}),
                               ("post", "/api/sessions/run_x/code", {"code": "1"}), ("post", "/api/sessions/run_x/suggest", {"code": "1"}),
                               ("get", "/api/students/asha/docs", None), ("delete", "/api/students/asha/docs/x", None),
                               ("post", "/api/students/asha/docs/sample", None), ("get", "/api/code/status", None),
                               ("get", "/api/auth/me", None)):
        r = getattr(c, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 401, (method, path, r.status_code)
    assert c.post("/api/auth/login", json={"name": "a", "password": "b"}).status_code == 401       # reachable, just wrong


def test_login_can_be_switched_off_for_tests_and_says_so(app, monkeypatch):
    monkeypatch.setattr(auth, "REQUIRED", False)
    assert app.browser().get("/api/auth/me").json() == {"student": None, "login_required": False}


# ------------------------------------------------------------------ what belongs to whom

def test_a_student_cannot_see_or_drive_someone_elses_session(app):
    asha, ben = app.signed_in("Asha"), app.signed_in("Ben")
    run = start(asha)
    assert asha.get(f"/api/sessions/{run}").status_code == 200
    for method, path, body in (("get", f"/api/sessions/{run}", None), ("post", f"/api/sessions/{run}/answer", {"choice": 1}),
                               ("post", f"/api/sessions/{run}/mode", {"mode": "text"}), ("post", f"/api/sessions/{run}/source", {"use_docs": False}),
                               ("post", f"/api/sessions/{run}/choice", {"choice": "quiz"}), ("post", f"/api/sessions/{run}/fallback", {"choice": "skip"}),
                               ("post", f"/api/sessions/{run}/suggest", {"code": "x"}), ("post", f"/api/sessions/{run}/code", {"code": "1"}),
                               ("post", f"/api/sessions/{run}/resume", None)):
        r = getattr(ben, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code)         # "no such session": it is not even confirmed to exist
    assert asha.get(f"/api/sessions/{run}").json()["messages"]             # and Ben's attempts changed nothing


def test_a_forged_student_name_in_the_request_is_ignored(app):
    asha = app.signed_in("Asha")
    run = start(asha, student_name="Ben")                                    # claims to be Ben
    assert asha.get(f"/api/sessions/{run}").json()["student"] == "Asha"
    store = app.store()
    assert store.meta(run)["student_id"] == "Asha"
    store.close()


def test_documents_are_locked_to_their_owner(app):
    asha, ben = app.signed_in("Asha"), app.signed_in("Ben")
    assert asha.post("/api/students/Asha/docs/sample").status_code == 200
    assert asha.get("/api/students/Asha/docs").json()["docs"]
    doc = asha.get("/api/students/Asha/docs").json()["docs"][0]
    for method, path in (("get", "/api/students/Asha/docs"), ("post", "/api/students/Asha/docs/sample"),
                         ("delete", f"/api/students/Asha/docs/{doc}")):
        assert getattr(ben, method)(path).status_code == 403, (method, path)
    r = ben.post("/api/students/Asha/docs", files=[("files", ("x.md", b"# mine now", "text/markdown"))])
    assert r.status_code == 403
    assert doc in asha.get("/api/students/Asha/docs").json()["docs"]        # still there
    assert ben.get("/api/students/Ben/docs").json() == {"docs": []}


# ------------------------------------------------------------------ the plain /classic page

def test_the_classic_page_sends_a_stranger_to_sign_in_and_serves_the_signed_in_student(app):
    stranger = app.browser()
    r = stranger.get("/classic/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert stranger.post("/classic/start", data={"concepts": "x"}, follow_redirects=False).status_code == 303

    asha = app.signed_in("Asha")
    assert "Signed in as <b>Asha</b>" in asha.get("/classic/").text
    r = asha.post("/classic/start", data={"student": "Ben", "concepts": "mutable-defaults"}, follow_redirects=False)
    assert r.status_code == 303
    run = r.headers["location"].rsplit("/", 1)[1]
    store = app.store()
    assert store.meta(run)["student_id"] == "Asha"                            # the form's name was ignored
    store.close()
    assert "No such session" in app.signed_in("Ben").get(f"/classic/s/{run}").text


# ------------------------------------------------------------------ the request's database connection

def test_a_requests_store_can_be_closed_from_another_thread(app):
    """FastAPI runs a request's dependencies on a thread pool, so the thread that opens the store is not
    always the one that closes it. SQLite's default refuses that, which showed up as random 500s."""
    import threading
    gen = tutor_api.get_store()
    store = next(gen)
    errors = []

    def finish():
        try:
            store.db.execute("SELECT 1").fetchone()              # used from another thread...
            next(gen, None)                                       # ...and closed from it
        except Exception as e:                                    # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=finish)
    t.start()
    t.join()
    assert errors == []


def test_many_signed_in_requests_at_once_never_fail(app):
    """The same hazard from the outside: overlapping requests hop between threads."""
    from concurrent.futures import ThreadPoolExecutor
    c = app.signed_in("Asha")
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: c.get("/api/me/activity?tz=0").status_code, range(60)))
    assert set(codes) == {200}

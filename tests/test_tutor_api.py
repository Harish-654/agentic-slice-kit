"""The chat page's JSON API, with the model stubbed and real background threads."""
import json
import threading
import time

from fastapi.testclient import TestClient

from demo.tutor.flow import build_flow
from demo.tutor.stub import Stub, grade, lesson
from slice.retrieve import Chunk
from tests.test_tutor import S
from web import student, tutor_api

NOTES = [Chunk("c1", "python-notes.md", 0, "Defaults are evaluated once.", 0.1)]
WRONG, RIGHT = 0, 1


def make(tmp_path, monkeypatch, script, call=None):
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(student, "DB", db)
    monkeypatch.setattr(tutor_api, "DB", db)
    stub = call or Stub(script)
    monkeypatch.setattr(tutor_api, "flow_factory",
                        lambda: build_flow(call=stub, find=lambda *a, **k: NOTES))
    monkeypatch.setattr(tutor_api, "get_settings", lambda: S)
    tutor_api._running.clear()
    return TestClient(student.app), stub


def settle(c, run, timeout=5.0):
    """Wait for the background thread to finish, as the page would by polling."""
    end = time.time() + timeout
    while time.time() < end:
        snap = c.get(f"/api/sessions/{run}").json()
        if snap["status"] != "working":
            return snap
        time.sleep(0.02)
    raise AssertionError("the session never stopped working")


def start(c, **kw):
    body = {"student": "asha", "concepts": ["mutable-defaults"], **kw}
    r = c.post("/api/sessions", json=body)
    assert r.status_code == 200
    return r.json()["id"]


def test_a_session_starts_and_hands_back_a_lesson_without_the_answer_key(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN")]})
    run = start(c)
    snap = settle(c, run)

    assert snap["status"] == "waiting_student"
    [msg] = snap["messages"]
    assert msg["kind"] == "lesson" and msg["style"] == "plain" and msg["explanation"] == "PLAIN"
    assert msg["quiz"]["answered"] is None
    assert [set(o) for o in msg["quiz"]["options"]] == [{"text"}] * 3      # no tags, no index
    sent = json.dumps(snap)
    assert "default-is-copied" not in sent and '"correct"' not in sent      # nothing gives it away


def test_a_wrong_answer_is_marked_explained_and_followed_by_a_new_lesson(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN"), lesson("ANALOGY")]})
    run = start(c)
    settle(c, run)
    c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG})
    snap = settle(c, run)

    kinds = [m["kind"] for m in snap["messages"]]
    assert kinds == ["lesson", "answer", "feedback", "lesson"]
    first, said, feedback, second = snap["messages"]
    assert first["quiz"]["answered"] == {"chosen": 0, "correct_index": 1, "correct": False}
    assert said["role"] == "user" and said["text"] == "[1]"
    assert feedback["correct"] is False and feedback["misconception"] == "default-is-copied"
    assert feedback["via"] == "mcq"
    assert second["style"] == "analogy"                                    # the back-edge
    row = snap["progress"]["concepts"][0]
    assert row["mastery"] < 0.3 and row["beliefs"] == [["default-is-copied", 1]]


def test_feedback_arrives_while_the_next_lesson_is_still_being_written(tmp_path, monkeypatch):
    gate = threading.Event()
    inner = Stub({"teach": [lesson("PLAIN"), lesson("ANALOGY")]})

    def slow(**kw):                       # the second lesson is held until the test lets go
        if len(inner.calls) == 1:
            gate.wait(5)
        return inner(**kw)

    c, _ = make(tmp_path, monkeypatch, None, call=slow)
    run = start(c)
    settle(c, run)
    c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG})

    deadline, snap = time.time() + 3, None
    while time.time() < deadline:
        snap = c.get(f"/api/sessions/{run}").json()
        if any(m["kind"] == "feedback" for m in snap["messages"]):
            break
        time.sleep(0.02)
    assert snap["status"] == "working"                                     # still generating...
    assert [m["kind"] for m in snap["messages"]] == ["lesson", "answer", "feedback"]   # ...but told
    gate.set()
    assert settle(c, run)["status"] == "waiting_student"


def test_a_session_ends_on_mastery_with_a_reason(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a"), lesson("b"), lesson("c")]})
    run = start(c)
    settle(c, run)
    for choice in (WRONG, RIGHT, RIGHT):
        c.post(f"/api/sessions/{run}/answer", json={"choice": choice})
        snap = settle(c, run)
    assert snap["status"] == "complete"
    assert snap["messages"][-1] == {"id": snap["messages"][-1]["id"], "role": "assistant",
                                    "kind": "end", "reason": "mastery"}
    assert snap["progress"]["concepts"][0]["mastered"] is True


def test_free_text_goes_to_the_grader(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a"), lesson("b")],
                                        "grade": [grade(False, "Default Is Copied", "Not quite.")]})
    run = start(c)
    settle(c, run)
    assert c.post(f"/api/sessions/{run}/mode", json={"mode": "text"}).json()["progress"]["answer_mode"] == "text"
    c.post(f"/api/sessions/{run}/answer", json={"text": "a fresh list each call"})
    snap = settle(c, run)
    said, feedback = snap["messages"][1], snap["messages"][2]
    assert said["text"] == "a fresh list each call" and feedback["text"] == "Not quite."
    assert feedback["via"] == "text"
    assert snap["messages"][0]["quiz"]["answered"]["chosen"] is None


def test_bad_requests_are_refused_not_swallowed(tmp_path, monkeypatch):
    gate = threading.Event()
    inner = Stub({"teach": [lesson("a"), lesson("b")]})

    def slow(**kw):
        if len(inner.calls) == 1:
            gate.wait(5)
        return inner(**kw)

    c, _ = make(tmp_path, monkeypatch, None, call=slow)
    assert c.get("/api/sessions/run_nope").status_code == 404
    run = start(c)
    settle(c, run)
    assert c.post(f"/api/sessions/{run}/answer", json={"choice": 9}).status_code == 422
    assert c.post(f"/api/sessions/{run}/answer", json={}).status_code == 422
    assert c.post(f"/api/sessions/{run}/mode", json={"mode": "essay"}).status_code == 422
    assert c.post("/api/sessions", json={"student": "x", "concepts": []}).status_code == 422

    c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG})
    time.sleep(0.1)                                        # the next lesson is being written
    assert c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT}).status_code == 409
    assert c.post(f"/api/sessions/{run}/mode", json={"mode": "text"}).status_code == 409
    gate.set()
    settle(c, run)


def test_a_crash_in_the_background_ends_the_session_visibly(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    monkeypatch.setattr(tutor_api, "flow_factory", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    run = start(c)
    snap = settle(c, run)
    assert snap["status"] == "failed"
    assert "boom" in snap["messages"][-1]["text"] and snap["messages"][-1]["problem"] is True


def test_a_run_left_mid_step_can_be_resumed(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a")]})
    monkeypatch.setattr(tutor_api, "_kick", lambda run_id: None)           # "the server restarted"
    run = start(c)
    assert c.get(f"/api/sessions/{run}").json()["status"] == "stalled"
    monkeypatch.undo()
    c2, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a")]})
    c2.post(f"/api/sessions/{run}/resume")
    assert settle(c2, run)["status"] == "waiting_student"


def test_the_root_serves_the_ui_or_says_how_to_build_it(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    r = c.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower() or "<!doctype" in r.text.lower()
    assert c.get("/classic/").status_code == 200                           # the fallback stays up


def test_the_notes_endpoint_lists_topics_from_the_ingested_documents(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    assert c.get("/api/notes").json() == {"concepts": []}                  # nothing ingested yet
    from slice.store import Store
    s = Store(tutor_api.DB)
    s.db.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, doc TEXT, ordinal INT, text TEXT)")
    for i, doc in enumerate(["mutable-defaults.md", "week3.pdf.md", "loops.docx.md", "loops.docx.md"]):
        s.db.execute("INSERT INTO chunks VALUES (?,?,?,?)", (f"c{i}", doc, 0, "x"))
    assert c.get("/api/notes").json() == {"concepts": ["loops", "mutable-defaults", "week3"]}


def test_the_committed_build_is_complete():
    """The UI ships as built files so running the tutor needs no Node. A build
    that is missing, or that points at files which were not committed with it,
    would leave the page blank; this fails first."""
    import re
    from pathlib import Path
    dist = Path(student.UI_DIST)
    index = (dist / "index.html").read_text()
    refs = re.findall(r'(?:src|href)="/(assets/[^"]+)"', index)
    assert refs, "index.html references no assets: was it built?"
    assert [r for r in refs if not (dist / r).is_file()] == []

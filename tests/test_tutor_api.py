"""The chat page's JSON API, with the model stubbed and real background threads."""
import json
import threading
import time

from fastapi.testclient import TestClient

from demo.tutor.flow import build_flow
from demo.tutor import library
from demo.tutor.stub import Stub, grade, lesson, open_lesson
from slice.retrieve import Chunk
from tests.test_tutor import S
from web import auth, student, tutor_api

NOTES = [Chunk("c1", "python-notes.md", 0, "Defaults are evaluated once.", 0.1)]
WRONG, RIGHT = 0, 1


def make(tmp_path, monkeypatch, script, call=None, find=lambda *a, **k: NOTES):
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(student, "DB", db)
    monkeypatch.setattr(tutor_api, "DB", db)
    monkeypatch.setattr(library, "ROOT", tmp_path / "uploads")
    monkeypatch.setattr(auth, "REQUIRED", False)     # these tests are about the tutor; test_tutor_auth.py signs in
    stub = call or Stub(script)
    monkeypatch.setattr(tutor_api, "flow_factory", lambda: build_flow(call=stub, find=find))
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


def test_the_committed_build_is_complete():
    """The UI ships as built files so running the tutor needs no Node. A build that is missing,
    that points at files which were not committed with it, or that git is ignoring, would leave
    a fresh checkout with a blank page. Checking the disk is not enough (it once passed while
    dist/ was gitignored), so this asks git what it actually tracks."""
    import re
    import subprocess
    from pathlib import Path
    dist = Path(student.UI_DIST)
    index = (dist / "index.html").read_text()
    refs = re.findall(r'(?:src|href)="/(assets/[^"]+)"', index)
    assert refs, "index.html references no assets: was it built?"
    assert [r for r in refs if not (dist / r).is_file()] == []
    tracked = set(subprocess.run(["git", "ls-files", "--", str(dist)], capture_output=True, text=True,
                                 cwd=dist.parent.parent.parent).stdout.split())
    needed = {f"web/ui/dist/{r}" for r in ["index.html", *refs]}
    assert needed <= tracked, f"not tracked by git: {sorted(needed - tracked)}"



SLICES = b"# List slicing\n\nAn index starts at 0. A slice items[1:3] excludes the stop index.\n"


def upload(c, student_name, name="slicing.md", data=SLICES):
    return c.post(f"/api/students/{student_name}/docs", files=[("files", (name, data, "text/markdown"))])


def test_written_questions_follow_the_toggle_and_go_to_the_grader(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a"), open_lesson("b"), open_lesson("c")],
                                        "grade": [grade(False, "Default Is Copied", "Not quite.")]})
    run = start(c)
    settle(c, run)

    snap = c.post(f"/api/sessions/{run}/mode", json={"mode": "text"}).json()
    assert snap["progress"]["answer_mode"] == "text"
    assert snap["messages"][0]["quiz"] is not None                          # the card on screen is unchanged
    assert c.post(f"/api/sessions/{run}/answer", json={"text": "typed"}).status_code == 422   # ...and still a choice

    c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT})
    snap = settle(c, run)
    written = snap["messages"][-1]
    assert written["kind"] == "lesson" and written["quiz"] is None
    assert set(written["open"]) == {"question", "code", "answered"}          # no rubric, no model answer
    assert c.post(f"/api/sessions/{run}/answer", json={"choice": 0}).status_code == 422

    c.post(f"/api/sessions/{run}/answer", json={"text": "a fresh list each call"})
    snap = settle(c, run)
    said, feedback = snap["messages"][-3], snap["messages"][-2]
    assert said["text"] == "a fresh list each call"
    assert feedback["via"] == "text" and feedback["text"] == "Not quite."
    assert feedback["misconception"] == "default-is-copied"
    assert snap["messages"][3]["open"]["answered"] == {"chosen": None, "correct_index": None, "correct": False}


def test_nothing_a_written_answer_is_graded_against_is_ever_sent(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [open_lesson("a")]})
    run = start(c)
    sent = json.dumps(settle(c, run))
    for secret in ("the default list is created once", "The default is built when def runs",
                   "default-is-copied", "says each call gets a fresh list", "rubric", "model_answer"):
        assert secret not in sent, secret


def test_documents_are_added_listed_and_removed_per_student(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    assert upload(c, "asha").json() == {"docs": ["slicing.md"]}
    assert c.get("/api/students/ravi/docs").json() == {"docs": []}               # not Ravi's
    assert c.delete("/api/students/ravi/docs/slicing.md").status_code == 404     # and he cannot remove it
    assert c.post("/api/students/ravi/docs/sample").json()["docs"] == [
        "is-vs-equals.md", "list-slicing.md", "mutable-defaults.md"]
    assert c.delete("/api/students/asha/docs/slicing.md").json() == {"docs": []}


def test_uploads_that_are_not_acceptable_are_refused_with_a_reason(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    r = upload(c, "asha", "run.exe", b"MZ")
    assert r.status_code == 422 and "only" in r.json()["detail"]
    r = upload(c, "asha", "big.md", b"x" * (library.MAX_BYTES + 1))
    assert r.status_code == 422 and "MB" in r.json()["detail"]
    assert c.get("/api/students/asha/docs").json() == {"docs": []}


def test_documents_mode_needs_a_document_and_can_be_switched_mid_session(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a", cites=()), lesson("b")]})
    assert c.post("/api/sessions", json={"student": "asha", "concepts": ["x"], "use_docs": True}).status_code == 422

    run = start(c)                                              # general mode
    snap = settle(c, run)
    assert snap["progress"]["use_docs"] is False and snap["messages"][0]["source"] == "general"
    assert c.post(f"/api/sessions/{run}/source", json={"use_docs": True}).status_code == 422   # no documents yet
    upload(c, "asha")
    snap = c.post(f"/api/sessions/{run}/source", json={"use_docs": True}).json()
    assert snap["progress"]["use_docs"] is True and snap["progress"]["docs"] == ["slicing.md"]

    c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT})
    snap = settle(c, run)
    lesson_msg = snap["messages"][-1]
    assert lesson_msg["source"] == "docs" and lesson_msg["citations"] == [NOTES[0].cite()]


def test_a_topic_missing_from_the_documents_waits_for_the_students_choice(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("general", cites=())]}, find=lambda *a, **k: [])
    upload(c, "asha")
    run = c.post("/api/sessions", json={"student": "asha", "concepts": ["decorators"], "use_docs": True}).json()["id"]
    snap = settle(c, run)

    assert snap["status"] == "waiting_choice"
    [notice] = snap["messages"]
    assert notice["kind"] == "notice" and notice["gap"] == {"concept": "decorators", "answer": None}
    assert c.post(f"/api/sessions/{run}/answer", json={"choice": 0}).status_code == 409
    assert c.post(f"/api/sessions/{run}/fallback", json={"choice": "maybe"}).status_code == 422

    c.post(f"/api/sessions/{run}/fallback", json={"choice": "general"})
    snap = settle(c, run)
    assert snap["status"] == "waiting_student"
    assert snap["messages"][0]["gap"]["answer"] == "general"                # the buttons are spent
    assert snap["messages"][1]["source"] == "general"                       # and the lesson says where it came from


def test_skipping_a_topic_ends_the_session_and_says_why(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {}, find=lambda *a, **k: [])
    upload(c, "asha")
    run = c.post("/api/sessions", json={"student": "asha", "concepts": ["decorators"], "use_docs": True}).json()["id"]
    settle(c, run)
    c.post(f"/api/sessions/{run}/fallback", json={"choice": "skip"})
    snap = settle(c, run)
    assert snap["status"] == "complete" and snap["messages"][-1]["reason"] == "skipped"


def test_a_citation_shows_the_students_file_name_not_the_storage_prefix():
    from types import SimpleNamespace
    payload = {"concept": "c", "style": "plain", "source": "docs", "explanation": "x", "diagram": None,
               "citations": ["asha-1__mutable-defaults.md#0"], "open": None,
               "quiz": {"question": "q", "code": None, "options": [{"text": "a"}, {"text": "b"}], "correct": 0}}
    msg = tutor_api._lesson_message(SimpleNamespace(seq=1, payload=payload))
    assert msg["citations"] == ["mutable-defaults.md#0"]


def test_confidence_and_dont_know_reach_the_page(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a"), lesson("b"), lesson("c")]})
    run = start(c)
    settle(c, run)

    assert c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG, "confidence": "certain"}).status_code == 422
    assert c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG, "dont_know": True}).status_code == 422
    c.post(f"/api/sessions/{run}/answer", json={"choice": WRONG, "confidence": "high"})
    snap = settle(c, run)
    feedback = snap["messages"][2]
    assert feedback["confidence"] == "high" and feedback["dont_know"] is False

    c.post(f"/api/sessions/{run}/answer", json={"dont_know": True})
    snap = settle(c, run)
    card = snap["messages"][3]["quiz"]
    said, feedback = snap["messages"][4], snap["messages"][5]
    assert said["text"] == "I don't know"
    assert card["answered"] == {"chosen": None, "correct_index": 1, "correct": False, "dont_know": True}
    assert feedback["dont_know"] is True and feedback["misconception"] is None and feedback["confidence"] is None
    assert snap["messages"][-1]["style"] == "worked_example"               # two lessons that did not land


def test_a_written_answer_carries_its_confidence_and_can_be_given_up_on(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("a"), open_lesson("b"), open_lesson("c"), open_lesson("d")],
                                        "grade": [grade(True, None, "Yes.")]})
    run = start(c, concepts=["x", "y", "z"])          # several topics, so one being learnt does not end it
    settle(c, run)
    c.post(f"/api/sessions/{run}/mode", json={"mode": "text"})             # the NEXT question is written
    c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT, "confidence": "medium"})
    snap = settle(c, run)
    assert snap["messages"][-1]["open"] is not None

    c.post(f"/api/sessions/{run}/answer", json={"text": "the default is built once", "confidence": "low"})
    snap = settle(c, run)
    feedback = snap["messages"][-2]
    assert feedback["via"] == "text" and feedback["confidence"] == "low" and feedback["correct"] is True

    c.post(f"/api/sessions/{run}/answer", json={"dont_know": True})
    snap = settle(c, run)
    card = snap["messages"][-4]["open"]
    assert card["answered"]["dont_know"] is True and card["answered"]["correct_index"] is None
    assert "A good answer:" in snap["messages"][-2]["text"]                # the model answer, shown once given up

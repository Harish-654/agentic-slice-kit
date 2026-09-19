"""The student page, driven through a browser-shaped client with the stub model."""
from fastapi.testclient import TestClient

from demo.tutor.flow import build_flow
from demo.tutor.stub import Stub, lesson
from slice.retrieve import Chunk
from web import expert, student

NOTES = [Chunk("c1", "python-notes.md", 0, "Defaults are evaluated once.", 0.1)]


def client(tmp_path, monkeypatch, script):
    db = str(tmp_path / "w.db")
    stub = Stub(script)
    for mod in (student, expert):
        monkeypatch.setattr(mod, "DB", db)
    monkeypatch.setattr(student, "NOTES", "")           # no corpus folder: no embeddings
    monkeypatch.setattr(student, "build_flow",
                        lambda: build_flow(call=stub, find=lambda *a, **k: NOTES))
    monkeypatch.setattr(student, "settings", lambda: __import__("tests.test_tutor", fromlist=["S"]).S)
    return TestClient(student.app, follow_redirects=True)


def test_a_student_learns_through_the_page(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, {"teach": [lesson("PLAIN", diagram="graph TD; A-->B"),
                                                 lesson("ANALOGY"), lesson("WORKED")]})
    r = c.post("/classic/start", data={"student": "asha", "concepts": "mutable-defaults"})
    assert "PLAIN" in r.text and "type='radio'" in r.text        # a lesson, and MCQ by default
    assert "class='mermaid'" in r.text                            # the diagram is drawn
    run = str(r.url).rsplit("/", 1)[1]

    # not for experts: the quiz must not appear on the teacher page
    assert "Nothing waiting" in TestClient(expert.app).get("/").text

    r = c.post(f"/classic/s/{run}/answer", data={"choice": "0"})           # the wrong belief
    assert "Not quite" in r.text and "ANALOGY" in r.text           # feedback, then a different lesson

    r = c.post(f"/classic/s/{run}/mode", data={"mode": "text"})            # the toggle
    assert "<textarea" in r.text and "type='radio'" not in r.text

    r = c.post(f"/classic/s/{run}/mode", data={"mode": "mcq"})
    c.post(f"/classic/s/{run}/answer", data={"choice": "1"})
    r = c.post(f"/classic/s/{run}/answer", data={"choice": "1"})
    assert "Session over" in r.text and "got the hang" in r.text


def test_code_and_markup_render_safely(tmp_path, monkeypatch):
    import json
    raw = json.loads(lesson("Look:\n\n```python\nx = [1]\n```\n\nUse `is` here <b>x</b>"))
    raw["quiz"]["question"] = "What does it print?"
    raw["quiz"]["code"] = "print(x == [1])"
    c = client(tmp_path, monkeypatch, {"teach": [json.dumps(raw)]})
    r = c.post("/classic/start", data={"student": "asha", "concepts": "x"})
    assert "<pre><code>x = [1]</code></pre>" in r.text            # fence, language tag dropped
    assert "<pre><code>print(x == [1])</code></pre>" in r.text    # the quiz's own code is visible
    assert "<code>is</code>" in r.text and "&lt;b&gt;" in r.text  # inline code; markup escaped

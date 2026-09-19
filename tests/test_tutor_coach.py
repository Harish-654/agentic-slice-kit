"""The editor coach: what a run of the student's code means, and the route that records it.
The sandbox is stubbed; the one test that needs real Docker is marked `integration`."""
import pytest

from demo.tutor import coach, sandbox
from demo.tutor.sandbox import Result
from demo.tutor.stub import Stub, lesson
from tests.test_tutor_api import make, settle, start
from web import tutor_api


def res(stdout="", stderr="", code=0, timed_out=False):
    return Result(stdout, stderr, code, timed_out)


# ---------------------------------------------------------------- pure rules

def test_an_error_names_the_idea_and_counts_as_wrong():
    r = res(stderr='Traceback...\nNameError: name "x" is not defined', code=1)
    assert coach.evidence(r) == (False, "undefined-name")
    assert "before it exists" in coach.hint(r, False)


def test_running_without_error_proves_nothing_unless_output_is_expected():
    assert coach.evidence(res("hi\n")) == (None, None)
    assert coach.evidence(res("4\n"), expected="4") == (True, None)
    assert coach.evidence(res("5\n"), expected="4") == (False, "wrong-output")


def test_a_timeout_or_a_bare_exit_is_no_evidence():
    assert coach.evidence(res(timed_out=True, code=None)) == (None, None)
    assert coach.evidence(res(code=1)) == (None, None)
    assert "too long" in coach.hint(res(timed_out=True, code=None), None)


# ---------------------------------------------------------------- the route

def ready(monkeypatch, result=None, ok=True):
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda: (ok, "" if ok else "Docker is not installed."))
    monkeypatch.setattr(tutor_api, "sandbox_run", lambda code: result or res("4\n"))


def test_a_failing_run_becomes_a_misconception_on_the_learner_model(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN")]})
    ready(monkeypatch, res(stderr="IndexError: list index out of range", code=1))
    run = start(c)
    settle(c, run)

    r = c.post(f"/api/sessions/{run}/code", json={"code": "[][0]"})
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is False and body["misconception"] == "index-out-of-range" and body["hint"]
    [row] = body["progress"]["concepts"]
    assert row["mastery"] < 0.3 and ["index-out-of-range", 1] in row["beliefs"]


def test_code_that_merely_runs_leaves_the_model_alone(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN")]})
    ready(monkeypatch)
    run = start(c)
    before = settle(c, run)["progress"]["concepts"][0]["mastery"]

    body = c.post(f"/api/sessions/{run}/code", json={"code": "print(2+2)"}).json()
    assert body["correct"] is None
    assert body["progress"]["concepts"][0]["mastery"] == before


def test_nothing_runs_when_the_sandbox_is_not_proven(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN")]})
    ready(monkeypatch, ok=False)
    monkeypatch.setattr(tutor_api, "sandbox_run", lambda code: pytest.fail("ran without isolation"))
    run = start(c)
    settle(c, run)

    assert c.get("/api/code/status").json() == {"available": False, "reason": "Docker is not installed."}
    assert c.post(f"/api/sessions/{run}/code", json={"code": "1"}).status_code == 503


def test_code_for_a_topic_outside_the_session_is_refused(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("PLAIN")]})
    ready(monkeypatch)
    run = start(c)
    settle(c, run)
    assert c.post(f"/api/sessions/{run}/code", json={"code": "1", "concept": "other"}).status_code == 422


# ---------------------------------------------------------- the real thing

@pytest.mark.integration
def test_the_real_sandbox_is_isolated_and_stops_runaway_code():
    ok, why = sandbox.available(force=True)
    assert ok, why                          # needs Docker running and `docker pull python:3.12-slim`
    assert sandbox.run("print(6*7)").stdout == "42\n"
    assert sandbox.run("while True: pass", timeout=3).timed_out

"""Program questions and twin-driven assist. The model is scripted and the "sandbox" is a
local Python, so the real harness (per-run token, hidden tests) is exercised with no Docker."""
import json
import subprocess
import sys
import time
from pathlib import Path

from demo.tutor import coach, learners, session
from demo.tutor.flow import build_flow
from demo.tutor.sandbox import Result
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, code_lesson
from slice import runner
from slice.store import Store
from tests.test_tutor import S, find
from tests.test_tutor_api import make, settle, start
from web import tutor_api

RIGHT = "def total(prices):\n    return sum(prices)"
FORGETS = "def total(prices):\n    return 0"           # fails total([1, 2, 3])
NO_EMPTY = "def total(prices):\n    return sum(prices) if prices else None"


def local_run(code, timeout=10):
    """Stands in for the Docker sandbox. Trusted test code only."""
    p = subprocess.run([sys.executable, "-I", "-"], input=code, capture_output=True, text=True, timeout=timeout)
    return Result(p.stdout, p.stderr, p.returncode)


def program_run(tmp_path, code, *, run=local_run, ready=lambda: (True, ""), assisted=False, model=None):
    store = Store(tmp_path / "r.db")
    if model:
        learners.save(store, model)
    run_id = session.start_session(store, "s1", ["mutable-defaults"])
    session.set_answer_mode(store, run_id, "code")
    stub = Stub({"teach": [code_lesson("A"), code_lesson("B")]})
    flow = lambda: build_flow(call=stub, find=find, run=run, ready=ready)   # noqa: E731
    runner.advance(store, run_id, flow(), S)
    q = session.open_quiz(store, run_id)
    session.submit_code(store, q.id, code, None, assisted)
    runner.advance(store, run_id, flow(), S)
    return store, run_id


def test_a_wrong_program_is_diagnosed_by_the_test_it_fails(tmp_path):
    store, run = program_run(tmp_path, FORGETS)
    check = store.history(run, "check")[0].payload
    assert check["correct"] is False and check["misconception"] == "forgets-to-accumulate"
    assert "forgets-to-accumulate" in check["feedback"] and "6" not in check["feedback"]   # names the idea, not the answer
    model = LearnerModel.model_validate(store.latest(run, "learner_model"))
    assert model.mastery["mutable-defaults"] < 0.3


def test_the_second_test_names_its_own_belief(tmp_path):
    store, run = program_run(tmp_path, NO_EMPTY)
    assert store.history(run, "check")[0].payload["misconception"] == "empty-input-not-handled"


def test_a_correct_program_passes_and_raises_mastery(tmp_path):
    store, run = program_run(tmp_path, RIGHT)
    check = store.history(run, "check")[0].payload
    assert check["correct"] is True and check["mode"] == "code"
    assert LearnerModel.model_validate(store.latest(run, "learner_model")).mastery["mutable-defaults"] == 0.65


def test_help_from_a_suggestion_counts_for_less(tmp_path):
    store, run = program_run(tmp_path, RIGHT, assisted=True)
    assert store.history(run, "check")[0].payload["confidence"] == "low"
    assert LearnerModel.model_validate(store.latest(run, "learner_model")).mastery["mutable-defaults"] == 0.51


def test_printing_a_pass_message_cannot_fake_the_checks(tmp_path):
    store, run = program_run(tmp_path, "import sys\nprint('@@x:0@@ 6', '@@x:1@@ 0')\nsys.exit(0)")
    check = store.history(run, "check")[0].payload
    assert check["correct"] is False and check["misconception"] == "did-not-run"


def test_a_crash_inside_a_check_is_reported_with_its_error_class(tmp_path):
    store, run = program_run(tmp_path, "def total(prices):\n    return prices[99]")
    check = store.history(run, "check")[0].payload
    assert check["misconception"] == "forgets-to-accumulate" and "IndexError" in check["feedback"]


def test_a_timeout_is_a_runaway_loop(tmp_path):
    store, run = program_run(tmp_path, "def total(p):\n    while True: pass",
                             run=lambda code: Result("", "", None, timed_out=True))
    assert store.history(run, "check")[0].payload["misconception"] == "runaway-loop"


def test_a_syntax_error_is_tagged_from_the_error_class(tmp_path):
    store, run = program_run(tmp_path, "def total(prices:\n    return 1")
    assert store.history(run, "check")[0].payload["misconception"] == "syntax-error"


def test_without_a_proven_sandbox_the_run_stops_and_says_why(tmp_path):
    store, run = program_run(tmp_path, RIGHT, ready=lambda: (False, "Docker is not installed."))
    [fail] = store.history(run, "failure")
    assert fail.payload["kind"] == "sandbox_unavailable" and "Docker is not installed" in fail.payload["detail"]
    assert not store.history(run, "check")


# ------------------------------------------------------------------ the API

def test_the_browser_gets_the_question_and_starter_but_never_the_tests(tmp_path, monkeypatch):
    stub = Stub({"teach": [code_lesson("A"), code_lesson("B")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    monkeypatch.setattr(tutor_api, "flow_factory",
                        lambda: build_flow(call=stub, find=find, run=local_run, ready=lambda: (True, "")))
    store = Store(Path(tutor_api.DB))
    run = session.start_session(store, "asha", ["mutable-defaults"])
    session.set_answer_mode(store, run, "code")
    store.close()
    tutor_api._kick(run)
    snap = settle(c, run)

    [msg] = snap["messages"]
    assert msg["quiz"] is None and msg["open"] is None
    assert msg["code_task"] == {"question": "Write total(prices) that returns the sum of the list.",
                                "starter": "def total(prices):\n    pass", "answered": None}
    sent = json.dumps(snap)
    for secret in ("forgets-to-accumulate", "total([1, 2, 3])", "sum(prices)", "model_solution", "expected"):
        assert secret not in sent

    r = c.post(f"/api/sessions/{run}/answer", json={"code": FORGETS, "confidence": "high"})
    assert r.status_code == 200
    after = settle(c, run)["messages"]
    fb = next(m for m in after if m["kind"] == "feedback")
    assert fb["via"] == "code" and fb["correct"] is False
    assert next(m for m in after if m["kind"] == "answer")["text"] == FORGETS
    assert "sum(prices)" not in json.dumps(after)


def test_the_mode_route_refuses_program_questions_without_a_sandbox(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [code_lesson("A")]})
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda: (False, "Docker is not installed."))
    run = start(c)
    settle(c, run)
    r = c.post(f"/api/sessions/{run}/mode", json={"mode": "code"})
    assert r.status_code == 422 and "Docker is not installed" in r.json()["detail"]


# --------------------------------------------------------------- assist

def known(now=None):
    return LearnerModel(student_id="asha", mastery={"mutable-defaults": 0.9},
                        last_seen={"mutable-defaults": now or time.time()})


def test_the_twin_helps_a_student_who_knows_the_topic_and_holds_back_otherwise():
    assert coach.help_level(known(), "mutable-defaults") == "assist"
    assert coach.help_level(LearnerModel(student_id="a", mastery={"mutable-defaults": 0.6}), "mutable-defaults") == "withhold"
    stale = known(time.time() - 60 * 86400)                  # 60 days ago: it has faded
    assert coach.help_level(stale, "mutable-defaults") == "withhold"


def test_chips_are_cleaned_before_they_are_shown():
    code = "def total(p):\n    return sum(p)"
    got = coach.clean(["", "  ", "x = 1", "x = 1", "return sum(p)", "a\nb\nc\nd\ne", "z" * 500, "q", "r"], code)
    assert got[0] == "x = 1" and "return sum(p)" not in got and len(got) == 3
    assert got[1] == "a\nb\nc" and len(got[2]) == 200


def test_a_weak_topic_gets_no_chips_and_no_model_call(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [code_lesson("A")]})
    sug = Stub({"suggest": []})
    monkeypatch.setattr(tutor_api, "suggest_call", sug)
    run = start(c)
    settle(c, run)
    r = c.post(f"/api/sessions/{run}/suggest", json={"code": "def total(p):"}).json()
    assert r["enabled"] is False and r["suggestions"] == [] and sug.calls == []


def test_a_known_topic_gets_chips_and_a_failure_gives_none(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [code_lesson("A")]})
    db = Path(tutor_api.DB)
    store = Store(db); learners.save(store, known()); store.close()
    sug = Stub({"suggest": [json.dumps({"suggestions": ["    return sum(p)", "    t = 0"]}), "not json at all"]})
    monkeypatch.setattr(tutor_api, "suggest_call", sug)
    run = start(c, student="asha")
    settle(c, run)
    r = c.post(f"/api/sessions/{run}/suggest", json={"code": "def total(p):"}).json()
    assert r["enabled"] is True and r["suggestions"] == ["    return sum(p)", "    t = 0"]
    assert sug.reasoning == [False]


import pytest  # noqa: E402


@pytest.mark.integration
def test_the_real_sandbox_grades_a_right_a_wrong_and_a_runaway_program():
    from demo.tutor import sandbox
    ok, why = sandbox.available(force=True)
    assert ok, why                                     # needs Docker running and the image pulled
    task = json.loads(code_lesson("x"))["code_task"]
    assert coach.grade_program(task, RIGHT, sandbox.run).correct is True
    assert coach.grade_program(task, FORGETS, sandbox.run).misconception == "forgets-to-accumulate"
    loop = "def total(p):\n    while True: pass"
    assert coach.grade_program(task, loop, lambda code: sandbox.run(code, timeout=4)).misconception == "runaway-loop"

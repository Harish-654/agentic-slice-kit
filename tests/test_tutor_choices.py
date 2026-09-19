"""Guided pacing, Phase B: an explanation no longer forces a quiz. The check is written with it
but held back, and the student chooses what happens next. Quick sessions are unchanged."""
import json
import time

from demo.tutor import learners, session, steps
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, lesson, plan
from slice.records import RunState
from slice.store import Store
from tests.test_tutor import RIGHT, WRONG
from tests.test_tutor_api import make, settle
from tests.test_tutor_guided import PRE, TARGET, answer, go, guided, quiz_me
from web import tutor_api

ALL = ["quiz", "example", "more_detail", "deeper", "skip", "stop"]


def trusted(store, student="s1"):
    """A student who already knows the prerequisite, so a guided run goes straight to teaching."""
    learners.save(store, LearnerModel(student_id=student, mastery={PRE: 0.92}, last_seen={PRE: time.time()}))


def started(tmp_path, teach=("T1", "T2", "T3")):
    store = Store(tmp_path / "r.db")
    trusted(store)
    run = guided(store)
    stub = Stub({"plan": [plan()], "teach": [lesson(t) for t in teach]})
    go(store, run, stub)
    return store, run, stub


def options(store, run):
    return session.open_choice(store, run).context["options"]


def test_the_menu_shrinks_after_two_explanations_in_a_row():
    assert steps.choices(0) == steps.choices(1) == ALL
    assert steps.choices(2) == steps.choices(5) == ["quiz", "skip", "stop"]


def test_an_explanation_is_held_with_its_check_and_the_student_is_given_a_choice(tmp_path):
    store, run, stub = started(tmp_path)
    [held] = store.history(run, "lesson")
    assert held.payload["held"] is True and held.payload["quiz"]           # written now, shown later
    assert session.open_quiz(store, run) is None                           # nothing to answer yet
    assert options(store, run) == ALL
    assert not store.history(run, "check")


def test_quiz_me_shows_the_held_check_with_no_model_call(tmp_path):
    store, run, stub = started(tmp_path)
    before = list(stub.calls)
    quiz_me(store, run, stub)
    assert stub.calls == before == ["plan", "teach"]                       # free
    assert [v.kind for v in store.replay(run) if v.kind == "reveal"] == ["reveal"]
    answer(store, run, RIGHT)
    go(store, run, stub)
    [check] = store.history(run, "check")
    assert check.payload["concept"] == TARGET and check.payload["correct"] is True


def test_asking_for_an_example_explains_again_and_the_second_explanation_narrows_the_menu(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "example")
    assert stub.calls == ["plan", "teach", "teach"]
    assert "THE STUDENT ASKED FOR: a NEW worked example" in stub.messages[2][1]["content"]
    first, second = store.history(run, "lesson")
    assert second.payload["style"] == "worked_example" and second.payload["held"]
    assert second.payload["concept"] == first.payload["concept"] == TARGET
    assert options(store, run) == ["quiz", "skip", "stop"]                 # two explanations: no more


def test_more_detail_steers_the_next_explanation(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "more_detail")
    assert "more detail, one step at a time" in stub.messages[2][1]["content"]


def test_going_deeper_steers_the_next_explanation(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "deeper")
    assert "a deeper look" in stub.messages[2][1]["content"]


def test_a_quiz_resets_the_count_so_the_menu_is_full_again(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "example")
    quiz_me(store, run, stub)                                              # reveal
    answer(store, run, WRONG); go(store, run, stub)                        # wrong: explain again, held
    assert options(store, run) == ALL


def test_skipping_the_topic_ends_the_session_as_skipped(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "skip")
    assert store.latest(run, "session_end")["reason"] == "skipped"
    assert store.get_state(run) is RunState.COMPLETE


def test_skipping_a_prerequisite_moves_on_to_the_topic(tmp_path):
    from demo.tutor.stub import probe
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe()], "teach": [lesson("PRE"), lesson("T1")]})
    go(store, run, stub)
    answer(store, run, WRONG); go(store, run, stub)                        # probe missed: teach PRE (held)
    quiz_me(store, run, stub, "skip")
    assert [v.payload["concept"] for v in store.history(run, "topic_skipped")] == [PRE]
    assert [v.payload["concept"] for v in store.history(run, "lesson")] == [PRE, PRE, TARGET]


def test_stop_ends_the_session_and_says_the_student_chose_to(tmp_path):
    store, run, stub = started(tmp_path)
    quiz_me(store, run, stub, "stop")
    assert store.latest(run, "session_end")["reason"] == "student_stopped"


def test_a_choice_nobody_answers_ends_the_session_as_the_student_leaving(tmp_path):
    store, run, stub = started(tmp_path)
    q = session.open_choice(store, run)
    store.answer(q.id, "")                                                 # what callback.sweep does on a timeout
    store.append(run, "expert_answer", {"question_id": q.id, "question": q.question, "answer": None,
                                        "who": None, "source": "unresolved_no_expert"}, "system")
    store.set_state(run, RunState.DRAFTING)
    go(store, run, stub)
    assert store.latest(run, "session_end")["reason"] == "student_left"


# ------------------------------------------------------------------ the API

def test_the_api_hides_the_held_check_until_quiz_me_and_never_shows_the_key(tmp_path, monkeypatch):
    stub = Stub({"plan": [plan()], "teach": [lesson("T1"), lesson("T2")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    store = Store(tmp_path / "api.db")
    trusted(store, "asha")
    store.close()
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET], "mode": "guided"}).json()["id"]
    snap = settle(c, run)

    assert snap["status"] == "waiting_choice"
    lesson_msg, menu = snap["messages"]
    assert lesson_msg["kind"] == "lesson" and lesson_msg["quiz"] is None and lesson_msg["open"] is None
    assert menu["kind"] == "choices" and menu["options"] == ALL and menu["chosen"] is None
    sent = json.dumps(snap)
    assert "default-is-copied" not in sent and "What does f() return" not in sent   # the check is not there yet

    assert c.post(f"/api/sessions/{run}/choice", json={"choice": "nonsense"}).status_code == 422
    snap = c.post(f"/api/sessions/{run}/choice", json={"choice": "quiz"}).json()
    snap = settle(c, run)
    assert snap["status"] == "waiting_student"
    kinds = [m["kind"] for m in snap["messages"]]
    assert kinds == ["lesson", "choices", "card"] and snap["messages"][1]["chosen"] == "quiz"
    card = snap["messages"][2]
    assert card["quiz"]["question"].startswith("What does f()") and card["quiz"]["answered"] is None
    assert '"correct"' not in json.dumps(snap) and "default-is-copied" not in json.dumps(snap)

    assert c.post(f"/api/sessions/{run}/choice", json={"choice": "quiz"}).status_code == 409   # nothing to choose now
    c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT, "confidence": "high"})
    snap = settle(c, run)
    assert [m["kind"] for m in snap["messages"]][:5] == ["lesson", "choices", "card", "answer", "feedback"]
    assert snap["messages"][2]["quiz"]["answered"]["correct"] is True


def test_the_api_refuses_a_menu_option_the_cap_has_withdrawn(tmp_path, monkeypatch):
    stub = Stub({"plan": [plan()], "teach": [lesson("T1"), lesson("T2")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    store = Store(tmp_path / "api.db")
    trusted(store, "asha")
    store.close()
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET], "mode": "guided"}).json()["id"]
    settle(c, run)
    c.post(f"/api/sessions/{run}/choice", json={"choice": "example"})
    snap = settle(c, run)
    assert snap["messages"][-1]["options"] == ["quiz", "skip", "stop"]
    assert c.post(f"/api/sessions/{run}/choice", json={"choice": "example"}).status_code == 422


def test_quick_sessions_are_not_held(tmp_path, monkeypatch):
    stub = Stub({"teach": [lesson("T1")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET]}).json()["id"]
    snap = settle(c, run)
    assert snap["status"] == "waiting_student" and [m["kind"] for m in snap["messages"]] == ["lesson"]
    assert snap["messages"][0]["quiz"] is not None

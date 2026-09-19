"""Guided depth, Phase C: every part of the topic is covered, then a written final that has to be
passed. A failed final re-teaches the weakest part, twice at most. Quick sessions are unchanged."""
import json
import time

from demo.tutor import learners, session, steps
from demo.tutor.flow import build_final_messages
from demo.tutor.schema import LearnerModel, OpenQuestion
from demo.tutor.stub import Stub, final, grade, lesson, plan
from slice.store import Store
from tests.test_tutor import RIGHT, WRONG
from tests.test_tutor_api import make, settle
from tests.test_tutor_guided import PRE, TARGET, answer, go, guided, quiz_me, seq, write
from web import tutor_api

S1, S2 = "parent-and-child", "overriding"
ORDER = [PRE, S1, S2, TARGET]


def ok(concept, n=2, mastery=0.83):
    """`n` right answers on a part, and the mastery those earn."""
    return [{"concept": concept, "correct": True} for _ in range(n)], {concept: mastery}


def model(mastery=None, seen=True):
    now = time.time()
    return LearnerModel(student_id="s", mastery=mastery or {}, last_seen={c: now for c in (mastery or {})} if seen else {})


def decide(checks, m=None, **kw):
    return steps.decide(ORDER, m or model({PRE: 0.92}), checks, subtopics=[S1, S2], **kw)


# ------------------------------------------------------------------ the policy

def test_every_part_must_be_covered_before_the_final():
    a, ma = ok(S1)
    b, mb = ok(S2)
    assert decide([]) == ("teach", S1)
    assert decide(a, model({PRE: 0.92, **ma})) == ("teach", S2)                    # first part done, second not
    assert decide(a + b, model({PRE: 0.92, **ma, **mb})) == ("final", TARGET)


def test_a_part_needs_two_right_answers_and_the_mastery_bar_not_just_one_of_them():
    assert decide([{"concept": S1, "correct": True}], model({PRE: 0.92, S1: 0.65})) == ("teach", S1)
    two = ok(S1)[0]
    assert decide(two, model({PRE: 0.92, S1: 0.6})) == ("teach", S1)               # right twice but still under the bar


def test_a_part_known_well_and_recently_is_not_taught_again():
    m = model({PRE: 0.92, S1: 0.95, S2: 0.95})
    assert decide([], m) == ("final", TARGET)


def test_a_skipped_part_counts_as_done_and_skipping_every_part_ends_the_session():
    b, mb = ok(S2)
    assert decide(b, model({PRE: 0.92, **mb}), skipped={S1}) == ("final", TARGET)
    assert decide([], skipped={S1, S2}) == ("done", "skipped")


def test_passing_the_final_ends_the_session_as_mastery():
    assert decide([{"concept": TARGET, "correct": True, "final": True}]) == ("done", "mastery")


def test_a_failed_final_re_teaches_the_weakest_part_then_tries_again():
    a, ma = ok(S1)
    b, mb = ok(S2)
    m = model({PRE: 0.92, **ma, **mb})
    failed = {"concept": TARGET, "correct": False, "final": True, "revisit": S2}
    assert decide(a + b + [failed], m) == ("teach", S2)                            # the part the failed check named
    fixed = {"concept": S2, "correct": True}
    assert decide(a + b + [failed, fixed], m) == ("final", TARGET)


def test_the_final_can_be_retried_twice_then_the_session_ends():
    a, ma = ok(S1)
    b, mb = ok(S2)
    m = model({PRE: 0.92, **ma, **mb})
    fail = lambda: {"concept": TARGET, "correct": False, "final": True, "revisit": S1}    # noqa: E731
    fix = {"concept": S1, "correct": True}
    two = a + b + [fail(), fix, fail(), fix]
    assert decide(two, m) == ("final", TARGET)                                     # third and last attempt
    assert decide(two + [fail()], m) == ("done", "revision_limit")


def test_a_topic_with_no_parts_is_taught_as_one_then_finalled():
    m = model({PRE: 0.92})
    assert steps.decide([PRE, TARGET], m, []) == ("teach", TARGET)
    two = ok(TARGET)[0]
    assert steps.decide([PRE, TARGET], model({PRE: 0.92, TARGET: 0.83}), two) == ("final", TARGET)


# ------------------------------------------------------------------ the loop

def trusted(store, student="s1"):
    learners.save(store, LearnerModel(student_id=student, mastery={PRE: 0.92}, last_seen={PRE: time.time()}))


def cover(store, run, stub, parts=2):
    """Explain, "quiz me", answer right, twice for each part."""
    for _ in range(parts * 2):
        quiz_me(store, run, stub)
        answer(store, run, RIGHT); go(store, run, stub)


def two_part_run(tmp_path, grades=(True,), exam=None, extra=()):
    store = Store(tmp_path / "r.db")
    trusted(store)
    run = guided(store, exam=exam) if exam is None else guided(store, exam=exam, topic=None)
    stub = Stub({"plan": [plan(subtopics=(S1, S2), target="Inheritance" if exam else "")],
                 "teach": [lesson(f"T{i}") for i in range(12)],
                 "final": [final() for _ in grades],
                 "grade": [grade(g, None if g else "override-deletes-parent", "fb") for g in grades]})
    go(store, run, stub)
    return store, run, stub


def test_the_topic_is_taught_part_by_part_and_ends_on_a_passed_final(tmp_path):
    store, run, stub = two_part_run(tmp_path)
    cover(store, run, stub)
    assert [c for c, _ in seq(store, run)] == [S1, S1, S2, S2, TARGET]              # each part twice, then the final
    assert seq(store, run)[-1][1] == "final"
    [q] = [v for v in store.history(run, "lesson") if v.payload.get("final")]
    assert q.payload["open"] and q.payload["quiz"] is None and not q.payload.get("held")

    write(store, run, "A child inherits its parent's methods and may override one.", stub)
    assert stub.calls.count("final") == 1 and stub.calls[-1] == "grade"
    assert store.latest(run, "session_end")["reason"] == "mastery"
    assert store.latest(run, "input")["concepts"] == [PRE, S1, S2, TARGET]


def test_a_failed_final_teaches_the_weakest_part_again_and_a_second_final_can_pass(tmp_path):
    store, run, stub = two_part_run(tmp_path, grades=(False, True))
    cover(store, run, stub)
    write(store, run, "Overriding deletes the parent's method.", stub)              # fails the final
    failed = [c.payload for c in store.history(run, "check") if c.payload.get("final")][0]
    assert failed["correct"] is False and failed["misconception"] == "override-deletes-parent"
    assert failed["revisit"] in (S1, S2)

    assert session.open_choice(store, run)                                           # the weak part is explained again, held
    assert store.history(run, "lesson")[-1].payload["concept"] == failed["revisit"]
    quiz_me(store, run, stub)
    answer(store, run, RIGHT); go(store, run, stub)                                  # ... and checked
    write(store, run, "A child inherits and may override one.", stub)                # second final passes
    assert stub.calls.count("final") == 2
    assert store.latest(run, "session_end")["reason"] == "mastery"


def test_three_failed_finals_end_the_session_as_the_revision_limit(tmp_path):
    store, run, stub = two_part_run(tmp_path, grades=(False, False, False))
    cover(store, run, stub)
    for _ in range(2):
        write(store, run, "No.", stub)                                               # fail, re-teach the weak part
        quiz_me(store, run, stub)
        answer(store, run, RIGHT); go(store, run, stub)
    write(store, run, "Still no.", stub)                                             # third failure
    assert stub.calls.count("final") == 3
    assert store.latest(run, "session_end")["reason"] == "revision_limit"


def test_a_pasted_exam_question_is_the_final_word_for_word(tmp_path):
    exam = "Why can a child class call a method that is only defined in its parent?"
    store, run, stub = two_part_run(tmp_path, exam=exam)
    cover(store, run, stub)
    [q] = [v for v in store.history(run, "lesson") if v.payload.get("final")]
    assert q.payload["open"]["question"] == exam                                    # not the model's wording
    assert q.payload["open"]["rubric"]                                              # but the model's rubric
    asked = stub.messages[stub.calls.index("final")][1]["content"]
    assert "EXAM QUESTION" in asked and exam in asked


def test_the_step_cap_stops_a_topic_that_never_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "MAX_STEPS", 3)
    store, run, stub = two_part_run(tmp_path)
    quiz_me(store, run, stub); answer(store, run, WRONG); go(store, run, stub)
    quiz_me(store, run, stub); answer(store, run, WRONG); go(store, run, stub)
    quiz_me(store, run, stub); answer(store, run, WRONG); go(store, run, stub)
    assert store.latest(run, "session_end")["reason"] == "session_limit"


def test_quick_sessions_have_no_final(tmp_path, monkeypatch):
    stub = Stub({"teach": [lesson("T1")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET]}).json()["id"]
    settle(c, run)
    assert "final" not in stub.calls and c.get(f"/api/sessions/{run}").json()["progress"]["plan"] is None


# ------------------------------------------------------------------ the prompt and the API

def test_the_final_prompt_spells_out_every_key_it_wants_back():
    from demo.tutor.flow import _prompt
    for key in OpenQuestion.model_fields:
        assert f'"{key}"' in _prompt("final"), key
    for key in ("belief", "sign"):
        assert f'"{key}"' in _prompt("final"), key


def test_the_final_messages_carry_the_parts_and_the_exam_question():
    msgs = build_final_messages("inheritance", [S1, S2], "Why?", "LEVEL: beginner")
    user = msgs[1]["content"]
    assert f"PARTS OF THE TOPIC: {S1}, {S2}" in user and "EXAM QUESTION" in user and "LEVEL: beginner" in user
    assert "EXAM QUESTION" not in build_final_messages("inheritance", [], None, "p")[1]["content"]


def test_the_api_shows_the_parts_and_serves_the_final_without_its_rubric(tmp_path, monkeypatch):
    stub = Stub({"plan": [plan(subtopics=(S1, S2))], "teach": [lesson(f"T{i}") for i in range(6)],
                 "final": [final()]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    store = Store(tmp_path / "api.db")
    trusted(store, "asha")
    store.close()
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET], "mode": "guided"}).json()["id"]
    snap = settle(c, run)
    assert snap["progress"]["plan"] == {"target": TARGET, "prereqs": [PRE], "subtopics": [S1, S2]}
    assert [r["concept"] for r in snap["progress"]["concepts"]] == [PRE, S1, S2, TARGET]

    for _ in range(4):                                                               # cover both parts through the API
        c.post(f"/api/sessions/{run}/choice", json={"choice": "quiz"}); settle(c, run)
        c.post(f"/api/sessions/{run}/answer", json={"choice": RIGHT, "confidence": "high"}); snap = settle(c, run)
    msg = snap["messages"][-1]
    assert msg["kind"] == "lesson" and msg["style"] == "final" and msg["open"]["question"].startswith("Explain how")
    sent = json.dumps(snap)
    for secret in ("the child inherits the parent", "model_answer", "override-deletes-parent", "rubric"):
        assert secret not in sent
    assert snap["status"] == "waiting_student"

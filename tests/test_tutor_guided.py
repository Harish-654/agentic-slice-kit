"""Guided sessions, Phase A: plan the topic, probe what it builds on BEFORE explaining, teach
only what the student does not know, then the topic. The model is scripted throughout."""
import json
import time

from demo.tutor import curriculum, learners, session, steps
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel, PlanDraft
from demo.tutor.stub import Stub, lesson, plan, probe
from slice import runner
from slice.llm import SchemaFailure
from slice.store import Store
from tests.test_tutor import S, WRONG, RIGHT, find
from tests.test_tutor_api import make, settle

PRE, TARGET = "classes-and-objects", "inheritance"


def go(store, run, stub, call=None):
    runner.advance(store, run, build_flow(call=call or stub, find=find), S)


def answer(store, run, choice):
    session.submit_mcq(store, session.open_quiz(store, run).id, choice)


def guided(store, exam=None, topic=TARGET, student="s1"):
    return session.start_session(store, student, [topic] if topic else ["exam-question"],
                                 mode="guided", exam_question=exam)


def seq(store, run):
    return [(v.payload["concept"], v.payload["style"]) for v in store.history(run, "lesson")]


# ------------------------------------------------------------------ pure rules

def test_key_and_resolve_make_one_id_out_of_many_spellings():
    assert curriculum.key("Classes and objects") == curriculum.key("object-classes")
    assert curriculum.resolve("classes & objects", ["classes-and-objects"]) == "classes-and-objects"
    assert curriculum.resolve("Class objects", ["classes-and-objects"]) == "classes-and-objects"   # close enough
    assert curriculum.resolve("Recursion", ["classes-and-objects"]) == "recursion"                # not close
    assert curriculum.resolve("!!!", []) is None


def test_a_plan_is_cleaned_capped_and_never_lists_the_topic_as_its_own_prerequisite():
    draft = PlanDraft(prereqs=["Inheritance", "classes-and-objects", "Classes and Objects", "loops", "lists", "tuples", "sets"],
                      subtopics=["overriding", "overriding", "super-calls"])
    got = curriculum.clean_plan(draft, "inheritance", ["classes-and-objects"])
    assert got["prereqs"] == ["classes-and-objects", "loops", "lists"]    # topic and repeat dropped, capped at 3
    assert got["subtopics"] == ["overriding", "super-calls"]


def known(mastery, days_ago=0.0):
    return LearnerModel(student_id="s", mastery={PRE: mastery}, last_seen={PRE: time.time() - days_ago * 86400})


def test_decide_probes_a_prerequisite_once_then_teaches_only_when_it_was_missed():
    order = [PRE, TARGET]
    m = LearnerModel(student_id="s")
    assert steps.decide(order, m, []) == ("probe", PRE)
    assert steps.decide(order, m, [{"concept": PRE, "correct": True, "probe": True}]) == ("teach", TARGET)
    missed = {"concept": PRE, "correct": False, "probe": True}
    assert steps.decide(order, m, [missed]) == ("teach", PRE)
    taught_wrong = {"concept": PRE, "correct": False}
    assert steps.decide(order, m, [missed, taught_wrong]) == ("teach", PRE)               # one more try
    assert steps.decide(order, m, [missed, taught_wrong, taught_wrong]) == ("teach", TARGET)   # then move on
    assert steps.decide(order, m, [missed, {"concept": PRE, "correct": True}]) == ("teach", TARGET)


def test_a_prerequisite_known_well_and_recently_is_trusted_but_not_when_it_has_faded():
    order = [PRE, TARGET]
    assert steps.decide(order, known(0.9), []) == ("teach", TARGET)
    assert steps.decide(order, known(0.9, days_ago=10), []) == ("probe", PRE)             # older than 3 days
    assert steps.decide(order, known(0.7), []) == ("probe", PRE)                          # not well enough


def test_with_documents_as_the_source_a_prerequisite_is_taught_not_probed():
    m = LearnerModel(student_id="s")
    assert steps.decide([PRE, TARGET], m, [], probing=False) == ("teach", PRE)


def test_the_run_ends_when_the_topic_is_already_mastered_or_skipped():
    m = LearnerModel(student_id="s", mastery={TARGET: 0.9}, last_seen={TARGET: time.time()})
    assert steps.decide([PRE, TARGET], m, []) == ("done", "mastery")
    assert steps.decide([PRE, TARGET], LearnerModel(student_id="s"), [], skipped={TARGET}) == ("done", "skipped")


# ------------------------------------------------------------------ the loop

def test_a_missed_prerequisite_is_probed_then_taught_then_the_topic(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe()],
                 "teach": [lesson("PRE"), lesson("T1"), lesson("T2")]})
    go(store, run, stub)                                     # plan, then the probe question
    [first] = store.history(run, "lesson")
    assert first.payload["style"] == "probe" and first.payload["concept"] == PRE
    assert first.payload["explanation"].startswith("First, a quick check")

    answer(store, run, WRONG); go(store, run, stub)          # missed: teach the prerequisite
    answer(store, run, RIGHT); go(store, run, stub)          # now the topic itself
    answer(store, run, RIGHT); go(store, run, stub)
    answer(store, run, RIGHT); go(store, run, stub)

    assert [c for c, _ in seq(store, run)] == [PRE, PRE, TARGET, TARGET]
    assert stub.calls == ["plan", "probe", "teach", "teach", "teach"]
    checks = store.history(run, "check")
    assert [bool(c.payload.get("probe")) for c in checks] == [True, False, False, False]
    assert store.latest(run, "session_end")["reason"] == "mastery"
    assert store.latest(run, "input")["concepts"] == [PRE, TARGET]


def test_a_known_prerequisite_is_not_explained(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe()], "teach": [lesson("T1"), lesson("T2")]})
    go(store, run, stub)
    answer(store, run, RIGHT); go(store, run, stub)          # probe right: straight to the topic
    answer(store, run, RIGHT); go(store, run, stub)
    answer(store, run, RIGHT); go(store, run, stub)
    assert stub.calls == ["plan", "probe", "teach", "teach"]
    assert [c for c, _ in seq(store, run)] == [PRE, TARGET, TARGET]


def test_a_trusted_prerequisite_costs_no_probe_at_all(tmp_path):
    store = Store(tmp_path / "r.db")
    learners.save(store, LearnerModel(student_id="s1", mastery={PRE: 0.92}, last_seen={PRE: time.time()}))
    run = guided(store)
    stub = Stub({"plan": [plan()], "teach": [lesson("T1")]})
    go(store, run, stub)
    assert stub.calls == ["plan", "teach"] and seq(store, run) == [(TARGET, "plain")]


def test_a_plan_the_model_cannot_write_degrades_to_no_prerequisites_not_a_crash(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"teach": [lesson("T1")]})

    def flaky(**kw):
        if kw["step"] == "plan":
            raise SchemaFailure("garbled")
        return stub(**kw)

    go(store, run, stub, call=flaky)
    assert store.latest(run, "input")["plan"]["degraded"] is True
    assert seq(store, run) == [(TARGET, "plain")]
    assert TARGET not in store.latest(run, "learner_model")["plans"]           # a failure is not cached


def test_a_topics_plan_is_remembered_so_the_next_session_does_not_pay_for_it_again(tmp_path):
    store = Store(tmp_path / "r.db")
    stub = Stub({"plan": [plan()], "probe": [probe(), probe()]})
    go(store, guided(store), stub)
    go(store, guided(store), stub)
    assert stub.calls == ["plan", "probe", "probe"]
    assert LearnerModel.model_validate(store.latest(guided(store), "learner_model")).plans


def test_a_pasted_exam_question_seeds_the_plan_and_names_the_topic(tmp_path):
    store = Store(tmp_path / "r.db")
    q = "Explain why a child class can call a method defined in its parent."
    run = guided(store, exam=q, topic=None)
    stub = Stub({"plan": [plan(target="Inheritance")], "probe": [probe()]})
    go(store, run, stub)
    assert "EXAM QUESTION: " + q in stub.messages[0][1]["content"]
    inp = store.latest(run, "input")
    assert inp["concepts"] == [PRE, "inheritance"] and inp["plan"]["target"] == "inheritance"
    assert inp["exam_question"] == q


# ------------------------------------------------------------------ the API

def test_the_api_shows_the_plan_and_hides_the_probe_answer_key(tmp_path, monkeypatch):
    stub = Stub({"plan": [plan()], "probe": [probe()]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    r = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET], "mode": "guided"})
    assert r.status_code == 200
    snap = settle(c, r.json()["id"])

    assert snap["status"] == "waiting_student"
    assert snap["progress"]["mode"] == "guided"
    assert snap["progress"]["plan"] == {"target": TARGET, "prereqs": [PRE]}
    assert [row["concept"] for row in snap["progress"]["concepts"]] == [PRE, TARGET]
    [msg] = snap["messages"]
    assert msg["style"] == "probe" and msg["quiz"]["answered"] is None
    sent = json.dumps(snap)
    assert "class-is-an-instance" not in sent and '"correct"' not in sent


def test_the_api_rules_for_guided_starts(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": []})
    post = lambda **kw: c.post("/api/sessions", json={"student": "a", **kw}).status_code   # noqa: E731
    assert post(concepts=[TARGET], exam_question="Why?") == 422          # exam questions need guided mode
    assert post(concepts=["a", "b"], mode="guided") == 422               # one topic at a time
    assert post(mode="guided") == 422                                    # nothing to learn
    assert post(concepts=[]) == 422


def test_the_plan_and_probe_prompts_spell_out_every_key_they_want_back():
    """Measured earlier: a prompt that does not show the shape makes the small model invent
    its own keys and every call costs a repair."""
    from demo.tutor.flow import _prompt
    from demo.tutor.schema import Quiz
    for key in PlanDraft.model_fields:
        assert f'"{key}"' in _prompt("plan"), key
    for key in ["quiz", *Quiz.model_fields, "misconception", "text"]:
        assert f'"{key}"' in _prompt("probe"), key

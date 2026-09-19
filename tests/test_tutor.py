"""The teach -> check -> adapt loop, with no key, no network and no embeddings."""
import json

import pytest

from demo.tutor import learner, session
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import CITE, Stub, grade, lesson
from slice import callback, runner
from slice.config import Settings
from slice.records import RunState
from slice.retrieve import Chunk
from slice.store import Store

S = Settings(api_key="x", model="m", fallback_model="f", escalation_model="e",
             max_tokens=100, max_tokens_per_run=100000, max_attempts_per_step=2,
             expert_timeout_minutes=45, langfuse_public="", langfuse_secret="",
             langfuse_host="")

NOTES = [Chunk("c1", "python-notes.md", 0, "Defaults are evaluated once.", 0.1)]
WRONG, RIGHT = 0, 1                     # option indexes in the stub's quiz


def find(store, query, k=4):
    return NOTES


def drive(store, run, stub, find=find):
    return runner.advance(store, run, build_flow(call=stub, find=find), S)


def answer(store, run, choice):
    q = session.open_quiz(store, run)
    assert q is not None, "the run should be waiting on the student"
    session.submit_mcq(store, q.id, choice)


def kinds(store, run):
    return [v.kind for v in store.replay(run)]


def test_wrong_option_names_the_misconception_and_the_reteach_differs(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("PLAIN"), lesson("ANALOGY"), lesson("WORKED")]})

    assert drive(store, run, stub) is RunState.AWAITING_EXPERT
    answer(store, run, WRONG)
    drive(store, run, stub)

    check = store.history(run, "check")[0].payload
    assert (check["correct"], check["misconception"]) == (False, "default-is-copied")
    model = LearnerModel.model_validate(store.latest(run, "learner_model"))
    assert model.misconceptions == {"default-is-copied": 1}
    assert model.mastery["mutable-defaults"] < learner.START

    first, second = (v.payload for v in store.history(run, "lesson"))
    assert (first["style"], second["style"]) == ("plain", "analogy")
    assert "default-is-copied" in stub.messages[1][1]["content"]   # aimed at the belief


def test_the_run_ends_on_mastery_and_says_why(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a"), lesson("b"), lesson("c")]})

    drive(store, run, stub)
    for choice in (WRONG, RIGHT, RIGHT):
        answer(store, run, choice)
        state = drive(store, run, stub)

    assert state is RunState.COMPLETE
    assert store.latest(run, "session_end") == {"reason": "mastery"}


def test_the_session_limit_also_records_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(learner, "MAX_CHECKS", 1)
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a")]})
    drive(store, run, stub)
    answer(store, run, WRONG)
    assert drive(store, run, stub) is RunState.COMPLETE
    assert store.latest(run, "session_end") == {"reason": "session_limit"}


def test_multiple_choice_is_the_default_and_the_toggle_persists(tmp_path):
    store = Store(tmp_path / "r.db")
    first = session.start_session(store, "s1", ["x"])
    assert LearnerModel.model_validate(store.latest(first, "learner_model")).answer_mode == "mcq"

    session.set_answer_mode(store, first, "text")
    second = session.start_session(store, "s1", ["x"])
    assert LearnerModel.model_validate(store.latest(second, "learner_model")).answer_mode == "text"


def test_the_learner_model_carries_into_the_next_session(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"], interests=["football"])
    stub = Stub({"teach": [lesson("a"), lesson("b")]})
    drive(store, run, stub)
    answer(store, run, WRONG)
    drive(store, run, stub)

    later = session.start_session(store, "s1", ["mutable-defaults"])
    carried = LearnerModel.model_validate(store.latest(later, "learner_model"))
    assert carried.misconceptions == {"default-is-copied": 1}
    assert carried.interests == ["football"]
    assert session.previous_model(store, "someone-else") is None


def test_free_text_is_graded_by_the_model_and_tagged(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a"), lesson("b")],
                 "grade": [grade(False, "Default Is Copied", "Not quite.")]})
    drive(store, run, stub)
    q = session.open_quiz(store, run)
    session.submit_text(store, q.id, "it returns [1] because each call gets a fresh list")
    drive(store, run, stub)

    check = store.history(run, "check")[0].payload
    assert check["mode"] == "text" and check["misconception"] == "default-is-copied"
    assert "Defaults are evaluated once." in stub.messages[1][1]["content"]   # graded on the notes


def test_no_course_notes_means_ask_the_teacher_not_the_internet(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["decorators"])
    stub = Stub({"teach": [lesson("from teacher", cites=())]})
    nothing = lambda *a, **k: []

    assert drive(store, run, stub, find=nothing) is RunState.AWAITING_EXPERT
    assert stub.calls == []                              # nothing invented
    [q] = callback.pending(store)
    assert q.context["kind"] == "teacher_gap"

    callback.answer(store, q.id, "A decorator wraps a function.", who="teacher")
    assert drive(store, run, stub, find=nothing) is RunState.AWAITING_EXPERT
    assert session.open_quiz(store, run) is not None     # now teaching, from the teacher's words


def test_an_unanswered_teacher_gap_fails_with_a_reason(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["decorators"])
    nothing = lambda *a, **k: []
    drive(store, run, Stub({}), find=nothing)
    [q] = callback.pending(store)
    store.answer(q.id, "")
    store.append(run, "expert_answer", {"answer": None, "source": "unresolved_no_expert"}, "system")
    store.set_state(run, RunState.DRAFTING)

    assert drive(store, run, Stub({}), find=nothing) is RunState.FAILED
    assert store.latest(run, "failure")["kind"] == "no_source_material"


def test_a_lesson_that_cites_nothing_it_was_given_is_refused(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("from the internet", cites=("wikipedia.org#0",))]})
    assert drive(store, run, stub) is RunState.FAILED
    assert store.latest(run, "failure")["kind"] == "ungrounded_lesson"


def test_a_quiz_must_tag_every_distractor():
    bad = json.loads(lesson("x"))
    bad["quiz"]["options"][0]["misconception"] = None
    with pytest.raises(Exception):
        from demo.tutor.schema import Lesson
        Lesson.model_validate(bad)


def test_learner_rules():
    m = LearnerModel(student_id="s")
    assert learner.pick_concept(m, ["a", "b"]) == "a"
    m = learner.apply_check(m, "a", correct=False, misconception="Off By One")
    assert m.misconceptions == {"off-by-one": 1}
    assert learner.pick_concept(m, ["a", "b"]) == "a"     # a is now the weaker
    for _ in range(3):
        m = learner.apply_check(m, "a", True, None)
        m = learner.apply_check(m, "b", True, None)
    assert learner.pick_concept(m, ["a", "b"]) is None
    assert learner.style_for(0) == "plain" and learner.style_for(99) == "diagram"


def test_a_question_that_points_at_code_must_include_it():
    from demo.tutor.schema import Lesson
    bad = json.loads(lesson("x"))
    bad["quiz"]["question"] = "What is the output of the following code?"
    with pytest.raises(Exception, match="refers to code"):
        Lesson.model_validate(bad)
    bad["quiz"]["code"] = "print(1 == 1)"
    assert Lesson.model_validate(bad).quiz.code == "print(1 == 1)"

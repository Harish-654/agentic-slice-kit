"""How sure the student is, and "I don't know", change how an answer is scored."""
from demo.tutor import learner, session
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, grade, lesson, open_lesson
from slice import runner
from slice.store import Store
from tests.test_tutor import NOTES, S, answer

WRONG, RIGHT = 0, 1


def drive(store, run, stub):
    return runner.advance(store, run, build_flow(call=stub, find=lambda *a: NOTES), S)


def mastery(m):
    return m.mastery["a"]


# ------------------------------------------------------------------ the rule

def test_a_right_answer_counts_for_more_the_surer_the_student_was():
    m = LearnerModel(student_id="s")
    low, mid, high = (mastery(learner.apply_check(m, "a", True, None, confidence=c))
                      for c in ("low", "medium", "high"))
    assert low < mid < high
    assert mid == mastery(learner.apply_check(m, "a", True, None))        # no stated confidence = "fairly sure"


def test_one_confident_right_answer_is_not_enough_to_call_a_topic_mastered():
    """A multiple-choice question can be guessed; certainty is a claim, not proof."""
    m = learner.apply_check(LearnerModel(student_id="s"), "a", True, None, confidence="high")
    assert mastery(m) < learner.MASTERY


def test_a_wrong_answer_costs_more_the_surer_the_student_was():
    m = LearnerModel(student_id="s", mastery={"a": 0.6})
    low, mid, high = (mastery(learner.apply_check(m, "a", False, "x", confidence=c))
                      for c in ("low", "medium", "high"))
    assert high < mid < low
    assert mid == mastery(learner.apply_check(m, "a", False, "x"))


def test_a_belief_held_with_certainty_counts_double():
    m = LearnerModel(student_id="s")
    for c, n in (("low", 1), ("medium", 1), ("high", 2), (None, 1)):
        got = learner.apply_check(m, "a", False, "default-is-copied", confidence=c)
        assert got.concept_misconceptions["a"]["default-is-copied"] == n, c
        assert got.wrong_answers["a"] == 1                                # the style ladder still moves one step


def test_i_dont_know_costs_a_little_and_names_no_belief():
    m = LearnerModel(student_id="s", mastery={"a": 0.6})
    got = learner.apply_check(m, "a", False, None, question="What is x?", dont_know=True)
    assert mastery(got) == round(0.6 * learner.UNKNOWN_LOSS, 4)
    assert mastery(got) > mastery(learner.apply_check(m, "a", False, "x", confidence="low"))   # gentler than any wrong answer
    assert got.misconceptions == {} and got.concept_misconceptions == {}
    assert got.wrong_answers["a"] == 1                                    # but the lesson did not land: teach it differently
    assert got.recent_questions["a"] == ["What is x?"]


# ------------------------------------------------------------------ the flow

def test_dont_know_on_a_choice_question_teaches_the_answer_and_never_calls_the_grader(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a", cites=()), lesson("b", cites=())]})
    drive(store, run, stub)
    session.submit_unknown(store, session.open_quiz(store, run).id)
    drive(store, run, stub)

    check = store.history(run, "check")[0].payload
    assert check["dont_know"] is True and check["correct"] is False and check["misconception"] is None
    assert "shared" in check["feedback"]                                   # the quiz's own explanation
    assert stub.calls == ["teach", "teach"]                                # no grade call: nothing to grade
    assert store.history(run, "lesson")[1].payload["style"] == "analogy"   # and it is explained a new way


def test_dont_know_on_a_written_question_shows_the_model_answer_without_grading(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    session.set_answer_mode(store, run, "text")
    stub = Stub({"teach": [open_lesson("a", cites=()), open_lesson("b", cites=())], "grade": []})
    drive(store, run, stub)
    session.submit_unknown(store, session.open_quiz(store, run).id)
    drive(store, run, stub)
    fb = store.history(run, "check")[0].payload["feedback"]
    assert "A good answer:" in fb and "built when def runs" in fb
    assert "grade" not in stub.calls


def test_the_stated_confidence_is_recorded_and_moves_mastery_accordingly(tmp_path):
    def after(confidence):
        store = Store(tmp_path / f"{confidence}.db")
        run = session.start_session(store, "s1", ["mutable-defaults"])
        stub = Stub({"teach": [lesson("a", cites=()), lesson("b", cites=())]})
        drive(store, run, stub)
        session.submit_mcq(store, session.open_quiz(store, run).id, WRONG, confidence)
        drive(store, run, stub)
        m = LearnerModel.model_validate(store.latest(run, "learner_model"))
        return store.history(run, "check")[0].payload["confidence"], m

    (c_low, m_low), (c_high, m_high) = after("low"), after("high")
    assert (c_low, c_high) == ("low", "high")
    assert m_high.mastery["mutable-defaults"] < m_low.mastery["mutable-defaults"]
    assert m_high.concept_misconceptions["mutable-defaults"]["default-is-copied"] == 2

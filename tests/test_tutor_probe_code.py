"""Code the model writes for a probe is run in the sandbox before a student sees it. A small
model once wrote a `bark` method outside its class and then called it, so the question asked about
something that could not happen. The sandbox here is a local Python (trusted test code only)."""
from demo.tutor import coach, session
from demo.tutor.flow import build_flow
from demo.tutor.sandbox import Result
from demo.tutor.stub import Stub, lesson, plan, probe
from slice import runner
from slice.store import Store
from tests.test_tutor import S, RIGHT, WRONG, find
from tests.test_tutor_guided import PRE, TARGET, answer, guided, quiz_me
from tests.test_tutor_program import local_run

# What the model actually wrote: `bark` is not indented inside the class, then it is called on an instance.
BROKEN = """class Dog:
    def __init__(self, name):
        self.name = name

def bark(self):
    print(f'{self.name} says woof')

my_dog = Dog('Buster')
my_dog.bark()
"""
CLEAN = """class Dog:
    def __init__(self, name):
        self.name = name

    def bark(self):
        print(f'{self.name} says woof')

Dog('Buster').bark()
"""
ON = lambda: (True, "")          # noqa: E731
OFF = lambda: (False, "Docker is not installed.")   # noqa: E731


def go(store, run, stub, ready=ON, run_code=local_run):
    runner.advance(store, run, build_flow(call=stub, find=find, run=run_code, ready=ready), S)


def quiz(code, *opts):
    return {"code": code, "options": [{"text": o} for o in (opts or ("a", "b", "c"))]}


# ------------------------------------------------------------------ the check

def test_the_broken_code_the_model_really_wrote_is_caught_and_named():
    problem = coach.question_code_problem(quiz(BROKEN), local_run)
    assert problem and "AttributeError" in problem and "bark" in problem
    assert coach.question_code_problem(quiz(CLEAN), local_run) is None


def test_code_that_does_not_compile_is_rejected_without_running_it():
    ran = []
    problem = coach.question_code_problem(quiz("def f(:\n    pass"), lambda c: ran.append(c))
    assert problem.startswith("SyntaxError") and ran == []


def test_no_code_means_nothing_to_check():
    assert coach.question_code_problem(quiz(None), lambda c: 1 / 0) is None
    assert coach.question_code_problem(quiz("   "), lambda c: 1 / 0) is None


def test_code_that_is_meant_to_fail_is_allowed_when_an_option_is_about_the_error():
    boom = "print(undefined_name)"
    assert coach.question_code_problem(quiz(boom, "prints None", "raises a NameError"), local_run) is None
    assert coach.question_code_problem(quiz(boom, "prints None", "prints 0"), local_run)


def test_a_hang_is_rejected_but_a_docker_failure_is_not_blamed_on_the_question():
    assert "too long" in coach.question_code_problem(
        quiz("while True: pass"), lambda c: Result("", "", None, timed_out=True))
    assert coach.question_code_problem(quiz("x = 1"), lambda c: Result("", "docker: error", 125)) is None


# ------------------------------------------------------------------ in the loop

def test_a_probe_with_broken_code_is_rewritten_once_and_the_student_sees_the_good_one(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe(BROKEN), probe(CLEAN)]})
    go(store, run, stub)

    assert stub.calls == ["plan", "probe", "probe"]
    [shown] = store.history(run, "lesson")
    assert shown.payload["quiz"]["code"] == CLEAN
    [rejected] = store.history(run, "probe_rejected")
    assert rejected.payload["concept"] == PRE and "AttributeError" in rejected.payload["problem"]
    retry = stub.messages[2][1]["content"]                       # the model is told what went wrong
    assert "REJECTED" in retry and "AttributeError" in retry


def test_a_probe_that_stays_broken_is_skipped_and_the_prerequisite_is_taught_instead(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe(BROKEN), probe(BROKEN)],
                 "teach": [lesson("PRE"), lesson("T1"), lesson("T2")]})
    go(store, run, stub)

    assert stub.calls == ["plan", "probe", "probe", "teach"]     # never showed the bad question
    assert [v.payload["style"] for v in store.history(run, "lesson")] == ["plain"]
    assert store.history(run, "lesson")[0].payload["concept"] == PRE
    assert [v.payload["concept"] for v in store.history(run, "probe_skipped")] == [PRE]

    quiz_me(store, run, stub)
    answer(store, run, RIGHT); go(store, run, stub)              # taught it: on to the topic, no re-probe
    assert stub.calls == ["plan", "probe", "probe", "teach", "teach"]
    assert store.history(run, "lesson")[1].payload["concept"] == TARGET


def test_with_the_sandbox_off_the_probe_is_shown_unchecked_rather_than_blocked(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe(BROKEN)]})
    go(store, run, stub, ready=OFF, run_code=lambda c: 1 / 0)    # must not even try to run it
    assert stub.calls == ["plan", "probe"]
    assert store.history(run, "lesson")[0].payload["quiz"]["code"] == BROKEN


def test_a_probe_without_code_never_touches_the_sandbox(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store)
    stub = Stub({"plan": [plan()], "probe": [probe()]})
    go(store, run, stub, ready=lambda: 1 / 0, run_code=lambda c: 1 / 0)
    assert stub.calls == ["plan", "probe"]


import pytest  # noqa: E402


@pytest.mark.integration
def test_the_real_sandbox_catches_the_broken_probe_code_and_passes_the_clean_one():
    from demo.tutor import sandbox
    ok, why = sandbox.available(force=True)
    assert ok, why                                     # needs Docker running and the image pulled
    problem = coach.question_code_problem(quiz(BROKEN), sandbox.run)
    assert problem and "AttributeError" in problem
    assert coach.question_code_problem(quiz(CLEAN), sandbox.run) is None
    assert "too long" in coach.question_code_problem(quiz("while True: pass"), lambda c: sandbox.run(c, timeout=3))

"""The code sandbox has a language and a version; nothing else does. Only a program question is written in it, and a
program question is only shown once its own model solution passes its own hidden tests. Lessons, quizzes, plans and
grading follow the topic, whatever the sandbox is set to. The model and the sandbox are scripted; no Docker is needed."""
import json

import pytest

from demo.tutor import languages, learners, session
from demo.tutor.flow import build_flow, build_final_messages, build_grade_messages, build_plan_messages
from demo.tutor.flow import build_probe_messages, build_teach_messages
from demo.tutor.sandbox import Judged, Result
from demo.tutor.stub import Stub, code_lesson, lesson, plan, probe, stdio_lesson
from slice import runner
from slice.store import Store
from tests.test_tutor import S, find
from tests.test_tutor_api import make, settle, start
from tests.test_tutor_guided import TARGET
from tests.test_tutor_program import local_run
from web import tutor_api

ON = lambda *a, **k: (True, "")          # noqa: E731
OFF = lambda *a, **k: (False, "The Java 17 runtime is not installed. Run: docker pull eclipse-temurin:17-jdk")   # noqa: E731


def squares(solutions):
    """A stand-in judge: each 'program' is a name, and `solutions` says what it prints for a given input."""
    calls = []

    def judge(code, stdins, *, language=None, version=None, timeout=None):
        calls.append((code, language, version))
        return Judged(runs=[Result(solutions[code](i), "", 0) for i in stdins])
    judge.calls = calls
    return judge


SQUARE = lambda i: str(int(i) ** 2)          # noqa: E731
FORGETS = lambda i: "3"                      # noqa: E731
JAVA_17 = ("java", "17")


def java_session(store, mode="quick", answer_mode="code", topic="recursion"):
    """A session whose code sandbox is set to Java 17 (picked in the sandbox, after the session began)."""
    run = session.start_session(store, "s1", [topic], mode=mode)
    session.set_language(store, run, *JAVA_17)
    session.set_answer_mode(store, run, answer_mode)
    return run


def system_of(messages):
    return messages[0]["content"]


def user_of(messages):
    return messages[1]["content"]


def everything(messages):
    return "".join(m["content"] for m in messages)


# ------------------------------------------------------------------ only a program question is told the language

def test_a_program_question_is_told_the_language_and_nothing_else_is():
    for want in ("mcq", "text"):
        assert "LANGUAGE:" not in everything(build_teach_messages("photosynthesis", "plain", "general", want, "p", None,
                                                                 language="java", version="17"))
    assert "LANGUAGE:" not in everything(build_plan_messages("photosynthesis", False, []))
    assert "LANGUAGE:" not in everything(build_probe_messages("photosynthesis", "p"))
    assert "LANGUAGE:" not in everything(build_final_messages("photosynthesis", [], None, "p"))
    assert "LANGUAGE:" not in everything(build_grade_messages({"question": "q", "rubric": ["r"], "model_answer": "m",
                                                              "common_mistakes": []}, "a", ""))
    java = build_teach_messages("recursion", "plain", "general", "code", "p", None, language="java", version="17")
    assert "LANGUAGE: Java 17." in user_of(java) and "use only features that exist in that version" in user_of(java)
    cpp = build_teach_messages("recursion", "plain", "general", "code", "p", None, language="cpp", version="20")
    assert "LANGUAGE: C++20." in user_of(cpp)
    default = build_teach_messages("recursion", "plain", "general", "code", "p", None)
    assert "LANGUAGE: Python 3.12." in user_of(default)


def test_the_prompts_are_about_any_subject_not_only_programming():
    texts = {"teach": system_of(build_teach_messages("x", "plain", "general", "mcq", "p", None)),
             "plan": system_of(build_plan_messages("x", False, [])),
             "probe": system_of(build_probe_messages("x", "p")),
             "final": system_of(build_final_messages("x", [], None, "p"))}
    for name, text in texts.items():
        assert "learning to program" not in text and "learning Python" not in text, name
    for name in ("plan", "probe", "final"):
        assert "on the LANGUAGE line" not in texts[name], name


def test_python_programs_call_a_function_and_every_other_language_reads_input():
    py = system_of(build_teach_messages("x", "plain", "general", "code", "p", None, language="python", version="3.11"))
    assert "Ask for ONE small function" in py and "Ask for ONE small program" not in py
    for language, version in (("javascript", "20"), ("java", "17"), ("cpp", "17")):
        other = system_of(build_teach_messages("x", "plain", "general", "code", "p", None,
                                               language=language, version=version))
        assert "Ask for ONE small program" in other and "Ask for ONE small function" not in other


def test_an_unknown_language_never_reaches_a_program_question():
    with pytest.raises(languages.UnknownLanguage):
        build_teach_messages("x", "plain", "general", "code", "p", None, language="cobol")


def test_a_rejected_program_question_is_sent_back_with_the_reason():
    msgs = build_teach_messages("x", "plain", "general", "code", "p", None, language="java", version="17",
                                problem="a check for the idea 'zero-not-handled' does not pass")
    assert "PREVIOUS PROGRAM QUESTION WAS REJECTED" in user_of(msgs) and "zero-not-handled" in user_of(msgs)


# ------------------------------------------------------------------ the sandbox language belongs to the student

def test_a_session_starts_in_python_and_takes_no_language(tmp_path):
    store = Store(tmp_path / "r.db")
    with pytest.raises(TypeError):
        session.start_session(store, "s1", ["x"], language="java")            # not something a session is started with
    run = session.start_session(store, "s1", ["x"])
    assert "language" not in store.latest(run, "input")
    model = learners.load(store, "s1")
    assert (model.language, model.version) == ("python", None)


def test_picking_a_language_in_the_sandbox_is_remembered_for_next_time(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["x"])
    session.set_language(store, run, "java", "17")
    assert (learners.load(store, "s1").language, learners.load(store, "s1").version) == JAVA_17
    session.set_language(store, run, "cpp")                                   # no version: that language's default
    assert (learners.load(store, "s1").language, learners.load(store, "s1").version) == ("cpp", "17")
    next_session = session.start_session(store, "s1", ["y"])                  # a later session begins where they left it
    latest = store.latest(next_session, "learner_model")
    assert (latest["language"], latest["version"]) == ("cpp", "17")


def test_a_language_or_version_we_cannot_run_is_refused(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["x"])
    with pytest.raises(languages.UnknownLanguage, match="cobol"):
        session.set_language(store, run, "cobol")
    with pytest.raises(languages.UnknownLanguage, match="3.4"):
        session.set_language(store, run, "python", "3.4")
    assert learners.load(store, "s1").language == "python"                   # nothing changed


def test_lessons_ignore_the_sandbox_language(tmp_path):
    """A student learning photosynthesis with the sandbox on Java gets a lesson that says nothing about Java."""
    store = Store(tmp_path / "r.db")
    run = java_session(store, answer_mode="mcq", topic="photosynthesis")
    stub = Stub({"teach": [lesson("LESSON")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=ON), S)
    assert "LANGUAGE:" not in everything(stub.messages[0])


def test_a_guided_plan_ignores_the_sandbox_language_and_is_cached_under_the_topic(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store, mode="guided", answer_mode="mcq", topic="recursion")
    stub = Stub({"plan": [plan(prereqs=(), subtopics=())], "teach": [lesson("LESSON")]})
    runner.advance(store, run, build_flow(call=stub, find=find, ready=OFF), S)
    assert "LANGUAGE:" not in everything(stub.messages[0])
    assert set(learners.load(store, "s1").plans) == {"recursion"}


# ------------------------------------------------------------------ a program question is written and graded in the sandbox language

def test_a_java_sandbox_asks_the_model_for_a_java_input_output_program(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [stdio_lesson("LESSON")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=ON, judge=squares({"SQUARE": SQUARE})), S)
    [msgs] = stub.messages
    assert "LANGUAGE: Java 17." in user_of(msgs) and '"style": "stdio"' in system_of(msgs)
    shown = store.latest(run, "lesson")
    assert shown["code_task"]["style"] == "stdio" and (shown["language"], shown["version"]) == JAVA_17


def test_a_question_keeps_its_language_when_the_sandbox_picker_moves_on(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    judge = squares({"SQUARE": SQUARE, "student": SQUARE})
    stub = Stub({"teach": [stdio_lesson("LESSON"), stdio_lesson("NEXT")]})
    flow = lambda: build_flow(call=stub, find=find, run=local_run, ready=ON, judge=judge)   # noqa: E731
    runner.advance(store, run, flow(), S)
    session.set_language(store, run, "cpp", "20")                              # the student switches the sandbox
    session.submit_code(store, session.open_quiz(store, run).id, "student", "high", False)
    runner.advance(store, run, flow(), S)
    assert judge.calls[:2] == [("SQUARE", "java", "17"), ("student", "java", "17")]   # graded where it was written
    assert store.history(run, "check")[0].payload["correct"] is True
    assert "LANGUAGE: C++20." in user_of(stub.messages[1])                      # the NEXT question follows the picker


def test_a_wrong_hidden_test_is_caught_before_the_student_sees_it_and_rewritten_once(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [stdio_lesson("BAD", solution="FORGETS"), stdio_lesson("GOOD")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=ON,
                                          judge=squares({"FORGETS": FORGETS, "SQUARE": SQUARE})), S)
    [rejected] = store.history(run, "task_rejected")
    assert "zero-not-handled" in rejected.payload["problem"] or "forgets-to-multiply" in rejected.payload["problem"]
    assert "PREVIOUS PROGRAM QUESTION WAS REJECTED" in user_of(stub.messages[1])       # told why, so it can fix it
    assert store.latest(run, "lesson")["explanation"] == "GOOD"
    assert session.open_quiz(store, run) is not None


def test_a_question_that_is_never_fair_becomes_multiple_choice_and_says_so(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [stdio_lesson("BAD1", solution="FORGETS"), stdio_lesson("BAD2", solution="FORGETS"),
                           lesson("MCQ")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=ON,
                                          judge=squares({"FORGETS": FORGETS})), S)
    shown = store.latest(run, "lesson")
    assert shown["quiz"] and not shown["code_task"] and "multiple choice" in shown["explanation"]
    assert "Java 17" in shown["explanation"]
    assert len(store.history(run, "task_rejected")) == 2 and stub.calls == ["teach"] * 3   # bounded: three model calls, no loop


def test_a_program_question_in_the_wrong_style_for_the_language_is_rejected(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [code_lesson("PYTHON STYLE"), stdio_lesson("OK")]})       # a Python function question for Java
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=ON,
                                          judge=squares({"SQUARE": SQUARE})), S)
    [rejected] = store.history(run, "task_rejected")
    assert "stdio" in rejected.payload["problem"]
    assert store.latest(run, "lesson")["explanation"] == "OK"


def test_without_the_language_runtime_the_check_is_multiple_choice_at_once(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [lesson("MCQ")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run, ready=OFF), S)
    shown = store.latest(run, "lesson")
    assert shown["quiz"] and "Java 17" in shown["explanation"] and stub.calls == ["teach"]


def test_the_runtime_is_checked_for_the_sandbox_language(tmp_path):
    asked = []
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [lesson("MCQ")]})
    runner.advance(store, run, build_flow(call=stub, find=find, run=local_run,
                                          ready=lambda *a, **k: asked.append(a) or (False, "no")), S)
    assert asked == [JAVA_17]


def test_a_sandbox_that_fails_while_grading_stops_the_run_and_never_blames_the_student(tmp_path):
    store = Store(tmp_path / "r.db")
    run = java_session(store)
    stub = Stub({"teach": [stdio_lesson("LESSON")]})
    judged = iter([Judged(runs=[Result("9", "", 0), Result("0", "", 0)]), Judged(broken=True, why="Docker went away.")])
    flow = lambda: build_flow(call=stub, find=find, run=local_run, ready=ON,       # noqa: E731
                              judge=lambda *a, **k: next(judged))
    runner.advance(store, run, flow(), S)
    session.submit_code(store, session.open_quiz(store, run).id, "student", "high", False)
    runner.advance(store, run, flow(), S)
    [fail] = store.history(run, "failure")
    assert fail.payload["kind"] == "sandbox_unavailable" and "Docker went away" in fail.payload["detail"]
    assert not store.history(run, "check")


# ------------------------------------------------------------------ a probe's code runs in the language it says it is in

JAVA_CODE = 'public class Main { public static void main(String[] a) { System.out.println("hi"); } }'


def _probe_run(tmp_path, language, code=JAVA_CODE):
    """A guided session (sandbox still Python) whose probe carries `code` and says `language` (None: says nothing)."""
    seen = []
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", [TARGET], mode="guided")
    raw = json.loads(probe(code))
    stub = Stub({"plan": [plan()], "probe": [json.dumps(raw if language is None else raw | {"code_language": language})]})

    def fake_run(c, timeout=None, *, language=None, version=None, stdin=""):
        seen.append((c, language, version))
        return Result("hi\n", "", 0)
    runner.advance(store, run, build_flow(call=stub, find=find, run=fake_run, ready=ON), S)
    return code, seen, store, run


def test_a_java_probe_is_run_as_java_whatever_the_sandbox_is_set_to(tmp_path):
    code, seen, store, run = _probe_run(tmp_path, "java")
    assert seen == [(code, "java", "21")]                                      # Java's default version, not compiled as Python
    assert not store.history(run, "probe_rejected")


def test_a_probe_that_does_not_say_its_language_is_run_as_python_as_before(tmp_path):
    code, seen, _, _ = _probe_run(tmp_path, None, code='print("hi")')
    assert seen == [(code, "python", "3.12")]


def test_a_probe_in_a_language_we_cannot_run_is_shown_unchecked(tmp_path):
    _, seen, store, run = _probe_run(tmp_path, "sql")
    assert seen == [] and not store.history(run, "probe_rejected") and not store.history(run, "probe_skipped")
    assert session.open_quiz(store, run) is not None


# ------------------------------------------------------------------ the API

def test_a_session_starts_in_python_and_the_start_request_takes_no_language(tmp_path, monkeypatch):
    c, stub = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON")]})
    run = start(c, language="java", version="17")                             # unknown fields are ignored, not honoured
    snap = settle(c, run)
    assert snap["progress"]["language"] == {"id": "python", "name": "Python", "version": "3.12", "label": "Python 3.12"}
    assert "LANGUAGE:" not in everything(stub.messages[0])


def test_the_sandbox_picker_changes_the_language_and_is_remembered(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON"), lesson("AGAIN")]})
    run = start(c)
    settle(c, run)
    snap = c.post(f"/api/sessions/{run}/language", json={"language": "java", "version": "17"}).json()
    assert snap["progress"]["language"] == {"id": "java", "name": "Java", "version": "17", "label": "Java 17"}
    snap = c.post(f"/api/sessions/{run}/language", json={"language": "cpp"}).json()          # no version: the default
    assert snap["progress"]["language"]["label"] == "C++17"
    assert settle(c, start(c))["progress"]["language"]["label"] == "C++17"                  # the next session begins there


def test_the_sandbox_picker_refuses_what_it_cannot_run_and_waits_for_a_lesson(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON")]})
    run = start(c)
    settle(c, run)
    bad = c.post(f"/api/sessions/{run}/language", json={"language": "cobol"})
    assert bad.status_code == 422 and "Choose one of" in bad.json()["detail"]
    bad = c.post(f"/api/sessions/{run}/language", json={"language": "java", "version": "6"})
    assert bad.status_code == 422 and "Java 6" in bad.json()["detail"]
    assert c.get(f"/api/sessions/{run}").json()["progress"]["language"]["label"] == "Python 3.12"   # unchanged
    tutor_api._running.add(run)                                              # a lesson is being written
    try:
        assert c.post(f"/api/sessions/{run}/language", json={"language": "java"}).status_code == 409
    finally:
        tutor_api._running.discard(run)


def test_the_language_list_says_which_runtimes_are_installed(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    monkeypatch.setattr(tutor_api, "sandbox_installed", lambda: {"python:3.12-slim", "eclipse-temurin:17-jdk"})
    body = c.get("/api/languages").json()
    by_id = {lang["id"]: lang for lang in body["languages"]}
    assert set(by_id) == {"python", "javascript", "java", "cpp"} and body["docker"] is True and "last" not in body
    assert by_id["java"]["installed"]["17"] is True and by_id["java"]["installed"]["8"] is False
    assert by_id["python"]["installed"]["3.12"] is True and by_id["python"]["default"] == "3.12"
    assert "images" not in by_id["java"]                                   # the page needs no image names from us
    monkeypatch.setattr(tutor_api, "sandbox_installed", lambda: None)
    body = c.get("/api/languages").json()
    assert body["docker"] is False and not any(any(lang["installed"].values()) for lang in body["languages"])


def test_code_status_is_asked_per_language(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {})
    asked = []
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda *a: asked.append(a) or (False, "The Java runtime is missing."))
    r = c.get("/api/code/status", params={"language": "java", "version": "17"}).json()
    assert r == {"available": False, "reason": "The Java runtime is missing.", "language": "java", "version": "17"}
    assert asked == [JAVA_17]
    assert c.get("/api/code/status", params={"language": "cobol"}).status_code == 422


def test_the_editor_runs_in_the_sandbox_language_with_its_input(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON")]})
    seen = {}

    def fake_run(code, **kw):
        seen.update(code=code, **kw)
        return Result("9\n", "", 0)
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda *a: (True, ""))
    monkeypatch.setattr(tutor_api, "sandbox_run", fake_run)
    run = start(c)
    settle(c, run)
    c.post(f"/api/sessions/{run}/language", json={"language": "java", "version": "17"})
    r = c.post(f"/api/sessions/{run}/code", json={"code": "class Main {}", "stdin": "3\n", "expected": "9"})
    assert r.status_code == 200 and r.json()["correct"] is True
    assert seen == {"code": "class Main {}", "language": "java", "version": "17", "stdin": "3\n"}
    ran = Store(tutor_api.DB).history(run, "code_run")[0].payload
    assert (ran["language"], ran["version"], ran["stdin"]) == ("java", "17", "3\n")


def test_a_program_questions_editor_can_name_its_own_language(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON")]})
    seen = {}
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda *a: (True, ""))
    monkeypatch.setattr(tutor_api, "sandbox_run", lambda code, **kw: seen.update(kw) or Result("", "", 0))
    run = start(c)
    settle(c, run)
    c.post(f"/api/sessions/{run}/language", json={"language": "python"})
    assert c.post(f"/api/sessions/{run}/code", json={"code": "x", "language": "java", "version": "17"}).status_code == 200
    assert (seen["language"], seen["version"]) == JAVA_17                      # the question's language beat the sandbox's
    bad = c.post(f"/api/sessions/{run}/code", json={"code": "x", "language": "cobol"})
    assert bad.status_code == 422 and "Choose one of" in bad.json()["detail"]


def test_the_editor_is_switched_off_per_language(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("LESSON")]})
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda language, version: (language == "python", "missing"))
    monkeypatch.setattr(tutor_api, "sandbox_run", lambda code, **kw: Result("", "", 0))
    run = start(c)
    settle(c, run)
    assert c.post(f"/api/sessions/{run}/code", json={"code": "x"}).status_code == 200        # Python still runs
    c.post(f"/api/sessions/{run}/language", json={"language": "java", "version": "17"})
    r = c.post(f"/api/sessions/{run}/code", json={"code": "class Main {}"})
    assert r.status_code == 503 and "missing" in r.json()["detail"]
    r = c.post(f"/api/sessions/{run}/mode", json={"mode": "code"})
    assert r.status_code == 422 and "missing" in r.json()["detail"]


def test_the_page_is_told_the_questions_language_and_kind_but_never_the_tests(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, None, call=Stub({"teach": [stdio_lesson("LESSON")]}))
    monkeypatch.setattr(tutor_api, "flow_factory", lambda: build_flow(
        call=Stub({"teach": [stdio_lesson("LESSON")]}), find=find, run=local_run, ready=ON,
        judge=squares({"SQUARE": SQUARE})))
    store = Store(tutor_api.DB)
    run = session.start_session(store, "asha", ["recursion"])
    session.set_language(store, run, *JAVA_17)
    session.set_answer_mode(store, run, "code")
    store.close()
    tutor_api._kick(run)
    [msg] = settle(c, run)["messages"]
    task = msg["code_task"]
    assert task["style"] == "stdio" and task["question"].startswith("Read one integer")
    assert task["language"] == {"id": "java", "name": "Java", "version": "17", "label": "Java 17"}
    sent = json.dumps(msg)
    for secret in ("forgets-to-multiply", "zero-not-handled", "model_solution", "expected", "SQUARE"):
        assert secret not in sent

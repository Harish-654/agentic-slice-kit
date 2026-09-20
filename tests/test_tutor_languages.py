"""Several languages and versions: the registry, how a program reaches the sandbox, and what its errors mean.

No Docker in this file: the sandbox's pieces are checked as data, and grading runs against a fake runner. The tests
that need real runtimes are marked `integration` and live at the bottom."""
import base64
import re

import pytest

from demo.tutor import coach, languages, sandbox
from demo.tutor.sandbox import Judged, Result

PY, JS, JAVA, CPP = (languages.LANGUAGES[k] for k in ("python", "javascript", "java", "cpp"))


# ------------------------------------------------------------------ the registry

def test_four_languages_each_with_versions_and_a_default_that_is_one_of_them():
    assert list(languages.LANGUAGES) == ["python", "javascript", "java", "cpp"]
    for lang in languages.LANGUAGES.values():
        assert lang.default in lang.versions and len(lang.versions) >= 3


@pytest.mark.parametrize("language,version,image", [
    ("python", "3.9", "python:3.9-slim"), ("python", None, "python:3.12-slim"), ("javascript", "20", "node:20-slim"),
    ("java", "17", "eclipse-temurin:17-jdk"), ("java", "8", "eclipse-temurin:8-jdk"), ("cpp", "20", "gcc:14")])
def test_a_language_and_version_choose_the_runtime_image(language, version, image):
    lang, v = languages.resolve(language, version)
    assert lang.image_for(v) == image


def test_nothing_chosen_means_python_at_its_default():
    lang, v = languages.resolve(None, None)
    assert (lang.id, v) == ("python", "3.12")
    assert languages.resolve("  Java ", " 17 ")[1] == "17"                       # tidied, any case


@pytest.mark.parametrize("language,version", [("ruby", None), ("python", "2.7"), ("java", "7"), ("cpp", "98"), ("", "x")])
def test_an_unsupported_language_or_version_is_refused_with_the_choices(language, version):
    with pytest.raises(languages.UnknownLanguage) as e:
        languages.resolve(language, version)
    assert "Choose one of" in str(e.value)


def test_labels_read_the_way_a_student_says_them():
    assert [languages.resolve(l, v)[0].label(v) for l, v in
            (("python", "3.12"), ("javascript", "22"), ("java", "17"), ("cpp", "17"))] == \
        ["Python 3.12", "JavaScript 22", "Java 17", "C++17"]


def test_the_prompt_line_pins_the_language_and_the_version():
    line = JAVA.prompt_line("8")
    assert line.startswith("LANGUAGE: Java 8.") and "only features that exist in that version" in line


def test_the_catalogue_lists_every_image_for_the_pickers():
    cat = {c["id"]: c for c in languages.catalogue()}
    assert cat["java"]["images"]["17"] == "eclipse-temurin:17-jdk" and cat["cpp"]["default"] == "17"


# ------------------------------------------------------------------ the class a Java program starts in

@pytest.mark.parametrize("code,cls", [
    ("public class Main { public static void main(String[] a) {} }", "Main"),
    ("public class Hello { public static void main(String[] args) {} }", "Hello"),
    ("class Helper {}\npublic class App { public static void main(String[] a) {} }", "App"),
    ("class A {}\nclass B { static void main(String[] a) {} }", "B"),                # the class that holds main
    ("public class OnlyThis { }", "OnlyThis"), ("int x = 1;", "Main")])
def test_the_java_file_is_named_after_the_class_that_starts_the_program(code, cls):
    assert languages.java_class(code) == cls


def test_only_a_plain_identifier_can_ever_reach_a_shell_command():
    evil = 'public class X; rm -rf /; # { public static void main(String[] a) {} }'
    cls = languages.java_class(evil)
    assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cls)


@pytest.mark.parametrize("language,version,expect", [
    ("python", "3.12", {"file": "main.py", "compile": "", "run": "exec python -I main.py"}),
    ("javascript", "22", {"file": "main.js", "compile": "", "run": "exec node main.js"}),
    ("cpp", "17", {"file": "main.cpp", "compile": "g++ -std=c++17 -O1 -pipe -o main main.cpp", "run": "exec ./main"}),
    ("cpp", "23", {"file": "main.cpp", "compile": "g++ -std=c++23 -O1 -pipe -o main main.cpp", "run": "exec ./main"})])
def test_each_language_and_version_gets_its_own_commands(language, version, expect):
    lang, v = languages.resolve(language, version)
    assert languages.commands(lang, v, "code") == expect


def test_java_compiles_and_runs_the_students_own_class_name():
    cmd = languages.commands(JAVA, "17", "public class Cart { public static void main(String[] a) {} }")
    assert cmd["file"] == "Cart.java" and cmd["compile"].endswith("Cart.java") and cmd["run"].endswith(" Cart")


# ------------------------------------------------------------------ how a program reaches the sandbox

def env(code, stdins=("",), lang=PY, version="3.12"):
    return sandbox.script_env(lang, version, code, list(stdins), "TOK")


def test_the_source_and_every_input_travel_only_as_base64_data():
    hostile = "'; rm -rf / #\n$(reboot) `id` \"; echo pwned\n" + "\x00‮"
    e = env(hostile, ["1\n2\n", hostile])
    assert base64.b64decode(e["SRC_B64"]).decode() == hostile
    assert base64.b64decode(e["IN_1"]).decode() == hostile
    assert all(re.fullmatch(r"[A-Za-z0-9+/=]*", e[k]) for k in ("SRC_B64", "IN_0", "IN_1", "SCRIPT_B64"))
    # nothing derived from the student is in any command: only fixed strings and the token
    assert e["RUN"] == "exec python -I main.py" and e["COMPILE"] == "" and e["TOKEN"] == "TOK"


def test_the_script_the_container_runs_never_contains_the_students_text():
    script = base64.b64decode(env("UNIQUE_STUDENT_TEXT_12345")["SCRIPT_B64"]).decode()
    assert "UNIQUE_STUDENT_TEXT_12345" not in script and "@@" in script            # fixed framing only


def test_a_program_gets_at_most_a_bounded_amount_of_input():
    e = env("x", ["a" * 10 ** 6])
    assert len(base64.b64decode(e["IN_0"])) == sandbox.MAX_STDIN


@pytest.mark.parametrize("language,version", [("python", "3.12"), ("javascript", "22"), ("java", "21"), ("cpp", "17")])
def test_every_language_runs_behind_the_same_walls(language, version):
    lang, v = languages.resolve(language, version)
    args = sandbox.docker_args(lang, v, "tutor-x", "/tmp/e.env", ["sh", "-c", "true"])
    flat = " ".join(args)
    for wall in ("--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges", "--pull never",
                 "--user 65534:65534", "--env-file /tmp/e.env"):
        assert wall in flat, wall
    assert "--memory " + lang.memory in flat and "--pids-limit " + str(lang.pids) in flat
    assert not any(a in ("-v", "--volume", "--mount", "--privileged", "--network=host") for a in args)   # nothing shared with the host


def test_only_compiled_languages_get_an_executable_scratch_area():
    def scratch(lang, v):
        a = sandbox.docker_args(lang, v, "n", None, ["true"])
        return next(x for x in a if x.startswith("/work:"))
    assert "exec" in scratch(JAVA, "21") and "exec" in scratch(CPP, "17")
    assert "exec" not in scratch(PY, "3.12") and "exec" not in scratch(JS, "22")
    assert "noexec" in next(x for x in sandbox.docker_args(CPP, "17", "n", None, ["true"]) if x.startswith("/tmp:"))


def test_output_is_read_back_from_marked_base64_and_cannot_be_forged():
    b = lambda s: base64.b64encode(s.encode()).decode()                              # noqa: E731
    docker_out = "\n".join([
        "@@TOK COMPILE 0@@", b(""),
        "@@TOK RUN 0 0@@", b("6\n"), b(""),
        "@@TOK RUN 1 1@@", b(""), b("Exception in thread main"),
        "@@TOK RUN 2 124@@", b(""), b(""),
        "@@FORGED RUN 0 0@@", b("i am fake"), b("")])                                # a marker without the real token
    j = sandbox._parse(docker_out, "TOK", 3)
    assert not j.compile_failed and len(j.runs) == 3
    assert (j.runs[0].stdout, j.runs[0].exit_code) == ("6\n", 0)
    assert j.runs[1].stderr == "Exception in thread main" and j.runs[1].exit_code == 1
    assert j.runs[2].timed_out is True


def test_a_compile_failure_is_reported_with_the_compilers_message():
    b = lambda s: base64.b64encode(s.encode()).decode()                              # noqa: E731
    j = sandbox._parse("@@T COMPILE 1@@\n" + b("Main.java:3: error: ';' expected"), "T", 1)
    assert j.compile_failed and "';' expected" in j.compile_output and j.runs == []


def test_a_missing_image_says_exactly_how_to_get_it():
    msg = sandbox._missing("docker: Error response from daemon: No such image: node:22-slim.", JS, "22")
    assert msg == "The JavaScript 22 runtime is not installed. Run: docker pull node:22-slim"
    assert sandbox._missing("something else", JS, "22") is None


def test_every_image_we_can_run_is_listed_for_the_pull_script():
    imgs = {i for _, _, i in sandbox.images()}
    assert {"python:3.12-slim", "node:22-slim", "eclipse-temurin:21-jdk", "gcc:14"} <= imgs


# ------------------------------------------------------------------ what an error means, in each language

def err(text, code=1, compile_failed=False, timed_out=False):
    return Result("", text, code, timed_out=timed_out, compile_failed=compile_failed)


@pytest.mark.parametrize("language,text,tag", [
    ("javascript", "ReferenceError: total is not defined\n    at main.js:2", "undefined-name"),
    ("javascript", "TypeError: Cannot read properties of undefined (reading 'length')", "null-access"),
    ("javascript", "TypeError: items.map is not a function", "type-mismatch"),
    ("javascript", "RangeError: Maximum call stack size exceeded", "runaway-recursion"),
    ("javascript", "SyntaxError: Unexpected token '}'", "syntax-error"),
    ("javascript", "TypeError: Assignment to constant variable.", "const-reassigned"),
    ("java", "Exception in thread \"main\" java.lang.NullPointerException", "null-dereference"),
    ("java", "Exception in thread \"main\" java.lang.ArrayIndexOutOfBoundsException: Index 5 out of bounds", "index-out-of-range"),
    ("java", "Exception in thread \"main\" java.lang.ArithmeticException: / by zero", "divide-by-zero"),
    ("java", "Exception in thread \"main\" java.lang.StackOverflowError", "runaway-recursion"),
    ("java", "Exception in thread \"main\" java.util.InputMismatchException", "bad-input"),
    ("java", "Main.java:4: error: cannot find symbol\n  symbol:   variable x", "undefined-name"),
    ("java", "Main.java:3: error: ';' expected", "syntax-error"),
    ("java", "Main.java:5: error: incompatible types: String cannot be converted to int", "type-mismatch"),
    ("java", "Main.java:7: error: missing return statement", "missing-return"),
    ("java", "Cart.java:1: error: class Main is public, should be declared in a file named Main.java", "class-file-name"),
    ("cpp", "main.cpp:5:3: error: 'x' was not declared in this scope", "undefined-name"),
    ("cpp", "main.cpp:4:20: error: expected ';' before 'return'", "syntax-error"),
    ("cpp", "main.cpp:6: error: no match for 'operator+' (operand types are 'int' and 'std::vector<int>')", "type-mismatch"),
    ("cpp", "/usr/bin/ld: main.o: undefined reference to `helper()'", "undefined-reference"),
    ("cpp", "terminate called after throwing an instance of 'std::out_of_range'\n  what():  vector::_M_range_check", "index-out-of-range"),
    ("cpp", "terminate called after throwing an instance of 'std::runtime_error'", "uncaught-exception")])
def test_each_language_error_becomes_the_same_kind_of_misconception_tag(language, text, tag):
    found = coach.classify(err(text), language)
    assert found and found[0] == tag and found[1]


def test_the_same_idea_has_one_tag_across_languages():
    """An index past the end is index-out-of-range whether it is a Python IndexError, a Java exception or a C++ one."""
    assert coach.classify(err("IndexError: list index out of range"), "python")[0] == "index-out-of-range"
    assert coach.classify(err("java.lang.ArrayIndexOutOfBoundsException"), "java")[0] == "index-out-of-range"
    assert coach.classify(err("terminate called after throwing an instance of 'std::out_of_range'"), "cpp")[0] == "index-out-of-range"


@pytest.mark.parametrize("code,tag", [(139, "invalid-memory-access"), (136, "divide-by-zero"), (134, "uncaught-exception")])
def test_a_native_program_that_dies_silently_is_read_from_its_exit_signal(code, tag):
    assert coach.classify(err("", code=code), "cpp")[0] == tag


def test_a_compile_failure_with_no_recognised_message_is_still_a_compile_error():
    assert coach.classify(err("weird unknown diagnostic", compile_failed=True), "cpp")[0] == "compile-error"


def test_nothing_readable_means_no_diagnosis_and_a_timeout_is_never_a_misconception():
    assert coach.classify(err("", code=1), "java") is None
    assert coach.evidence(err("", code=None, timed_out=True), None, "java") == (None, None)
    assert coach.classify(err("NullPointerException", timed_out=True), "java") is None      # a timeout says nothing about ideas
    assert coach.evidence(err("java.lang.NullPointerException"), None, "java") == (False, "null-dereference")
    assert coach.hint(err("cannot find symbol", compile_failed=True), False, "java")


def test_running_code_without_error_still_proves_nothing_unless_output_is_expected():
    ok = Result("42\n", "", 0)
    assert coach.evidence(ok, None, "javascript") == (None, None)
    assert coach.evidence(ok, "42", "javascript") == (True, None)
    assert coach.evidence(ok, "43", "javascript") == (False, "wrong-output")


# ------------------------------------------------------------------ grading a program that reads input and prints output

TASK = {"style": "stdio", "question": "Read n, print n squared.", "model_solution": "SOLUTION",
        "tests": [{"stdin": "3\n", "expected": "9", "belief": "forgets-to-multiply"},
                  {"stdin": "0\n", "expected": "0", "belief": "zero-not-handled"},
                  {"stdin": "-4\n", "expected": "16", "belief": "negative-not-handled"}]}


def judge_returning(*runs, **kw):
    def judge(code, stdins, language=None, version=None):
        judge.seen = (code, list(stdins), language, version)
        return Judged(runs=list(runs), **kw)
    return judge


def R(out="", code=0, err_text="", timed_out=False):
    return Result(out, err_text, code, timed_out=timed_out)


def test_a_program_that_prints_every_expected_output_passes_and_sees_each_hidden_input():
    judge = judge_returning(R("9\n"), R("0"), R("16 \n\n"))                               # trailing spaces and blank lines do not matter
    g = coach.grade_program(TASK, "code", None, "java", "17", judge)
    assert g.correct and judge.seen == ("code", ["3\n", "0\n", "-4\n"], "java", "17")


def test_the_first_wrong_output_names_the_idea_it_exposes_and_not_the_answer():
    g = coach.grade_program(TASK, "c", None, "cpp", "17", judge_returning(R("9"), R("1"), R("16")))
    assert not g.correct and g.misconception == "zero-not-handled"
    assert "zero-not-handled" in g.feedback
    assert not re.search(r"\b16\b|-4|\b9\b", g.feedback)                                  # neither the hidden inputs nor answers


def test_a_crash_is_named_by_its_error_not_by_the_tests_belief():
    g = coach.grade_program(TASK, "c", None, "java", "17",
                            judge_returning(R("9"), R("", 1, "Exception in thread main java.lang.ArithmeticException")))
    assert g.misconception == "divide-by-zero" and "crashed" in g.feedback


def test_a_compile_error_says_what_the_compiler_said():
    g = coach.grade_program(TASK, "c", None, "java", "17",
                            judge_returning(compile_failed=True, compile_output="Main.java:3: error: ';' expected\n  int x = 1\n"))
    assert g.misconception == "syntax-error" and "did not compile" in g.feedback and "';' expected" in g.feedback


def test_a_run_that_takes_too_long_is_a_runaway_loop():
    assert coach.grade_program(TASK, "c", None, "cpp", "17", judge_returning(R("9"), R("", None, "", True), R())).misconception == "runaway-loop"
    assert coach.grade_program(TASK, "c", None, "cpp", "17", judge_returning(timed_out=True)).misconception == "runaway-loop"


def test_a_broken_sandbox_is_never_marked_as_the_students_mistake():
    with pytest.raises(coach.SandboxUnavailable):
        coach.grade_program(TASK, "c", None, "java", "17", judge_returning(broken=True, why="Docker is not installed."))


# ------------------------------------------------------------------ a question must be fair before a student sees it

def test_a_question_whose_own_solution_passes_its_own_tests_is_fair():
    judge = judge_returning(R("9"), R("0"), R("16"))
    assert coach.task_problem(TASK, None, "cpp", "17", judge) is None
    assert judge.seen[0] == "SOLUTION"                                                    # it ran the MODEL's solution


def test_a_question_whose_solution_fails_its_own_tests_is_unfair_and_says_which_idea():
    problem = coach.task_problem(TASK, None, "cpp", "17", judge_returning(R("9"), R("7"), R("16")))
    assert problem and "zero-not-handled" in problem


def test_an_unavailable_sandbox_leaves_a_question_unchecked_not_condemned():
    assert coach.task_problem(TASK, None, "cpp", "17", judge_returning(broken=True, why="x")) is None


def test_python_function_questions_are_checked_the_same_way():
    task = {"style": "function", "question": "q", "model_solution": "def total(p):\n    return sum(p)",
            "tests": [{"call": "total([1, 2])", "expected": "3", "belief": "b1"}]}
    real = lambda code, **kw: _local(code)                                                # noqa: E731  (a local Python stands in for the sandbox)
    assert coach.task_problem(task, real) is None
    bad = dict(task, model_solution="def total(p):\n    return 0")
    assert coach.task_problem(bad, real) and "b1" in coach.task_problem(bad, real)


def _local(code):
    import subprocess
    import sys
    p = subprocess.run([sys.executable, "-I", "-"], input=code, capture_output=True, text=True, timeout=10)
    return Result(p.stdout, p.stderr, p.returncode)


# ------------------------------------------------------------------ probes: model-written code, in the right language

def quiz(code, *opts):
    return {"code": code, "options": [{"text": o} for o in (opts or ("a", "b", "c"))]}


def test_python_probe_code_is_still_checked_as_python():
    assert coach.question_code_problem(quiz("def f(:\n  pass"), lambda c: pytest.fail("ran")) .startswith("SyntaxError")


def test_java_probe_code_is_run_as_java_not_compiled_as_python():
    calls = []

    def run(code, language=None, version=None):
        calls.append((language, version))
        return Result("", "", 0)
    assert coach.question_code_problem(quiz("public class Main { public static void main(String[] a) {} }"), run, "java", "17") is None
    assert calls == [("java", "17")]                     # the old checker would have called this a Python syntax error


def test_a_probe_that_does_not_compile_is_rejected_with_the_compilers_message():
    run = lambda code, language=None, version=None: Result("", "Main.java:2: error: cannot find symbol", 1, compile_failed=True)   # noqa: E731
    problem = coach.question_code_problem(quiz("class X {}"), run, "java", "17")
    assert problem.startswith("it did not compile") and "cannot find symbol" in problem


def test_code_meant_to_fail_to_compile_is_allowed_when_an_option_is_about_the_error():
    run = lambda code, language=None, version=None: Result("", "error: x", 1, compile_failed=True)    # noqa: E731
    assert coach.question_code_problem(quiz("int x = ;", "prints 0", "a compile error"), run, "cpp", "17") is None

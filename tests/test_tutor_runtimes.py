"""The real runtimes, in real containers: does each language grade correctly, and do the walls hold?

These need Docker and the runtime images (`python scripts/pull_runtimes.py`). A language whose image is not
installed is skipped with the exact pull command, never failed. Marked `integration`, so the normal run leaves them out."""
import dataclasses
import time

import pytest

from demo.tutor import coach, languages, sandbox

pytestmark = pytest.mark.integration

RUNTIMES = [("python", "3.12"), ("python", "3.9"), ("javascript", "22"), ("java", "21"), ("cpp", "17")]


def need(language, version):
    ok, why = sandbox.available(language, version)
    if not ok:
        pytest.skip(why)


def rt(param):
    return pytest.param(*param, id=f"{param[0]}-{param[1]}")


# One "read n, print n squared" program per language, and the ways students get it wrong.
SQUARE = {
    "python": "n = int(input())\nprint(n * n)",
    "javascript": "const n = parseInt(require('fs').readFileSync(0, 'utf8'));\nconsole.log(n * n);",
    "java": "import java.util.*;\npublic class Main { public static void main(String[] a) {\n"
            "  Scanner s = new Scanner(System.in); int n = s.nextInt(); System.out.println(n * n); } }",
    "cpp": "#include <iostream>\nint main() { int n; std::cin >> n; std::cout << n * n << std::endl; }",
}
WRONG = {k: v.replace("n * n", "n + n") for k, v in SQUARE.items()}
BROKEN = {"python": "n = int(input(\nprint(n)", "javascript": "const n = ;\nconsole.log(n)",
          "java": "public class Main { public static void main(String[] a) { int n = 1 } }",
          "cpp": "#include <iostream>\nint main() { int n = 1 std::cout << n; }"}
CRASH = {"python": "print([][3])", "javascript": "console.log(nothingHere)",
         "java": "public class Main { public static void main(String[] a) { int[] x = new int[2]; System.out.println(x[5]); } }",
         "cpp": "#include <vector>\n#include <iostream>\nint main() { std::vector<int> v(2); std::cout << v.at(5); }"}
SPIN = {"python": "while True: pass", "javascript": "while (true) {}",
        "java": "public class Main { public static void main(String[] a) { while (true) {} } }",
        "cpp": "int main() { while (true) {} }"}
TASK = {"style": "stdio", "question": "q", "model_solution": "", "tests": [
    {"stdin": "3\n", "expected": "9", "belief": "b-three"}, {"stdin": "0\n", "expected": "0", "belief": "b-zero"},
    {"stdin": "-4\n", "expected": "16", "belief": "b-negative"}]}


def grade(language, version, code):
    return coach.grade_program(TASK, code, sandbox.run, language, version, sandbox.run_tests)


@pytest.mark.parametrize("language,version", [rt(r) for r in RUNTIMES])
def test_the_runtime_passes_its_own_isolation_self_test(language, version):
    need(language, version)
    ok, why = sandbox.available(language, version, force=True)
    assert ok, why


@pytest.mark.parametrize("language,version", [rt(r) for r in RUNTIMES])
def test_a_right_program_passes_and_a_wrong_one_names_the_idea(language, version):
    need(language, version)
    assert grade(language, version, SQUARE[language]).correct is True
    g = grade(language, version, WRONG[language])
    assert g.correct is False and g.misconception == "b-three" and "b-three" in g.feedback


@pytest.mark.parametrize("language,version,tag", [
    ("python", "3.12", "syntax-error"), ("javascript", "22", "syntax-error"), ("java", "21", "syntax-error"), ("cpp", "17", "syntax-error")])
def test_a_program_that_does_not_compile_or_parse_is_diagnosed(language, version, tag):
    need(language, version)
    g = grade(language, version, BROKEN[language])
    assert g.correct is False and g.misconception == tag, g


@pytest.mark.parametrize("language,version,tag", [
    ("python", "3.12", "index-out-of-range"), ("javascript", "22", "undefined-name"),
    ("java", "21", "index-out-of-range"), ("cpp", "17", "index-out-of-range")])
def test_a_crash_becomes_the_same_kind_of_tag_in_every_language(language, version, tag):
    need(language, version)
    g = grade(language, version, CRASH[language])
    assert g.correct is False and g.misconception == tag and "crashed" in g.feedback, g


@pytest.mark.parametrize("language,version", [rt(r) for r in RUNTIMES if r != ("python", "3.9")])
def test_an_endless_loop_is_stopped_and_named(language, version):
    need(language, version)
    t = time.time()
    g = grade(language, version, SPIN[language])
    assert g.misconception == "runaway-loop" and time.time() - t < 30


def test_the_older_python_really_is_the_older_python():
    need("python", "3.9")
    r = sandbox.run("import sys; print(sys.version_info[:2])", language="python", version="3.9")
    assert r.stdout.strip() == "(3, 9)"
    r = sandbox.run("match 1:\n    case 1: print('new')", language="python", version="3.9")       # 3.10+ syntax
    assert "SyntaxError" in r.stderr


def test_java_uses_the_students_own_class_name():
    need("java", "21")
    code = "public class Cart { public static void main(String[] a) { System.out.println(\"cart\"); } }"
    assert sandbox.run(code, language="java", version="21").stdout.strip() == "cart"


# ------------------------------------------------------------------ the walls

NET = {"python": "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), 2); print('CONNECTED')\nexcept OSError as e:\n    print('blocked')",
       "javascript": "require('net').connect(53, '1.1.1.1').on('connect', () => console.log('CONNECTED')).on('error', () => console.log('blocked'));",
       "java": "public class Main { public static void main(String[] a) { try { new java.net.Socket().connect(new java.net.InetSocketAddress(\"1.1.1.1\", 53), 2000); System.out.println(\"CONNECTED\"); } catch (Exception e) { System.out.println(\"blocked\"); } } }",
       "cpp": "#include <sys/socket.h>\n#include <netinet/in.h>\n#include <arpa/inet.h>\n#include <cstdio>\nint main() { int s = socket(AF_INET, SOCK_STREAM, 0); sockaddr_in a{}; a.sin_family = AF_INET; a.sin_port = htons(53); inet_pton(AF_INET, \"1.1.1.1\", &a.sin_addr); std::puts(connect(s, (sockaddr*)&a, sizeof a) == 0 ? \"CONNECTED\" : \"blocked\"); }"}


@pytest.mark.parametrize("language,version", [rt(r) for r in RUNTIMES if r != ("python", "3.9")])
def test_a_program_cannot_reach_the_network_in_any_language(language, version):
    need(language, version)
    r = sandbox.run(NET[language], language=language, version=version, timeout=30)
    assert "CONNECTED" not in r.stdout and "blocked" in r.stdout, r


@pytest.mark.parametrize("language,version", [rt(r) for r in RUNTIMES if r != ("python", "3.9")])
def test_a_program_cannot_write_outside_its_scratch_area(language, version):
    need(language, version)
    code = {"python": "try:\n    open('/etc/pwned', 'w'); print('WROTE')\nexcept OSError:\n    print('refused')",
            "javascript": "try { require('fs').writeFileSync('/etc/pwned', 'x'); console.log('WROTE') } catch (e) { console.log('refused') }",
            "java": "public class Main { public static void main(String[] a) { try { new java.io.FileWriter(\"/etc/pwned\").close(); System.out.println(\"WROTE\"); } catch (Exception e) { System.out.println(\"refused\"); } } }",
            "cpp": "#include <cstdio>\nint main() { std::puts(std::fopen(\"/etc/pwned\", \"w\") ? \"WROTE\" : \"refused\"); }"}[language]
    r = sandbox.run(code, language=language, version=version, timeout=30)
    assert "WROTE" not in r.stdout and "refused" in r.stdout, r


def test_a_program_sees_nothing_of_the_host_and_none_of_our_working_variables():
    """It prints its ENTIRE environment and its filesystem: no host secret, no host path, and none of the
    sandbox's own variables (the hidden test inputs, the framing token, the script) lying where it can read them."""
    import os
    need("python", "3.12")
    code = ("import os\n"
            "print('ENV', sorted(os.environ.items()))\n"
            "print('FILES', [p for p in ('/agentic-slice-kit', '/c', '/mnt/c', '/run.db', '/.env', '/work/run.db') if os.path.exists(p)])\n"
            "print('USER', os.getuid())")
    out = sandbox.run(code, language="python", version="3.12", stdin="HIDDEN-INPUT").stdout
    host_secrets = [v for k, v in os.environ.items() if len(v) >= 8 and any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
    assert not any(secret in out for secret in host_secrets)                        # nothing from the host's own environment
    assert "FILES []" in out and "USER 65534" in out
    for ours in ("IN_0", "SRC_B64", "SCRIPT_B64", "TOKEN", "COMPILE", "UNSET", "HIDDEN-INPUT"):
        assert ours not in out, ours


def test_source_and_input_are_data_and_never_run_as_commands():
    need("python", "3.12")
    nasty = "$(echo PWNED1) `echo PWNED2` '; echo PWNED3; # \" && echo PWNED4"
    r = sandbox.run(f"import sys\nprint({nasty!r})\nprint(sys.stdin.read().strip())", language="python", version="3.12", stdin=nasty)
    lines = r.stdout.strip().splitlines()
    assert lines == [nasty, nasty]                                                    # printed literally, twice, never executed


def test_a_fork_bomb_and_a_memory_bomb_are_contained():
    need("python", "3.12")
    t = time.time()
    r = sandbox.run("import os\nwhile True:\n    os.fork()", language="python", version="3.12", timeout=20)
    assert time.time() - t < 25                                                       # returned: the pids limit held, the host is fine
    r = sandbox.run("x = bytearray(2 * 1024 ** 3)\nprint('ALLOCATED')", language="python", version="3.12", timeout=20)
    assert "ALLOCATED" not in r.stdout and r.exit_code != 0


def test_huge_output_is_cut_short_not_returned_whole():
    need("python", "3.12")
    r = sandbox.run("import sys\nsys.stdout.write('x' * 20_000_000)", language="python", version="3.12", timeout=30)
    assert 0 < len(r.stdout) <= sandbox.MAX_OUT


def test_a_runtime_that_is_not_installed_says_how_to_get_it_and_is_not_the_students_fault(monkeypatch):
    if sandbox.installed() is None:
        pytest.skip("Docker is not running")            # with no Docker at all the message is a different one
    fake =dataclasses.replace(languages.LANGUAGES["python"], image="tutor-no-such-runtime:{v}")
    monkeypatch.setitem(languages.LANGUAGES, "python", fake)
    ok, why = sandbox.available("python", "3.12", force=True)
    assert not ok and "docker pull tutor-no-such-runtime:3.12" in why
    r = sandbox.run("print(1)", language="python", version="3.12")
    assert r.exit_code == 125 and "docker pull" in r.stderr                            # "the sandbox failed", not "your code failed"
    with pytest.raises(coach.SandboxUnavailable):
        coach.grade_program(TASK, "x", sandbox.run, "python", "3.12", sandbox.run_tests)
    sandbox._verdict.clear()

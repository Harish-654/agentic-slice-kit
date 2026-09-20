"""Turns a run of the student's code into evidence and a hint. Pure functions,
no model: the error a student hits already names the idea they are missing.
That keeps the coach instant and free, and every decision testable.

The same idea gets the same misconception tag in every language ("index-out-of-range" is a Python IndexError, a Java
ArrayIndexOutOfBoundsException and a C++ std::out_of_range), so the learner model reasons about ideas, not syntax."""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from slice.budget import BudgetExceeded
from slice.llm import ModelError

from . import learner
from .sandbox import Result

# Python: the exception's class name -> (misconception tag, the nudge). A nudge points; it never gives the fix.
ERRORS = {
    "SyntaxError": ("syntax-error", "Python could not read a line. Check brackets, quotes and colons near the line it names."),
    "IndentationError": ("bad-indentation", "Indentation is part of Python's grammar. Look at which lines belong inside which block."),
    "NameError": ("undefined-name", "A name is used before it exists. Where did you create it, and is it spelled the same here?"),
    "UnboundLocalError": ("local-before-assignment", "Assigning to a name inside a function makes it local to that function, for the whole function."),
    "TypeError": ("type-mismatch", "An operation got a type it does not support. Print the types of the values involved."),
    "IndexError": ("index-out-of-range", "You asked for a position the list does not have. Indexes start at 0; what is the last valid one?"),
    "KeyError": ("missing-key", "That key is not in the dictionary. Print the keys, or use `in` to check first."),
    "AttributeError": ("wrong-attribute", "That object has no such attribute. What type is it really? Try `type()` and `dir()`."),
    "ValueError": ("bad-value", "The type was right but the value was not acceptable. What does the function expect?"),
    "ZeroDivisionError": ("divide-by-zero", "Something you divide by can be 0. Which value, and when?"),
    "RecursionError": ("runaway-recursion", "A function keeps calling itself. What makes it stop?"),
}

_SYNTAX = "The compiler could not read a line. Check brackets, quotes and semicolons near the line it names."
_UNDEFINED = "A name is used before it exists. Where did you declare it, and is it spelled the same here?"
_TYPES = "An operation got a type it does not support. What type is each value really?"
_INDEX = "You asked for a position that does not exist. Positions start at 0; what is the last valid one?"
_ZERO = "Something you divide by can be 0. Which value, and when?"
_DEEP = "A function keeps calling itself. What makes it stop?"

# The other languages: ordered (pattern, tag, nudge); the first that matches the error text wins, so the specific
# messages come before the general ones. Patterns are taken from real compiler and runtime messages.
PATTERNS: dict[str, list[tuple[str, str, str]]] = {
    "javascript": [
        (r"Maximum call stack size exceeded", "runaway-recursion", _DEEP),
        (r"Cannot read propert(?:y|ies) of (?:undefined|null)", "null-access",
         "You used something that is undefined or null as if it were an object. Where does it get its value?"),
        (r"Assignment to constant variable", "const-reassigned", "A `const` cannot be given a new value. Should it be `let`?"),
        (r"ReferenceError: .* is not defined", "undefined-name", _UNDEFINED),
        (r"TypeError: .* is not a function", "type-mismatch", "You called something that is not a function. What is it really?"),
        (r"TypeError|is not iterable", "type-mismatch", _TYPES),
        (r"Cannot find module", "import-unavailable", "That module does not exist here. Only the standard library is available."),
        (r"RangeError", "bad-value", "A value was outside what the function accepts."),
        (r"SyntaxError", "syntax-error", _SYNTAX),
    ],
    "java": [
        (r"StackOverflowError", "runaway-recursion", _DEEP),
        (r"NullPointerException", "null-dereference", "You used a reference that points to nothing (null). Where does it get its value?"),
        (r"IndexOutOfBoundsException", "index-out-of-range", _INDEX),
        (r"ArithmeticException", "divide-by-zero", _ZERO),
        (r"NumberFormatException", "bad-value", "That text cannot be turned into a number. What does it really contain?"),
        (r"ClassCastException", "type-mismatch", _TYPES),
        (r"InputMismatchException|NoSuchElementException", "bad-input",
         "The program read input that was not what it expected, or read past the end. What is the input's shape?"),
        (r"OutOfMemoryError", "out-of-memory", "The program used more memory than it is allowed."),
        (r"cannot find symbol", "undefined-name", _UNDEFINED),
        (r"missing return statement", "missing-return", "Some path through the method reaches the end without returning a value."),
        (r"might not have been initialized", "uninitialized-variable", "A variable is read before it is given a value on every path."),
        (r"unreported exception", "unhandled-checked-exception", "A method can throw a checked exception, so it must be caught or declared."),
        (r"is public, should be declared in a file named", "class-file-name", "A public class must have the same name as its file. Rename it, or drop `public`."),
        (r"non-static .* cannot be referenced from a static context", "static-context", "A static method cannot use instance members directly. Which object do they belong to?"),
        (r"incompatible types|bad operand types|cannot be applied to|cannot be dereferenced", "type-mismatch", _TYPES),
        (r"error: .*expected|illegal start of|reached end of file while parsing|not a statement|unclosed string literal"
         r"|class, interface, enum, or record expected", "syntax-error", _SYNTAX),
    ],
    "cpp": [
        (r"std::out_of_range", "index-out-of-range", _INDEX),
        (r"std::bad_alloc", "out-of-memory", "The program tried to use more memory than it is allowed."),
        (r"terminate called after throwing", "uncaught-exception", "An exception was thrown and nothing caught it. Where could it come from?"),
        (r"Floating point exception", "divide-by-zero", _ZERO),
        (r"was not declared in this scope|does not name a type|has not been declared", "undefined-name", _UNDEFINED),
        (r"undefined reference to", "undefined-reference", "Something was declared and used but never defined. Is the function's body written?"),
        (r"no match for|invalid conversion|cannot convert|invalid operands|invalid types", "type-mismatch", _TYPES),
        (r"error: expected .* (?:before|at end of)|error: expected", "syntax-error", _SYNTAX),
    ],
}
# C++ (and anything native) that dies without a message: the shell reports the signal as 128 + its number.
SIGNALS = {139: ("invalid-memory-access", "The program touched memory it does not own, often an index past the end or a null pointer. What could be out of range?"),
           136: ("divide-by-zero", _ZERO),
           134: ("uncaught-exception", "The program aborted, often from an exception nothing caught.")}

WRONG_OUTPUT = ("wrong-output", "It ran, but the output is not what was expected. Trace one input by hand and compare.")
COMPILE_FAILED = ("compile-error", "The program did not compile. Read the first error message: it names a line.")
TIMEOUT_HINT = "It ran too long. Is there a loop or recursion that never reaches its end?"
_DOCKER_TROUBLE = 125            # docker's own exit codes: the container failed, not the student's code


class SandboxUnavailable(RuntimeError):
    """The sandbox itself failed while grading. That is not the student's mistake and must not count as one."""


def error_name(res: Result) -> str | None:
    """The Python exception class reported: the last stderr line reads `Name: message`."""
    lines = [ln for ln in res.stderr.strip().splitlines() if ln.strip()]
    head = lines[-1].split(":")[0].strip() if lines else ""
    return head if head in ERRORS else None


def classify(res: Result, language: str = "python") -> tuple[str, str] | None:
    """(misconception tag, nudge) for what went wrong in this run, or None if nothing readable went wrong."""
    if language == "python":
        name = error_name(res)
        return ERRORS[name] if name else None
    if res.timed_out:
        return None
    for pattern, tag, nudge in PATTERNS.get(language, []):
        if re.search(pattern, res.stderr):
            return tag, nudge
    if res.compile_failed:
        return COMPILE_FAILED
    return SIGNALS.get(res.exit_code)


def evidence(res: Result, expected: str | None = None, language: str = "python") -> tuple[bool | None, str | None]:
    """(correct, misconception) for the learner model, or (None, None) when the run
    proves nothing. Code that merely ran without error is NOT evidence of
    understanding, so it only counts when the student gave an expected output."""
    if res.timed_out:
        return None, None
    found = classify(res, language)
    if found:
        return False, found[0]
    if res.exit_code != 0:              # sys.exit(1), a killed process: nothing we can read
        return None, None
    if expected is not None:
        ok = res.stdout.strip() == expected.strip()
        return ok, None if ok else WRONG_OUTPUT[0]
    return None, None


def hint(res: Result, correct: bool | None, language: str = "python") -> str | None:
    if res.timed_out:
        return TIMEOUT_HINT
    found = classify(res, language)
    if found:
        return found[1]
    return WRONG_OUTPUT[1] if correct is False else None
    # ponytail: a table of nudges. A model-written Socratic hint is the upgrade, one small call.


# ------------------------------------------------------------ program questions

@dataclass
class Graded:
    correct: bool
    misconception: str | None
    feedback: str


def _harness(code: str, tests: list[dict], token: str) -> str:
    """Python function-style questions: the student's code, then one guarded call per hidden test. Each result
    line carries a per-run token, so code that just prints "pass" cannot fake one."""
    out = [code, "", ""]
    for i, t in enumerate(tests):
        out += ["try:", f"    _r = repr({t['call']})",
                "except BaseException as _e:", "    _r = 'ERR ' + type(_e).__name__",
                f"print({f'@@{token}:{i}@@'!r}, _r)"]
    return "\n".join(out)


def _trouble(res: Result) -> None:
    if res.exit_code is not None and res.exit_code >= _DOCKER_TROUBLE and not res.compile_failed:
        raise SandboxUnavailable(res.stderr.strip()[:200] or "The sandbox failed.")


def _grade_function(task: dict, code: str, run, language: str, version: str | None) -> Graded:
    """Python only: call the student's function with each hidden input and compare `repr()`."""
    token = secrets.token_hex(6)
    tests = task["tests"]
    res = run(_harness(code, tests, token)) if (language, version) == ("python", None) \
        else run(_harness(code, tests, token), language=language, version=version)
    _trouble(res)
    if res.timed_out:
        return Graded(False, "runaway-loop", TIMEOUT_HINT)
    seen = {}
    for line in res.stdout.splitlines():
        if line.startswith("@@" + token + ":"):
            head, _, val = line.partition("@@ ")
            seen[int(head.rsplit(":", 1)[1])] = val.strip()
    if not seen:                                    # it never got as far as the checks
        found = classify(res, language)
        return (Graded(False, found[0], found[1]) if found
                else Graded(False, "did-not-run", "Your program stopped before the checks could run."))
    for i, t in enumerate(tests):
        if seen.get(i) != t["expected"].strip():
            crashed = (seen.get(i) or "").startswith("ERR ")
            why = (seen[i] + " on one of the checks. " if crashed else "")
            return Graded(False, t["belief"],
                          f"Not quite: {why}a check for the idea “{t['belief']}” does not pass. "
                          "Trace your code by hand on a small input.")
    return Graded(True, None, "Every check passed.")


def _same(a: str, b: str) -> bool:
    """Output equal, ignoring trailing spaces on a line and blank lines at the end."""
    norm = lambda s: "\n".join(ln.rstrip() for ln in s.strip().splitlines())    # noqa: E731
    return norm(a) == norm(b)


def _grade_stdio(task: dict, code: str, judge, language: str, version: str | None) -> Graded:
    """Any language: the program reads a hidden input on stdin and must print the expected output."""
    tests = task["tests"]
    j = judge(code, [t.get("stdin", "") for t in tests], language=language, version=version)
    if j.broken:
        raise SandboxUnavailable(j.why)
    if j.timed_out:
        return Graded(False, "runaway-loop", TIMEOUT_HINT)
    if j.compile_failed:
        res = Result("", j.compile_output, 1, compile_failed=True)
        tag, nudge = classify(res, language) or COMPILE_FAILED
        first = next((ln for ln in j.compile_output.splitlines() if "error" in ln.lower()), "")
        return Graded(False, tag, f"It did not compile. {nudge}" + (f"\n{first.strip()[:200]}" if first else ""))
    for t, r in zip(tests, j.runs):
        if r.timed_out:
            return Graded(False, "runaway-loop", TIMEOUT_HINT)
        if r.exit_code not in (0, None):
            found = classify(r, language)
            return Graded(False, found[0] if found else t["belief"],
                          "It crashed on one of the checks. " + (found[1] if found else "Read the error it printed."))
        if not _same(r.stdout, t["expected"]):
            return Graded(False, t["belief"],
                          f"Not quite: a check for the idea “{t['belief']}” does not pass. "
                          "Compare what your program prints with what the question asks for, on a small input.")
    return Graded(True, None, "Every check passed.")


def grade_program(task: dict, code: str, run, language: str = "python", version: str | None = None,
                  judge=None) -> Graded:
    """Run the submission against the task's hidden tests. No model call: the first failing test names the wrong
    idea it exposes. A crash names the error instead. Raises SandboxUnavailable if the sandbox itself failed."""
    if task.get("style", "function") == "stdio":
        return _grade_stdio(task, code, judge, language, version)
    return _grade_function(task, code, run, language, version)


def task_problem(task: dict, run, language: str = "python", version: str | None = None, judge=None) -> str | None:
    """Why a program question is unfair, or None. The model wrote the hidden tests AND a model solution, so the
    solution must pass its own tests; if it does not, a correct student answer would be marked wrong. Run before a
    student ever sees the question. An unavailable sandbox means "unchecked", not "unfair"."""
    if language != "python" and task.get("style", "function") != "stdio":
        return 'a program question here must read input and print output ("style": "stdio")'
    try:
        g = grade_program(task, task["model_solution"], run, language, version, judge)
    except SandboxUnavailable:
        return None
    return None if g.correct else g.feedback.splitlines()[0][:200]


# ------------------------------------------------------------------ assist

_PROMPTS = Path(__file__).parent / "prompts"
MAX_CHIPS, MAX_LINES, MAX_CHARS = 3, 3, 200


def help_level(model, concept: str) -> str:
    """The twin's call on how much to help: assist a student who knows the topic well,
    hold back for one who does not, so help never stands in for learning."""
    return "assist" if learner.effective_mastery(model, concept) >= learner.MASTERY else "withhold"


class Suggestions(BaseModel):
    suggestions: list[str] = []


def clean(items: list[str], code: str) -> list[str]:
    """The model's chips, made safe to show: no blanks, no repeats, no wall of text, and
    nothing the code already ends with."""
    out: list[str] = []
    for raw in items:
        item = "\n".join(raw.rstrip().splitlines()[:MAX_LINES])[:MAX_CHARS]
        if item.strip() and item not in out and not code.rstrip().endswith(item.strip()):
            out.append(item)
    return out[:MAX_CHIPS]


def suggest(call, settings, budget, topic: str, level: str, code: str, language_line: str = "") -> list[str]:
    """Up to three ways the student might continue. Any failure is an empty list: a missing
    chip must never break the editor."""
    system = (_PROMPTS / "suggest.md").read_text(encoding="utf-8")
    user = f"TOPIC: {topic}\nLEVEL: {level}\n" + (language_line + "\n" if language_line else "") + f"CODE SO FAR:\n{code}"
    try:
        got = call(settings=settings, budget=budget, schema=Suggestions, step="suggest",
                   reasoning=False,
                   messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    except (ModelError, BudgetExceeded):
        return []
    return clean(got.suggestions, code)


# ------------------------------------------------- code a model wrote for a question

_ABOUT_AN_ERROR = re.compile(r"error|exception|raise|traceback|crash|fail|compile", re.I)
_SANDBOX_TROUBLE = _DOCKER_TROUBLE


def question_code_problem(quiz: dict, run, language: str = "python", version: str | None = None) -> str | None:
    """Why the code shown with a question cannot be trusted, or None if it can (or there is
    none). A small model sometimes writes code that does not run, so the student is asked about
    something that cannot happen. The code must compile and run cleanly, unless an option is
    itself about an error (then the code is meant to fail and only has to compile). `run` is the
    sandbox: model-written code never executes anywhere else."""
    code = (quiz.get("code") or "").strip()
    if not code:
        return None
    if language == "python":
        try:
            compile(code, "<question>", "exec")             # compiles, never executes
        except (SyntaxError, ValueError, RecursionError) as e:
            return f"{type(e).__name__}: {getattr(e, 'msg', e)} (line {getattr(e, 'lineno', '?')})"
        res = run(code) if version is None else run(code, language=language, version=version)
    else:
        res = run(code, language=language, version=version)
    if res.timed_out:
        return "it ran for too long"
    if res.compile_failed:
        if any(_ABOUT_AN_ERROR.search(o["text"]) for o in quiz["options"]):
            return None
        first = next((ln for ln in res.stderr.splitlines() if "error" in ln.lower()), res.stderr.strip()[:200])
        return f"it did not compile: {first.strip()}"[:200]
    if not res.exit_code or res.exit_code >= _SANDBOX_TROUBLE:
        return None
    if any(_ABOUT_AN_ERROR.search(o["text"]) for o in quiz["options"]):
        return None
    last = [ln for ln in res.stderr.strip().splitlines() if ln.strip()]
    return (last[-1] if last else f"it exited with code {res.exit_code}")[:200]

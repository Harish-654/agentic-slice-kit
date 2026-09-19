"""Turns a run of the student's code into evidence and a hint. Pure functions,
no model: the Python error a student hits already names the idea they are missing.
That keeps the coach instant and free, and every decision testable."""
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

# error class -> (misconception tag, the nudge). A nudge points; it never gives the fix.
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
WRONG_OUTPUT = ("wrong-output", "It ran, but the output is not what was expected. Trace one input by hand and compare.")
TIMEOUT_HINT = "It ran too long. Is there a loop or recursion that never reaches its end?"


def error_name(res: Result) -> str | None:
    """The exception class Python reported: the last stderr line reads `Name: message`."""
    lines = [ln for ln in res.stderr.strip().splitlines() if ln.strip()]
    head = lines[-1].split(":")[0].strip() if lines else ""
    return head if head in ERRORS else None


def evidence(res: Result, expected: str | None = None) -> tuple[bool | None, str | None]:
    """(correct, misconception) for the learner model, or (None, None) when the run
    proves nothing. Code that merely ran without error is NOT evidence of
    understanding, so it only counts when the student gave an expected output."""
    if res.timed_out:
        return None, None
    name = error_name(res)
    if name:
        return False, ERRORS[name][0]
    if res.exit_code != 0:              # sys.exit(1), a killed process: nothing we can read
        return None, None
    if expected is not None:
        ok = res.stdout.strip() == expected.strip()
        return ok, None if ok else WRONG_OUTPUT[0]
    return None, None


def hint(res: Result, correct: bool | None) -> str | None:
    if res.timed_out:
        return TIMEOUT_HINT
    name = error_name(res)
    if name:
        return ERRORS[name][1]
    return WRONG_OUTPUT[1] if correct is False else None
    # ponytail: a table of nudges. A model-written Socratic hint is the upgrade, one small call.


# ------------------------------------------------------------ program questions

@dataclass
class Graded:
    correct: bool
    misconception: str | None
    feedback: str


def _harness(code: str, tests: list[dict], token: str) -> str:
    """The student's code, then one guarded call per hidden test. Each result line carries a
    per-run token, so code that just prints "pass" cannot fake one."""
    out = [code, "", ""]
    for i, t in enumerate(tests):
        out += ["try:", f"    _r = repr({t['call']})",
                "except BaseException as _e:", "    _r = 'ERR ' + type(_e).__name__",
                f"print({f'@@{token}:{i}@@'!r}, _r)"]
    return "\n".join(out)


def grade_program(task: dict, code: str, run) -> Graded:
    """Run the submission against the task's hidden tests. No model call: the first failing
    test names the wrong idea it exposes. A crash names the error class instead."""
    token = secrets.token_hex(6)
    tests = task["tests"]
    res = run(_harness(code, tests, token))
    if res.timed_out:
        return Graded(False, "runaway-loop", TIMEOUT_HINT)
    seen = {}
    for line in res.stdout.splitlines():
        if line.startswith("@@" + token + ":"):
            head, _, val = line.partition("@@ ")
            seen[int(head.rsplit(":", 1)[1])] = val.strip()
    if not seen:                                    # it never got as far as the checks
        name = error_name(res)
        return (Graded(False, ERRORS[name][0], ERRORS[name][1]) if name
                else Graded(False, "did-not-run", "Your program stopped before the checks could run."))
    for i, t in enumerate(tests):
        if seen.get(i) != t["expected"].strip():
            crashed = (seen.get(i) or "").startswith("ERR ")
            why = (seen[i] + " on one of the checks. " if crashed else "")
            return Graded(False, t["belief"],
                          f"Not quite: {why}a check for the idea “{t['belief']}” does not pass. "
                          "Trace your code by hand on a small input.")
    return Graded(True, None, "Every check passed.")


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


def suggest(call, settings, budget, topic: str, level: str, code: str) -> list[str]:
    """Up to three ways the student might continue. Any failure is an empty list: a missing
    chip must never break the editor."""
    system = (_PROMPTS / "suggest.md").read_text(encoding="utf-8")
    user = f"TOPIC: {topic}\nLEVEL: {level}\nCODE SO FAR:\n{code}"
    try:
        got = call(settings=settings, budget=budget, schema=Suggestions, step="suggest",
                   reasoning=False,
                   messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    except (ModelError, BudgetExceeded):
        return []
    return clean(got.suggestions, code)


# ------------------------------------------------- code a model wrote for a question

_ABOUT_AN_ERROR = re.compile(r"error|exception|raise|traceback|crash|fail", re.I)
_SANDBOX_TROUBLE = 125          # docker's own exit codes: the container failed, not the code


def question_code_problem(quiz: dict, run) -> str | None:
    """Why the code shown with a question cannot be trusted, or None if it can (or there is
    none). A small model sometimes writes code that does not run, so the student is asked about
    something that cannot happen. The code must compile and run cleanly, unless an option is
    itself about an error (then the code is meant to fail and only has to compile). `run` is the
    sandbox: model-written code never executes anywhere else."""
    code = (quiz.get("code") or "").strip()
    if not code:
        return None
    try:
        compile(code, "<question>", "exec")             # compiles, never executes
    except (SyntaxError, ValueError, RecursionError) as e:
        return f"{type(e).__name__}: {getattr(e, 'msg', e)} (line {getattr(e, 'lineno', '?')})"
    res = run(code)
    if res.timed_out:
        return "it ran for too long"
    if not res.exit_code or res.exit_code >= _SANDBOX_TROUBLE:
        return None
    if any(_ABOUT_AN_ERROR.search(o["text"]) for o in quiz["options"]):
        return None
    last = [ln for ln in res.stderr.strip().splitlines() if ln.strip()]
    return (last[-1] if last else f"it exited with code {res.exit_code}")[:200]

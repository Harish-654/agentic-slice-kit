"""Runs a student's code in a throwaway Docker container, or refuses to.

Running a stranger's code is a security decision, so this fails closed: `available()` proves, with a real container
of the SAME image, that the code has no network and no writable disk, and that a program in that language really
compiles and runs. Nothing runs unless that proof passes. Nothing from the host is mounted or passed in: no .env,
no run.db, no environment.

One container per request, for any language in languages.py: the program is compiled ONCE (if the language needs it)
and then run once per input, so grading three tests costs one container start, not three.

How student text stays out of the shell: the container's script is fixed text we build, plus a random per-run token.
The student's source and every test input reach it as base64 in a temporary env file (never on the command line, never
mounted), are decoded to files inside the container, and are only ever read as data. The program's output comes back
as base64 between markers carrying that token, so it can neither break the framing nor fake a result.
"""
from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field

from . import languages
from .languages import Language

MAX_OUT = 4000                      # characters kept of stdout and of stderr
MAX_STDIN = 2000                    # characters of input per run
MAX_RUNS = 8                        # inputs per container
RUN_SECONDS = 5                     # each run of the program, on top of its compile
_HOST_ENV = ("PATH", "SYSTEMROOT", "USERPROFILE", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT")
_gate = threading.Semaphore(2)      # ponytail: two runs at a time server-wide, per-student limits if shared
_DOCKER_TROUBLE = 125               # docker's own exit codes: the container failed, not the student's code


@dataclass
class Result:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False
    compile_failed: bool = False    # the program never started: `stderr` is the compiler's message


@dataclass
class Judged:
    """One program, compiled once and run against several inputs."""
    runs: list[Result] = field(default_factory=list)
    compile_failed: bool = False
    compile_output: str = ""
    broken: bool = False            # the sandbox itself failed (no Docker, no image): nothing was judged
    why: str = ""
    timed_out: bool = False         # the whole container hit its time limit before it finished


# The script the container runs. Fixed text: no student text is ever put into it.
_SCRIPT = r"""
cd /work || exit 70
printf '%s' "$SRC_B64" | base64 -d > "$SRC_FILE"
if [ -n "$COMPILE" ]; then
  sh -c "$COMPILE" > compile.out 2>&1 < /dev/null
  c=$?
  printf '@@%s COMPILE %s@@\n' "$TOKEN" "$c"
  head -c 4000 compile.out | base64 -w0; printf '\n'
  [ "$c" -eq 0 ] || exit 0
fi
i=0
while [ "$i" -lt "$N" ]; do
  eval "printf '%s' \"\$IN_$i\"" | base64 -d > input.txt
  timeout "$RUN_SECONDS" env $UNSET sh -c "$RUN" < input.txt > out.txt 2> err.txt
  c=$?
  printf '@@%s RUN %s %s@@\n' "$TOKEN" "$i" "$c"
  head -c 4000 out.txt | base64 -w0; printf '\n'
  head -c 4000 err.txt | base64 -w0; printf '\n'
  i=$((i+1))
done
"""

# Checks that need no program at all, so they hold for every language: only the loopback network interface, a
# read-only root, and not root.
_CHECKS = ('[ "$(id -u)" != "0" ] || echo root; '
           'ls /sys/class/net 2>/dev/null | grep -qv "^lo$" && echo network; '
           'touch /probe 2>/dev/null && echo disk; '
           'echo ok')


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _unb64(text: str) -> str:
    try:
        return base64.b64decode(text.strip()).decode("utf-8", errors="replace")[:MAX_OUT]
    except Exception:
        return ""


def script_env(lang: Language, version: str, code: str, stdins: list[str], token: str) -> dict[str, str]:
    """Every value the container's script needs, all of it data. The only student-derived values are base64."""
    cmd = languages.commands(lang, version, code)
    env = {"SCRIPT_B64": _b64(_SCRIPT), "SRC_B64": _b64(code), "SRC_FILE": cmd["file"], "COMPILE": cmd["compile"],
           "RUN": cmd["run"], "N": str(len(stdins)), "TOKEN": token, "RUN_SECONDS": str(RUN_SECONDS), "HOME": "/tmp",
           "PYTHONDONTWRITEBYTECODE": "1"}
    for i, text in enumerate(stdins):
        env[f"IN_{i}"] = _b64(text[:MAX_STDIN])
    # The student's program is started with all of our working variables removed, so a program that prints its own
    # environment does not find the hidden inputs (or the framing token) lying in it. (A process of the same user can
    # still read /proc/1/environ: this stops casual peeking, not a determined cheater, who only cheats themselves.)
    hidden = [k for k in env if k.startswith("IN_") or k in ("SRC_B64", "SCRIPT_B64", "TOKEN", "COMPILE", "RUN", "N")]
    env["UNSET"] = " ".join(f"-u {k}" for k in [*hidden, "UNSET"])              # including the list itself
    return env


def docker_args(lang: Language, version: str, name: str, env_file: str | None, command: list[str]) -> list[str]:
    """`docker run` with every wall up, the same for every language: no network, a read-only root, no capabilities,
    no privilege gain, a non-root user, memory, CPU and process limits, and no pulling of images at run time.
    Compiled languages get an executable scratch area in memory; nothing else in the container can execute."""
    scratch = "size=32m,mode=1777,nosuid" + (",exec" if lang.compiled else "")
    return ["run", "--rm", "--pull", "never", "--name", name, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--tmpfs", "/tmp:size=16m,mode=1777,noexec,nosuid", "--tmpfs", f"/work:{scratch}", "-w", "/work",
            "--memory", lang.memory, "--memory-swap", lang.memory, "--cpus", lang.cpus, "--pids-limit", str(lang.pids),
            "--user", "65534:65534", *(["--env-file", env_file] if env_file else []),
            lang.image_for(version), *command]


def _docker(*args: str, timeout: float) -> subprocess.CompletedProcess:
    env = {k: os.environ[k] for k in _HOST_ENV if k in os.environ}      # never the API key
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, env=env)


def _missing(stderr: str, lang: Language, version: str) -> str | None:
    if "No such image" in stderr or "Unable to find image" in stderr:
        return f"The {lang.label(version)} runtime is not installed. Run: docker pull {lang.image_for(version)}"
    return None


def _parse(stdout: str, token: str, n: int) -> Judged:
    """Read the marked, base64 output back into results. Anything not in a marked block is ignored."""
    lines = stdout.splitlines()
    marker = f"@@{token} "
    j = Judged()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(marker) and ln.endswith("@@"):
            parts = ln[len(marker):-2].split()
            if parts[0] == "COMPILE" and len(parts) == 2:
                out = _unb64(lines[i + 1]) if i + 1 < len(lines) else ""
                if parts[1] != "0":
                    j.compile_failed, j.compile_output = True, out
                i += 2
                continue
            if parts[0] == "RUN" and len(parts) == 3 and parts[1].isdigit():
                code = int(parts[2]) if parts[2].lstrip("-").isdigit() else None
                out = _unb64(lines[i + 1]) if i + 1 < len(lines) else ""
                err = _unb64(lines[i + 2]) if i + 2 < len(lines) else ""
                j.runs.append(Result(out, err, code, timed_out=(code == 124)))
                i += 3
                continue
        i += 1
    return j


def run_tests(code: str, stdins: list[str], *, language: str | None = None, version: str | None = None,
              timeout: float | None = None) -> Judged:
    """Compile `code` once and run it once per entry of `stdins`. Never raises for a student's mistake."""
    lang, version = languages.resolve(language, version)
    stdins = list(stdins)[:MAX_RUNS] or [""]
    token = uuid.uuid4().hex
    name = f"tutor-{uuid.uuid4().hex[:12]}"
    fd, path = tempfile.mkstemp(suffix=".env", prefix="tutor-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(f"{k}={v}\n" for k, v in script_env(lang, version, code, stdins, token).items()))
        command = ["sh", "-c", 'printf %s "$SCRIPT_B64" | base64 -d > /tmp/run.sh && exec sh /tmp/run.sh']
        with _gate:
            try:
                p = _docker(*docker_args(lang, version, name, path, command), timeout=timeout or lang.seconds)
            except subprocess.TimeoutExpired:
                try:
                    _docker("rm", "-f", name, timeout=15)     # the CLI stopped waiting; the container did not
                except Exception:
                    pass
                return Judged(timed_out=True, runs=[Result("", "", None, timed_out=True)] * len(stdins))
            except FileNotFoundError:
                return Judged(broken=True, why="Docker is not installed.")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    judged = _parse(p.stdout, token, len(stdins))
    if not judged.runs and not judged.compile_failed:
        why = _missing(p.stderr, lang, version) or (p.stderr.strip().splitlines() or ["The sandbox did not answer."])[-1][:200]
        return Judged(broken=True, why=why)
    return judged


def run(code: str, timeout: float | None = None, *, language: str | None = None, version: str | None = None,
        stdin: str = "") -> Result:
    """Run a program once. Docker trouble comes back as exit code 125, which callers treat as "the sandbox failed,
    not the student's code"."""
    judged = run_tests(code, [stdin], language=language, version=version, timeout=timeout)
    if judged.broken:
        return Result("", judged.why, _DOCKER_TROUBLE)
    if judged.timed_out:
        return Result("", "", None, timed_out=True)
    if judged.compile_failed:
        return Result("", judged.compile_output, 1, compile_failed=True)
    return judged.runs[0] if judged.runs else Result("", "", _DOCKER_TROUBLE)


# ------------------------------------------------------------------ is it safe to run code in this language?

_verdict: dict[tuple[str, str], tuple[bool, str, float]] = {}
_RECHECK = 30.0                     # a failed check is retried after this many seconds (Docker may have started)


def _check(lang: Language, version: str) -> tuple[bool, str]:
    try:
        name = f"tutor-{uuid.uuid4().hex[:12]}"
        p = _docker(*docker_args(lang, version, name, None, ["sh", "-c", _CHECKS]), timeout=90)
        if p.returncode != 0:
            return False, (_missing(p.stderr, lang, version)
                           or "Docker did not run the isolation check. Is Docker running?")
        seen = p.stdout.split()
        if seen != ["ok"]:
            return False, "The sandbox is not isolated (" + ", ".join(seen[:-1] or ["no answer"]) + ")."
        hello = run_tests(lang.hello, [""], language=lang.id, version=version, timeout=120)
        if hello.broken or hello.compile_failed or not hello.runs or hello.runs[0].stdout.strip() != "ok":
            return False, f"A {lang.label(version)} program would not compile and run here."
        return True, ""
    except FileNotFoundError:
        if os.environ.get("CODESPACES") == "true":      # the message a student sees, so say how to fix it
            return False, ("Docker is not available in this Codespace. Rebuild the container (Command Palette: "
                           "Codespaces: Rebuild Container) so the Docker setup in .devcontainer applies.")
        return False, "Docker is not installed."
    except subprocess.TimeoutExpired:
        return False, "The sandbox check timed out. Is Docker running?"
    except Exception as e:               # anything unexpected must also mean "no"
        return False, f"Sandbox check failed: {type(e).__name__}."


def available(language: str | None = None, version: str | None = None, force: bool = False) -> tuple[bool, str]:
    """(True, "") when code in this language and version may run here, else (False, why). Success is cached
    for the life of the process; failure is re-checked, so starting Docker or pulling an image later just works."""
    try:
        lang, version = languages.resolve(language, version)
    except languages.UnknownLanguage as e:
        return False, str(e)
    key, now = (lang.id, version), time.time()
    cached = _verdict.get(key)
    if cached and not force and (cached[0] or now - cached[2] < _RECHECK):
        return cached[0], cached[1]
    ok, why = _check(lang, version)
    _verdict[key] = (ok, why, now)
    return ok, why


def installed() -> set[str] | None:
    """The images Docker already has ("python:3.12-slim"), or None if Docker cannot be asked."""
    try:
        p = _docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}}", timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return set(p.stdout.split()) if p.returncode == 0 else None


def images() -> list[tuple[str, str, str]]:
    """(language, version, image) for everything we can run, so an admin can pull them."""
    return [(l.id, v, l.image_for(v)) for l in languages.LANGUAGES.values() for v in l.versions]

"""Runs a student's code in a throwaway Docker container, or refuses to.

Running a stranger's code is a security decision, so this fails closed: `available()`
proves, with a real container, that the code has no network and no writable disk,
and nothing runs unless that proof passes. Nothing from the host is mounted or
passed in (no .env, no run.db, no environment), and the code arrives on stdin.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass

IMAGE = "python:3.12-slim"          # `docker pull python:3.12-slim` once; the self-test fails closed without it
TIMEOUT = 10                        # seconds, including container start
MAX_OUT = 4000                      # characters kept of stdout and of stderr
_HOST_ENV = ("PATH", "SYSTEMROOT", "USERPROFILE", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT")
_gate = threading.Semaphore(2)      # ponytail: two runs at a time server-wide, per-student limits if shared

_ISOLATION = "--network none --read-only --cap-drop ALL --security-opt no-new-privileges"


@dataclass
class Result:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False


def _docker(*args: str, stdin: str | None = None, timeout: float = TIMEOUT) -> subprocess.CompletedProcess:
    env = {k: os.environ[k] for k in _HOST_ENV if k in os.environ}      # never the API key
    return subprocess.run(["docker", *args], input=stdin, capture_output=True, text=True,
                          timeout=timeout, env=env)


def _run_args(name: str) -> list[str]:
    return ["run", "--rm", "-i", "--name", name, *_ISOLATION.split(),
            "--tmpfs", "/tmp:size=8m,noexec", "--memory", "128m", "--memory-swap", "128m",
            "--cpus", "0.5", "--pids-limit", "64", "--user", "65534:65534",
            "-e", "PYTHONDONTWRITEBYTECODE=1", IMAGE, "python", "-I", "-"]


def run(code: str, timeout: float = TIMEOUT) -> Result:
    name = f"tutor-{uuid.uuid4().hex[:12]}"
    with _gate:
        try:
            p = _docker(*_run_args(name), stdin=code, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                _docker("rm", "-f", name, timeout=15)     # the CLI stopped waiting; the container did not
            except Exception:
                pass
            return Result("", "", None, timed_out=True)
    return Result(p.stdout[:MAX_OUT], p.stderr[:MAX_OUT], p.returncode)


# What a student's code could try if the walls were missing. Each attempt that
# WORKS prints its name; "ok" last proves the container ran the code at all.
_PROBE = """\
import socket
try:
    socket.create_connection(("1.1.1.1", 53), 2); print("network")
except OSError:
    pass
try:
    open("/probe", "w"); print("disk")
except OSError:
    pass
print("ok")
"""

_verdict: tuple[bool, str, float] | None = None
_RECHECK = 30.0                     # a failed check is retried after this many seconds (Docker may have started)


def available(force: bool = False) -> tuple[bool, str]:
    """(True, "") when code may run here, else (False, why). Success is cached for the
    life of the process; failure is re-checked, so starting Docker later just works."""
    global _verdict
    now = time.time()
    if _verdict and not force and (_verdict[0] or now - _verdict[2] < _RECHECK):
        return _verdict[0], _verdict[1]
    try:
        r = run(_PROBE, timeout=60)      # the first run may pull nothing, but a cold Docker is slow
        if r.timed_out or r.exit_code != 0:
            ok, why = False, "Docker did not run the isolation check. Is Docker running, and is the image pulled?"
        elif r.stdout.split() != ["ok"]:
            ok, why = False, "The sandbox is not isolated (" + ", ".join(r.stdout.split()[:-1]) + ")."
        else:
            ok, why = True, ""
    except FileNotFoundError:
        ok, why = False, "Docker is not installed."
    except Exception as e:               # anything unexpected must also mean "no"
        ok, why = False, f"Sandbox check failed: {type(e).__name__}."
    _verdict = (ok, why, now)
    return ok, why

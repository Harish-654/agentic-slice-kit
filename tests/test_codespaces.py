"""The code sandbox in GitHub Codespaces: the container must have Docker, must pull the runtime images in the
background, and must say what to do when Docker is missing. None of this needs Docker itself."""
import importlib.util
import json
import re
from pathlib import Path

from demo.tutor import languages, sandbox

ROOT = Path(__file__).resolve().parent.parent


def pull_script():
    spec = importlib.util.spec_from_file_location("pull_runtimes", ROOT / "scripts" / "pull_runtimes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def devcontainer():
    text = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))          # the file allows whole-line comments


def no_docker(monkeypatch):
    def gone(*args, **kwargs):
        raise FileNotFoundError("docker")
    monkeypatch.setattr(sandbox, "_docker", gone)


# ------------------------------------------------------------------ the container definition

def test_the_codespace_has_docker_inside_it_and_pulls_the_runtimes_in_the_background():
    cfg = devcontainer()
    assert "ghcr.io/devcontainers/features/docker-in-docker:2" in cfg["features"]
    start = cfg["postStartCommand"]
    assert "scripts/pull_runtimes.py --wait" in start          # waits for the daemon, then pulls
    assert start.rstrip().endswith("&")                          # never holds the Codespace start-up


# ------------------------------------------------------------------ what a student is told

def test_a_codespace_without_docker_is_told_how_to_fix_it(monkeypatch):
    no_docker(monkeypatch)
    monkeypatch.setenv("CODESPACES", "true")
    ok, why = sandbox._check(languages.LANGUAGES["python"], "3.12")
    assert not ok and "Rebuild Container" in why and "Codespace" in why


def test_anywhere_else_it_just_says_docker_is_not_installed(monkeypatch):
    no_docker(monkeypatch)
    monkeypatch.delenv("CODESPACES", raising=False)
    assert sandbox._check(languages.LANGUAGES["python"], "3.12") == (False, "Docker is not installed.")


# ------------------------------------------------------------------ the pull script

def test_pulling_without_docker_says_so_instead_of_a_traceback(monkeypatch, capsys):
    script = pull_script()
    monkeypatch.setattr(script.shutil, "which", lambda name: None)
    assert script.main([]) == 3
    assert "Docker is not installed" in capsys.readouterr().out


def test_an_unknown_language_is_refused_before_anything_else(capsys):
    assert pull_script().main(["cobol"]) == 2


def test_waiting_gives_up_after_its_time_and_says_so(monkeypatch, capsys):
    script = pull_script()
    monkeypatch.setattr(script.shutil, "which", lambda name: "docker")
    monkeypatch.setattr(script, "daemon_up", lambda: False)
    ticks = iter(range(0, 10_000, 30))                           # every look at the clock is 30 seconds later
    assert script.wait_for_daemon(120, clock=lambda: next(ticks), sleep=lambda s: None) is False
    monkeypatch.setattr(script, "wait_for_daemon", lambda: False)
    assert script.main(["--wait"]) == 4
    assert "did not start" in capsys.readouterr().out


def test_waiting_stops_as_soon_as_the_daemon_answers(monkeypatch):
    script = pull_script()
    answers = iter([False, False, True])
    monkeypatch.setattr(script, "daemon_up", lambda: next(answers))
    slept = []
    assert script.wait_for_daemon(120, clock=lambda: 0, sleep=slept.append) is True
    assert len(slept) == 2

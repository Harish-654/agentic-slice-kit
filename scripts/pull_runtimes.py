#!/usr/bin/env python3
"""
pull_runtimes.py - download the Docker images the code sandbox runs students' programs in.

The tutor can teach a language without any of this; only RUNNING code needs its image, and a language whose image is
missing simply has code running switched off (with the exact `docker pull` line to fix it). Images are never pulled
while a student is waiting: the sandbox refuses to.

    python scripts/pull_runtimes.py                  the default version of every language (about 3.4 GB on disk)
    python scripts/pull_runtimes.py java             every version of Java
    python scripts/pull_runtimes.py java 17          just Java 17
    python scripts/pull_runtimes.py --all            every version of every language (roughly 6 GB)
    python scripts/pull_runtimes.py --list           what would be pulled, and what is already here
    python scripts/pull_runtimes.py --wait           first wait (up to 2 minutes) for the Docker daemon to come up,
                                                     which the Codespace start-up uses because the daemon starts a
                                                     moment after the container does

Exit codes: 0 done, 1 some image failed to pull, 2 unknown language, 3 Docker is not installed, 4 Docker did not start.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demo.tutor import languages  # noqa: E402

WAIT_SECONDS = 120


def daemon_up() -> bool:
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def wait_for_daemon(seconds: float = WAIT_SECONDS, clock=time.monotonic, sleep=time.sleep) -> bool:
    """True once `docker info` answers, False if it has not within `seconds`."""
    end = clock() + seconds
    while not daemon_up():
        if clock() >= end:
            return False
        sleep(2)
    return True


def have(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode == 0


def wanted(argv: list[str]) -> list[tuple[str, str]]:
    """(language, version) pairs to pull."""
    args = [a for a in argv if not a.startswith("--")]
    if "--all" in argv:
        return [(l.id, v) for l in languages.LANGUAGES.values() for v in l.versions]
    if not args:
        return [(l.id, l.default) for l in languages.LANGUAGES.values()]
    lang, version = languages.resolve(args[0], args[1] if len(args) > 1 else None)
    return [(lang.id, v) for v in ([version] if len(args) > 1 else lang.versions)]


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    try:
        todo = wanted(argv)
    except languages.UnknownLanguage as e:
        print(e)
        return 2
    if shutil.which("docker") is None:
        print("Docker is not installed here, so there is nowhere to pull the runtime images. Install Docker, or in a "
              "Codespace rebuild the container so its Docker setup applies.")
        return 3
    if "--wait" in argv and not wait_for_daemon():
        print(f"Docker did not start within {WAIT_SECONDS} seconds. Run this again once `docker info` works.")
        return 4
    failed = 0
    for lang_id, version in todo:
        lang = languages.LANGUAGES[lang_id]
        image = lang.image_for(version)
        if "--list" in argv:
            print(f"{'present' if have(image) else 'missing':8s} {lang.label(version):16s} {image}")
        elif have(image):
            print(f"already here: {image}")
        else:
            print(f"pulling {image} ...", flush=True)
            failed += subprocess.run(["docker", "pull", image]).returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

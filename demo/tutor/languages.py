"""The languages the tutor can teach and run, and the versions of each.

One table, so a fifth language is one entry here plus its error patterns (coach.py) and tests. Everything
that differs between languages lives here as data: which Docker image runs a version, how to compile and run
a program, how much time and memory it gets, and what to tell the model about the language it is writing.

A "version" is whatever a student would say: Python 3.12, Node 22, Java 17, C++17 (for C++ it is the language
standard, compiled by a current gcc). The lessons AND the sandbox follow it, so a student on Java 8 is never
shown, or allowed to run, something that only exists in Java 21.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_LANGUAGE = "python"


class UnknownLanguage(ValueError):
    """The language or version is not one we support. The message is safe to show the student."""


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    versions: tuple[str, ...]
    default: str
    image: str                  # {v} is the version
    filename: str               # the source file's name ({cls} for Java)
    compile: str | None         # a shell command, or None if the language is interpreted
    run: str                    # a shell command that reads the program's input on stdin
    seconds: int                # the whole run: container start, compile and every test
    memory: str                 # docker --memory
    cpus: str
    pids: int
    hello: str                  # a program that prints "ok"; proves an image works

    def image_for(self, version: str) -> str:
        return self.image.format(v=version)

    def label(self, version: str) -> str:
        """How a student reads it: "Python 3.12", "Java 17", "C++17"."""
        return f"C++{version}" if self.id == "cpp" else f"{self.name} {version}"

    @property
    def compiled(self) -> bool:
        return self.compile is not None

    def prompt_line(self, version: str) -> str:
        """The line every model call gets, so lessons, questions and code are in the right language and
        only use what that version has."""
        return (f"LANGUAGE: {self.label(version)}. Write all code in {self.label(version)} and use only features "
                f"that exist in that version; if something was added later, do not use it.")


_JAVA_HELLO = 'public class Main { public static void main(String[] a) { System.out.println("ok"); } }'

LANGUAGES: dict[str, Language] = {l.id: l for l in (
    Language("python", "Python", ("3.9", "3.10", "3.11", "3.12", "3.13"), "3.12", "python:{v}-slim",
             "main.py", None, "exec python -I main.py", 10, "256m", "0.5", 64, 'print("ok")'),
    Language("javascript", "JavaScript", ("18", "20", "22"), "22", "node:{v}-slim",
             "main.js", None, "exec node main.js", 12, "256m", "0.5", 128, 'console.log("ok")'),
    Language("java", "Java", ("8", "11", "17", "21"), "21", "eclipse-temurin:{v}-jdk",
             "{cls}.java", "javac -encoding UTF-8 -nowarn {file}",
             "exec java -Xshare:auto -XX:TieredStopAtLevel=1 -Xmx200m {cls}", 40, "512m", "1", 256, _JAVA_HELLO),
    Language("cpp", "C++", ("11", "14", "17", "20", "23"), "17", "gcc:14",
             "main.cpp", "g++ -std=c++{v} -O1 -pipe -o main main.cpp", "exec ./main", 40, "384m", "1", 128,
             '#include <cstdio>\nint main() { std::puts("ok"); }'),
)}


def resolve(language: str | None, version: str | None = None) -> tuple[Language, str]:
    """(the language, the version to use). None means the default. Raises UnknownLanguage."""
    lang = LANGUAGES.get((language or DEFAULT_LANGUAGE).strip().lower())
    if lang is None:
        raise UnknownLanguage(f"We do not teach {language!r} yet. Choose one of: "
                              + ", ".join(l.name for l in LANGUAGES.values()) + ".")
    v = (version or lang.default).strip()
    if v not in lang.versions:
        raise UnknownLanguage(f"{lang.name} {v} is not available. Choose one of: {', '.join(lang.versions)}.")
    return lang, v


_CLASS = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")
_MAIN = re.compile(r"\bstatic\s+void\s+main\s*\(")


def java_class(code: str) -> str:
    """The class a Java program starts in: the nearest class declared before `main`, else the first public
    class, else `Main`. The file must carry that name, so the student can call their class anything.
    Only a plain identifier ever comes out, because the name is placed into shell commands."""
    m = _MAIN.search(code)
    if m:
        before = _CLASS.findall(code[:m.start()])
        if before:
            return before[-1]
    public = re.search(r"\bpublic\s+(?:final\s+|abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    return public.group(1) if public else "Main"


def commands(lang: Language, version: str, code: str) -> dict[str, str]:
    """The concrete file name, compile command and run command for this program and version."""
    cls = java_class(code) if lang.id == "java" else ""
    fill = {"v": version, "cls": cls}
    filename = lang.filename.format(**fill)
    return {"file": filename,
            "compile": (lang.compile.format(file=filename, **fill) if lang.compile else ""),
            "run": lang.run.format(**fill)}


def catalogue() -> list[dict]:
    """What the page needs to build its pickers."""
    return [{"id": l.id, "name": l.name, "versions": list(l.versions), "default": l.default,
             "images": {v: l.image_for(v) for v in l.versions}} for l in LANGUAGES.values()]

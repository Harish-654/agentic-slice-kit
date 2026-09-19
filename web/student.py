"""
The page a student learns on: a lesson, a diagram when one helps, then a short
check. The check is multiple choice by default; "answer in my own words" is a
toggle, remembered for next time.

Server-rendered like web/expert.py. The one script is Mermaid, loaded only to
draw a diagram when a lesson has one.

    uvicorn web.student:app --port 8001

Teacher notes are read from SLICE_NOTES (default corpus/python). Where the notes
run out, the agent asks a teacher on web/expert.py instead of guessing.
"""
from __future__ import annotations

import html
import os
import re

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from demo.tutor import notes, session
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from slice import runner
from slice.config import settings
from slice.retrieve import ingest
from slice.store import Store

DB = os.environ.get("SLICE_DB", "run.db")
NOTES = os.environ.get("SLICE_NOTES", "corpus/python")
app = FastAPI(title="Tutor")


def _store() -> Store:
    s = Store(DB)
    if os.path.isdir(NOTES):
        notes.prepare(NOTES)               # PDF/Word -> .md, only what changed
        ingest(s, NOTES)                   # idempotent: content-hash chunk ids
    return s


def _step(s: Store, run: str) -> None:
    runner.advance(s, run, build_flow(), settings())


CSS = """
:root{color-scheme:light dark;font-family:system-ui,sans-serif}
body{max-width:42rem;margin:2rem auto;padding:0 1rem;line-height:1.55}
.card{border:1px solid #8884;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0}
.cite{font-size:.8rem;color:#6b7280}.pill{font-size:.75rem;border:1px solid #8886;
border-radius:99px;padding:.1rem .6rem;margin-right:.3rem}
label.opt{display:block;padding:.5rem .7rem;border:1px solid #8884;border-radius:8px;margin:.4rem 0}
textarea,input[type=text]{width:100%;box-sizing:border-box;padding:.5rem;font:inherit}
textarea{min-height:6rem}button{padding:.5rem 1.1rem;font:inherit;margin-top:.5rem}
.good{border-color:#1a7f4b}.bad{border-color:#b42318}
pre{background:#8881;border-radius:8px;padding:.7rem .9rem;overflow-x:auto}
code{background:#8882;border-radius:4px;padding:0 .25rem}pre code{background:none;padding:0}
#busy{display:none;margin-top:.8rem;color:#6b7280}
"""


def _rich(text: str) -> str:
    """Paragraphs, ``` fenced blocks and `inline code`. Everything is escaped
    first, so model output cannot inject markup."""
    out = []
    for i, part in enumerate(text.split("```")):
        if i % 2:                                   # inside a fence
            lang = re.match(r"[\w+-]*\n", part)     # ```python -> drop the tag
            body = part[lang.end():] if lang else part
            out.append(f"<pre><code>{html.escape(body.strip(chr(10)))}</code></pre>")
            continue
        for para in part.strip().split("\n\n"):
            if para.strip():
                esc = html.escape(para.strip()).replace("\n", "<br>")
                out.append("<p>" + re.sub(r"`([^`]+)`", r"<code>\1</code>", esc) + "</p>")
    return "".join(out)


BUSY = ("<p id='busy'>Checking your answer and preparing the next lesson&hellip; "
        "this usually takes 10 to 20 seconds.</p><script>"
        "document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',()=>{"
        "document.getElementById('busy').style.display='block';"
        "document.querySelectorAll('button').forEach(b=>b.disabled=true);}))</script>")


def _page(title: str, body: str, mermaid: bool = False) -> HTMLResponse:
    script = ("<script type='module'>import m from 'https://cdn.jsdelivr.net/npm/mermaid@11/"
              "dist/mermaid.esm.min.mjs';m.initialize({startOnLoad:false,suppressErrorRendering:true});"
              "for(const el of document.querySelectorAll('.mermaid')){try{await m.parse(el.textContent);"
              "await m.run({nodes:[el]});}catch(e){el.remove();}}</script>"
              if mermaid else "")
    return HTMLResponse(
        f"<!doctype html><meta charset='utf-8'><meta name='viewport' "
        f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>"
        f"<style>{CSS}</style>{body}{script}")


@app.get("/", response_class=HTMLResponse)
def home():
    return _page("Tutor",
                 "<h1>Learn Python from your teacher's notes</h1>"
                 "<form method='post' action='/start'>"
                 "<p><label>Your name or id<br><input type='text' name='student' required></label></p>"
                 "<p><label>What to learn (comma separated)<br>"
                 "<input type='text' name='concepts' "
                 "value='mutable-defaults, is-vs-equals, list-slicing'></label></p>"
                 "<p><label>Things you like: games, films, sport... (optional)<br>"
                 "<input type='text' name='interests'></label></p>"
                 "<button>Start</button></form>")


@app.post("/start")
def start(student: str = Form(...), concepts: str = Form(...), interests: str = Form("")):
    s = _store()
    cs = [c.strip() for c in concepts.split(",") if c.strip()]
    ints = [i.strip() for i in interests.split(",") if i.strip()] or None
    run = session.start_session(s, student.strip(), cs, ints)
    _step(s, run)
    return RedirectResponse(f"/s/{run}", status_code=303)


@app.get("/s/{run}", response_class=HTMLResponse)
def show(run: str):
    s = _store()
    try:
        state = s.get_state(run)
    except KeyError:
        return _page("Not found", "<h1>No such session</h1>")
    model = LearnerModel.model_validate(s.latest(run, "learner_model"))
    lesson, checks = s.latest(run, "lesson"), s.history(run, "check")
    body = ""

    if checks:
        last = checks[-1].payload
        body += (f"<div class='card {'good' if last['correct'] else 'bad'}'>"
                 f"<b>{'Correct' if last['correct'] else 'Not quite'}.</b> "
                 f"{html.escape(last['feedback'])}</div>")

    if state.is_terminal:
        end, fail = s.latest(run, "session_end"), s.latest(run, "failure")
        rows = "".join(f"<li>{html.escape(c)}: {round(m * 100)}%</li>"
                       for c, m in model.mastery.items())
        why = ("You have got the hang of these." if end and end["reason"] == "mastery"
               else html.escape(fail["detail"]) if fail else "Session finished.")
        return _page("Done", body + f"<h1>Session over</h1><p>{why}</p><ul>{rows}</ul>"
                             "<p><a href='/'>Start another</a></p>")

    q = session.open_quiz(s, run)
    if lesson is None or q is None:
        return _page("Waiting",
                     body + "<h1>Waiting on your teacher</h1><p>The notes do not cover this "
                            "yet, so a question has gone to your teacher.</p>")

    body += (f"<h1>{html.escape(lesson['concept'].replace('-', ' '))}</h1>"
             f"<p><span class='pill'>{html.escape(lesson['style'].replace('_', ' '))}</span>"
             f"<span class='cite'>from {html.escape(', '.join(lesson['citations']) or 'teacher note')}</span></p>"
             f"{_rich(lesson['explanation'])}")
    if lesson.get("diagram"):
        body += f"<pre class='mermaid'>{html.escape(lesson['diagram'])}</pre>"

    quiz = lesson["quiz"]
    body += f"<div class='card'><b>Check yourself</b>{_rich(quiz['question'])}"
    if quiz.get("code"):
        body += f"<pre><code>{html.escape(quiz['code'].strip())}</code></pre>"
    if model.answer_mode == "mcq":
        opts = "".join(f"<label class='opt'><input type='radio' name='choice' value='{i}' required> "
                       f"{html.escape(o['text'])}</label>" for i, o in enumerate(quiz["options"]))
        body += f"<form method='post' action='/s/{run}/answer'>{opts}<button>Answer</button></form>"
        other, label = "text", "Answer in my own words instead"
    else:
        body += (f"<form method='post' action='/s/{run}/answer'>"
                 "<textarea name='text' required placeholder='Explain in your own words'></textarea>"
                 "<button>Answer</button></form>")
        other, label = "mcq", "Give me choices instead"
    body += (f"<form method='post' action='/s/{run}/mode'><input type='hidden' name='mode' "
             f"value='{other}'><button>{label}</button></form></div>")
    return _page(lesson["concept"], body + BUSY, mermaid=bool(lesson.get("diagram")))


@app.post("/s/{run}/answer")
def answer(run: str, choice: int | None = Form(None), text: str = Form("")):
    s = _store()
    q = session.open_quiz(s, run)
    if q is not None:
        if choice is not None:
            session.submit_mcq(s, q.id, choice)
        elif text.strip():
            session.submit_text(s, q.id, text.strip())
        else:
            return RedirectResponse(f"/s/{run}", status_code=303)
        _step(s, run)
    return RedirectResponse(f"/s/{run}", status_code=303)


@app.post("/s/{run}/mode")
def mode(run: str, mode: str = Form(...)):
    if mode in ("mcq", "text"):
        session.set_answer_mode(_store(), run, mode)
    return RedirectResponse(f"/s/{run}", status_code=303)

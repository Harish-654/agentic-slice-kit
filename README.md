# Cognitive-twin tutor

**For judges.** This is a tutor for any topic that remembers what each student gets
wrong and teaches the next lesson differently. Beside every lesson sits a code sandbox
that runs Python, JavaScript, Java and C++ (each in a version the student picks). It runs in a browser: the student
picks topics, reads a short lesson, answers a check, and says how sure they were.
It is built on the Agentic Slice Kit, the starter kit from the organisers; the
kit's own guide for participants is kept further down this page, below the divider.

Jump to: [Run it](#run-it-in-5-minutes) ·
[If you have no key](#if-you-have-no-key) ·
[Five-minute tour](#a-five-minute-tour) ·
[What outside users told us](#what-outside-users-told-us-and-what-we-changed) ·
[Where the agentic behaviour is](#where-the-agentic-behaviour-is) ·
[Resetting](#resetting-and-where-state-lives) ·
[Troubleshooting](#troubleshooting) ·
[Repo map](#repo-map)

Also in this repo: [`PRE-EVENT-ASSETS.md`](PRE-EVENT-ASSETS.md) (what was brought
in before the event) and [`docs/PROGRESS-REPORT.md`](docs/PROGRESS-REPORT.md)
(progress report).

---

## Run it in 5 minutes

Every command once, in the order to run them. Run them from the repo folder.

```bash
git clone https://github.com/Harish-654/agentic-slice-kit.git
cd agentic-slice-kit
python -m venv .venv
source .venv/bin/activate          # bash/zsh. fish: source .venv/bin/activate.fish
                                   # Windows cmd: .venv\Scripts\activate
                                   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows cmd: copy .env.example .env
```

Now open `.env` in any editor and put your key after `OPENROUTER_API_KEY=`
(no quotes, no spaces), then save. Do this **before** starting the server: the
server reads `.env` once, so if you change it later, stop the server (Ctrl+C) and
start it again.

```bash
python -m uvicorn web.student:app --port 8001
```

Then open <http://127.0.0.1:8001> in a browser. Stop the server with Ctrl+C.

**What you need**

- Python 3 with `venv` and `pip`. We tested Python 3.14.7 on Linux (below). The
  Codespaces image uses Python 3.12; We did not test that version. We did not test
  Windows or macOS either, so those activate lines are the standard ones, not
  proven here.
- **No Node.** The built web page is committed in `web/ui/dist/`, and the Python
  server serves it. Node is only needed to change the page.
- **Docker is optional, and only for running code.** Lessons, quizzes and written
  answers need none. Program questions and the code coach run a student's code in a
  throwaway Docker container (no network, read-only, non-root, memory and time
  limited), one image per language and version. Pull them once with
  `python scripts/pull_runtimes.py` (the default version of each language, about
  1.5 GB; `--list` shows what is already here). A language whose image is missing
  still teaches: its program questions become multiple choice and the page says so.
- **A free OpenRouter key is enough** (as the team reports; this was not checked
  independently). Get one at openrouter.ai. Lessons call the models named in
  `.env.example`.
- **The tests need no key, no network and no Docker:** `python -m pytest`. The ones
  that need a live key or Docker (with the runtime images pulled) skip themselves
  when it is missing. Checked here with Docker hidden from `PATH`: all 40 Docker
  tests skip.
- **Internet, once, for documents.** The first document upload downloads a small
  embedding model (measured: 65 MB on disk, about 9 s download, about 16 s for the
  first upload, on a fast connection). It is cached after that.
- Mermaid diagrams inside lessons load from `cdn.jsdelivr.net` when a lesson has
  one. Without internet the diagram is simply left out (code, not tried).

**GitHub Codespaces.** Only port 8000 is forwarded
(see [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json)), so
start the server like this instead, and open port 8000 from the **Ports** tab:

```bash
python -m uvicorn web.student:app --host 0.0.0.0 --port 8000
```

The Codespaces image also has the embedding model baked in, so no download there,
and it creates `.env` from `.env.example` for you (you still add the key).

**Running code in Codespaces.** The code sandbox needs Docker, so the Codespace runs
Docker inside itself (the `docker-in-docker` feature in `.devcontainer/devcontainer.json`)
and pulls the runtime images in the background each time it starts. The first time takes
a few minutes and about 1.5 GB; until an image is there, **Run** says that runtime is not
installed, and Python 3.12 arrives first. Watch it with `tail -f /tmp/pull_runtimes.log`,
and see what is present with `python scripts/pull_runtimes.py --list`. **A Codespace
created before this was added does not pick it up by itself: run "Codespaces: Rebuild
Container" from the Command Palette.** If the sandbox still says "Docker is not
available in this Codespace", the rebuild has not happened yet.

**We could not test Codespaces (Python 3.12) at all, and that includes the Docker
setup above.** Treat this paragraph as untested until someone has rebuilt a Codespace
and run `python -m pytest -m integration` in it.

**Verified on a fresh clone** (run by the team's AI coding assistant, following this page literally; this was at an earlier commit, before sign-in and the code sandbox, and the suite has since grown to 493 tests). Fresh `git clone` of `main`, a brand-new venv,
Python 3.14.7, Linux, no `.env`, no `run.db`, no `uploads/`. Every command above
ran as written. `pip install` finished cleanly.
`python -m pytest -k "not integration"` gives **148 passed, 3 deselected** in
about 2 seconds. The whole suite is 151 tests: the 3 in `tests/test_integration.py`
need a live key and are skipped without one. The server started, `/` served the
built page (`index.html` points at `/assets/index-BHwdL50M.js` and
`/assets/index-dmwCZPbx.css`, both answer HTTP 200), `/classic/` and
`/api/students/x/docs` answered, and a document upload was listed and found by
search. No live model calls were made in this check, so the lesson text and the timings in the
tour below come from the code and the team, not from a run we watched.

---

## If you have no key

What still works without a key:

- `python -m pytest` runs (the tests that need a live key or Docker skip themselves).
  It uses a scripted stand-in for the model, so it exercises the whole
  teach-check-adapt loop.
- The server starts, the chat page and the classic page (`/classic/`) load.
- Adding documents (or "Try sample notes") works: embeddings are computed on your
  machine.
- The "not in your documents" step works. With sample notes added and "Use my
  documents as the source of truth" on, start a session on a topic the notes do not
  cover (for example `photosynthesis`). The page says a topic is not in your
  documents and offers **Teach it from general knowledge** or **Skip this topic**.
  **Skip this topic** ends the session with "You skipped the topics your documents
  do not cover." No model is involved up to there.

What does not work: **lessons.** Every lesson and every written-answer grade needs a model.

What you will see if you click **Start learning** with an empty key: a moment of
"Reading your teacher’s notes and preparing your first lesson…", then (within a
couple of seconds, no waiting for a timeout) a session with a red notice:

> Both models unreachable (Illegal header value b'Bearer '). Run `python scripts/doctor.py` - this is usually the network or a provider outage, not your code.

with a **Start a new session** button. That message is misleading: the cause is
the empty key, not the network. The classic page shows the same text under "Session
over". We checked this text through the API and the classic page, not in a browser.

`python scripts/doctor.py` says `[ FAIL ] OPENROUTER_API_KEY is empty`, skips the
model checks, and exits with code 1. Its two warnings (cloudflared not installed,
embedding model not baked in) only matter inside Codespaces and can be ignored.

---

## A five-minute tour

Use a wide window (the progress panel is on the right; on a phone it folds into
**Your progress** at the top). A lesson takes about 10 to 25 seconds on a free key
(the team's figure, not re-timed in the fresh-clone check). While it is written the page says
"Writing your next lesson…". Your right-or-wrong feedback appears at once, while
the next lesson is still being written.

The labels below are copied from the page's source
(`web/ui/src/components/tutor/`). What each step should show is read from the code
and the offline tests; the model's wording will vary.

1. **Sign in, then start with topics and no documents.** The first page is a sign-in
   screen. Choose **Create account**, enter a name (say `judge`) and a password of 8
   or more characters (repeat it), and create it. The start screen then says "What
   do you want to learn?" and greets you as `judge`; it never asks for a name again.
   In **Topics** type `mutable defaults, list slicing`. Leave the documents box
   alone. Click **Start learning**. (The start screen has no language choice: the
   tutor teaches any topic, and languages belong to the code sandbox, step 8.)
   Expect: a lesson with the topic as heading, a badge such as "Straight
   explanation", and a badge **General knowledge** (hover it: "Written by the AI
   from what it knows. It has not been checked against your documents."). No
   citation badges. Under it, a **Check yourself** card with lettered options.

2. **Answer wrong, and say "Certain".** Pick an option you think is wrong, click
   **Certain** (the choices are **Just guessing**, **Fairly sure**, **Certain**),
   then **Submit answer**. The button stays off until you have picked an option
   and a confidence.
   Expect, immediately: a card headed "Not quite", "That option rests on the idea:
   ...", and "You said you were certain. You were certain, so this is the idea most
   worth fixing." In the right panel the topic moves from "not started" to a low
   percentage (the spec's walkthrough computes 9%) and the idea appears under
   **Ideas to watch**. The next lesson uses a different explanation
   style (for example "By analogy") and aims at that idea. (If you happen to be
   right, the card says "Correct"; try another question.)

3. **Click "I don’t know".** On the next question, click **I don’t know** instead of
   answering. Expect a card headed "No problem", and the right answer marked green
   on the question card. It costs a little progress and records no wrong idea.

4. **Add the sample notes and switch on documents.** In the right panel, under
   **Your documents**, click **Try sample notes** (the first time this downloads
   the embedding model). Three files appear. Then, once the next lesson has
   appeared (the switch is off while a lesson is being written), switch on **Use my
   documents as the source of truth**. The panel says "Changes apply from the next lesson."
   Answer the question on screen; the next lesson should carry the badge **From
   your documents** and a badge naming the file it used, for example
   `mutable-defaults.md#0`.

5. **Write your own answers.** Switch on **Ask my next questions in my own words**
   (bottom right of the thread). The question on screen stays as it is, and the page
   says "Your next question will be in your own words." After you answer this one,
   the next card is headed **Explain in your own words**. The box
   ("Explain it in your own words…") is locked until you choose a confidence, then
   press Enter. Expect "Checking your answer…" for a while: a model grades it.

6. **A topic outside the documents.** Click **New session** (top right). The start
   screen says "Already saved for judge: ..." under your documents. Type the topic
   `photosynthesis`, switch on **Use my documents as the source of truth**, click
   **Start learning**.
   Expect, quickly: "“photosynthesis” is not in your documents." with two buttons,
   **Teach it from general knowledge** and **Skip this topic**. The tutor does not
   guess. Pick either; the first gives a lesson badged **General knowledge**.

7. **Start again and see it remember.** Click **New session** (or **Sign out** and
   sign in again with the same account). Use `mutable defaults, list slicing` again.
   The **What you know** panel already shows your earlier percentages ("Learning",
   "Review due" or "Got it") and **Ideas to watch** still lists the idea you got
   wrong. This memory is stored in `run.db` on the server, not in the browser, and
   belongs to the account: another account starts from nothing.

8. **Try the code sandbox** (needs Docker and the runtime images, see "What you
   need"). In the right panel, under **Code sandbox**, the **Language** and
   **Version** pickers start on Python 3.12, on every topic, including
   `photosynthesis`. Type `print(6 * 7)` and click **Run**: expect `42`. Pick
   **Java** and a version: the editor becomes a Java one, and a version with no
   runtime here reads "(no code)" and shows why, with the `docker pull` line, while
   the pickers stay. **Program input (optional)** is what the program reads. Then
   switch on **Ask my next question as a program to write** (bottom of the thread),
   answer the question on screen, and the next card is headed **Write a program**,
   written in the sandbox's language, with that language ("Java 17") beside **Run**.
   It is checked on hidden inputs when you click **Submit program**. Changing the
   picker afterwards affects the next question, not this one. Without Docker the
   sandbox says it is switched off and program questions become multiple choice.

9. **Watch the streak.** After you answer a question the 🔥 number in the top bar
   goes to 1, and today's square on the **Learning activity** heatmap (on the start
   screen, under the form) fills in. A day counts if you answered a question or ran
   your own code, in your own timezone.

10. **See what you have learnt.** Click **New session** to get back to the start
    screen. Once you have any history, the first thing on it is **Your learning**:
    four figures (topics learnt, parts completed, ideas to review, sessions) and a
    card for each topic you have studied, newest first. A guided topic's card shows
    how many of its parts you have done and lists each one as **Got it**, **Learning**,
    **Review due** or **New**, with what the topic builds on. **Study again** puts that
    topic in the box below. A brand-new account has no history, so it sees no dashboard.

**The progress panel** (right side) shows **What you know**: one percentage per topic,
`0%` and "not started" until you answer something, "Got it" at 75% or more, and
"Review due" when a topic you had learnt has slid back below 75% with time.
**Ideas to watch** lists the wrong ideas your answers pointed to, with a count.

---

## The code sandbox: languages and versions

The tutor teaches anything. The **code sandbox** (the "Code sandbox" panel beside every
lesson, on every topic) is the one place a language is chosen: a **Language** and a
**Version** picker above the editor. The choice is remembered for next time. It changes
what the editor runs and what the *next program question* is written in. It never changes
what a lesson is about: lessons, quizzes, plans and grading follow the topic, and the start
screen asks only what you want to learn. Name a language in the topic ("inheritance in
C++") and every part of a guided lesson is written in it, because your own words travel with
each part (a part's id, like `virtual-functions`, has lost the language). If you name none,
lessons use Python. A plan made for one language is not reused for another.

| Language | Versions (default first) | Runs in |
|---|---|---|
| Python | 3.12, 3.9, 3.10, 3.11, 3.13 | `python:<v>-slim` |
| JavaScript | Node 22, 18, 20 | `node:<v>-slim` |
| Java | 21, 8, 11, 17 | `eclipse-temurin:<v>-jdk` (the class holding `main` is found automatically) |
| C++ | C++17, 11, 14, 20, 23 | `gcc:14` with `-std=c++<v>` |

- **Program questions.** Python keeps function-style questions (write `total(prices)`).
  The other languages read input and print output, and are judged on hidden inputs. A
  failing test names the wrong idea it exposes, never the answer.
- **A program question keeps its language.** It is written, labelled ("Java 17") and graded in
  the language the sandbox was set to when it was asked, even if you change the picker later.
- **A question is checked before you see it.** The model writes the hidden tests and a
  model solution; the solution is run against its own tests in the sandbox first. If it
  fails, the question is rewritten once, then replaced by a multiple-choice one.
- **Mastery is shared across languages** (the concept ids are the same), so knowing
  "recursion" in Python counts when you switch to Java. Per-language mastery is not built.
- The sandbox shows on every topic, so a student can ask for "a program" about any subject.
- Single-file programs only, no interactive input, and compiled languages take a few
  seconds per run. Adding a language is one entry in `demo/tutor/languages.py` plus its
  error patterns in `demo/tutor/coach.py`.

## What outside users told us, and what we changed

The team reports that people outside the team tried the tutor and suggested changes. At least three are named below. The same table,
with more detail, is in [`docs/PROGRESS-REPORT.md`](docs/PROGRESS-REPORT.md).

| Who | What they raised | What we changed | Where (commit, files) | How to see it in the tour |
|---|---|---|---|---|
| Arun N M | Tested an early version, before the UI change (the first server-rendered page, still at `/classic/`), and asked for UI improvements. | The chat page (assistant-ui and shadcn/ui, with a progress side panel) replaced it. Later, a percentage per topic instead of a bar, and the answer controls moved inside the question card so nothing covers the options. | `82ee223` (`web/ui/`, `web/tutor_api.py`); `1ebec1a` | Open `/classic/` and compare it with the tour |
| Kavin | Suggested a confidence level: a way to say how sure you are of an answer. Also raised using their own documents as the source of truth. | **How sure are you?** with **Just guessing / Fairly sure / Certain**, never defaulted, plus **I don’t know**; confidence changes scoring. And documents are opt-in: the model teaches from its own knowledge by default, and with **Use my documents as the source of truth** on, only from the student's files, with citations; a topic they do not cover is asked about, not guessed. | `1ebec1a`, `732a8ef` · `demo/tutor/learner.py`, `flow.py`, `library.py`, `web/ui/src/components/tutor/cards.tsx` | Steps 1 to 4 and 6 |
| Akileswaran | Raised adding documents: it did not work on the first screen. | Fixed: a file chosen on the start screen was never added, because the handler read the file list after the input had been cleared. Documents can also be added, listed and removed from the side panel; **Try sample notes** adds three sample files. | `1ebec1a` (`StartScreen.tsx`); `732a8ef` (`demo/tutor/library.py`, `web/tutor_api.py`) | Step 4 |

- **How fast:** every change was committed on 19 September 2026 between 15:38 and 16:45 IST, and the tutor's first commit is 13:30 the
  same day, so each loop from "someone tried it" to "we changed it" was at most 3 hours 15 minutes. That is worked out from commit
  times, not timed by anyone.
- **What surprised us:** a tester chose **kho kho** as their interest. Interests are free text and only shape the analogies (never
  the grading); our own examples were football and chess.
- **What we did not do:** nothing the named testers asked for was turned down. The repository holds no record of a second round with
  the same people, the confidence weights are our guesses, and documents have only been tried with the sample notes and a synthetic PDF.
- **Did it help?** Not measured. There is no before-and-after test and no comparison with a plain chat assistant, so this shows that
  testers were heard and the tool changed quickly, not that it improved their results.

The commit messages do not mention outside users, and all of the tutor's commits fall on one day (19 September 2026), so this table records
what the team reports, not something the git history proves.

---

## Where the agentic behaviour is

- **A wrong answer sends the run back.** The gating step ends by returning to the
  teaching step, which reteaches the same topic in a different style and aims at
  the wrong idea just seen: `demo/tutor/flow.py` (`handle_gating` returns to
  `handle_drafting`).
- **State that persists across sessions.** One learner model per student (mastery
  per topic, wrong ideas with counts, questions already asked, preferences),
  saved after every answer in the `learners` table of `run.db`, with mastery
  fading over time so old successes come due for review:
  `demo/tutor/learners.py`, `demo/tutor/learner.py`.
- **Waiting states where a human decides.** The run stops and waits for the
  student's answer, and again for the "not in your documents" choice. Nobody
  answering counts as a skip, never as consent: `demo/tutor/flow.py`,
  `slice/callback.py`.
- **Code decides what happens next; the model only writes.** Which topic comes
  next, which style, when to stop, and whether a multiple-choice answer is right
  are plain code (`demo/tutor/learner.py`, `flow.py`). The model writes lessons
  and questions, and grades written answers.
- **The answer key and the rubric never reach the browser.** `web/tutor_api.py`
  sends only what the student may see; the correct option arrives after they
  answer. Tested by `tests/test_tutor_api.py`.

The design is in [`demo/tutor/TUTOR-SPEC.md`](demo/tutor/TUTOR-SPEC.md) (the
AgentSpec, with a step-by-step walkthrough and its numbers). The event's judging
rubric is in [`docs/ON-THE-DAY.md`](docs/ON-THE-DAY.md) under "What you are
judged on".

---

## Resetting and where state lives

- `run.db` is one SQLite file. It holds every session, every student's learner
  model, and the document search index.
- `uploads/` holds each student's documents, in one folder per name.
- Both are created in the folder you start the server from, and both are
  gitignored. Start the server from the repo folder.
- To start clean: stop the server, then delete both.
  `rm -rf run.db uploads` (Windows: `del run.db` and `rmdir /s /q uploads`).
- **Students sign in.** The first page is a sign-in screen: create an account
  (a name and a password of 8 or more characters), and sign in with it after
  that. Passwords are stored hashed, a sign-in is a random token in an `HttpOnly`
  cookie, and every session and document is locked to its owner. A name that
  was used *before* accounts existed (it already has sessions in `run.db`) is
  locked, so nobody can take over someone else's progress by signing up first.
  There is no email, so the person running the server is the recovery path:
  `python scripts/manage_accounts.py reset <name>` gives an account a new
  password, and `claim <name>` deliberately attaches an old name to a new
  password. `list` shows the accounts.
- **Streaks and the activity heatmap** need nothing stored. Every answered
  question and every run of a student's own code is already a timestamped record;
  a day counts as a check-in if the student did at least one, in the student's
  own timezone. The 🔥 streak is the number of days in a row; it stays alive
  until midnight, then breaks if a whole day is missed.
- **The "Your learning" dashboard** also needs nothing stored. It reads the student's
  twin (how well they know each idea now, with forgetting) and their past sessions
  (each one's topic and, for a guided one, its plan). A part counts as completed once
  the student reached the bar on it, and reads "Review due" if it has since faded. A
  topic whose final check was passed stays "Learnt". Only the newest 200 sessions and
  30 topics are read, and mastery is shared across languages, so an idea learnt in
  Python counts under the same idea in Java.
- Stop the server with Ctrl+C in its terminal. Ports: 8001 in the command above
  (any free port works: change `--port` and the address); 8000 in Codespaces. By
  default the server listens on 127.0.0.1, so only your own machine can reach it.

---

## Troubleshooting

Only things we reproduced, or read directly from the code (marked "code").

| What you see | Cause and fix |
|---|---|
| A page that says "The chat UI has not been built" (reproduced) | `web/ui/dist/` is missing from your copy. Re-clone, or run `git checkout -- web/ui/dist`. Meanwhile `/classic/` still works. |
| Blank page | `web/ui/dist/` is committed and served: `index.html` and its JS and CSS all answered 200 on a fresh clone. Check the address (port) and open the browser's developer console for the error. We could not reproduce a blank page. |
| `error while attempting to bind on address ('127.0.0.1', 8001): address already in use` (reproduced) | Something is already on that port. Use another: `--port 8002`, and open that address. |
| "Both models unreachable (Illegal header value b'Bearer ')" (reproduced) | `OPENROUTER_API_KEY` is empty. Put the key in `.env` and **restart the server**: a running server does not re-read `.env` (reproduced). `python scripts/doctor.py` confirms. |
| A red notice saying `... returned HTTP 401` (code) | The key is wrong or revoked. Fix `.env`, restart the server. |
| A red notice saying `HTTP 429` (code) | The provider is throttling the free tier. Wait a minute, then **Start a new session**. |
| A red notice about credit or `402` (code) | OpenRouter refused the request because the key's balance cannot cover it. Use a key with credit, or lower `SLICE_MAX_TOKENS` in `.env` (see the comments in `.env.example`), then restart. `python scripts/doctor.py` reports it. |
| Lessons very slow | Free-tier models can be slow. The page keeps saying "Writing your next lesson…". Each model call gives up after 120 s and then tries a second model; if both fail you get a red notice and a **Start a new session** button (code). Progress up to the last answer is saved. |
| An upload is rejected (reproduced) | Only `.md`, `.txt`, `.pdf`, `.docx`; at most 5 MB per file; at most 10 files per student. The page shows the reason, for example `'a.exe': only .docx, .md, .pdf, .txt files can be added.` or `You can keep up to 10 documents. Remove one first.` A broken PDF says `could not be read`. |
| The first upload (or **Try sample notes**) takes a while, or fails offline | It downloads a 65 MB embedding model once and needs internet. The default cache is your system temp folder (`/tmp/fastembed_cache` on Linux), so a reboot can clear it. Set `FASTEMBED_CACHE_PATH` to keep it. |
| A session stuck on "Reading your teacher’s notes and preparing your first lesson…" or "Writing your next lesson…" | Normal for up to about 25 s. Longer: the model call is waiting on a slow provider (up to 120 s per call). If the server was restarted mid-lesson, reload the page: it resumes an interrupted session by itself (code, not reproduced). Otherwise click **New session**. |
| "Running code is switched off on this server" or "The Java 17 runtime is not installed. Run: docker pull …" (code) | That language's Docker image is missing, or Docker is not running. Start Docker, then run the `docker pull` line it prints, or `python scripts/pull_runtimes.py java 17`. No restart needed: a failed check is retried after 30 seconds. |
| The tutor does not remember you (code) | You signed in with a different account (a different name is a different student), or you deleted `run.db`. |
| "Too many wrong passwords. Try again in N seconds." when signing in (code) | Five wrong passwords in 15 minutes lock that name for a minute. Wait, then try again. A forgotten password is reset by whoever runs the server: `python scripts/manage_accounts.py reset <name>`. |

---

## Repo map

What a judge would read:

- [`demo/tutor/`](demo/tutor/): the tutor. `flow.py` (the loop), `learner.py` and
  `learners.py` (what it remembers), `session.py` (starting, answering),
  `library.py` (a student's documents), `prompts/` (what the model is told),
  `languages.py` and `sandbox.py` (the supported languages, and running code safely),
  `coach.py` (grading programs, error hints), `stub.py` (the scripted model for offline tests).
- [`web/tutor_api.py`](web/tutor_api.py): the JSON API behind the page.
  [`web/auth.py`](web/auth.py): sign-up, sign-in and the cookie.
  [`web/student.py`](web/student.py): the server, and the `/classic/` page.
  `demo/tutor/accounts.py` (accounts and sign-in tokens) and `activity.py` (the
  streak and the heatmap, worked out from records that already exist).
- [`web/ui/`](web/ui/): the chat page's source (React, Vite, Tailwind, shadcn/ui,
  assistant-ui). The built files are committed in `web/ui/dist/`.
- [`tests/`](tests/): 493 tests; `test_tutor*.py` cover the tutor. 40 of them
  (37 in `test_tutor_runtimes.py`, one each in `test_tutor_coach.py`,
  `test_tutor_probe_code.py` and `test_tutor_program.py`) need Docker
  and are marked `integration`; `python -m pytest -m "not integration"` skips them.
- [`demo/tutor/TUTOR-SPEC.md`](demo/tutor/TUTOR-SPEC.md): the AgentSpec.
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the kit's design, with links to the
  lines of code.
- `slice/`: the kit's spine (runner, store, model call, retrieval). It is the
  organisers' code; `PRE-EVENT-ASSETS.md` lists the few edits made to it.

---

# Agentic Slice Kit: participant guide

*Everything below is the organisers' guide for participants, kept as it was.*

A starter kit for building a **working agentic slice** in two days.

Not a framework. Not a library. About 1,100 lines you are expected to read,
understand, and edit — because the architecture is the thing being taught, and
you cannot learn an architecture you have imported.

---

## Start here

Click **Open in Codespaces**. Nothing to install — no Python, no Node, no
Docker. You need a browser and a GitHub account.

```bash
cp .env.example .env      # then paste the key from the registration desk
python -m pytest          # should be green
```

Only `OPENROUTER_API_KEY` is required. Everything else in `.env` is an upgrade
you can add at hour four, not a blocker at hour zero.

---

## What "agentic" means here

A single-prompt LLM wrapper does not qualify, however clever the prompt. A real
agentic slice demonstrates at least one of:

- **state persistence** across steps
- **autonomous tool or API use**
- **multi-step reasoning or decomposition**
- **human-in-the-loop callback mechanics**

Useful as that list is, one line does most of the sorting: **an agent is a
workflow that can go backwards.** Straight through A → B → C is a pipeline,
however many models are in it. The moment a later step can hand work back to an
earlier one and the run carries on from there, you have the thing. That
back-edge is the cheapest part to leave out and the most expensive to retrofit,
so decide early where yours is.

This kit demonstrates all four. [`docs/PRINCIPLES-BRIEF.md`](docs/PRINCIPLES-BRIEF.md)
is the short version — the ideas, in a page or two, and the file to paste into a
chat when you want a critic rather than an enthusiast.
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the long version: nine
principles, tiered by build order, each anchored to the line of code it actually
lives on.

**Read the brief before you write anything.** It will save you the rewrite that
hits teams on the second morning who start with prompts.

---

## Who does what

A team of four will not all do the same job, and the strongest teams split it
three ways. This is a strong recommendation, not a rule - organise differently if
you have a better idea, but decide deliberately rather than by drift.

| | owns | reads |
|---|---|---|
| **Designer** | the problem and the spec - what it does, what makes an answer wrong, what it refuses | [`docs/DESIGNER.md`](docs/DESIGNER.md) |
| **Builder** | the machinery - environment, the spine, `demo/flow.py`, unblocking everyone else | [`docs/BUILDER.md`](docs/BUILDER.md) |
| **Verifier** | real people using it, the stress test, the design rationale | [`docs/VERIFIER.md`](docs/VERIFIER.md) |

**Everyone starts in the same place.** Part one of
[`docs/DESIGNER.md`](docs/DESIGNER.md) is a guided design session &mdash; about
three hours, any frontier chat, no keys, nothing installed &mdash; and the whole
team should be in it. It produces a spec for your own agent, which is near
enough what a strong preliminary submission has to say. The roles start
mattering on the first morning, not during the fortnight.

The ideas the three guides assume are in
[`docs/PRINCIPLES-BRIEF.md`](docs/PRINCIPLES-BRIEF.md) &mdash; short, and worth
reading before any of them. [`docs/ON-THE-DAY.md`](docs/ON-THE-DAY.md) is the
operational page: keys, money, deadlines, what the two error codes mean, and who
to ask when something non-technical is in your way.

**The Verifier role is not the consolation prize.** Roughly a third of what you are judged on is evidence that real people used
your agent and that you changed it in response - and it is the part almost every
team leaves until the last afternoon, by which point it is too late to do honestly.

---

## Layout

```
slice/      THE SPINE — read this, edit it, do not treat it as a black box
  records.py    what a run is made of                   stdlib   88
  store.py      durable append-only state               stdlib  246
  config.py     the one place .env is read              stdlib   64
  budget.py     the fences: attempts and tokens         stdlib   94
  llm.py        the ONE place a model is ever called            277
  retrieve.py   chunk / embed / search, in the same db          138
  callback.py   suspend on a human, resume, time out             81
  runner.py     the state machine                               101
  __init__.py   what this package is, and what it is not  stdlib   16

demo/       THE DOMAIN — rewrite this for your own problem
web/        the form a human expert answers on
scripts/    doctor · bakeoff · sync_architecture
tests/      six files — the store, the fences, the callbacks, the runner,
            a check that ARCHITECTURE.md still points at real code, and
            one live-key integration test
```

The split is the point. Swap `demo/` for your problem and keep the machinery.

---

## Three things that will bite you

**Your Codespaces quota is finite, and how much you get depends on your plan.**
A free GitHub account includes 120 core-hours a month; the Student Developer Pack
upgrades you to Pro, which includes more. On the 2-core machine this repo asks
for, 120 core-hours is 60 hours of actual use. **Check your own** at
[github.com/settings/billing](https://github.com/settings/billing) — the
Codespaces tab shows what you have used against what is included, and it is the
only figure that is definitely right for you.

For scale, measured on this repo in September 2026: **a two-hour working session
on the 2-core machine costs 4.1 core-hours** — roughly 3% of a free account's
monthly allowance, at $0.18 an hour. Storage over the same period was 0.28
GB-hours, which is nothing. That is about thirty sessions a month before the free
tier runs out, so a team has room for the event several times over.

Billing lags a day or so, so a session you have just finished will not show up
straight away.

What actually eats the allowance is not working, it is **walking away**. Closing
the browser tab does not stop a codespace; it idles for 30 minutes first. Stop it
from [github.com/codespaces](https://github.com/codespaces), and consider
dropping the idle timeout to 5 minutes in your Codespaces settings. If you do get
blocked, push your work to a branch and a teammate can open a fresh codespace on
it.

**Your API key has a hard cap.** It is enforced, and it refuses a request
*before* running it if the worst case would exceed your balance — so an
oversized `max_tokens` produces a 402 while you still have credit. Leave
`SLICE_MAX_TOKENS` where it is unless you know why you are changing it.

**Default to the cheap model.** `SLICE_MODEL` is Flash-class and will carry
almost everything. `SLICE_ESCALATION_MODEL` costs roughly thirty times as much
per token. Escalate for the one hard subproblem, deliberately — not by habit
when something is not working and you are tired.

---

## The bar you are actually being judged against

Working code is necessary, not sufficient. You also owe: three fellow students
who walked your flow with their feedback captured and one visible iteration; a
recorded stress test where a classmate tried to break your agent, and the fix
commit that answers it; a short design rationale saying what your agent does and
where its limits are; and a repo someone else could pick up and continue.

Budget for that. Teams that treat the second morning as a feature deadline rather than a
feedback deadline consistently ship the least convincing demos.

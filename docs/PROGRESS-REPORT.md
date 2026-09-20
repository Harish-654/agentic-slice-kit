# Progress report: Strata, the cognitive-twin tutor

*As of commit `2b78b68` on `main` (2026-09-20, 12:33); this report was written just after it. Every number here was measured or
counted, and says how. Where something is not done or not verified, it says that instead.*

## In one paragraph

Strata is a tutor for any topic that **teaches, checks, and adapts**. It remembers what each student knows and which wrong ideas they
hold, teaches the same idea a different way after a wrong answer, and never ends a session without saying why. By default it teaches
from the AI's own knowledge, shaped by what the student already knows. If a student attaches their own documents and switches them on, it
teaches only from those and cites them. A **guided** mode plans a topic (what it builds on, and its parts), checks each prerequisite
before explaining it, lets the student choose what happens next, and ends with a written final check. Beside every lesson is a **code
sandbox** that runs Python, JavaScript, Java and C++ in throwaway Docker containers, and program questions are graded on hidden tests.
Students sign in, keep a streak, and see a dashboard of what they have learnt. It runs as a chat page (React, shadcn, assistant-ui) served
by one Python process, with a JSON API behind it. **493 tests exist. With no API key and no Docker, 450 run and pass and 43 skip
themselves.**

## Timeline

The tutor's first commit is 2026-09-19 13:30. The first phases landed that day and the rest on 2026-09-20 (times are as recorded in the
commits). The kit underneath (`slice/`, the docs, `demo/smoke`) was given to us and dates from 3 to 18 September.

| when | commit | what landed |
|---|---|---|
| 09-03 → 09-18 | `7100b84` … `090662b` | The kit as provided: spine (`slice/`), docs, smoke agent, event rules. Not ours. |
| 09-19 13:30 | `6c2a1f2` | **Phase 1.** The teach → check → adapt loop for Python: learner model, multiple choice whose wrong options each name one wrong belief, teacher notes as the source, a first web page. |
| 09-19 15:00 | `db9fd7b` | **Phase 2 and the speed fix.** History used in teaching, a learners table, forgetting, PDF and Word notes, the spec. Lessons made 4-5x faster after measuring (below). |
| 09-19 15:38 | `82ee223` | **Phase 3.** The chat UI (assistant-ui, shadcn), the JSON API, background lesson generation. Old page kept at `/classic`. |
| 09-19 16:24 | `732a8ef` | **Phase 4.** Documents became the student's choice; general knowledge by default; written questions; per-student document storage. |
| 09-19 16:45 | `1ebec1a` | "I don't know", a confidence rating that changes scoring, mastery as a percentage, two bug fixes. |
| 09-20 00:19 | `143c41c` | **Code coach and guided Phase A.** A code window with a sandbox: run code, program questions graded on hidden tests, suggestion chips shown only when the twin says the topic is known. Guided mode starts: a topic is planned, and each prerequisite is checked before it is explained. |
| 09-20 01:36 | `258f66c` | **Guided phases B and C.** After an explanation the student chooses (quiz me, another example, more detail, go deeper, skip, stop); the check is written with the explanation but held back; a topic is taught in parts and ends with a written final check. |
| 09-20 02:18 | `a5cf0b3` | **Guided phase D.** A concept map built by code and coloured by what the student knows, and lesson diagrams checked against an allow-list before they are drawn. |
| 09-20 02:20 | `4a1249e`, `8eb4e03` | **The atlas redesign.** The page rebuilt as three views of one session: Study, Twin (what the tutor believes about you) and Route. |
| 09-20 06:02 | `0bfa631` | **Sign-in, streaks and four languages.** Accounts, a daily streak and an activity heatmap, and a code sandbox for Python, JavaScript, Java and C++, each with a version. |
| 09-20 10:16 | `b52b4c9` | **Codespaces.** Docker inside the Codespace so the sandbox can run there (not yet run in a real Codespace). |
| 09-20 11:34 | `eedafbb` | An architecture diagram of the tutor (`docs/diagrams/`). |
| 09-20 11:47 | `509bf89`, `bf4fa91` | **A lesson keeps the language the student named**, and a **learning dashboard**. |
| 09-20 12:33 | `2b78b68` | The dashboard becomes a tab, the product is named **Strata**, a rotating status message while a lesson is written, and the next-question switch can be flipped at any time. |

The history above: `git log --format='%h %ad %s' --date=iso`.

## What works today

**The loop.** Code, not the model, decides what happens next. `demo/tutor/flow.py` has two steps. *Teach* picks the next thing to do
(the weakest topic, or in guided mode the next step of the plan), writes a lesson and a check, then waits for the student. *Check* reads
the answer, updates the learner model, and goes back to *Teach*: the back-edge that makes this an agent and not a lesson plan. Every stop
records a reason (`mastery`, `session_limit`, `student_left`, `skipped`, or a failure with its cause).

**What it remembers, per student** (`demo/tutor/learner.py`, `learners.py`): mastery per topic; every wrong belief it has caught and
how often; the questions already asked, so none repeat; interests, used only for analogies; whether the next question should be
written or a program; whether their documents are the source of truth; the plan it made for each topic (so a topic is not planned twice);
and which language the code sandbox uses. Mastery slides back over about two weeks, so an old success comes due for review.

**Two sources of facts, never mixed silently.**
- *No documents (default):* nothing predefined. The model teaches and asks from its own knowledge, shaped by a profile built in code
  (level, wrong answers so far, the belief to aim at, interests, past questions). Every lesson is labelled "General knowledge".
- *Documents:* the student attaches PDF, Word, Markdown or text and switches on "Use my documents as the source of truth". Retrieval is
  scoped to that student's files only. Lessons cite them, and a lesson that cites nothing it was given is refused.
- *A topic missing from their documents:* the tutor says so and lets the student choose general knowledge or skip. It never guesses.

**Three kinds of question.** Multiple choice by default, where each wrong option stands for one specific wrong belief, so picking it is
the diagnosis and needs no grading call. "Answer in my own words" makes the **next** question one that is written and graded against a
rubric kept on the server. "Ask my next question as a program to write" makes it a small program, run against hidden tests in the sandbox.
Both switches can be flipped at any time, even while a lesson is being written (a change made then waits and is sent when the lesson
lands). The question on screen is never converted, and a check that is already written is never rewritten.

**How sure the student is, and "I don't know".** Pick, say how sure you are (just guessing, fairly sure, certain), then submit; the submit
button stays locked until you have said. Confidence scales the score: a right answer moves mastery towards 100% by 0.3, 0.5 or 0.6, and a
wrong one multiplies it by 0.7, 0.5 or 0.3. A belief held with certainty counts double. "I don't know" is never graded and costs a little
(x0.85) with no belief recorded. One certain right answer cannot master a topic on its own (0.30 → 0.72, under the 0.75 bar).

**Guided mode** (on by default on the start screen). One model call plans the topic: what it builds on (up to 3 prerequisites) and its parts
(2 to 4), cleaned and capped in code. Each prerequisite is checked once **before** it is explained: right means it was known and it is
skipped; wrong or "I don't know" means it is taught. Then each part must be covered (mastery at the bar and two right answers this
session), and the topic ends with one written final check that needs several parts at once. Fail it and the weakest part is taught again,
at most twice. After every explanation the student chooses what happens next; after two explanations in a row the ways to keep explaining
are withdrawn. The order of all this is plain functions in `demo/tutor/steps.py`, not the model, and every loop is capped (16 checks, 30
steps). A pasted exam question can be the topic. A concept map, built by code and coloured by what the student knows, shows where they are.
A student's own words ("inheritance in C++") travel with every part of the topic, so each part is taught in the language they named.

**The code sandbox and the code coach.** Every run is a throwaway Docker container with no network, a read-only root, all capabilities
dropped, a non-root user, and memory, CPU, process and time limits. The student's source and the test inputs go in as base64 in an
environment file, never on a command line. Each language and version is proven on first use (only a loopback network, a read-only root, not
root, and a hello program runs) and fails closed. There are four languages and 17 versions (13 images: C++ shares one). Python program
questions call a function; the other languages read input and print output, judged on hidden inputs. A failing test names the wrong idea
it exposes, never the answer. **A program question is checked before the student sees it:** the model's own solution is run against its own
hidden tests, and if it fails the question is rewritten once, then replaced by a multiple-choice one that says so. A multiple-choice
question's code is run too, in the language it declares. The language and version are picked in the sandbox panel only and never change
what a lesson is about. If Docker or an image is missing, everything but running code still works: program questions become multiple choice
and the page says why, with the `docker pull` line.

**Accounts, the streak and the dashboard.** A student signs in with a name and a password (hashed with scrypt). A sign-in is a random token
in an `HttpOnly` cookie, five wrong passwords in 15 minutes lock a name for a minute, and every session and document belongs to its owner.
A name used before accounts existed is locked, so nobody can take over its progress. The 🔥 streak and a year-long heatmap are worked out
from records that already exist (answered questions and code runs), in the student's own timezone. The **Dashboard** tab on the start screen
shows each topic studied, newest first, and which of its parts are completed: *Got it*, *Learning*, *Review due* or *New*, from the twin. A
topic whose final check was passed stays *Learnt*, with a count of how many of its ideas have since faded.

**The page.** Lessons are chat messages with cards for the check, a diagram when one helps, feedback and the end of the session. Feedback
appears the moment an answer is sent, while the next lesson is still being written, and a status line changes every few seconds so a wait
does not read as stuck. A session has three views, Study, Twin and Route, and a side panel shows the route, the ideas being watched, the
documents and the code sandbox. The start screen has two tabs, Learn and Dashboard. It works on a phone and in dark mode.

**What never reaches the browser:** the correct option, the wrong-belief tags, everything a written answer is graded against, and the
hidden tests and model solutions of program questions. Tests pin this.

## Measured results

Measured on 19 September, before the sandbox and guided mode. These timings have not been re-measured since.

| what | before | after | how it was measured |
|---|---|---|---|
| Time per lesson | median **55 s**, up to 84 s | **10-25 s**; 7.7-7.9 s for a multiple-choice lesson from either source | timestamps in `run.db` from 12 real lessons; then timed live calls |
| Tokens per lesson | about **6,500** | about **1,400-1,600** | run counters |
| Valid lesson JSON on the first try | **0 of 2** | **6 of 6**; written questions **0 of 3 → 3 of 3** | the real request, parsed by the real schema |
| Grading a typed answer | not measured | **3.1 s** | one live call |
| Does "documents" separate covered from uncovered topics? | not measured | covered 0.59-0.71; unrelated 0.96 and up; same-subject-but-uncovered 0.76-1.00 (overlaps) | embedding distance on the sample notes; cutoff set at 0.80 |

Measured since, on 20 September:

| what | result | how it was measured |
|---|---|---|
| Tests | **493**. With no key and no Docker: **450 pass, 43 skip** (40 need Docker, 3 need a live key) | `python -m pytest`, run with `OPENROUTER_API_KEY` empty and Docker hidden from `PATH` |
| Sandbox isolation | Contained in real Docker: a program that tries the network, writes outside its scratch area, forks without end, allocates without end, or prints 20 MB | `tests/test_tutor_runtimes.py` (37 tests), run here against Python 3.12 and 3.9, Node 22, Java 21 and gcc 14 |
| Model-written program questions | Java 21, C++17, JavaScript 22 and Python 3.12: in each, the model's own solution passed its own hidden tests in the real sandbox, and the untouched starter did not | two live checks (6 and 5 requests) to one free-tier model |
| Runtime image size | one version per language: about **3.4 GB on disk** (`gcc:14` 2.15 GB, Java 21 726 MB, Node 22 329 MB, Python 3.12 179 MB); every version, roughly 6 GB, **estimated** (not all pulled) | `docker image ls` on this machine |
| A part of a topic keeps the language typed | With the student's words passed to a part, a language-neutral part came back in C++. Without them the same part came back language-neutral, not Python: the exact symptom was **not reproduced** in that one sample | 9 live requests in all: 6 in a first check whose control proved nothing (see below), 3 in the corrected one |
| Interface behaviour | Dashboard tab, the Strata name, the rotating message, and the always-available switch checked in a real browser: tabs and switches on screen and not covered, no sideways scroll at 390 px, light and dark | scripted server with 8-second lessons and a fake sandbox, so **no model calls** |

## Feedback from outside users, and what we changed

People outside the team have tried the tutor and suggested changes. Three are named here. The team has not recorded a total beyond
these three, so this report says "at least three".

| who | what they raised | what we changed | where |
|---|---|---|---|
| **Arun N M** | Tested an **early version, before the UI change** (the first server-rendered page, still at `/classic`), and asked for **UI improvements**. | The chat page (assistant-ui and shadcn) replaced the first page, with feedback shown at once and a card for each kind of step. Later: mastery as a percentage instead of a bar, and the answer controls moved inside the question so nothing covers the options. | `82ee223`, `1ebec1a`; `web/ui/` |
| **Kavin** | Suggested a **confidence level**: a way to say how sure you are of an answer. Also raised **using their own documents as the source of truth**. | A "How sure are you?" rating (just guessing, fairly sure, certain) and an "I don't know" answer, which change the score: being certain and wrong costs the most and counts double towards that wrong belief, a lucky guess proves little, and one certain right answer cannot master a topic alone. And a "Use my documents as the source of truth" switch: off by default, when on the tutor teaches only from the student's files and cites them, and says so when a topic is not in them instead of guessing. | `1ebec1a`; `732a8ef`; `demo/tutor/learner.py`, `flow.py`, `library.py`, `cards.tsx` |
| **Akileswaran** | Raised **adding documents**: it did not work on the first screen. | Fixed: a file chosen on the start screen was never added, because the handler read the file list after the input had been cleared. Reproduced in a browser, fixed, and checked end to end. Documents can also be added, listed and removed from the side panel. | `1ebec1a`, `732a8ef`; `StartScreen.tsx`, `demo/tutor/library.py` |

**How fast the loop was.** The tutor's first commit is 13:30 on 19 September 2026 (IST), so no test of it can be earlier. Every change
above was committed by 16:45 the same day: the chat page at 15:38, the source-of-truth switch at 16:24, the confidence rating and the
document fix at 16:45. So each loop from "someone tried it" to "we changed it" was **at most 3 hours 15 minutes**, and shorter for most.
That is a limit worked out from commit times, not something anyone timed, and the team should confirm the actual times.

**What surprised us.** A tester chose **kho kho** as their interest. Interests are free text and only shape the analogies; they never
affect grading. The examples we had put on the start screen and used while building were football and chess, so this is a case we had
not tried ourselves. We have not recorded how the analogy turned out.

**What we did not do about their feedback.** No suggestion the named testers made was turned down: all four (UI improvements, the
confidence level, adding documents, documents as the source of truth) were built. What is missing is follow-up, not features:

- The repository holds no record of a second round: nothing shows these people using the changed version.
- The confidence weights (0.3 / 0.5 / 0.6 for a right answer, 0.7 / 0.5 / 0.3 for a wrong one) are our guesses. Nothing compares what
  students say about their confidence with how they actually do.
- Documents have only been tried with the three sample notes and a synthetic PDF, not with a real teacher's PDF or slides.

**Did it help?** What a tester can do now that they could not before, taken from the code and not from watching anyone:

- Say how sure they are, and have that change the result. Say "I don't know" without it being recorded as a wrong belief.
- Add their own documents from the first screen, and choose whether the tutor may teach only from them.
- See whether they were right the moment they answer, and see which wrong idea an answer points to.

**We have not measured whether anyone learned more.** There is no before-and-after test and no comparison with a plain chat assistant,
so this section shows that testers were heard and the tool changed quickly, not that it improved their results. A quick way to get real
evidence is: ask a tester three questions on a topic cold, let them use the tutor for about 15 minutes on it, then ask three different
questions on the same topic, and note both scores and what they said.

The suggestion the team has raised since is depth: questions felt too simple and a session ended after a couple of right answers. That has
since been built as guided mode (see "What works today"). We have not put it in front of the same testers.

## What went wrong, and what we found

This is the useful part.

**On 19 September**

- **Lessons were slow because of us, not the model.** The configured model is a reasoning model and spent its token budget thinking
  (1,143 of 1,200 tokens in one run, then returned nothing). Separately, our prompt never named the JSON keys, so models invented their own,
  each lesson failed validation, and cost a repair call plus a fallback call. Fix: the prompts now show the exact JSON shape, and
  `complete(reasoning=False)` is an opt-in argument.
- **The fallback model could not rescue anything.** With `json_object` mode it answered `[1]` in one second.
- **A written question went under the wrong key.** The model put it under `quiz` (its natural word) on 3 of 3 tries until the prompt said,
  loudly, that `quiz` must be null. Same class of mistake as above.
- **A quiz referred to "the following code" with no code shown.** The schema now rejects that and carries the code separately.
- **Bad diagrams showed an error graphic.** The page now checks a diagram parses first and drops it silently if not.
- **Bugs found by looking at screenshots, not tests:** new lessons landed mid-page; the quiz card lost its options when the "own words"
  switch was flipped; citations showed an internal file prefix; "Ideas to watch" listed a belief twice.
- **A file chosen on the start screen was never added.** The handler read the file list after the input had been cleared. Reproduced in a
  browser, fixed, then verified end to end.
- **We told you the built UI was committed. It was not.** Vite's own `.gitignore` ignored `web/ui/dist`, so a fresh clone had no app.
  Found while committing the next change. The test now asks git what is tracked, and it failed before the fix.
- **Design reversals, on purpose.** "Teach only from the teacher's notes" was our first rule; you changed it to a student's choice, so we
  removed the teacher-question path. "Answer in text" first only changed how the current question was answered; it now sets the type of the
  next one.

**On 20 September, building the sandbox, sign-in and dashboard**

- **The sandbox first leaked its own hidden test inputs.** A student's program could read the per-run token and the hidden inputs from its
  environment. They are now removed before the program starts. One related gap remains (see below).
- **Code in a question was checked as Python for every language.** A Java or C++ question would have been rejected twice and skipped. Now
  the question declares the language of its code and it is run in that language; for a language we cannot run (SQL, HTML) it is shown
  unchecked.
- **The language was put in the wrong place, then moved.** First built as a Language and Version choice on the start screen and in every
  lesson prompt. But Strata teaches any topic, and four languages are only what the sandbox can run, so it moved into the code sandbox
  only; lessons follow the topic.
- **The parts of a guided topic lost the language the student typed.** "inheritance in C++" was split into ids like `virtual-functions`,
  and the model, seeing only the id, fell back to Python. The student's own words now travel with every part. Our first check proved
  nothing (virtual functions is a C++ idea, so it came back in C++ anyway); we redid it on a language-neutral part, where the symptom did
  not reproduce either, so the fix rests on the mechanism and the tests, not on a before-and-after.
- **A topic passed three days ago read "Review due" instead of "Learnt".** On the dashboard its mastery had faded just under the bar. A
  topic whose final check was passed now stays Learnt, and how many of its ideas have faded is shown separately.
- **The Codespace had no Docker**, so the sandbox said "Docker is not installed" there. The dev container now installs Docker and pulls
  the runtime images (`b52b4c9`). That fix has not been run in a real Codespace.
- **Claims that were wrong.** Three older Docker tests failed instead of skipping when Docker was missing, so "the tests need no Docker"
  was untrue on a fresh clone; they skip now. And the runtime images were written up as "about 1.5 GB" without being measured; measured,
  one version per language is about 3.4 GB on disk.

## Not done, or not verified

- **Outside-user evidence is real but thin.** Outside users have tried it (see "Feedback from outside users" above; three are named), and the
  rubric gives real users as much weight as the build (35 of 100). What is missing is a second round with the same people, and any measure
  of whether they learned more. The repository holds no record of an outside tester using anything built since 19 September (guided mode,
  the sandbox, sign-in, the dashboard).
- **`PRE-EVENT-ASSETS.md`** (required by the event rules) exists now, but it was not the first commit, and it has `TODO(team)` lines that
  only the team can answer (who wrote the sample notes, when the event started, where the repository came from).
- **Codespaces:** the Docker setup for the sandbox has not been run in a real Codespace, and the Codespace uses Python 3.12 where we ran on
  3.14. Two risks: the Docker inside it may not support one of the sandbox's resource limits (the sandbox's own check would then keep it
  off, with a stated reason), and Docker Hub may rate-limit the image downloads.
- **Only 5 of the 17 language versions have run against a real image:** Python 3.12 and 3.9, Node 22, Java 21 and C++17. The others rest on the
  same code and tests with a fake runner.
- **Sandbox limits.** A program running as the same user can still read `/proc/1/environ`, so a determined student could read the hidden
  test inputs. Programs are one file, with no interactive input. Each runtime image has to be pulled once (`scripts/pull_runtimes.py`).
- **The mastery constants are guesses:** the 75% bar, the two-week fading and the confidence weights are not calibrated on real students.
- **Mastery is shared across languages,** so an idea learnt in Python counts under the same idea in Java. Per-language mastery is not built.
- **Mostly tested on programming topics.** The prompts are subject-neutral and a live check on "photosynthesis" produced a clean lesson and
  plan, but nearly all our use has been programming.
- **Real teacher PDFs:** only a synthetic PDF is tested. **Free-tier rate limits:** latency was measured, limits were not. **Diagrams
  offline:** Mermaid loads from a CDN, so a diagram needs internet.
- **General-knowledge lessons cannot be checked** against anything. They carry a visible label and an instruction to leave out what the
  model is unsure of.
- **Accounts have no email,** so a forgotten password is reset by whoever runs the server (`scripts/manage_accounts.py`).
- **Not started:** a teacher's view across students. (The sandbox, editor coach and accounts listed here on 19 September are built. The
  Dashboard tab is per student.)

## What is next

The guided mode designed on 19 September is built. What is not:

- A second round with the same testers, and a before-and-after measure of whether students learn more. The quick version (three questions
  cold, 15 minutes with the tool, three different questions) is still the cheapest real evidence.
- Calibrating the mastery bar, the fading and the confidence weights on real sessions.
- Running the Codespace Docker setup in a real Codespace and fixing what it shows.
- A view for a teacher across students, per-language mastery, and email for password reset.
- Real teacher PDFs and slides.

## How to check any of this yourself

- Tests: `python -m pytest`. It needs no key and no Docker: the tests that do skip themselves. `python -m pytest -m "not integration"`
  leaves the Docker ones out explicitly. The UI's own tests: `cd web/ui && npm test`.
- The Docker tests: `python scripts/pull_runtimes.py`, then `python -m pytest -m integration`.
- Try it: the tour in the [README](../README.md).
- The spec, including the walkthrough with real numbers: [`demo/tutor/TUTOR-SPEC.md`](../demo/tutor/TUTOR-SPEC.md).
- The rubric these claims are measured against: [`ON-THE-DAY.md`](ON-THE-DAY.md).
- The history above: `git log --format='%h %ad %s' --date=iso`.

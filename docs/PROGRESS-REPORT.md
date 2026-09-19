# Progress report: the cognitive-twin tutor

*As of commit `6c79792` on `main` (2026-09-19, 16:45). Every number here was measured or counted, and says how. Where
something is not done or not verified, it says that instead.*

## In one paragraph

A tutor for college Python students that **teaches, checks, and adapts**. It remembers what each student knows and which wrong
ideas they hold, teaches the same idea a different way after a wrong answer, and never ends a session without saying why.
By default it teaches from the AI's own knowledge, shaped by what the student already knows. If a student attaches their own
documents and switches them on, it teaches only from those and cites them. It runs as a chat page (React, shadcn,
assistant-ui) served by one Python process, with a JSON API behind it. **151 tests exist, 148 of them run with no key and no network.**

## Timeline

Everything from the tutor was committed on the same day, 2026-09-19. The kit underneath (`slice/`, the docs, `demo/smoke`) was given
to us and dates from 4 to 18 September.

| when | commit | what landed |
|---|---|---|
| 09-04 → 09-18 | `8909684` … `090662b` | The kit as provided: spine (`slice/`), docs, smoke agent, event rules. Not ours. |
| 09-19 13:30 | `6c2a1f2` | **Phase 1.** The teach → check → adapt loop for Python: learner model, multiple choice whose wrong options each name one wrong belief, teacher notes as the source, a first web page. |
| 09-19 15:00 | `db9fd7b` | **Phase 2 and the speed fix.** History used in teaching, a learners table, forgetting, PDF and Word notes, the spec. Lessons made 4-5x faster after measuring (below). |
| 09-19 15:38 | `82ee223` | **Phase 3.** The chat UI (assistant-ui, shadcn), the JSON API, background lesson generation. Old page kept at `/classic`. |
| 09-19 16:24 | `732a8ef` | **Phase 4.** Documents became the student's choice; general knowledge by default; written questions; per-student document storage. |
| 09-19 16:45 | `1ebec1a` | "I don't know", a confidence rating that changes scoring, mastery as a percentage, two bug fixes. |

`main` is pushed and matches the local copy. The last two merges are `8050f57` and `6c79792`.

## What works today

**The loop.** Code, not the model, decides what happens next. `demo/tutor/flow.py` has two steps. *Teach* picks the weakest topic,
writes one lesson and one check in a single model call, then waits for the student. *Check* reads the answer, updates the learner
model, and goes back to *Teach*: the back-edge that makes this an agent and not a lesson plan. Every stop records a reason
(`mastery`, `session_limit`, `student_left`, `skipped`, or a failure with its cause).

**What it remembers, per student** (`demo/tutor/learner.py`, `learners.py`): mastery per topic; every wrong belief it has caught and
how often; the questions already asked, so none repeat; interests, used only for analogies; whether the next question should be
written; whether their documents are the source of truth. Mastery slides back over about two weeks, so an old success comes due for review.

**Two sources of facts, never mixed silently.**
- *No documents (default):* nothing predefined. The model teaches and asks from its own knowledge, shaped by a profile built in code
  (level, wrong answers so far, the belief to aim at, interests, past questions). Every lesson is labelled "General knowledge".
- *Documents:* the student attaches PDF, Word, Markdown or text and switches on "Use my documents as the source of truth". Retrieval is
  scoped to that student's files only. Lessons cite them, and a lesson that cites nothing it was given is refused.
- *A topic missing from their documents:* the tutor says so and lets the student choose general knowledge or skip. It never guesses.

**Two kinds of question.** Multiple choice by default, where each wrong option stands for one specific wrong belief, so picking it is
the diagnosis and needs no grading call. "Answer in my own words" sets the type of the **next** question, which is then written and graded
against a rubric kept on the server. The question on screen is never converted.

**How sure the student is, and "I don't know".** Pick, say how sure you are (just guessing, fairly sure, certain), then submit; the submit
button stays locked until you have said. Confidence scales the score: a right answer moves mastery towards 100% by 0.3, 0.5 or 0.6, and a
wrong one multiplies it by 0.7, 0.5 or 0.3. A belief held with certainty counts double. "I don't know" is never graded and costs a little
(x0.85) with no belief recorded. One certain right answer cannot master a topic on its own (0.30 → 0.72, under the 0.75 bar).

**The page.** Lessons are chat messages with cards for the check, a diagram when one helps, feedback and the end of the session.
Feedback appears the moment an answer is sent, while the next lesson is still being written. A side panel shows a percentage per topic, the
documents, and the wrong ideas being watched. It works on a phone and in dark mode.

**What never reaches the browser:** the correct option, the wrong-belief tags, and everything a written answer is graded against.
Tests pin this.

## Measured results

| what | before | after | how it was measured |
|---|---|---|---|
| Time per lesson | median **55 s**, up to 84 s | **10-25 s**; 7.7-7.9 s for a multiple-choice lesson from either source | timestamps in `run.db` from 12 real lessons; then timed live calls |
| Tokens per lesson | about **6,500** | about **1,400-1,600** | run counters |
| Valid lesson JSON on the first try | **0 of 2** | **6 of 6**; written questions **0 of 3 → 3 of 3** | the real request, parsed by the real schema |
| Grading a typed answer | not measured | **3.1 s** | one live call |
| Does "documents" separate covered from uncovered topics? | not measured | covered 0.59-0.71; unrelated 0.96 and up; same-subject-but-uncovered 0.76-1.00 (overlaps) | embedding distance on the sample notes; cutoff set at 0.80 |

Tests: **151 collected, 148 run offline** with a scripted model. The three that need a key call the live provider.

## Feedback from outside users, and what we changed

People outside the team have tried the tutor and suggested changes. Three of them are named here; the team reports that more of the
suggestions came from outside users too.

| who | what they did or suggested | what we changed | where |
|---|---|---|---|
| **Arun N M** | Tested an **early version, before the UI change**: the first server-rendered page (still available at `/classic`). | Nothing is claimed as a result of this test. The chat page (assistant-ui and shadcn) came **after** it; see the UI row below for who asked for UI changes. | `82ee223` came later |
| **Kavin** | Suggested a **confidence level**: a way to say how sure you are of an answer. | A "How sure are you?" rating (just guessing, fairly sure, certain) and an "I don't know" answer. The rating changes the score: being certain and wrong costs the most and counts double towards that wrong belief, a lucky guess proves little, and one certain right answer cannot master a topic alone. | `1ebec1a`; `demo/tutor/learner.py`, `web/ui/src/components/tutor/cards.tsx` |
| **Akileswaran** | Raised **adding documents**: it did not work on the first screen. | Fixed: a file chosen on the start screen was never added, because the handler read the file list after the input had been cleared. Reproduced in a browser, fixed, and checked end to end. Documents can also be added, listed and removed from the side panel. | `1ebec1a`, `732a8ef`; `StartScreen.tsx`, `demo/tutor/library.py` |
| *TODO(team): who* | Asked to **use their documents as the source of truth**. | A "Use my documents as the source of truth" switch. Off by default: the tutor teaches from the AI's own knowledge. On: it teaches only from the student's files and cites them, and says so when a topic is not in them instead of guessing. | `732a8ef`; `demo/tutor/flow.py`, `library.py` |
| *TODO(team): who* | Asked for **UI improvements**. | The chat page replaced the first server-rendered page, with feedback shown at once and a card for each kind of step. Later: mastery as a percentage instead of a bar, and the answer controls moved inside the question so nothing covers the options. | `82ee223`, `1ebec1a`; `web/ui/` |

Details a judge will want, which we have **not** recorded here yet:

- `TODO(team)`: how many outside users in total (at least the three named above), and who they were (course, year, role).
- `TODO(team)`: when and where each tried it, and whether the team watched or they tried it alone.
- `TODO(team)`: one or two quotes in their own words, and what surprised the team.
- `TODO(team)`: who suggested the source-of-truth switch and the UI changes, and what exactly they said.
- `TODO(team)`: anything they suggested that we did **not** do, and why.
- `TODO(team)`: what they could do afterwards that they could not before (the rubric's "did it help" question).

The suggestion the team has raised since, and that the design now addresses, is depth: questions felt too simple and a session ended after
a couple of right answers. That one has not been built (see "What is next").

## What went wrong, and what we found

This is the useful part.

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

## Not done, or not verified

- **The evidence from outside users is thin in this file.** Outside users have tried it (see the next section; three are named), and the
  rubric gives real users as much weight as the build (35 of 100). What is missing is the detail a judge will ask for: how many in total,
  when, and what they said, in their words. Those are marked `TODO(team)` below. More sessions with people outside the team would strengthen this.
- **`PRE-EVENT-ASSETS.md`** (required by the event rules) did not exist at the time of writing, and the README still described the kit
  for participants rather than telling a judge how to run the tutor. Both are being written separately.
- **Codespaces:** never tested with the current UI. It uses Python 3.12; we ran on 3.14. Only port 8000 is forwarded there.
- **Real teacher PDFs:** only a synthetic PDF is tested. **Free-tier rate limits:** latency was measured, limits were not. **Diagrams
  offline:** Mermaid loads from a CDN, so a diagram needs internet.
- **General-knowledge lessons cannot be checked** against anything. They carry a visible label and an instruction to leave out what the
  model is unsure of.
- **A student is a typed name.** Anyone who types the same name sees, and can delete, that student's documents.
- **Not started:** running a student's code in a sandbox, an editor coach, a teacher dashboard, and real accounts.

## What is next

The largest complaint we have received is that questions are too simple and the session ends after a couple of right answers. A design is
written and **not built**: a *guided* mode where a request like "inheritance" (or a pasted exam question) is broken into what must be known
first (classes and objects) and the parts of the topic itself; a prerequisite is checked and explained if unknown; explanations and
quizzes are mixed, not every step a quiz; the student chooses what happens next (quiz me, an example, more detail); and a concept map,
built by code and coloured by what the student knows, shows where they are. Later topics re-check earlier ones (polymorphism re-checks
inheritance when it has faded). Build order, each step stoppable: prerequisites and explain-first; pacing and choices; depth and a final
question; then the maps. About 13 model calls for a full topic. Plan reliability on the small model gets measured first.

## How to check any of this yourself

- Tests: `python -m pytest -k "not integration"` (no key needed).
- The spec, including the walkthrough with real numbers: [`demo/tutor/TUTOR-SPEC.md`](../demo/tutor/TUTOR-SPEC.md).
- The rubric these claims are measured against: [`ON-THE-DAY.md`](ON-THE-DAY.md).
- The history above: `git log --format='%h %ad %s' --date=iso`.

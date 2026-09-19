# Pre-event assets

The event rules ([`docs/ON-THE-DAY.md`](docs/ON-THE-DAY.md), section 1) ask for a
declaration of what was brought in: prior code; prompts, agent definitions and
evaluation sets written before the event; datasets; and libraries beyond the
obvious.

This file was drafted **only** from `git log --format='%h %ad %an %s' --date=iso`
and from the files in the repository. Where the repository cannot answer, the
line says `TODO(team)` and is left for the team to fill in. Nothing here is a
guess.

Two facts about this file itself:

- The rule asks for this file to be the first commit. It was not: the first
  commit in this repository is the organisers' kit scaffold (`7100b84`, 2026-09-03).
  This file was added later. `TODO(team): say where the repository came from
  (fork, copy or clone of the organisers' kit) and when it was created.`
- Dates are as recorded in git. The kit's commits carry a US Eastern offset
  (-0400); the tutor's commits carry India Standard Time (+0530).

---

## A. The Agentic Slice Kit, as provided by the organisers

25 commits by the author recorded as "Raj", from `7100b84` (2026-09-03 17:05
+0000, "Scaffold the agentic slice kit") to `090662b` (2026-09-18 19:43 -0400,
"Finish ON-THE-DAY: the Day 1 rules, the rubric and the demo").

`TODO(team): confirm that these 25 commits are the kit exactly as the organisers
handed it out, and that nothing in them is the team's own work.`

What is in the tree at `090662b` (`git ls-tree -r 090662b`):

| Path | What it is |
|---|---|
| `slice/` (`records`, `store`, `config`, `budget`, `llm`, `retrieve`, `callback`, `runner`) | The kit's spine: run state, model calls, retrieval, human callbacks. |
| `web/expert.py` | The kit's expert callback form. |
| `demo/smoke/`, `demo/SPEC-SAMPLE.md`, `scripts/smoke.py` | The kit's smoke-test agent and a sample spec. |
| `scripts/` (`doctor.py`, `bakeoff.py`, `sync_architecture.py`) | Environment check, model bake-off, architecture sync. |
| `tests/` (`test_architecture`, `test_budget`, `test_callback`, `test_integration`, `test_runner`, `test_smoke`, `test_store`) | The kit's tests. |
| `docs/` (`ARCHITECTURE`, `BUILDER`, `DESIGNER`, `ON-THE-DAY`, `PRINCIPLES-BRIEF`, `SPEC-TEMPLATE`, `VERIFIER`, `PREP for AGENT-A-THON`, `One Dinner Four Kitchens.pdf`) | The kit's guides. |
| `corpus/` (`README.md` and six `.md` notes on founders and AI capability) | The kit's example corpus for its own demo agent. |
| `.devcontainer/`, `.env.example`, `.gitignore`, `pytest.ini`, `README.md` | Environment and configuration. |
| `requirements.txt` | Six direct dependencies: pydantic, httpx, sqlite-vec, fastembed, fastapi, uvicorn (plus pytest for development). |

The kit's `.env.example` names the models used (`inclusionai/ling-3.0-flash`,
fallback `mistralai/mistral-small-3.2-24b-instruct`, escalation
`anthropic/claude-haiku-4.5`), reached through OpenRouter. The tutor uses the
kit's model settings and does not change them.

The kit's commits carry a `Co-Authored-By` trailer naming an AI model
(`7100b84`: Claude Opus 5).

---

## B. Everything added after the kit

7 commits by the author recorded as "Harish", all on 2026-09-19, India Standard
Time. This is the team's work on top of the kit.

| Commit | Date (git) | What it added |
|---|---|---|
| `6c2a1f2` | 2026-09-19 13:30 +0530 | The tutor: `demo/tutor/` (`flow.py`, `learner.py`, `schema.py`, `session.py`, `stub.py`, first `prompts/teach.md` and `prompts/grade.md`), the first server-rendered page `web/student.py`, `corpus/python/` sample notes (3 files), `tests/test_tutor.py`, `tests/test_tutor_web.py`, 2 dependencies added to `requirements.txt`. |
| `db9fd7b` | 2026-09-19 15:00 +0530 | `demo/tutor/learners.py`, `notes.py` (PDF and Word conversion), `TUTOR-SPEC.md`; hardening; `reasoning=False` option in `slice/llm.py`. |
| `82ee223` | 2026-09-19 15:38 +0530 | The chat UI in `web/ui/` (source and built files) and the JSON API `web/tutor_api.py`; the first page moved to `/classic`. |
| `8050f57` | 2026-09-19 15:39 +0530 | Merge of the tutor branches. |
| `732a8ef` | 2026-09-19 16:24 +0530 | Documents opt-in; `demo/tutor/library.py`; `prompts/source_docs.md`, `source_general.md`, `format_mcq.md`, `format_open.md`; written questions. |
| `1ebec1a` | 2026-09-19 16:45 +0530 | "I don't know" and the confidence rating; percentages; the start-screen file fix; the built UI made tracked in `web/ui/dist/`. |
| `6c79792` | 2026-09-19 16:45 +0530 | Merge of the `tutor-modes` branch into `main`. |

Also added by these commits: `tests/test_tutor*.py`, `tests/test_llm_reasoning.py`
(offline tests, no key), and this file.

Edits to files that came from the kit:

- `slice/llm.py`: an opt-in `reasoning` argument on `complete()` (`6c2a1f2`,
  `db9fd7b`). No other file in `slice/` changed.
- `web/expert.py`: the expert page hides student quiz questions (`6c2a1f2`).
- `docs/ARCHITECTURE.md`: line references re-synced after the `llm.py` edit.
- `requirements.txt`: added `python-multipart` and `pypdf`.
- `.gitignore`: added `corpus/**/.converted/`, `web/ui/node_modules/`, `uploads/`.
- `README.md`: a judge-facing section placed above the kit's participant guide.

The tutor commits carry a `Co-Authored-By: Claude Sonnet 5` trailer, meaning the
code and prompts in section B were written with an AI assistant.

### What the repository cannot tell us

- `TODO(team): whether any code, prompt, agent definition or evaluation set in
  section B was written before the event began, or brought from a previous
  project. The first tutor commit is 2026-09-19 13:30 +0530; git does not show
  what existed on anyone's machine before that.`
- `TODO(team): the event's actual start time, to compare with the commit times.`
- `TODO(team): who wrote the three sample notes in corpus/python/ (mutable-defaults.md,
  is-vs-equals.md, list-slicing.md), or where they were taken from.`
- `TODO(team): the names of the team members behind the git author "Harish".`
- `TODO(team): any prior code, prompts or datasets from earlier projects, if there
  are any. If there are none, say so.`

---

## C. Data used

| Item | Where | Note |
|---|---|---|
| Sample teacher notes | `corpus/python/*.md` (3 files) | Added in `6c2a1f2`. Used by the "Try sample notes" button. Authorship: see the TODO above. |
| Kit corpus | `corpus/*.md` | Part of the kit (section A). Not used by the tutor. |
| Embedding model | Downloaded at run time from Hugging Face by `fastembed`: `BAAI/bge-small-en-v1.5` | Named in the kit's `slice/retrieve.py` and `.devcontainer/Dockerfile`. About 65 MB, downloaded on the first document upload (measured). |
| Fonts | `web/ui/dist/assets/*.woff2` | Geist variable font, from the `@fontsource-variable/geist` package, bundled in the built UI. |

No other datasets and no evaluation sets were found in the repository. The kit's
`scripts/bakeoff.py` is a model comparison script from section A.

---

## D. Libraries beyond the obvious

**Python** (`requirements.txt`)

| Library | For | From |
|---|---|---|
| pydantic, httpx, sqlite-vec, fastembed, fastapi, uvicorn | Typed records, model calls, vector search in the run database, local embeddings, the web server | The kit (section A) |
| python-multipart | Reading file uploads and form posts | Added after the kit (`6c2a1f2`) |
| pypdf | Reading teacher notes supplied as PDF | Added after the kit (`db9fd7b`) |
| pytest | Tests | The kit |

Word (`.docx`) notes are read with the standard library (`zipfile`, `xml.etree`),
not a separate library (`demo/tutor/notes.py`).

**Front end** (`web/ui/package.json`; all added after the kit, in `82ee223` unless noted)

| Library | For |
|---|---|
| React 19 (`react`, `react-dom`) | The page |
| Vite 8, `@vitejs/plugin-react`, TypeScript | Building the page into `web/ui/dist/` |
| Tailwind CSS 4 (`tailwindcss`, `@tailwindcss/vite`), `tw-animate-css`, `tw-shimmer` | Styling and animation |
| shadcn/ui (`shadcn`, components in `web/ui/src/components/ui/`), `radix-ui`, `@base-ui/react`, `class-variance-authority`, `cn`, `lucide-react` | Buttons, cards, switches, badges, icons |
| assistant-ui (`@assistant-ui/react`, `@assistant-ui/react-markdown`), `remark-gfm`, `zustand` | The chat thread and rendering lesson text |
| `@fontsource-variable/geist` | The font |
| oxlint | Linting (development only) |

**Loaded at run time from the internet**

- Mermaid 11, from `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`,
  only when a lesson contains a diagram (`web/ui/src/components/tutor/cards.tsx`
  and the classic page in `web/student.py`). It is not in the repository.
- The Hugging Face model download above.

**Not in the repository:** Playwright. Nothing in the repo uses it. (Commit
`82ee223` says the page was "verified in a real browser"; the repository does not
say which tool was used. `TODO(team): name it if it should be declared.`)

**Services:** OpenRouter (the model API), with the models named in `.env.example`.
Langfuse tracing is optional in the kit and off unless keys are set.

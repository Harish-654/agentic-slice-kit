"""The teach -> check -> adapt loop.

DRAFTING teaches and sets a check, then suspends on the student.
GATING reads the student's answer, updates the learner model, and hands back to
DRAFTING: the back-edge that makes this an agent rather than a lesson plan.

Where a lesson's facts come from is the student's choice. By default the model
teaches from its own knowledge, shaped by what the student already knows. If they
attached documents and switched "use my documents" on, it teaches only from those,
cites them, and says so when they do not cover the topic.

The rules that decide what happens next are in learner.py and here, in code.
The model writes a lesson and, for typed answers, judges one. Nothing more.

Nothing in slice/ changes for this to run.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

from slice import callback
from slice.llm import SchemaFailure, Truncated, complete
from slice.records import RunState

from . import coach, curriculum, learner, learners, library, sandbox, steps
from .schema import Grade, LearnerModel, Lesson, OpenQuestion, PlanDraft, Probe

STUDENT_WAIT_MINUTES = 24 * 60
"""A student who steps away for a meal has not abandoned the lesson. The kit's
default wait is minutes, sized for an expert on call."""

KIND_QUIZ, KIND_GAP, KIND_CHOICE = "student_quiz", "doc_gap", "step_choice"

_PROMPTS = Path(__file__).parent / "prompts"
FORMATS = {"mcq": "format_mcq", "text": "format_open", "code": "format_code"}
KINDS = {"mcq": "multiple-choice", "text": "written", "code": "program"}
PROBE_TRIES = 2                 # a probe whose code will not run gets one retry, then is skipped
# What a student asks for when they want more of a lesson instead of the quiz.
FOCUS = {"example": "a NEW worked example of the same idea, different from anything already shown",
         "more_detail": "the same idea explained in more detail, one step at a time",
         "deeper": "a deeper look: what the idea really means, subtle cases, and how it connects to other ideas"}


def _prompt(*names: str) -> str:
    return "".join((_PROMPTS / f"{n}.md").read_text(encoding="utf-8") for n in names)


def _notes(chunks) -> str:
    return "\n\n".join(f"[{c.cite()}]\n{c.text}" for c in chunks)


def build_teach_messages(concept, style, source, want, profile, misconception,
                         recent: bool = True, notes: str = "", focus: str | None = None) -> list[dict]:
    """`source` is "general" or "docs"; `want` is "mcq", "text" (an open question) or "code".
    `focus` is what a guided student asked for instead of the quiz (a key of FOCUS)."""
    system = _prompt("teach", f"source_{source}", FORMATS[want])
    user = [f"TOPIC: {concept}", f"STYLE: {style}", "STUDENT PROFILE:\n" + profile]
    if focus:
        user.append("THE STUDENT ASKED FOR: " + FOCUS[focus])
    if misconception:
        when = "the student just chose" if recent else "this student held in an earlier session on this topic"
        user.append(f"MISCONCEPTION {when}: {misconception}")
    if source == "docs":
        user.append("NOTES:\n\n" + notes)
    return [{"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user)}]


def build_grade_messages(open_q: dict, answer: str, notes: str) -> list[dict]:
    parts = [f"QUESTION: {open_q['question']}"]
    if open_q.get("code"):
        parts.append("CODE:\n" + open_q["code"])
    parts.append("RUBRIC:\n" + "\n".join(f"- {r}" for r in open_q["rubric"]))
    parts.append("MODEL ANSWER: " + open_q["model_answer"])
    if open_q["common_mistakes"]:
        parts.append("COMMON MISTAKES:\n" + "\n".join(f"- {m['belief']}: {m['sign']}"
                                                       for m in open_q["common_mistakes"]))
    parts.append(f"STUDENT ANSWER: {answer}")
    if notes:
        parts.append("NOTES:\n\n" + notes)
    return [{"role": "system", "content": _prompt("grade")},
            {"role": "user", "content": "\n\n".join(parts)}]


def build_plan_messages(seed: str, is_exam: bool, known: list[str]) -> list[dict]:
    user = [f"{'EXAM QUESTION' if is_exam else 'TOPIC'}: {seed}",
            "KNOWN CONCEPTS (reuse these ids when they mean the same thing): " + (", ".join(known) or "none")]
    return [{"role": "system", "content": _prompt("plan")},
            {"role": "user", "content": "\n\n".join(user)}]


def build_probe_messages(concept: str, profile: str, problem: str | None = None) -> list[dict]:
    user = f"TOPIC: {concept}\n\nSTUDENT PROFILE:\n{profile}"
    if problem:
        user += ("\n\nYOUR PREVIOUS QUESTION WAS REJECTED: when its `code` was run it failed with:\n"
                 f"{problem}\nWrite a different question whose `code` runs cleanly.")
    return [{"role": "system", "content": _prompt("probe")},
            {"role": "user", "content": user}]


def build_final_messages(target: str, parts: list[str], exam: str | None, profile: str) -> list[dict]:
    user = [f"TOPIC: {target}", "PARTS OF THE TOPIC: " + (", ".join(parts) or "the topic as a whole"),
            "STUDENT PROFILE:\n" + profile]
    if exam:
        user.append("EXAM QUESTION (it will be shown to the student exactly as written; "
                    "write the rubric, model answer and common mistakes for it): " + exam)
    return [{"role": "system", "content": _prompt("final")},
            {"role": "user", "content": "\n\n".join(user)}]


def build_flow(call=complete, find=library.search, run=sandbox.run, ready=sandbox.available):
    """`call` and `find` are injected so the whole loop runs offline: no key, no
    network, no embedding model. See demo/tutor/stub.py. `find(store, student,
    query)` returns the student's own chunks relevant to the query. `run` executes
    a student's program and `ready()` says whether it may (see sandbox.py)."""

    def _model(ctx) -> LearnerModel:
        return LearnerModel.model_validate(ctx.latest("learner_model"))

    def _end(ctx, reason: str) -> RunState:
        ctx.append("session_end", {"reason": reason}, produced_by="system")
        return RunState.COMPLETE

    def _fail(ctx, kind: str, detail: str) -> RunState:
        ctx.append("failure", {"kind": kind, "detail": detail}, produced_by="system")
        return RunState.FAILED

    def _history(ctx, model, concept) -> tuple[int, str | None, bool]:
        """Wrong answers on this concept, this session AND earlier ones, and the
        belief to aim at. The model already holds this session's count
        (apply_check updates it each turn), so it is the single source: adding
        the history too would count every wrong answer twice. A belief chosen
        this session beats one carried over, and is worded as "just chose"."""
        wrong, held = learner.carried(model, concept)
        now = [c.payload["misconception"] for c in ctx.history("check")
               if c.payload["concept"] == concept and not c.payload["correct"]
               and c.payload["misconception"]]
        return (wrong, now[-1], True) if now else (wrong, held, False)

    def _gap(ctx, concept) -> str | None:
        """What the student chose when their documents did not cover `concept`:
        "general", "skip", or None if they were never asked. An unanswered
        question that timed out counts as a skip: nobody replied is not consent."""
        asked = [v.payload["id"] for v in ctx.history("question")
                 if v.payload["context"].get("kind") == KIND_GAP
                 and v.payload["context"]["concept"] == concept]
        answers = {v.payload["question_id"]: v.payload["answer"]
                   for v in ctx.history("expert_answer") if v.payload.get("question_id")}
        for qid in reversed(asked):
            if qid in answers:
                return answers[qid] or "skip"
        return None

    def _doc_gap(ctx, concept) -> RunState:
        callback.ask(ctx.store, ctx.run_id,
                     f"Your documents do not cover {concept!r}.",
                     {"kind": KIND_GAP, "concept": concept,
                      "resume_state": RunState.DRAFTING.value},
                     dataclasses.replace(ctx.settings, expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def _ensure_plan(ctx, model, inp):
        """Guided runs only. Work out once what the topic builds on, and record it on the run
        (the `input` gains a `plan` and its concepts become prerequisites then target). A plan
        the student already has is reused; a failed plan call just means no prerequisites."""
        if "plan" in inp:
            return model, inp
        exam, typed = inp.get("exam_question"), inp["concepts"][0]
        known = list(model.mastery)
        plan = None if exam else model.plans.get(curriculum.key(typed))
        target = typed
        if plan is None:
            degraded = False
            try:
                draft = call(settings=ctx.settings, budget=ctx.budget,
                             messages=build_plan_messages(exam or typed, bool(exam), known),
                             schema=PlanDraft, step="plan", reasoning=False)
            except (SchemaFailure, Truncated):
                draft, degraded = PlanDraft(), True
            if exam:
                target = (curriculum.resolve(draft.target, known) if draft.target
                          else learner.slug(" ".join(exam.split()[:4]))) or "exam-question"
            plan = curriculum.clean_plan(draft, target, known)
            if not degraded and not exam:               # a topic's plan is the same next time
                model = model.model_copy(update={"plans": {**model.plans, curriculum.key(typed): plan}})
                ctx.append("learner_model", model.model_dump(), produced_by="system")
                learners.save(ctx.store, model)
            plan = plan | {"degraded": degraded}
        plan = {"target": target, **plan}
        inp = {**inp, "concepts": [*plan["prereqs"], *plan["subtopics"], target], "plan": plan}
        ctx.append("input", inp, produced_by="agent:plan")
        return model, inp

    def _probe(ctx, model, concept) -> RunState | None:
        """Ask about a prerequisite before explaining it. The question is stored as a lesson with
        no teaching in it, so the page and the grader treat it like any other check.

        Any code in the question is run in the sandbox first: a question about code that does not
        run is worse than no question. One retry, with the failure fed back; after that the probe
        is given up (None) and the prerequisite is simply taught. This check is about quality,
        not safety, so it is skipped when the sandbox is off rather than blocking the probe."""
        problem = None
        for _ in range(PROBE_TRIES):
            got = call(settings=ctx.settings, budget=ctx.budget,
                       messages=build_probe_messages(concept, learner.profile(model, concept), problem),
                       schema=Probe, step="probe", reasoning=False)
            problem = (coach.question_code_problem(got.quiz.model_dump(), run)
                       if got.quiz.code and ready()[0] else None)
            if problem is None:
                break
            ctx.append("probe_rejected", {"concept": concept, "problem": problem}, produced_by="system")
        else:
            ctx.append("probe_skipped", {"concept": concept}, produced_by="system")
            return None
        label = concept.replace("-", " ")
        ctx.append("lesson", {"covered": True, "citations": [], "diagram": None, "open": None,
                              "code_task": None, "quiz": got.quiz.model_dump(),
                              "explanation": f"First, a quick check on **{label}**, which this topic builds on.",
                              "concept": concept, "style": "probe", "source": "general",
                              "notes": "", "probe": True}, produced_by="agent:probe")
        callback.ask(ctx.store, ctx.run_id, got.quiz.question,
                     {"kind": KIND_QUIZ, "concept": concept, "resume_state": RunState.GATING.value},
                     dataclasses.replace(ctx.settings, expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def _explains_in_row(ctx) -> int:
        """Held explanations since the student last saw a check: the cap on how long the
        tutor can keep explaining before it must let them be asked something."""
        n = 0
        for v in reversed(ctx.store.replay(ctx.run_id)):
            if v.kind in ("reveal", "check", "topic_skipped"):
                break
            if v.kind == "lesson" and v.payload.get("held"):
                n += 1
        return n

    def _ask_choice(ctx, concept) -> RunState:
        """After an explanation, hand the student the wheel. The check is already written and held
        back, so "quiz me" costs no model call."""
        callback.ask(ctx.store, ctx.run_id, "What would you like to do next?",
                     {"kind": KIND_CHOICE, "concept": concept,
                      "options": steps.choices(_explains_in_row(ctx)),
                      "resume_state": RunState.DRAFTING.value},
                     dataclasses.replace(ctx.settings, expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def _reveal(ctx, concept) -> RunState:
        """Show the check that was held back with the last explanation. No model call."""
        lesson = ctx.latest("lesson")
        ctx.append("reveal", {"concept": concept}, produced_by="system")
        callback.ask(ctx.store, ctx.run_id, (lesson["quiz"] or lesson["open"] or lesson["code_task"])["question"],
                     {"kind": KIND_QUIZ, "concept": concept, "resume_state": RunState.GATING.value},
                     dataclasses.replace(ctx.settings, expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def _resumed_by_choice(ctx):
        """None when this DRAFTING is not the answer to a "what next?" question. Otherwise
        (choice, concept), or ("left", None) if nobody answered in time."""
        last = ctx.store.replay(ctx.run_id)[-1]
        if last.kind != "expert_answer":
            return None
        ask = next((q.payload for q in ctx.history("question")
                    if q.payload["id"] == last.payload.get("question_id")), None)
        if not ask or ask["context"].get("kind") != KIND_CHOICE:
            return None
        if last.payload.get("who") != "student_choice":
            return "left", None
        return last.payload["answer"], ask["context"]["concept"]

    def _final(ctx, model, inp) -> RunState:
        """The last check on the whole topic: one written question, graded against a rubric. A pasted
        exam question is used word for word, and the model only writes how to grade it."""
        plan, exam = inp["plan"], inp.get("exam_question")
        target = plan["target"]
        q = call(settings=ctx.settings, budget=ctx.budget,
                 messages=build_final_messages(target, plan["subtopics"], exam, learner.profile(model, target)),
                 schema=OpenQuestion, step="final", reasoning=False)
        if exam:
            q = q.model_copy(update={"question": exam})
        ctx.append("lesson", {"covered": True, "citations": [], "diagram": None, "quiz": None,
                              "code_task": None, "open": q.model_dump(),
                              "explanation": f"**Final check** on {target.replace('-', ' ')}. "
                                             "Answer in your own words, using what you have learned.",
                              "concept": target, "style": "final", "source": "general",
                              "notes": "", "final": True}, produced_by="agent:final")
        callback.ask(ctx.store, ctx.run_id, q.question,
                     {"kind": KIND_QUIZ, "concept": target, "resume_state": RunState.GATING.value},
                     dataclasses.replace(ctx.settings, expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def handle_drafting(ctx) -> RunState:
        model = _model(ctx)
        inp = ctx.latest("input")
        action, focus, held = "teach", None, False

        if inp.get("mode") == "guided":
            model, inp = _ensure_plan(ctx, model, inp)
            held = True                       # guided explanations wait for the student's choice
            skipped = ({c for c in inp["concepts"] if _gap(ctx, c) == "skip"}
                       | {v.payload["concept"] for v in ctx.history("topic_skipped")})
            resumed = _resumed_by_choice(ctx)
            if resumed:
                choice, concept = resumed
                if choice == "left":
                    return _end(ctx, "student_left")
                if choice == "stop":
                    return _end(ctx, "student_stopped")
                if choice == "quiz":
                    return _reveal(ctx, concept)
                if choice == "skip":
                    ctx.append("topic_skipped", {"concept": concept}, produced_by="system")
                    skipped.add(concept)
                else:
                    focus = choice            # example / more_detail / deeper: explain again
            if focus is None:
                checks = [c.payload for c in ctx.history("check")]
                action, concept = steps.decide(
                    inp["concepts"], model, checks, skipped, probing=not model.use_docs,
                    unprobed={v.payload["concept"] for v in ctx.history("probe_skipped")},
                    subtopics=inp["plan"]["subtopics"])
                if action == "done":
                    return _end(ctx, concept)
                if len(checks) >= steps.MAX_CHECKS or len(ctx.history("lesson")) >= steps.MAX_STEPS:
                    return _end(ctx, "session_limit")
                if action == "final":
                    return _final(ctx, model, inp)
                if action == "probe":
                    asked = _probe(ctx, model, concept)
                    if asked is not None:
                        return asked
                    # no trustworthy probe could be made: teach the prerequisite instead
        else:
            skipped = {c for c in inp["concepts"] if _gap(ctx, c) == "skip"}
            concept = learner.pick_concept(model, [c for c in inp["concepts"] if c not in skipped])
            if concept is None:
                return _end(ctx, "skipped" if skipped else "mastery")
            if len(ctx.history("check")) >= learner.MAX_CHECKS:
                return _end(ctx, "session_limit")

        source, chunks = "general", []
        if model.use_docs and _gap(ctx, concept) != "general":
            chunks = find(ctx.store, inp["student_id"], concept.replace("-", " "))
            if not chunks:
                return _doc_gap(ctx, concept)
            source = "docs"

        want = model.answer_mode
        wrong, misconception, recent = _history(ctx, model, concept)
        style = "worked_example" if focus == "example" else learner.style_for(wrong)
        lesson = call(
            settings=ctx.settings, budget=ctx.budget,
            messages=build_teach_messages(concept, style, source, want,
                                          learner.profile(model, concept), misconception,
                                          recent, _notes(chunks), focus),
            schema=Lesson, step="teach", reasoning=False,
        )

        if source == "docs" and not lesson.covered:
            return _doc_gap(ctx, concept)
        if lesson.kind != want:                             # asked for one type, got another
            return _fail(ctx, "wrong_question_type",
                         f"Asked for a {KINDS[want]} question and the model wrote the other kind.")

        allowed = {c.cite() for c in chunks}
        cited = [c for c in lesson.citations if c in allowed] if source == "docs" else []
        if source == "docs" and not cited:
            return _fail(ctx, "ungrounded_lesson", "The lesson cited none of the notes it was given.")

        payload = lesson.model_dump() | {"citations": cited, "concept": concept, "style": style,
                                         "source": source, "notes": _notes(chunks)}
        if held:                              # the check is written now but shown only on "quiz me"
            payload["held"] = True
        ctx.append("lesson", payload, produced_by="agent:teach")
        if held:
            return _ask_choice(ctx, concept)

        # Suspend on the student. Waiting is a state, not this process's job.
        callback.ask(ctx.store, ctx.run_id, (lesson.quiz or lesson.open or lesson.code_task).question,
                     {"kind": KIND_QUIZ, "concept": concept,
                      "resume_state": RunState.GATING.value},
                     dataclasses.replace(ctx.settings,
                                         expert_timeout_minutes=STUDENT_WAIT_MINUTES))
        return RunState.AWAITING_EXPERT

    def handle_gating(ctx) -> RunState:
        lesson = ctx.latest("lesson")
        reply = ctx.latest("expert_answer")
        if not reply or reply.get("source") != "human_expert" or reply.get("who") != "student":
            return _end(ctx, "student_left")

        given = json.loads(reply["answer"])
        concept = lesson["concept"]
        unknown = given["mode"] == "dont_know"
        confidence = given.get("confidence")

        task = lesson.get("code_task")
        if unknown:                  # no grading call: nothing was said to grade
            correct, mis = False, None
            stem = (lesson["quiz"] or lesson["open"] or task)["question"]
            teach = (lesson["quiz"]["why"] if lesson["quiz"]
                     else "A working solution:\n" + task["model_solution"] if task
                     else "A good answer: " + lesson["open"]["model_answer"])
            feedback = "That is fine, not knowing is useful to know. " + teach
        elif task:                   # a program: run it against the hidden tests, no model call
            ok, why = ready()
            if not ok:
                return _fail(ctx, "sandbox_unavailable", "Running code is switched off here. " + why)
            g = coach.grade_program(task, given["code"], run)
            correct, mis, feedback, stem = g.correct, g.misconception, g.feedback, task["question"]
            if correct and given.get("assisted"):
                confidence = "low"   # a suggestion did part of the work, so the win counts for less
        elif lesson["quiz"]:
            quiz = lesson["quiz"]
            chosen = quiz["options"][given["choice"]]
            correct, mis = given["choice"] == quiz["correct"], chosen["misconception"]
            feedback, stem = quiz["why"], quiz["question"]
        else:
            g = call(settings=ctx.settings, budget=ctx.budget,
                     messages=build_grade_messages(lesson["open"], given["text"], lesson["notes"]),
                     schema=Grade, step="grade", reasoning=False)
            correct, mis, feedback = g.correct, g.misconception, g.feedback
            stem = lesson["open"]["question"]

        model = learner.apply_check(_model(ctx), concept, correct, mis, question=stem,
                                    confidence=confidence, dont_know=unknown)
        extra = {"probe": True} if lesson.get("probe") else {}
        if lesson.get("final"):
            extra["final"] = True
            if not correct:                   # the weakest part is what gets explained again
                parts = (ctx.latest("input").get("plan") or {}).get("subtopics") or [concept]
                extra["revisit"] = min(parts, key=lambda c: learner.effective_mastery(model, c))
        ctx.append("check", {"concept": concept, "mode": given["mode"], "correct": correct,
                             "misconception": learner.slug(mis), "feedback": feedback,
                             "confidence": confidence, "dont_know": unknown} | extra,
                   produced_by="agent:gate" if given["mode"] == "text" else "system")
        ctx.append("learner_model", model.model_dump(), produced_by="system")
        learners.save(ctx.store, model)
        return RunState.DRAFTING

    return SimpleNamespace(
        name="tutor",
        handlers={RunState.DRAFTING: handle_drafting, RunState.GATING: handle_gating},
    )

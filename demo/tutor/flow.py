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
from slice.llm import complete
from slice.records import RunState

from . import learner, learners, library
from .schema import Grade, LearnerModel, Lesson

STUDENT_WAIT_MINUTES = 24 * 60
"""A student who steps away for a meal has not abandoned the lesson. The kit's
default wait is minutes, sized for an expert on call."""

KIND_QUIZ, KIND_GAP = "student_quiz", "doc_gap"

_PROMPTS = Path(__file__).parent / "prompts"


def _prompt(*names: str) -> str:
    return "".join((_PROMPTS / f"{n}.md").read_text(encoding="utf-8") for n in names)


def _notes(chunks) -> str:
    return "\n\n".join(f"[{c.cite()}]\n{c.text}" for c in chunks)


def build_teach_messages(concept, style, source, want, profile, misconception,
                         recent: bool = True, notes: str = "") -> list[dict]:
    """`source` is "general" or "docs"; `want` is "mcq" or "text" (an open question)."""
    system = _prompt("teach", f"source_{source}", "format_mcq" if want == "mcq" else "format_open")
    user = [f"TOPIC: {concept}", f"STYLE: {style}", "STUDENT PROFILE:\n" + profile]
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


def build_flow(call=complete, find=library.search):
    """`call` and `find` are injected so the whole loop runs offline: no key, no
    network, no embedding model. See demo/tutor/stub.py. `find(store, student,
    query)` returns the student's own chunks relevant to the query."""

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

    def handle_drafting(ctx) -> RunState:
        model = _model(ctx)
        inp = ctx.latest("input")
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
        style = learner.style_for(wrong)
        lesson = call(
            settings=ctx.settings, budget=ctx.budget,
            messages=build_teach_messages(concept, style, source, want,
                                          learner.profile(model, concept), misconception,
                                          recent, _notes(chunks)),
            schema=Lesson, step="teach", reasoning=False,
        )

        if source == "docs" and not lesson.covered:
            return _doc_gap(ctx, concept)
        if (lesson.quiz is None) == (want == "mcq"):        # asked for one type, got the other
            return _fail(ctx, "wrong_question_type",
                         f"Asked for a {'multiple-choice' if want == 'mcq' else 'written'} "
                         "question and the model wrote the other kind.")

        allowed = {c.cite() for c in chunks}
        cited = [c for c in lesson.citations if c in allowed] if source == "docs" else []
        if source == "docs" and not cited:
            return _fail(ctx, "ungrounded_lesson", "The lesson cited none of the notes it was given.")

        payload = lesson.model_dump() | {"citations": cited, "concept": concept, "style": style,
                                         "source": source, "notes": _notes(chunks)}
        ctx.append("lesson", payload, produced_by="agent:teach")

        # Suspend on the student. Waiting is a state, not this process's job.
        callback.ask(ctx.store, ctx.run_id, (lesson.quiz or lesson.open).question,
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

        if unknown:                  # no grading call: nothing was said to grade
            correct, mis = False, None
            stem = (lesson["quiz"] or lesson["open"])["question"]
            teach = lesson["quiz"]["why"] if lesson["quiz"] else "A good answer: " + lesson["open"]["model_answer"]
            feedback = "That is fine, not knowing is useful to know. " + teach
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
        ctx.append("check", {"concept": concept, "mode": given["mode"], "correct": correct,
                             "misconception": learner.slug(mis), "feedback": feedback,
                             "confidence": confidence, "dont_know": unknown},
                   produced_by="agent:gate" if given["mode"] == "text" else "system")
        ctx.append("learner_model", model.model_dump(), produced_by="system")
        learners.save(ctx.store, model)
        return RunState.DRAFTING

    return SimpleNamespace(
        name="tutor",
        handlers={RunState.DRAFTING: handle_drafting, RunState.GATING: handle_gating},
    )

"""The teach -> check -> adapt loop.

DRAFTING teaches and sets a check, then suspends on the student.
GATING reads the student's answer, updates the learner model, and hands back to
DRAFTING: the back-edge that makes this an agent rather than a lesson plan.

The rules that decide what happens next are in learner.py and here, in code.
The model writes a lesson and, for free text, judges an answer. Nothing more.

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
from slice.retrieve import search

from . import learner, learners
from .schema import Grade, LearnerModel, Lesson

STUDENT_WAIT_MINUTES = 24 * 60
"""A student who steps away for a meal has not abandoned the lesson. The kit's
default wait is minutes, sized for an expert on call."""

KIND_QUIZ, KIND_TEACHER = "student_quiz", "teacher_gap"

_PROMPTS = Path(__file__).parent / "prompts"


def _prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _notes(chunks, teacher_notes) -> str:
    parts = [f"[{c.cite()}]\n{c.text}" for c in chunks]
    parts += [f"[teacher-note]\n{t}" for t in teacher_notes]
    return "\n\n".join(parts)


def build_teach_messages(concept, style, notes, interests, misconception,
                         recent: bool = True) -> list[dict]:
    user = [f"CONCEPT: {concept}", f"STYLE: {style}",
            f"INTERESTS: {', '.join(interests) or 'none known'}"]
    if misconception:
        when = "the student just chose" if recent else "this student held in an earlier session on this concept"
        user.append(f"MISCONCEPTION {when}: {misconception}")
    user.append("NOTES:\n\n" + notes)
    return [{"role": "system", "content": _prompt("teach")},
            {"role": "user", "content": "\n\n".join(user)}]


def build_grade_messages(quiz: dict, answer: str, notes: str) -> list[dict]:
    return [{"role": "system", "content": _prompt("grade")},
            {"role": "user", "content": f"QUESTION: {quiz['question']}\n\n"
                                        f"STUDENT ANSWER: {answer}\n\nNOTES:\n\n{notes}"}]


def build_flow(call=complete, find=search):
    """`call` and `find` are injected so the whole loop runs offline: no key, no
    network, no embedding model. See demo/tutor/stub.py."""

    def _model(ctx) -> LearnerModel:
        return LearnerModel.model_validate(ctx.latest("learner_model"))

    def _end(ctx, reason: str) -> RunState:
        ctx.append("session_end", {"reason": reason}, produced_by="system")
        return RunState.COMPLETE

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

    def handle_drafting(ctx) -> RunState:
        model = _model(ctx)
        concepts = ctx.latest("input")["concepts"]

        concept = learner.pick_concept(model, concepts)
        if concept is None:
            return _end(ctx, "mastery")
        if len(ctx.history("check")) >= learner.MAX_CHECKS:
            return _end(ctx, "session_limit")

        chunks = find(ctx.store, concept.replace("-", " "), k=4)
        told = [v.payload["answer"] for v in ctx.history("expert_answer")
                if v.payload.get("source") == "human_expert"
                and v.payload.get("who") != "student"]
        if not chunks and not told:
            asked = [q for q in ctx.history("question")
                     if q.payload["context"].get("kind") == KIND_TEACHER
                     and q.payload["context"].get("concept") == concept]
            if asked:                   # already asked; nobody answered
                ctx.append("failure",
                           {"kind": "no_source_material",
                            "detail": f"No course notes cover {concept!r} and the teacher "
                                      "did not answer. Not guessing from the internet."},
                           produced_by="system")
                return RunState.FAILED
            callback.ask(ctx.store, ctx.run_id,
                         f"The course notes do not cover {concept!r}. What should be "
                         "taught about it?",
                         {"kind": KIND_TEACHER, "concept": concept,
                          "resume_state": RunState.DRAFTING.value}, ctx.settings)
            return RunState.AWAITING_EXPERT

        wrong, misconception, recent = _history(ctx, model, concept)
        style = learner.style_for(wrong)
        lesson = call(
            settings=ctx.settings, budget=ctx.budget,
            messages=build_teach_messages(concept, style, _notes(chunks, told),
                                          model.interests, misconception, recent),
            schema=Lesson, step="teach", reasoning=False,
        )

        allowed = {c.cite() for c in chunks}
        cited = [c for c in lesson.citations if c in allowed]
        if not cited and not told:
            ctx.append("failure",
                       {"kind": "ungrounded_lesson",
                        "detail": "The lesson cited none of the notes it was given."},
                       produced_by="system")
            return RunState.FAILED

        payload = lesson.model_dump() | {"citations": cited, "concept": concept,
                                         "style": style, "notes": _notes(chunks, told)}
        ctx.append("lesson", payload, produced_by="agent:teach")

        # Suspend on the student. Waiting is a state, not this process's job.
        callback.ask(ctx.store, ctx.run_id, lesson.quiz.question,
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
        quiz, concept = lesson["quiz"], lesson["concept"]

        if given["mode"] == "mcq":
            chosen = quiz["options"][given["choice"]]
            correct, mis = given["choice"] == quiz["correct"], chosen["misconception"]
            feedback = quiz["why"]
        else:
            g = call(settings=ctx.settings, budget=ctx.budget,
                     messages=build_grade_messages(quiz, given["text"], lesson["notes"]),
                     schema=Grade, step="grade", reasoning=False)
            correct, mis, feedback = g.correct, g.misconception, g.feedback

        model = learner.apply_check(_model(ctx), concept, correct, mis)
        ctx.append("check", {"concept": concept, "mode": given["mode"], "correct": correct,
                             "misconception": learner.slug(mis), "feedback": feedback},
                   produced_by="agent:gate" if given["mode"] == "text" else "system")
        ctx.append("learner_model", model.model_dump(), produced_by="system")
        learners.save(ctx.store, model)
        return RunState.DRAFTING

    return SimpleNamespace(
        name="tutor",
        handlers={RunState.DRAFTING: handle_drafting, RunState.GATING: handle_gating},
    )

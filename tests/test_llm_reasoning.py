"""`reasoning=False` reaches the wire, and only when asked for."""
import json

from demo.tutor import session
from demo.tutor.stub import Stub, grade, open_lesson
from slice import llm
from slice.budget import Budget
from slice.store import Store
from tests.test_tutor import S, answer, drive


class Reply:
    status_code = 200
    def __init__(self, content): self._c = content
    def json(self): return {"choices": [{"message": {"content": self._c}, "finish_reason": "stop"}],
                            "usage": {"total_tokens": 10}}


def sent_bodies(monkeypatch, tmp_path, replies, **kw):
    bodies, it = [], iter(replies)
    monkeypatch.setattr(llm.httpx, "post", lambda url, json, **k: (bodies.append(json), Reply(next(it)))[1])
    store = Store(tmp_path / "r.db")
    from demo.tutor.schema import Grade
    llm.complete(settings=S, budget=Budget(store, store.create_run("t"), S),
                 messages=[{"role": "user", "content": "x"}], schema=Grade, **kw)
    return bodies


GOOD = json.dumps({"correct": True, "misconception": None, "feedback": "ok"})


def test_reasoning_is_switched_off_only_when_asked(monkeypatch, tmp_path):
    assert sent_bodies(monkeypatch, tmp_path, [GOOD], reasoning=False)[0]["reasoning"] == {"enabled": False}
    assert "reasoning" not in sent_bodies(monkeypatch, tmp_path, [GOOD])[0]         # default untouched
    assert "reasoning" not in sent_bodies(monkeypatch, tmp_path, [GOOD], reasoning=True)[0]


def test_the_repair_call_keeps_reasoning_off_too(monkeypatch, tmp_path):
    bodies = sent_bodies(monkeypatch, tmp_path, ["[null]", GOOD], reasoning=False)
    assert len(bodies) == 2 and all(b["reasoning"] == {"enabled": False} for b in bodies)


def test_the_tutor_asks_for_no_thinking_on_both_of_its_calls(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    session.set_answer_mode(store, run, "text")
    stub = Stub({"teach": [open_lesson("a"), open_lesson("b")], "grade": [grade(True, None)]})
    drive(store, run, stub)
    session.submit_text(store, session.open_quiz(store, run).id, "my answer")
    drive(store, run, stub)
    assert stub.calls == ["teach", "grade", "teach"] and stub.reasoning == [False, False, False]


def test_every_prompt_that_wants_json_names_its_keys():
    """Measured: without the shape, models invented their own keys and every
    lesson cost a repair call. Each format prompt must carry every key it needs."""
    from demo.tutor.flow import _prompt
    from demo.tutor.schema import Grade, Lesson, Mistake, OpenQuestion, Quiz
    mcq, text = _prompt("format_mcq"), _prompt("format_open")
    for key in [*Lesson.model_fields, *Quiz.model_fields, "misconception", "text"]:
        assert f'"{key}"' in mcq, key
    for key in [*Lesson.model_fields, *OpenQuestion.model_fields, *Mistake.model_fields]:
        assert f'"{key}"' in text, key
    # Measured: a small model put the written question under `quiz` (its natural word for
    # "the check") on 3 of 3 tries until the prompt said, loudly, that `quiz` must be null.
    assert "`quiz` is only for\nmultiple choice" in text and "MUST be `null`" in text
    for key in Grade.model_fields:
        assert f'"{key}"' in _prompt("grade"), key

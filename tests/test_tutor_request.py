"""A guided topic is split into parts whose ids have lost the language the student named ("virtual-functions"), so
without help a lesson on one part is written in Python. The student's own words travel with every part instead, and a
cached plan is reused across spellings of a topic but not across languages. The model is scripted; no Docker, no key."""
from demo.tutor import curriculum, session
from demo.tutor.flow import _prompt, build_flow, build_probe_messages, build_teach_messages
from demo.tutor.stub import Stub, lesson, plan, probe
from slice import runner
from slice.store import Store
from tests.test_tutor import RIGHT, S, find
from tests.test_tutor_guided import answer, go, guided

TYPED = "inheritance in C++"
ASKED = "THE STUDENT ASKED TO LEARN: inheritance in C++"


def user_of(messages):
    return messages[1]["content"]


# ------------------------------------------------------------------ the prompts

def test_a_part_is_told_what_the_student_asked_for_so_it_keeps_their_language():
    teach = build_teach_messages("virtual-functions", "plain", "general", "mcq", "p", None, request=TYPED)
    assert ASKED in user_of(teach) and "This topic is one part of that." in user_of(teach)
    assert user_of(teach).startswith("TOPIC: virtual-functions")           # the part is still the topic
    assert ASKED in user_of(build_probe_messages("classes-and-objects", "p", request=TYPED))


def test_the_topic_itself_and_a_quick_session_are_not_told_twice():
    same = build_teach_messages(TYPED, "plain", "general", "mcq", "p", None, request=TYPED)
    none = build_teach_messages(TYPED, "plain", "general", "mcq", "p", None)
    assert "ASKED TO LEARN" not in user_of(same) and "ASKED TO LEARN" not in user_of(none)
    assert "ASKED TO LEARN" not in user_of(build_probe_messages(TYPED, "p", request=TYPED))
    assert "ASKED TO LEARN" not in user_of(build_probe_messages(TYPED, "p"))


def test_the_prompts_say_to_use_the_language_asked_for_and_never_switch():
    teach, probe_text, final = _prompt("teach"), _prompt("probe"), _prompt("final")
    assert "THE STUDENT ASKED TO LEARN" in teach and "never switch to another" in teach and "use Python" in teach
    assert "THE STUDENT ASKED TO LEARN" in probe_text and "language it names" in probe_text
    assert "language the TOPIC names" in final


# ------------------------------------------------------------------ the flow

def test_every_part_of_a_guided_topic_is_told_what_the_student_typed(tmp_path):
    store = Store(tmp_path / "r.db")
    run = guided(store, topic=TYPED)
    stub = Stub({"plan": [plan(prereqs=("classes-and-objects",), subtopics=("virtual-functions",))],
                 "probe": [probe()], "teach": [lesson("PART")]})
    go(store, run, stub)                                                    # the plan, then a probe on the prerequisite
    assert ASKED in user_of(stub.messages[stub.calls.index("probe")])
    answer(store, run, RIGHT)
    go(store, run, stub)                                                    # known: on to the first part
    part = user_of(stub.messages[stub.calls.index("teach")])
    assert part.startswith("TOPIC: virtual-functions") and ASKED in part


def test_a_pasted_exam_question_is_what_each_part_is_told(tmp_path):
    exam = "Explain how virtual functions work in C++."
    store = Store(tmp_path / "r.db")
    run = guided(store, exam=exam, topic=None)
    stub = Stub({"plan": [plan(prereqs=(), subtopics=("virtual-functions",), target="polymorphism")],
                 "teach": [lesson("PART")]})
    go(store, run, stub)
    part = user_of(stub.messages[stub.calls.index("teach")])
    assert f"THE STUDENT ASKED TO LEARN: {exam}" in part


def test_a_quick_session_already_teaches_the_typed_topic_and_adds_nothing(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", [TYPED])
    stub = Stub({"teach": [lesson("LESSON")]})
    runner.advance(store, run, build_flow(call=stub, find=find), S)
    assert user_of(stub.messages[0]).startswith("TOPIC: inheritance in C++") and "ASKED TO LEARN" not in user_of(stub.messages[0])


# ------------------------------------------------------------------ the plan cache

def test_concept_ids_still_ignore_the_language_but_a_cached_plan_does_not():
    assert curriculum.key("inheritance in Java") == curriculum.key("inheritance in Python") == curriculum.key("Inheritance")
    assert curriculum.key("inheritance in Java", keep_language=True) != curriculum.key("inheritance in Python", keep_language=True)
    assert curriculum.key("Inheritance in Java", keep_language=True) == curriculum.key("inheritance, in java", keep_language=True)
    assert curriculum.key("Classes and objects", keep_language=True) == curriculum.key("object-classes", keep_language=True)


def test_a_plan_is_reused_for_the_same_topic_in_the_same_language_and_not_for_another(tmp_path):
    store = Store(tmp_path / "r.db")
    stub = Stub({"plan": [plan(prereqs=("classes-and-objects",), subtopics=("interfaces",))] * 3, "probe": [probe()] * 3})
    for topic in ("inheritance in Java", "inheritance in Python", "Inheritance in Java"):
        go(store, guided(store, topic=topic), stub)
    assert stub.calls.count("plan") == 2                    # Java once, Python once; the second Java reused the first plan

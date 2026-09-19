"""Phase D: the concept map, built in code from the plan and what the student knows, and the gate every
model-written diagram passes before a browser sees it. No model anywhere in these."""
import re
import time

import pytest

from demo.tutor import learner, learners, visuals
from demo.tutor.flow import _prompt
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, lesson, plan
from slice.store import Store
from tests.test_tutor_api import make, settle
from tests.test_tutor_guided import PRE, TARGET

S1, S2 = "parent-and-child", "overriding"
PLAN = {"target": TARGET, "prereqs": [PRE], "subtopics": [S1, S2]}
KINDS = ("flowchart TD", "classDiagram", "sequenceDiagram", "stateDiagram-v2")


def model(**mastery):
    """Mastery by keyword, underscores standing for hyphens, all last seen just now."""
    ids = {k.replace("_", "-"): v for k, v in mastery.items()}
    return LearnerModel(student_id="s", mastery=ids, last_seen={k: time.time() for k in ids})


NODE = re.compile(r'^  n\d+\["[^"]*"\]:::(known|shaky|unknown)$')


def edges(flow):
    return {ln.strip() for ln in flow.splitlines() if "-->" in ln}


# ------------------------------------------------------------------ the concept map

def test_the_map_colours_each_concept_by_what_the_student_knows_and_marks_the_current_one():
    m = model(classes_and_objects=0.92, parent_and_child=0.5)          # known, shaky; the rest unseen
    flow = visuals.concept_map(PLAN, m, current=S2)["flowchart"]
    assert flow.splitlines()[0] == "flowchart TD"
    assert '  n0["Classes and objects"]:::known' in flow
    assert '  n1["Parent and child"]:::shaky' in flow
    assert '  n2["Overriding"]:::unknown' in flow
    assert '  n3["Inheritance"]:::unknown' in flow
    assert "  class n2 current" in flow and flow.count("  class n") == 1
    for kind in ("known", "shaky", "unknown", "current"):
        assert f"  classDef {kind} " in flow


def test_the_map_wires_prerequisites_into_the_parts_and_the_parts_into_the_topic():
    assert edges(visuals.concept_map(PLAN, model())["flowchart"]) == {"n0 --> n1", "n0 --> n2", "n1 --> n3", "n2 --> n3"}


def test_a_plan_with_no_parts_or_no_prerequisites_still_makes_a_connected_map():
    chain = {"target": TARGET, "prereqs": ["a-one", "b-two"], "subtopics": []}
    assert edges(visuals.concept_map(chain, model())["flowchart"]) == {"n0 --> n1", "n1 --> n2"}
    parts = {"target": TARGET, "prereqs": [], "subtopics": [S1, S2]}
    assert edges(visuals.concept_map(parts, model())["flowchart"]) == {"n0 --> n2", "n1 --> n2"}
    assert edges(visuals.concept_map({"target": TARGET}, model())["flowchart"]) == set()   # one node, nothing to join


def test_hostile_concept_names_cannot_break_out_of_the_diagram():
    nasty = ["end", 'a"] --> x["b', "<script>alert(1)</script>", 'x]:::known\n  n9["y', "%%{init: {}}%%", "click n0 callback"]
    flow = visuals.concept_map({"target": "ok", "prereqs": nasty[:3], "subtopics": nasty[3:]}, model())["flowchart"]
    nodes = [ln for ln in flow.splitlines() if re.match(r"^  n\d+\[", ln)]
    assert len(nodes) == 7 and all(NODE.match(ln) for ln in nodes), nodes      # every label stayed inside its quotes
    assert [re.match(r"^  (n\d+)", ln).group(1) for ln in nodes] == [f"n{i}" for i in range(7)]   # ids never come from text
    assert "%%{" not in flow and "<script" not in flow and "click n0" not in flow


def test_labels_are_words_only_and_short():
    assert visuals.label("classes-and-objects") == "Classes and objects"
    assert visuals.label('he said "hi" (x) [y] {z}') == "He said hi x y z"
    assert visuals.label("!!!") == "Topic" and visuals.label("") == "Topic"
    assert len(visuals.label("a-very-" * 20)) <= visuals.LABEL_CHARS
    assert visuals.label("naïve café") == "Naïve café"                          # not only ASCII


def test_the_mind_map_lists_the_branches_and_shows_percentages_only_for_what_was_seen():
    mind = visuals.concept_map(PLAN, model(classes_and_objects=0.92, overriding=0.5))["mindmap"].splitlines()
    assert mind[0] == "mindmap" and mind[1] == "  root((Inheritance))"          # the topic itself is unseen: no number
    assert "    Prerequisites" in mind and "      Classes and objects 92%" in mind
    assert "    Parts" in mind and "      Overriding 50%" in mind and "      Parent and child" in mind
    bare = visuals.concept_map({"target": TARGET, "prereqs": [], "subtopics": []}, model())["mindmap"]
    assert "Prerequisites" not in bare and "Parts" not in bare


def test_state_uses_the_forgetting_curve_not_just_the_stored_mastery():
    old = LearnerModel(student_id="s", mastery={PRE: 0.9}, last_seen={PRE: time.time() - 90 * 86400})
    assert learner.effective_mastery(old, PRE) < learner.MASTERY
    assert visuals.state(old, PRE) == "shaky"                                  # 90 days on, it has faded below the bar


# ------------------------------------------------------------------ the diagram gate

@pytest.mark.parametrize("src", [
    'flowchart TD\n  A["x"] --> B["y"]', "graph LR\n  A --> B", "classDiagram\n  Animal <|-- Dog",
    "sequenceDiagram\n  main->>Dog: speak()", "stateDiagram-v2\n  [*] --> Open", "stateDiagram\n  [*] --> Open",
    "mindmap\n  root((x))"])
def test_every_kind_a_lesson_may_draw_gets_through(src):
    assert visuals.safe_diagram(src) == src


def test_fences_and_leading_comments_are_stripped_or_tolerated():
    assert visuals.safe_diagram("```mermaid\nclassDiagram\n  A <|-- B\n```") == "classDiagram\n  A <|-- B"
    assert visuals.safe_diagram("%% a note\nflowchart TD\n  A --> B") is not None


@pytest.mark.parametrize("src", [
    None, "", "   ", "gantt\n  title x", 'pie\n  "a": 1', "journey\n  title x", "not a diagram",
    "flowchart TD\n%%{init: {'securityLevel': 'loose'}}%%\n  A --> B",
    'flowchart TD\n  A["<script>alert(1)</script>"] --> B', "flowchart TD\n  A --> B\n  click A callback",
    'flowchart TD\n  A["javascript:alert(1)"] --> B', 'flowchart TD\n  A["<img src=x onerror=alert(1)>"] --> B',
    "flowchart TD\n  " + "A --> B\n  " * 400])
def test_other_kinds_and_dangerous_content_never_get_through(src):
    assert visuals.safe_diagram(src) is None


def test_ordinary_words_are_not_mistaken_for_attacks():
    assert visuals.safe_diagram('flowchart TD\n  A["one = 1"] --> B["online = True"]') is not None
    assert visuals.safe_diagram("classDiagram\n  Link <|-- Hyperlink\n  Link : +click()") is not None


def test_the_teaching_prompt_offers_exactly_the_kinds_the_gate_allows():
    prompt = _prompt("teach")
    for kind in KINDS:
        assert kind in prompt, kind
        assert visuals.safe_diagram(kind + "\n  A --> B") is not None, kind      # and the gate accepts each of them


# ------------------------------------------------------------------ the API

@pytest.mark.parametrize("src,shown", [
    ("classDiagram\n  Animal <|-- Dog", "classDiagram\n  Animal <|-- Dog"),
    ("gantt\n  title x", None),
    ("flowchart TD\n%%{init: {}}%%\n A --> B", None)])
def test_a_lesson_diagram_reaches_the_browser_only_if_it_passes_the_gate(tmp_path, monkeypatch, src, shown):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("T", diagram=src)]})
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET]}).json()["id"]
    assert settle(c, run)["messages"][0]["diagram"] == shown


def test_a_guided_session_shows_its_plan_as_a_map_and_keeps_the_live_map_current(tmp_path, monkeypatch):
    stub = Stub({"plan": [plan(subtopics=(S1, S2))], "teach": [lesson("T1"), lesson("T2")]})
    c, _ = make(tmp_path, monkeypatch, None, call=stub)
    store = Store(tmp_path / "api.db")
    learners.save(store, LearnerModel(student_id="asha", mastery={PRE: 0.92}, last_seen={PRE: time.time()}))
    store.close()
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET], "mode": "guided"}).json()["id"]
    snap = settle(c, run)

    card = snap["messages"][0]
    assert card["kind"] == "map" and '  n0["Classes and objects"]:::known' in card["flowchart"]
    assert card["mindmap"].startswith("mindmap")
    live = snap["progress"]["map"]
    assert live["flowchart"].splitlines()[0] == "flowchart TD"
    assert "  class n1 current" in live["flowchart"]                          # the first part is being taught right now


def test_quick_sessions_have_no_map(tmp_path, monkeypatch):
    c, _ = make(tmp_path, monkeypatch, {"teach": [lesson("T")]})
    run = c.post("/api/sessions", json={"student": "asha", "concepts": [TARGET]}).json()["id"]
    snap = settle(c, run)
    assert snap["progress"]["map"] is None and all(m["kind"] != "map" for m in snap["messages"])

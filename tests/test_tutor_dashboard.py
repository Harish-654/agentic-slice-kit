"""The learning dashboard: what a student has learnt and which parts of each topic they completed, worked out from
their twin and their past sessions with nothing stored for it."""
import pytest

from demo.tutor import dashboard, learner, learners, session
from demo.tutor.schema import LearnerModel
from slice.store import Store
from tests.test_tutor_auth import app  # noqa: F401  (the `app` fixture)

NOW = 1_800_000_000.0
DAY = 86400


def guided_run(store, student, target, prereqs=(), parts=(), ended=None, began=None):
    """A guided session that has made its plan, as the flow records it."""
    run = session.start_session(store, student, [target], mode="guided")
    plan = {"target": target, "prereqs": list(prereqs), "subtopics": list(parts)}
    store.append(run, "input", {"student_id": student, "concepts": [*prereqs, *parts, target], "mode": "guided",
                                "exam_question": None, "plan": plan}, "agent:plan")
    if ended:
        store.append(run, "session_end", {"reason": ended}, "system")
    if began is not None:
        store.db.execute("UPDATE runs SET created_at = ? WHERE id = ?", (began, run))
    return run


def twin(store, student, **ideas):
    """Save a twin. Each idea is (stored mastery, days since it was last practised) or None for never seen."""
    mastery, seen = {}, {}
    for name, given in ideas.items():
        if given is not None:
            mastery[name.replace("_", "-")], seen[name.replace("_", "-")] = given[0], NOW - given[1] * DAY
    learners.save(store, LearnerModel(student_id=student, mastery=mastery, last_seen=seen))


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "d.db")


def test_a_student_with_no_history_has_nothing_to_show(store):
    assert dashboard.report(store, "nobody", NOW) == {"totals": {"topics": 0, "learnt": 0, "parts_done": 0, "to_review": 0, "sessions": 0},
                                                      "topics": []}


def test_each_part_shows_where_the_student_stands_on_it(store):
    guided_run(store, "asha", "inheritance", prereqs=["classes"], parts=["parent-and-child", "overriding", "super-calls"])
    twin(store, "asha", classes=(0.95, 30), parent_and_child=(0.9, 0), overriding=(0.5, 1), inheritance=(0.5, 1))
    [topic] = dashboard.report(store, "asha", NOW)["topics"]
    assert {p["concept"]: p["band"] for p in topic["parts"]} == {"parent-and-child": "got-it", "overriding": "learning", "super-calls": "new"}
    assert (topic["parts_done"], topic["parts_total"]) == (1, 3)
    assert [(p["concept"], p["band"]) for p in topic["prereqs"]] == [("classes", "review")]      # learnt, then faded over a month
    assert topic["state"] == "learning" and topic["mastery"] == pytest.approx(0.5, abs=0.02)


def test_the_totals_count_each_idea_once(store):
    guided_run(store, "asha", "inheritance", prereqs=["classes"], parts=["overriding"])
    guided_run(store, "asha", "polymorphism", prereqs=["classes"], parts=["overriding", "interfaces"])   # shares two ideas
    twin(store, "asha", classes=(0.95, 30), overriding=(0.9, 0), interfaces=(0.4, 0))
    totals = dashboard.report(store, "asha", NOW)["totals"]
    assert totals["parts_done"] == 1 and totals["to_review"] == 1 and totals["topics"] == 2 and totals["sessions"] == 2


def test_passing_the_final_check_means_the_topic_is_learnt_even_below_the_bar(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"], ended="mastery")
    twin(store, "asha", overriding=(0.9, 0), inheritance=(0.72, 0))          # one confident right answer from fresh is 72%
    [topic] = dashboard.report(store, "asha", NOW)["topics"]
    assert topic["state"] == "learnt" and dashboard.report(store, "asha", NOW)["totals"]["learnt"] == 1


def test_a_topic_passed_long_ago_is_still_learnt_and_says_how_many_of_its_ideas_have_faded(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"], ended="mastery")
    twin(store, "asha", overriding=(0.9, 40), inheritance=(0.9, 40))
    [topic] = dashboard.report(store, "asha", NOW)["topics"]
    assert topic["state"] == "learnt" and topic["due"] == 2                  # learnt, with the part and the topic itself faded
    assert (topic["parts_done"], topic["parts_total"]) == (1, 1)             # the part was completed, and is now due for review
    assert dashboard.report(store, "asha", NOW)["totals"]["to_review"] == 2


def test_a_topic_never_passed_whose_idea_has_faded_reads_review(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"])
    twin(store, "asha", inheritance=(0.9, 40))                               # known once, in an earlier session, then left
    [topic] = dashboard.report(store, "asha", NOW)["topics"]
    assert topic["state"] == "review" and topic["due"] == 1


def test_a_fresh_topic_has_nothing_due(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"], ended="mastery")
    twin(store, "asha", overriding=(0.9, 0), inheritance=(0.9, 0))
    assert dashboard.report(store, "asha", NOW)["topics"][0]["due"] == 0


def test_a_session_that_never_got_anywhere_is_new(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"])
    assert dashboard.report(store, "asha", NOW)["topics"][0]["state"] == "new"


def test_two_sessions_on_one_topic_are_one_card_using_the_newest_plan(store):
    guided_run(store, "asha", "Inheritance", parts=["old-part"], began=NOW - 5 * DAY)
    guided_run(store, "asha", "inheritance", parts=["new-part-a", "new-part-b"], began=NOW - DAY)
    report = dashboard.report(store, "asha", NOW)
    [topic] = report["topics"]
    assert topic["sessions"] == 2 and topic["last_studied"] == NOW - DAY
    assert [p["concept"] for p in topic["parts"]] == ["new-part-a", "new-part-b"] and report["totals"]["sessions"] == 2


def test_the_same_topic_in_two_languages_stays_two_cards(store):
    guided_run(store, "asha", "inheritance in Java", parts=["interfaces"], began=NOW - 2 * DAY)
    guided_run(store, "asha", "inheritance in Python", parts=["mixins"], began=NOW - DAY)
    names = [t["name"] for t in dashboard.report(store, "asha", NOW)["topics"]]
    assert names == ["inheritance in Python", "inheritance in Java"]          # newest first


def test_another_students_sessions_never_appear(store):
    guided_run(store, "asha", "inheritance", parts=["overriding"])
    guided_run(store, "ben", "recursion", parts=["base-case"])
    assert [t["name"] for t in dashboard.report(store, "asha", NOW)["topics"]] == ["inheritance"]
    assert [t["name"] for t in dashboard.report(store, "ben", NOW)["topics"]] == ["recursion"]


def test_quick_practice_is_one_topic_per_thing_typed_and_has_no_parts(store):
    session.start_session(store, "asha", ["recursion", "list slicing"])
    twin(store, "asha", **{"recursion": (0.9, 0)})
    topics = {t["name"]: t for t in dashboard.report(store, "asha", NOW)["topics"]}
    assert set(topics) == {"recursion", "list slicing"}
    assert topics["recursion"]["state"] == "learnt" and topics["list slicing"]["state"] == "new"
    assert topics["recursion"]["parts_total"] == 0 and topics["recursion"]["parts"] == []


def test_a_guided_session_that_never_made_a_plan_is_left_out_not_shown_as_a_placeholder(store):
    session.start_session(store, "asha", ["exam-question"], mode="guided", exam_question="Explain recursion.")
    assert dashboard.report(store, "asha", NOW)["topics"] == []


def test_only_the_newest_topics_are_listed(store):
    session.start_session(store, "asha", [f"topic {i:02d}" for i in range(dashboard.MAX_TOPICS + 5)])
    report = dashboard.report(store, "asha", NOW)
    assert len(report["topics"]) == dashboard.MAX_TOPICS == report["totals"]["topics"]


def test_standing_is_what_the_route_and_the_dashboard_both_read():
    m = LearnerModel(student_id="s", mastery={"a": 0.9, "b": 0.5}, last_seen={"a": NOW, "b": NOW})
    assert learner.standing(m, "a", NOW) == {"mastery": 0.9, "mastered": True, "seen": True, "review_due": False}
    assert learner.standing(m, "b", NOW)["review_due"] is False and learner.standing(m, "b", NOW)["mastered"] is False
    old = learner.standing(m, "a", NOW + 40 * DAY)
    assert old["mastered"] is False and old["review_due"] is True                # learnt, then faded
    assert learner.standing(m, "never", NOW) == {"mastery": 0.3, "mastered": False, "seen": False, "review_due": False}


# ------------------------------------------------------------------ the API

def test_the_api_gives_a_signed_in_student_only_their_own_learning(app):
    asha, ben = app.signed_in("Asha"), app.signed_in("Ben")
    store = app.store()
    guided_run(store, "Asha", "inheritance", parts=["overriding"], ended="mastery")
    twin(store, "Asha", overriding=(0.9, 0))
    store.close()
    mine = asha.get("/api/me/learning").json()
    assert [t["name"] for t in mine["topics"]] == ["inheritance"] and mine["totals"]["parts_done"] == 1
    assert ben.get("/api/me/learning").json() == {"totals": {"topics": 0, "learnt": 0, "parts_done": 0, "to_review": 0, "sessions": 0},
                                                  "topics": []}

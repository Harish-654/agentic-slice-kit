"""Daily activity, streaks and check-ins. All derived from answered questions and code runs already in the
database, so these tests build history directly and check what comes out."""
from datetime import date, datetime, timedelta, timezone

from demo.tutor import activity, session
from slice.store import Store
from tests.test_tutor_auth import PASSWORD, app, start  # noqa: F401  (the `app` fixture)
from web import tutor_api

D = date(2026, 9, 21)


def days(*ago, n=1, today=D):
    return {(today - timedelta(days=a)).isoformat(): n for a in ago}


# ------------------------------------------------------------------ the streak rules

def test_a_new_student_has_no_streak_and_has_not_checked_in():
    s = activity.summarize({}, D)
    assert (s["current_streak"], s["longest_streak"], s["active_days"], s["total"]) == (0, 0, 0, 0)
    assert s["checked_in_today"] is False and s["at_risk"] is False and s["today_count"] == 0


def test_doing_something_today_starts_a_streak_of_one():
    s = activity.summarize(days(0, n=4), D)
    assert s["current_streak"] == 1 and s["checked_in_today"] is True and s["today_count"] == 4 and s["at_risk"] is False


def test_consecutive_days_ending_today_make_the_streak():
    s = activity.summarize(days(0, 1, 2), D)
    assert s["current_streak"] == s["longest_streak"] == 3 and s["at_risk"] is False


def test_the_streak_is_still_alive_today_until_midnight_but_flagged_at_risk():
    s = activity.summarize(days(1, 2, 3), D)                        # nothing yet today, but yesterday and before
    assert s["current_streak"] == 3 and s["at_risk"] is True and s["checked_in_today"] is False


def test_missing_a_whole_day_breaks_it():
    s = activity.summarize(days(2, 3, 4), D)                        # yesterday is empty, so it is gone
    assert s["current_streak"] == 0 and s["at_risk"] is False and s["longest_streak"] == 3


def test_a_gap_starts_the_count_again_and_the_longest_streak_remembers_the_best_run():
    s = activity.summarize(days(0, 2, 3, 4, 5, 6), D)               # today, a gap, then five days
    assert s["current_streak"] == 1 and s["longest_streak"] == 5


def test_an_old_long_streak_is_remembered_even_though_it_is_over():
    s = activity.summarize(days(*range(30, 40), 0), D)
    assert s["current_streak"] == 1 and s["longest_streak"] == 10 and s["active_days"] == 11


def test_days_with_a_zero_count_are_not_active_and_totals_add_up():
    s = activity.summarize({**days(0, n=2), **days(1, n=0), **days(2, n=5)}, D)
    assert s["current_streak"] == 1 and s["active_days"] == 2 and s["total"] == 7


def test_the_streak_counts_across_a_month_end_and_a_leap_day():
    leap = date(2028, 3, 1)
    assert activity.summarize(days(0, 1, 2, today=leap), leap)["current_streak"] == 3     # 1 Mar, 29 Feb, 28 Feb
    assert activity.summarize(days(0, 1, today=date(2026, 1, 1)), date(2026, 1, 1))["current_streak"] == 2


# ------------------------------------------------------------------ the student's own day

def test_a_late_evening_answer_belongs_to_the_students_day_not_the_servers():
    t = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc).timestamp()              # 8pm UTC on the 20th
    assert activity.today_for(t, 0) == date(2026, 9, 20)
    assert activity.today_for(t, -330) == date(2026, 9, 21)                          # India: already 1:30 am on the 21st
    assert activity.today_for(t, 420) == date(2026, 9, 20)                           # US Pacific: 1 pm on the 20th
    assert activity.clamp_tz(10 ** 6) == 12 * 60 and activity.clamp_tz(-10 ** 6) == -14 * 60


def add_check(store, run, when, kind="check"):
    """A version written at a chosen time. The history is append-only (it cannot be edited), so insert."""
    seq = store.db.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM versions WHERE run_id=?", (run,)).fetchone()["n"]
    store.db.execute("INSERT INTO versions(run_id, seq, kind, produced_by, payload_json, created_at) "
                     "VALUES (?,?,?,?,?,?)", (run, seq, kind, "system", "{}", when))


def test_answers_are_bucketed_by_the_timezone_the_student_sent(tmp_path):
    store = Store(tmp_path / "a.db")
    run = session.start_session(store, "Asha", ["x"])
    t = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc).timestamp()
    for when in (t - 3 * 3600, t, t + 3600):                                         # 5pm, 8pm and 9pm UTC on the 20th
        add_check(store, run, when)
    assert activity.counts_by_day(store, "Asha", 0) == {"2026-09-20": 3}
    assert activity.counts_by_day(store, "Asha", 420) == {"2026-09-20": 3}
    assert activity.counts_by_day(store, "Asha", -330) == {"2026-09-20": 1, "2026-09-21": 2}   # 10:30pm, then two after midnight
    assert activity.counts_by_day(store, "Asha", -840) == {"2026-09-21": 3}


def test_only_this_students_answers_and_code_runs_count(tmp_path):
    store = Store(tmp_path / "a.db")
    mine = session.start_session(store, "Asha", ["x"])
    theirs = session.start_session(store, "Ben", ["x"])
    other = store.create_run("something-else", {"student_id": "Asha"})              # not a tutor run
    t = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc).timestamp()
    add_check(store, mine, t)
    add_check(store, mine, t, kind="code_run")                                       # running your own code counts
    add_check(store, mine, t, kind="lesson")                                         # reading a lesson does not
    add_check(store, mine, t, kind="learner_model")
    add_check(store, theirs, t)
    add_check(store, other, t)
    assert activity.counts_by_day(store, "Asha", 0) == {"2026-09-20": 2}
    assert activity.counts_by_day(store, "Ben", 0) == {"2026-09-20": 1}
    assert activity.counts_by_day(store, "Nobody", 0) == {}


def test_a_streak_longer_than_the_heatmap_is_not_cut_off_by_its_window(tmp_path):
    store = Store(tmp_path / "a.db")
    run = session.start_session(store, "Asha", ["x"])
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc).timestamp()
    for ago in range(400):                                                           # 400 days in a row
        add_check(store, run, now - ago * 86400)
    r = activity.report(store, "Asha", 0, now=now)
    assert r["current_streak"] == r["longest_streak"] == 400
    assert len(r["days"]) <= activity.WEEKS * 7 and "2026-09-21" in r["days"] and r["today"] == "2026-09-21"
    assert min(r["days"]) > (date(2026, 9, 21) - timedelta(days=activity.WEEKS * 7 + 1)).isoformat()


# ------------------------------------------------------------------ through the API

def test_activity_needs_a_sign_in(app):
    assert app.browser().get("/api/me/activity").status_code == 401


def test_answering_a_question_is_a_check_in_and_starts_the_streak(app):
    asha = app.signed_in("Asha")
    before = asha.get("/api/me/activity?tz=0").json()
    assert before["checked_in_today"] is False and before["current_streak"] == 0 and before["days"] == {}

    run = start(asha)
    assert asha.post(f"/api/sessions/{run}/answer", json={"choice": 1, "confidence": "high"}).status_code == 200
    after = asha.get("/api/me/activity?tz=0").json()
    assert after["checked_in_today"] is True and after["current_streak"] == 1 and after["at_risk"] is False
    assert after["today_count"] == 1 and after["days"][after["today"]] == 1 and after["total"] == 1


def test_running_code_counts_too_and_each_student_sees_only_their_own(app, monkeypatch):
    from demo.tutor.sandbox import Result
    monkeypatch.setattr(tutor_api, "sandbox_ready", lambda *a, **k: (True, ""))
    monkeypatch.setattr(tutor_api, "sandbox_run", lambda code, **k: Result("4\n", "", 0))
    asha, ben = app.signed_in("Asha"), app.signed_in("Ben")
    run = start(asha)
    assert asha.post(f"/api/sessions/{run}/code", json={"code": "print(2+2)"}).status_code == 200
    assert asha.get("/api/me/activity?tz=0").json()["today_count"] == 1
    assert ben.get("/api/me/activity?tz=0").json()["today_count"] == 0


def test_the_date_follows_the_timezone_the_browser_sends(app):
    asha = app.signed_in("Asha")
    far_east = asha.get("/api/me/activity?tz=-840").json()["today"]
    far_west = asha.get("/api/me/activity?tz=720").json()["today"]
    assert far_east != far_west                                                      # 26 hours apart: never the same date
    assert asha.get("/api/me/activity?tz=9999999").status_code == 200                # nonsense is clamped, not a crash

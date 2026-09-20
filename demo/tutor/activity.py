"""What a student has done, day by day, and the streak that follows from it.

Nothing is stored for this. Every answered question is already a `check` version and every run of a student's
own code a `code_run` version, each with a timestamp, so a day is simply "active" if the student did at least
one of those on it. That makes the streak honest (it cannot be earned by clicking a button) and means history
from before this feature existed shows up straight away.

Days are the STUDENT's days, not the server's: the page sends its timezone offset, so an answer at 11:30 pm
counts for that evening even when the server is on the far side of the world.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from slice.store import Store

ACTIVE_KINDS = ("check", "code_run")
WEEKS = 53                      # the heatmap's width; the streak itself looks at all of history
_MIN_TZ, _MAX_TZ = -14 * 60, 12 * 60


def clamp_tz(minutes: int) -> int:
    """A browser's Date.getTimezoneOffset(), kept to the range real timezones use."""
    return max(_MIN_TZ, min(_MAX_TZ, int(minutes)))


def today_for(now: float, tz_minutes: int) -> date:
    """The student's calendar date right now. JavaScript's offset is minutes BEHIND UTC (India is -330)."""
    return datetime.fromtimestamp(now - clamp_tz(tz_minutes) * 60, timezone.utc).date()


def counts_by_day(store: Store, student: str, tz_minutes: int = 0) -> dict[str, int]:
    """{"2026-09-21": 3, ...}: answered questions plus code runs on each of the student's local days, over
    every session they have ever had. Only THIS student's tutor runs are counted."""
    off = clamp_tz(tz_minutes) * 60
    marks = ",".join("?" * len(ACTIVE_KINDS))
    rows = store.db.execute(
        f"SELECT date(v.created_at - ?, 'unixepoch') AS d, COUNT(*) AS n "
        f"FROM versions v JOIN runs r ON r.id = v.run_id "
        f"WHERE r.domain = 'tutor' AND json_extract(r.meta_json, '$.student_id') = ? "
        f"AND v.kind IN ({marks}) GROUP BY d", (off, student, *ACTIVE_KINDS))
    return {r["d"]: r["n"] for r in rows}


def summarize(days: dict[str, int], today: date) -> dict:
    """The streak numbers, from {date: count}.

    The current streak is the run of consecutive active days ending today. If today has nothing yet but
    yesterday did, the streak is still ALIVE (you have until midnight), so it is counted from yesterday and
    `at_risk` says so. Miss a whole day and it drops to 0. The longest streak looks at all of history."""
    active = sorted(date.fromisoformat(d) for d, n in days.items() if n > 0)
    have = set(active)
    tail = today if today in have else today - timedelta(days=1)
    current = 0
    while tail - timedelta(days=current) in have:
        current += 1
    longest = run = 0
    previous = None
    for d in active:
        run = run + 1 if previous is not None and d - previous == timedelta(days=1) else 1
        longest, previous = max(longest, run), d
    return {"current_streak": current, "longest_streak": longest,
            "at_risk": current > 0 and today not in have,
            "checked_in_today": today in have, "today_count": days.get(today.isoformat(), 0),
            "active_days": len(active), "total": sum(n for n in days.values() if n > 0)}


def report(store: Store, student: str, tz_minutes: int = 0, now: float | None = None) -> dict:
    """What GET /api/me/activity returns: the last WEEKS weeks of non-zero days for the heatmap, and the
    summary (computed over ALL history, so a long streak is never cut off by the heatmap's window)."""
    import time
    tz = clamp_tz(tz_minutes)
    today = today_for(time.time() if now is None else now, tz)
    days = counts_by_day(store, student, tz)
    since = today - timedelta(days=WEEKS * 7)
    return {"today": today.isoformat(), **summarize(days, today),
            "days": {d: n for d, n in days.items() if n > 0 and date.fromisoformat(d) > since}}

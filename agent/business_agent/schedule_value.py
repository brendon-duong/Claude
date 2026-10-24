"""Read Curia's schedule, price the work, and say what changed since last time.

Curia edit their schedule without telling anyone -- twice in two days on
19 September, once mid-session, and again on 24 September while a roster was
being discussed. A figure read even a few hours earlier can be wrong, so this
module exists to be run repeatedly and to report the *difference*.

Two rules from CLAUDE.md are load-bearing here and are implemented, not
assumed:

* ``PL Staff Confirmed`` is column 5 BY INDEX. Never count columns from the
  left on a collapsed snippet -- ``download_file_content`` is the only read
  that preserves empty cells.
* **An empty column 5 means the poll is Curia's own** and none of our callers
  go on it. Such a row contributes nothing to our headcount or our revenue.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from dataclasses import dataclass, asdict, field
from datetime import date, datetime

# What one rostered caller is worth: a three-hour shift at an hourly rate.
SHIFT_HOURS = 3.0
HOURLY_RATE = 19.50

DATE_COL, POLL_COL, CURIA_COL, PL_COL, EXTRA_COL = 0, 1, 4, 5, 6


@dataclass(frozen=True)
class Poll:
    """One poll on one day, as Curia's sheet has it."""

    poll: str
    pl_staff: int
    curia_staff: int | None = None
    extra_required: int | None = None


@dataclass
class Day:
    """A shift day: the date Curia wrote, and every poll that is OURS."""

    day: date
    weekday: str
    polls: list[Poll] = field(default_factory=list)

    @property
    def slots(self) -> int:
        return sum(p.pl_staff for p in self.polls)

    @property
    def hours(self) -> float:
        return self.slots * SHIFT_HOURS

    @property
    def value(self) -> float:
        return round(self.hours * HOURLY_RATE, 2)


def _parse_date(cell: str) -> date | None:
    """``Friday 25-Sep-26`` -> a date. Anything else -> None."""
    cell = cell.strip()
    if not cell:
        return None
    part = cell.split(None, 1)[-1] if " " in cell else cell
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(part.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _int_or_none(cell: str) -> int | None:
    cell = (cell or "").strip()
    if not cell:
        return None
    try:
        return int(float(cell))
    except ValueError:
        return None


def parse_schedule(csv_text: str) -> list[Day]:
    """Every day that has at least one poll of OURS, in sheet order.

    A day with two polls uses a continuation row whose date cell is empty, so
    the date is carried forward. A row whose ``PL Staff Confirmed`` cell is
    empty is Curia staffing that poll themselves and is dropped.
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    days: list[Day] = []
    by_day: dict[date, Day] = {}
    current: date | None = None

    for row in rows[1:]:
        if len(row) <= PL_COL:
            row = row + [""] * (PL_COL + 1 - len(row))
        parsed = _parse_date(row[DATE_COL])
        if parsed:
            current = parsed
        if current is None:
            continue

        pl = _int_or_none(row[PL_COL])
        if pl is None or pl <= 0:
            continue  # Curia's own poll, or a row with no headcount yet.
        poll = row[POLL_COL].strip()
        if not poll:
            continue

        if current not in by_day:
            weekday = row[DATE_COL].strip().split(None, 1)[0] if parsed else current.strftime("%A")
            day = Day(day=current, weekday=weekday or current.strftime("%A"))
            by_day[current] = day
            days.append(day)
        by_day[current].polls.append(
            Poll(
                poll=poll,
                pl_staff=pl,
                curia_staff=_int_or_none(row[CURIA_COL]),
                extra_required=_int_or_none(row[EXTRA_COL] if len(row) > EXTRA_COL else ""),
            )
        )
    return days


def parse_drive_payload(path: str) -> list[Day]:
    """Parse a saved ``download_file_content`` result straight off disk."""
    payload = json.load(open(path))
    text = base64.b64decode(payload["content"]).decode("utf-8-sig")
    return parse_schedule(text)


def window(days: list[Day], start: date, end: date) -> list[Day]:
    return [d for d in days if start <= d.day <= end]


def totals(days: list[Day]) -> dict:
    slots = sum(d.slots for d in days)
    hours = slots * SHIFT_HOURS
    return {
        "slots": slots,
        "hours": round(hours, 1),
        "value": round(hours * HOURLY_RATE, 2),
        "rate": HOURLY_RATE,
        "shift_hours": SHIFT_HOURS,
    }


def snapshot(days: list[Day]) -> dict:
    """A comparable form: date -> poll -> headcount. Ordering does not matter."""
    return {
        d.day.isoformat(): {p.poll: p.pl_staff for p in d.polls}
        for d in days
    }


def diff(before: dict, after: dict) -> list[dict]:
    """What Curia changed. One entry per poll that appeared, vanished or moved.

    Reported per poll rather than per day, because "Wednesday went from 17 to
    42" hides which poll arrived -- and the poll is what a roster is built on.
    """
    out: list[dict] = []
    for day in sorted(set(before) | set(after)):
        was, now = before.get(day, {}), after.get(day, {})
        for poll in sorted(set(was) | set(now)):
            a, b = was.get(poll), now.get(poll)
            if a == b:
                continue
            kind = "added" if a is None else "removed" if b is None else "changed"
            out.append({"day": day, "poll": poll, "kind": kind, "was": a, "now": b})
    return out


def describe(change: dict) -> str:
    d, poll = change["day"], change["poll"]
    if change["kind"] == "added":
        return f"{d}  + {poll} added, {change['now']} callers"
    if change["kind"] == "removed":
        return f"{d}  - {poll} removed (was {change['was']} callers)"
    delta = change["now"] - change["was"]
    return f"{d}  ~ {poll} {change['was']} -> {change['now']} callers ({delta:+d})"

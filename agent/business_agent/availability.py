"""Reading who put their hand up for which day.

The team votes in a WhatsApp poll — "which days can you work next week?" —
and the poll results are pasted in here. That turns rostering from "who are
the best callers" into the question that actually matters: "of the people
available on Tuesday, who are the best twenty?"

The expected format is a date, then the names under it, which is how WhatsApp
shows poll results when you tap through to see who voted:

    Sunday 13 Sep (12 votes)
    Lia Villapaz
    Kharen Ybas
    ...

    Monday 14 Sep
    1. Tristan Bustamante
    - Jasmine Magdayao

Bullets, numbering and vote counts are all tolerated, because this gets
copied and pasted by a person in a hurry.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime

from .audit import normalise_name
from .performance import MIN_FUZZY_TOKEN, _one_edit_apart
from .sheets import Row

_MONTHS = (
    "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
    "|january|february|march|april|june|july|august|september|october|november|december"
)
_WEEKDAY = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*"

# "Sunday 13 Sep", "13 September 2026", "Sun 13 Sep 2026 (12 votes)"
_DATE_WORDS = re.compile(
    rf"^(?:{_WEEKDAY}\s+)?(?P<day>\d{{1,2}})\s*(?:st|nd|rd|th)?\s+"
    rf"(?P<month>{_MONTHS})\.?\s*(?P<year>\d{{4}})?\s*$",
    re.IGNORECASE,
)
# "13/9", "13/09/2026", "13-9-26"
_DATE_NUMERIC = re.compile(
    r"^(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{2,4}))?\s*$"
)
# Trailing "(12 votes)" or "- 12 votes" that WhatsApp adds to poll options.
_VOTE_COUNT = re.compile(r"[\(\[\-–—,]?\s*\d+\s*votes?\s*[\)\]]?\s*$", re.IGNORECASE)
# Leading "1.", "1)", "-", "*", "•"
_BULLET = re.compile(r"^\s*(?:\d{1,3}[.)]|[-*•·–—])\s*")
# Lines that are structure, not people.
_NOISE = re.compile(
    r"^\s*(?:poll|votes?|options?|results?|which days?.*|availability.*|no votes?|"
    r"total.*|\d+\s*votes?)\s*$",
    re.IGNORECASE,
)

_MONTH_NUMBERS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@dataclass
class Availability:
    """Who volunteered for which day."""

    by_day: dict[date, set[str]] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)
    # Names in the poll that match nobody in the audit history. Reported
    # rather than dropped: a new starter and a typo look identical here, and
    # silently ignoring either loses a caller who is expecting a shift.
    unmatched: list[tuple[date, str]] = field(default_factory=list)

    def on(self, day: date) -> set[str] | None:
        """Volunteers for a day, or None if the poll said nothing about it."""
        return self.by_day.get(day)

    @property
    def days(self) -> list[date]:
        return sorted(self.by_day)

    @property
    def volunteer_count(self) -> int:
        return len({key for keys in self.by_day.values() for key in keys})


def parse_heading_date(line: str, reference: date) -> date | None:
    """A poll option line as a date, or None if it is not one."""
    text = _VOTE_COUNT.sub("", line.strip()).strip(" :-–—")
    if not text:
        return None

    match = _DATE_WORDS.match(text)
    if match:
        month = _MONTH_NUMBERS[match.group("month")[:3].lower()]
        year = int(match.group("year")) if match.group("year") else reference.year
        try:
            found = date(year, month, int(match.group("day")))
        except ValueError:
            return None
        # A bare "13 Sep" written in December means next year's.
        if not match.group("year") and (found - reference).days < -180:
            found = found.replace(year=found.year + 1)
        return found

    match = _DATE_NUMERIC.match(text)
    if match:
        year_text = match.group("year")
        year = int(year_text) if year_text else reference.year
        if year < 100:
            year += 2000
        try:
            return date(year, int(match.group("month")), int(match.group("day")))
        except ValueError:
            return None
    return None


def match_caller(name: str, known: dict[str, str]) -> str | None:
    """Match a pasted name to a caller in the audit history.

    Exact first, then the same conservative fuzzy rules used for spotting
    duplicate names — one contained in the other, or a single-letter typo in
    a long-enough token.
    """
    key = normalise_name(name)
    if not key:
        return None
    if key in known:
        return key

    tokens = set(key.split())
    for candidate in known:
        candidate_tokens = set(candidate.split())
        if tokens and candidate_tokens and (tokens < candidate_tokens or candidate_tokens < tokens):
            return candidate

    parts = key.split()
    for candidate in known:
        other = candidate.split()
        if len(parts) != len(other):
            continue
        differences = [i for i, (a, b) in enumerate(zip(parts, other)) if a != b]
        if len(differences) == 1:
            index = differences[0]
            if _one_edit_apart(parts[index], other[index]):
                return candidate
    return None


def parse_availability(
    text: str, known: dict[str, str], reference: date
) -> Availability:
    """Parse pasted poll results into per-day volunteer lists."""
    result = Availability()
    current: date | None = None

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = parse_heading_date(line, reference)
        if heading is not None:
            current = heading
            result.by_day.setdefault(current, set())
            continue

        if _NOISE.match(line):
            continue
        if current is None:
            continue  # preamble before the first day

        name = _BULLET.sub("", line).strip(" :-–—\t")
        name = _VOTE_COUNT.sub("", name).strip()
        if not name or len(name) < MIN_FUZZY_TOKEN:
            continue

        key = match_caller(name, known)
        if key is None:
            result.unmatched.append((current, name))
            continue
        result.by_day[current].add(key)
        result.display_names.setdefault(key, known.get(key, name))

    return result


# ---------------------------------------------------------------------------
# Google Form responses
# ---------------------------------------------------------------------------
#
# A form beats a WhatsApp poll for one reason above all others: the name is a
# dropdown, so callers pick themselves off a list instead of typing. That
# removes the whole class of "Loraine / Lorraine / Lorraine Sabraso" problems
# at the point where they are created, rather than trying to untangle them
# afterwards.
#
# Google writes one row per response, with the checkbox answers joined into a
# single cell:
#
#   Timestamp            | Your name       | Which days can you work?
#   09/09/2026 14:02:11  | Lia Villapaz    | Sunday 13 Sep, Monday 14 Sep
#
# Column names are matched loosely, because the question wording will change
# and nobody should have to edit code when it does.

_NAME_HINTS = ("name", "who are you", "caller")
_DAYS_HINTS = ("day", "available", "availability", "work", "shift")
_IGNORE_HINTS = ("timestamp", "email", "score", "time")


def _find_column(rows: list[Row], hints: tuple[str, ...]) -> str | None:
    """The first column whose heading mentions any of these words."""
    if not rows:
        return None
    for column in rows[0]:
        lowered = column.lower()
        if any(word in lowered for word in _IGNORE_HINTS):
            continue
        if any(hint in lowered for hint in hints):
            return column
    return None


def _split_days(cell: str) -> list[str]:
    """Split a checkbox answer into its individual options.

    Google joins the ticked options with ", ", so a comma inside an option
    label would split wrongly — semicolons and newlines are accepted too,
    which is what a form built with those separators produces.
    """
    parts = re.split(r"[;\n]|,(?=\s)", cell or "")
    return [part.strip() for part in parts if part.strip()]


def from_form_responses(
    rows: list[Row],
    known: dict[str, str],
    reference: date,
    *,
    name_column: str | None = None,
    days_column: str | None = None,
    offered_days: Iterable[date] | None = None,
) -> Availability:
    """Read Google Form responses into per-day volunteer lists.

    Later responses win: people change their minds and resubmit, and the last
    answer is the one they meant. Rows are taken in sheet order, which is the
    order Google appends them.
    """
    result = Availability()
    # A day the form offered that nobody ticked means nobody is available —
    # which must not be confused with a day the form never asked about. The
    # first leaves a shift short and says so; the second falls back to the
    # whole pool. Seeding the offered days keeps them distinguishable.
    for day in offered_days or ():
        result.by_day.setdefault(day, set())

    if not rows:
        return result

    name_column = name_column or _find_column(rows, _NAME_HINTS)
    days_column = days_column or _find_column(rows, _DAYS_HINTS)
    if not name_column or not days_column:
        raise ValueError(
            "could not find the name and days columns in the form responses; "
            f"columns present: {', '.join(rows[0])}"
        )

    # One entry per person, last response winning.
    latest: dict[str, tuple[str, list[str]]] = {}
    order: list[str] = []
    for row in rows:
        raw_name = (row.get(name_column) or "").strip()
        if not raw_name:
            continue

        day_labels = _split_days(row.get(days_column, ""))
        # Any day mentioned anywhere in the responses is a day the form asked
        # about, even if the only person who ticked it later changed their
        # answer. Without this it would read as "never asked" and quietly fall
        # back to the whole pool instead of showing the shift as unstaffed.
        for label in day_labels:
            day = parse_heading_date(label, reference)
            if day is not None:
                result.by_day.setdefault(day, set())

        key = match_caller(raw_name, known) or f"?{normalise_name(raw_name)}"
        if key not in latest:
            order.append(key)
        latest[key] = (raw_name, day_labels)

    for key in order:
        raw_name, day_labels = latest[key]
        for label in day_labels:
            day = parse_heading_date(label, reference)
            if day is None:
                continue
            result.by_day.setdefault(day, set())
            if key.startswith("?"):
                result.unmatched.append((day, raw_name))
                continue
            result.by_day[day].add(key)
            result.display_names.setdefault(key, known.get(key, raw_name))

    return result

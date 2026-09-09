"""Availability nobody has to be asked for.

Asking ninety people every week which days they can work does not scale, and
it does not fail gracefully: the people who answer are not the people who turn
up, and chasing the silent two thirds is the job that eats the week.

But the answer is already in the data. People are creatures of habit, and a
caller who has worked Monday, Tuesday and Thursday for the last eight weeks is
telling you their availability far more reliably than a poll they filled in
while distracted. So this module derives a *standing pattern* per caller from
what they actually did, and the weekly question shrinks from "who can work?" to
"is anything different this week?" — a question only a handful of people ever
need to answer.

Against six months of real audits, 46 of the 52 currently-active callers have
at least one weekday they work in half or more of the weeks they work at all.

Two honest limits, both of which the caller has to see rather than have hidden:

  * The history here is *audited* shifts, not all shifts. A caller who works
    Sundays but is rarely audited on a Sunday will look less available than she
    is. The rates are therefore a floor, not a measurement, which is why a
    pattern never removes anyone from the pool — it only proposes.
  * A pattern describes the past. Someone whose circumstances changed last week
    is wrong in the data and right in real life, so a pattern that has not been
    seen recently is marked stale rather than trusted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .availability import Availability
from .audit import normalise_name

# Eight weeks: long enough that one holiday does not erase a pattern, short
# enough that a caller who changed jobs in June is not still rostered on June's
# habits in September.
DEFAULT_WINDOW_DAYS = 56
# Below this a "pattern" is just noise — three points can look like anything.
DEFAULT_MIN_SHIFTS = 3
# Worked on half or more of the weeks they were active. Deliberately not higher:
# the source undercounts, so a strict threshold loses real availability.
DEFAULT_THRESHOLD = 0.5
# A pattern nobody has acted on in three weeks describes someone who may have
# moved on. Still reported, never assumed.
DEFAULT_STALE_DAYS = 21

_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass
class StandingPattern:
    """The days one caller reliably works, and how reliably."""

    key: str
    name: str
    # Python weekday numbers: Monday is 0, Sunday is 6.
    weekdays: set[int] = field(default_factory=set)
    # weekday -> the share of their active weeks they worked it, 0.0-1.0.
    rates: dict[int, float] = field(default_factory=dict)
    shifts: int = 0
    active_weeks: int = 0
    last_seen: date | None = None
    stale: bool = False

    @property
    def label(self) -> str:
        """"Mon Tue Thu", in week order."""
        return " ".join(_DAY_NAMES[d] for d in sorted(self.weekdays))

    @property
    def confidence(self) -> float:
        """How strong the weakest day in the pattern is.

        The weakest day is the one that will let you down, so it is the one
        worth reporting.
        """
        return min((self.rates[d] for d in self.weekdays), default=0.0)

    def works(self, day: date) -> bool:
        return day.weekday() in self.weekdays


@dataclass
class PatternSet:
    """Every caller's standing pattern, and who was too new to have one."""

    patterns: dict[str, StandingPattern] = field(default_factory=dict)
    # Callers seen in the window but without enough shifts to read a pattern
    # from. They are not unavailable — they are unknown, and the difference
    # matters when deciding who to actually ask.
    too_few_shifts: list[str] = field(default_factory=list)
    window_from: date | None = None
    window_to: date | None = None

    def __len__(self) -> int:
        return len(self.patterns)

    @property
    def fresh(self) -> dict[str, StandingPattern]:
        return {k: p for k, p in self.patterns.items() if not p.stale}

    def on(self, day: date, *, include_stale: bool = False) -> set[str]:
        """Who would normally be working on this date."""
        source = self.patterns if include_stale else self.fresh
        return {key for key, pattern in source.items() if pattern.works(day)}

    def cover(self, days: list[date], *, include_stale: bool = False) -> dict[date, int]:
        """How many callers each day of a week would normally draw on."""
        return {day: len(self.on(day, include_stale=include_stale)) for day in days}

    def to_availability(
        self, days: list[date], *, include_stale: bool = False
    ) -> Availability:
        """The standing patterns as a week's availability.

        This is the point of the whole module: it produces exactly what a poll
        or a form would have produced, so the roster builder does not need to
        know where its availability came from.
        """
        result = Availability()
        for day in sorted(days):
            keys = self.on(day, include_stale=include_stale)
            result.by_day[day] = set(keys)
            for key in keys:
                result.display_names.setdefault(key, self.patterns[key].name)
        return result


def derive_patterns(
    audits,
    *,
    as_of: date | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_shifts: int = DEFAULT_MIN_SHIFTS,
    threshold: float = DEFAULT_THRESHOLD,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> PatternSet:
    """Read each caller's standing pattern out of their shift history.

    Rates are per *active week*, not per calendar week: someone who took a
    fortnight off and worked every Monday either side has a Monday pattern, not
    a two-thirds-of-Mondays pattern. Holidays should not read as unreliability.
    """
    records = list(audits)
    if not records:
        return PatternSet()

    latest = as_of or max(record.day for record in records)
    earliest = latest - timedelta(days=window_days)

    days_by_person: dict[str, set[date]] = defaultdict(set)
    names: dict[str, str] = {}
    for record in records:
        if not (earliest <= record.day <= latest):
            continue
        key = normalise_name(record.name)
        if not key:
            continue
        # A set, because one caller audited twice in a day is one shift.
        days_by_person[key].add(record.day)
        names.setdefault(key, record.name)

    result = PatternSet(window_from=earliest, window_to=latest)
    for key, days in days_by_person.items():
        if len(days) < min_shifts:
            result.too_few_shifts.append(names[key])
            continue

        active_weeks = len({day.isocalendar()[:2] for day in days})
        # Weeks worked per weekday, so working two Mondays in one week — which
        # cannot happen, but a double-audited day could imitate — still counts
        # once.
        weeks_per_weekday: Counter[int] = Counter()
        for weekday in range(7):
            weeks_per_weekday[weekday] = len(
                {day.isocalendar()[:2] for day in days if day.weekday() == weekday}
            )

        rates = {
            weekday: count / active_weeks
            for weekday, count in weeks_per_weekday.items()
            if count
        }
        last_seen = max(days)
        result.patterns[key] = StandingPattern(
            key=key,
            name=names[key],
            weekdays={d for d, rate in rates.items() if rate >= threshold},
            rates=rates,
            shifts=len(days),
            active_weeks=active_weeks,
            last_seen=last_seen,
            stale=(latest - last_seen).days > stale_days,
        )

    result.too_few_shifts.sort()
    return result


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
#
# The standing pattern is the default. The only thing that still has to be
# collected each week is the deviations — "I can't do Tuesday", "I can do the
# extra Sunday" — and there are far fewer of those than there are people.
#
# An exception is deliberately per-date rather than per-weekday. "I can't work
# next Tuesday" must not quietly become "I never work Tuesdays".


@dataclass(frozen=True)
class Exception_:
    """One caller, one date, on or off."""

    key: str
    day: date
    available: bool
    note: str = ""


def apply_exceptions(
    availability: Availability,
    exceptions: list[Exception_],
    *,
    known: dict[str, str] | None = None,
) -> Availability:
    """Overlay this week's deviations on the standing availability.

    Returns a new Availability; the input is untouched, so the difference
    between "what they normally do" and "what they told us this week" stays
    inspectable rather than being overwritten in place.
    """
    updated = Availability(
        by_day={day: set(keys) for day, keys in availability.by_day.items()},
        display_names=dict(availability.display_names),
        unmatched=list(availability.unmatched),
    )
    for exception in exceptions:
        # An exception for a day nobody is planning is a typo or a message
        # about a different week; adding the day would invent a shift.
        if exception.day not in updated.by_day:
            continue
        if exception.available:
            updated.by_day[exception.day].add(exception.key)
            if known and exception.key in known:
                updated.display_names.setdefault(exception.key, known[exception.key])
        else:
            updated.by_day[exception.day].discard(exception.key)
    return updated


def who_to_ask(
    patterns: PatternSet,
    days: list[date],
    needed_by_day: dict[date, int],
) -> dict[date, int]:
    """The shortfall each day, if nobody says anything at all.

    This is the message that replaces the weekly poll. Instead of asking
    everyone and hoping, you ask nobody, look at this, and chase only the days
    that are short.
    """
    cover = patterns.cover(days)
    return {
        day: max(0, needed_by_day.get(day, 0) - cover.get(day, 0))
        for day in sorted(days)
    }

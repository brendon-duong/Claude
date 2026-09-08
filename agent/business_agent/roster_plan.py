"""Building next week's roster from audit performance and the poll schedule.

The schedule says how many callers each poll needs. The audits say who is worth
putting on. This turns the two into a named roster.

Ordering principle: completing surveys is the job, so productivity leads the
ranking — but trust gates it. Anyone barred by their audit history is never
offered a shift no matter how many surveys they complete, because completes
that the call logs do not support are not completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .curia import PollDay
from .performance import StaffPerformance, find_possible_duplicates

# The business week runs Sunday to Thursday, so it straddles two ISO weeks.
# Counting shifts per ISO week would split Sunday off from the rest.
_WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

TIER_ORDER = {"trusted": 0, "watch": 1, "do_not_roster": 2}


def business_week_start(day: date, week_starts: str = "sunday") -> date:
    """The first day of the business week containing `day`."""
    start_weekday = _WEEKDAY_NAMES[week_starts.strip().lower()]
    return day - timedelta(days=(day.weekday() - start_weekday) % 7)


@dataclass
class Assignment:
    """One caller placed on one poll."""

    person: StaffPerformance
    rank_score: float
    reasons: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.person.name


@dataclass
class PollShift:
    """One poll on one day, and who is on it."""

    day: date
    poll: str
    needed: int
    assigned: list[Assignment] = field(default_factory=list)

    @property
    def filled(self) -> int:
        return len(self.assigned)

    @property
    def shortfall(self) -> int:
        return max(0, self.needed - self.filled)


def group_duplicates(performance: dict[str, StaffPerformance]) -> dict[str, str]:
    """Map each caller key to a group shared by their name variants.

    Scoring keeps the variants apart — merging histories without confirmation
    could pin one person's integrity failures on another. Scheduling cannot
    afford the same caution: "Loraine Sabroso" and "Lorraine Sabroso" are one
    human being who can only be in one place, and rostering both onto the same
    day sends a shift out one caller short.
    """
    parent: dict[str, str] = {key: key for key in performance}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for name_a, name_b, _ in find_possible_duplicates(performance):
        key_a, key_b = name_a.strip().lower(), name_b.strip().lower()
        key_a = " ".join(key_a.split())
        key_b = " ".join(key_b.split())
        if key_a in parent and key_b in parent:
            root_a, root_b = find(key_a), find(key_b)
            if root_a != root_b:
                parent[root_b] = root_a

    return {key: find(key) for key in parent}


@dataclass
class RosterPlan:
    start: date
    end: date
    shifts: list[PollShift] = field(default_factory=list)
    excluded: list[StaffPerformance] = field(default_factory=list)
    bench: list[StaffPerformance] = field(default_factory=list)
    skipped_non_working_days: list[date] = field(default_factory=list)
    # Name variants that would have been double-booked had they been treated
    # as different people.
    duplicate_conflicts: list[tuple[date, str, str]] = field(default_factory=list)

    @property
    def total_needed(self) -> int:
        return sum(s.needed for s in self.shifts)

    @property
    def total_filled(self) -> int:
        return sum(s.filled for s in self.shifts)

    @property
    def total_shortfall(self) -> int:
        return sum(s.shortfall for s in self.shifts)

    def shifts_per_person(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for shift in self.shifts:
            for assignment in shift.assigned:
                counts[assignment.person.key] = counts.get(assignment.person.key, 0) + 1
        return counts


def eligible_pool(
    performance: dict[str, StaffPerformance],
    today: date,
    active_within_days: int,
) -> tuple[list[StaffPerformance], list[StaffPerformance]]:
    """Split everyone into those who can be rostered and those who cannot.

    Being audited recently is how we tell who is still on the team — an audit
    sheet keeps names long after people stop working.
    """
    available: list[StaffPerformance] = []
    excluded: list[StaffPerformance] = []
    for person in performance.values():
        if not person.audits or person.last_audit is None:
            continue
        if (today - person.last_audit).days > active_within_days:
            continue  # no longer active
        (available if person.rosterable else excluded).append(person)
    return available, excluded


def build_roster(
    polls: list[PollDay],
    performance: dict[str, StaffPerformance],
    *,
    start: date,
    end: date,
    today: date,
    working_days: list[str],
    max_shifts_per_week: int = 5,
    active_within_days: int = 45,
    fairness_weight: float = 0.06,
    week_starts: str = "sunday",
) -> RosterPlan:
    """Assign named callers to every poll in the date range."""
    allowed = {d.strip().lower() for d in working_days}
    plan = RosterPlan(start=start, end=end)

    in_range = [p for p in polls if start <= p.day <= end and p.pl_staff_needed > 0]
    plan.skipped_non_working_days = sorted(
        {p.day for p in in_range if f"{p.day:%A}".lower() not in allowed}
    )
    scheduled = [p for p in in_range if f"{p.day:%A}".lower() in allowed]
    scheduled.sort(key=lambda p: (p.day, p.poll))

    available, plan.excluded = eligible_pool(performance, today, active_within_days)
    groups = group_duplicates(performance)

    week_counts: dict[tuple[str, date], int] = {}
    assigned_on_day: dict[date, dict[str, str]] = {}

    for poll in scheduled:
        shift = PollShift(day=poll.day, poll=poll.poll, needed=poll.pl_staff_needed)
        week = business_week_start(poll.day, week_starts)
        taken = assigned_on_day.setdefault(poll.day, {})

        candidates = []
        for person in available:
            group = groups.get(person.key, person.key)
            # Anyone already on a poll today is left in the candidate list on
            # purpose: the assignment loop is the single place that skips them
            # and records the name-variant collision, so it cannot be reported
            # in one path and silently dropped in the other.
            worked = week_counts.get((group, week), 0)
            if worked >= max_shifts_per_week:
                continue
            # Spread the work a little among people who rank closely, without
            # letting fairness outrank a materially better caller.
            fairness = fairness_weight * (max_shifts_per_week - worked)
            candidates.append((TIER_ORDER[person.tier], -(person.ranking_score + fairness), person))

        candidates.sort(key=lambda row: (row[0], row[1]))

        # Re-check the group as we assign, not only when collecting: two
        # spellings of one caller are both candidates until the first is
        # placed, so filtering up front lets the second slip through.
        for _, _, person in candidates:
            if shift.filled >= shift.needed:
                break
            group = groups.get(person.key, person.key)
            if group in taken:
                if taken[group] != person.name:
                    plan.duplicate_conflicts.append((poll.day, taken[group], person.name))
                continue
            reasons = [
                f"{person.avg_completes:.1f} completes/shift",
                f"{person.clean_audits}/{person.audits} audits clean",
            ]
            if person.tier == "watch":
                reasons.append(f"watch: {person.headline}")
            shift.assigned.append(
                Assignment(person=person, rank_score=person.ranking_score, reasons=reasons)
            )
            taken[group] = person.name
            week_counts[(group, week)] = week_counts.get((group, week), 0) + 1

        plan.shifts.append(shift)

    used = set(plan.shifts_per_person())
    plan.bench = sorted(
        (p for p in available if p.key not in used),
        key=lambda p: -p.ranking_score,
    )
    return plan

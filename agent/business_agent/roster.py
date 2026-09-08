"""The roster brain: what's needed, what's covered, who can fill the gap.

Deliberately plain Python. Counting shifts and ranking people is arithmetic,
and arithmetic should be deterministic, testable and free -- not a prompt. The
LLM's job is upstream (reading messages) and downstream (wording the ask).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta

from .config import Config
from .models import Candidate, Demand, Event, Gap, Person, Shift


def week_key(day: date) -> tuple[int, int]:
    """ISO year/week, so 'shifts this week' means the same thing all year."""
    iso = day.isocalendar()
    return iso[0], iso[1]


def apply_events(
    shifts: list[Shift], demand: list[Demand], events: list[Event], min_confidence: float = 0.6
) -> tuple[list[Shift], list[Demand], list[Event]]:
    """Fold message events into the roster and demand.

    Returns updated shifts, updated demand, and the events that could not be
    applied (missing a person or a date) so they can be surfaced for a human.
    """
    updated = list(shifts)
    updated_demand = list(demand)
    unresolved: list[Event] = []

    for event in events:
        if event.kind == "noise":
            continue
        if event.confidence < min_confidence:
            unresolved.append(event)
            continue

        if event.kind == "dropout":
            if not event.person_id or not event.day:
                unresolved.append(event)
                continue
            hit = False
            for index, shift in enumerate(updated):
                if (
                    shift.person_id == event.person_id
                    and shift.day == event.day
                    and shift.status != "dropped"
                    and (event.shift is None or shift.shift == event.shift)
                ):
                    note = f"dropped via {event.message.channel} {event.message.sent_at:%d %b %H:%M}"
                    updated[index] = replace(shift, status="dropped", notes=note)
                    hit = True
            if not hit:
                unresolved.append(event)  # said they can't work a shift they weren't on

        elif event.kind == "client_request":
            if not event.day or event.calls is None:
                unresolved.append(event)
                continue
            matched = False
            for index, item in enumerate(updated_demand):
                if item.day == event.day:
                    updated_demand[index] = replace(
                        item,
                        calls_required=item.calls_required + event.calls,
                        notes=(item.notes + " | " if item.notes else "")
                        + f"+{event.calls} from {event.message.sender}",
                    )
                    matched = True
                    break
            if not matched:
                unresolved.append(event)

        elif event.kind == "offer":
            if not event.person_id or not event.day:
                unresolved.append(event)

    return updated, updated_demand, unresolved


def offers_by_person(events: list[Event]) -> dict[tuple[str, date], Event]:
    return {
        (event.person_id, event.day): event
        for event in events
        if event.kind == "offer" and event.person_id and event.day
    }


def _shifts_in_week(shifts: list[Shift], person_id: str, day: date) -> int:
    target = week_key(day)
    return sum(
        1
        for shift in shifts
        if shift.person_id == person_id
        and shift.counts_toward_cover
        and week_key(shift.day) == target
    )


def rank_candidates(
    day: date,
    shift_name: str,
    people: dict[str, Person],
    shifts: list[Shift],
    offers: dict[tuple[str, date], Event],
    required_skills: frozenset[str],
) -> list[Candidate]:
    """Score everyone for one open slot. Blocked people are kept, with reasons.

    Keeping the blocked ones is the point: when nobody is eligible you need to
    see *why* so you can decide what rule to bend.
    """
    on_that_day = {
        shift.person_id
        for shift in shifts
        if shift.day == day and shift.status != "dropped"
    }
    # Someone who just dropped this day has told you they can't work it.
    # Without this the agent cheerfully asks them to cover their own shift.
    dropped_that_day = {
        shift.person_id for shift in shifts if shift.day == day and shift.status == "dropped"
    }

    candidates: list[Candidate] = []
    for person in people.values():
        reasons: list[str] = []
        blockers: list[str] = []
        score = 0.0

        ok, why = person.can_work(day, shift_name, required_skills)
        if not ok:
            blockers.append(why)

        if person.person_id in on_that_day:
            blockers.append("already rostered that day")

        if person.person_id in dropped_that_day:
            blockers.append("dropped out of this day")

        this_week = _shifts_in_week(shifts, person.person_id, day)
        if this_week >= person.max_shifts_per_week:
            blockers.append(f"at weekly cap ({this_week}/{person.max_shifts_per_week})")

        offer = offers.get((person.person_id, day))
        if offer:
            score += 3.0
            reasons.append(f"offered to cover ({offer.message.sent_at:%d %b})")

        score += 1.5 * person.reliability
        if person.reliability >= 0.9:
            reasons.append(f"reliable ({person.reliability:.0%} turn-up)")

        if shift_name in person.preferred_shifts:
            score += 1.0
            reasons.append(f"prefers {shift_name} shifts")

        headroom = person.max_shifts_per_week - this_week
        if headroom > 0:
            score += min(headroom, 3) * 0.3
            reasons.append(f"{this_week} shift(s) this week")

        candidates.append(
            Candidate(person=person, score=round(score, 3), reasons=reasons, blockers=blockers)
        )

    candidates.sort(key=lambda c: (c.eligible, c.score), reverse=True)
    return candidates


def build_gaps(
    people: dict[str, Person],
    shifts: list[Shift],
    demand: list[Demand],
    events: list[Event],
    config: Config,
    today: date,
) -> list[Gap]:
    """Every under-staffed slot in the planning horizon, worst first."""
    horizon_end = today + timedelta(days=config.horizon_days)
    offers = offers_by_person(events)

    by_slot: dict[tuple[date, str], list[Shift]] = defaultdict(list)
    for shift in shifts:
        by_slot[(shift.day, shift.shift)].append(shift)

    gaps: list[Gap] = []
    for item in demand:
        if not (today <= item.day <= horizon_end):
            continue
        needed = item.staff_needed(config.calls_per_person)
        slot = by_slot.get((item.day, item.shift), [])
        covered = sum(1 for shift in slot if shift.counts_toward_cover)
        if covered >= needed:
            continue

        required_skills = frozenset(
            s.lower() for s in config.shift_skills.get(item.shift, [])
        )
        gaps.append(
            Gap(
                day=item.day,
                shift=item.shift,
                needed=needed,
                covered=covered,
                dropouts=[s for s in slot if s.status == "dropped"],
                candidates=rank_candidates(
                    item.day, item.shift, people, shifts, offers, required_skills
                ),
            )
        )

    gaps.sort(key=lambda g: (g.day, g.shift))
    return gaps

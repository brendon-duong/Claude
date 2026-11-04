"""Writing the messages -- and never sending them.

There is no send function in this file, or anywhere in this project. The agent
produces text; a human presses send. That boundary is the whole safety model
while you are learning what the agent actually does, so keep it.
"""

from __future__ import annotations

from datetime import date

from .models import Draft, Gap

MAX_ASKS_PER_GAP = 3


def _day_label(day: date) -> str:
    """"Thursday 12 Mar" -- how a person would say it in a message."""
    return f"{day:%A} {day.day} {day:%b}"


def draft_cover_request(gap: Gap, candidate_index: int, business_name: str) -> Draft | None:
    """Ask one person to cover one gap."""
    eligible = [c for c in gap.candidates if c.eligible]
    if candidate_index >= len(eligible):
        return None
    candidate = eligible[candidate_index]
    person = candidate.person

    dropped = ", ".join(shift.person_id for shift in gap.dropouts)
    context = f" ({dropped} dropped out)" if dropped else ""
    first_name = person.name.split()[0] if person.name else person.person_id

    body = (
        f"Hi {first_name}, are you free to cover the {gap.shift} shift on "
        f"{_day_label(gap.day)}?{context} "
        f"We're {gap.short_by} short. Let me know either way and I'll lock it in. "
        f"Thanks! - {business_name}"
    )
    return Draft(
        to_name=person.name,
        to_phone=person.phone,
        channel="whatsapp",
        subject=f"Cover request: {gap.shift} shift {gap.day.isoformat()}",
        body=body,
        about=f"gap {gap.day.isoformat()} {gap.shift} (short {gap.short_by})",
    )


def draft_escalation(gap: Gap, business_name: str) -> Draft:
    """Nobody is eligible -- this one is for you, not for the team."""
    blocked = "; ".join(
        f"{c.person.name}: {', '.join(c.blockers)}" for c in gap.candidates[:5] if c.blockers
    )
    body = (
        f"No eligible cover for the {gap.shift} shift on {_day_label(gap.day)} "
        f"(short {gap.short_by} of {gap.needed}).\n\n"
        f"Why everyone is blocked:\n{blocked or 'no team members loaded'}\n\n"
        f"Options: lift someone's weekly cap, split the calls across other days, "
        f"or tell the client this day is capped."
    )
    return Draft(
        to_name="You",
        to_phone="",
        channel="internal",
        subject=f"ESCALATION: no cover for {gap.day.isoformat()} {gap.shift}",
        body=body,
        about=f"gap {gap.day.isoformat()} {gap.shift}",
    )


def draft_partial_cover(gap: Gap, eligible_count: int, business_name: str) -> Draft:
    """Enough people to ask, but not enough to actually fill the shift."""
    body = (
        f"The {gap.shift} shift on {_day_label(gap.day)} is short {gap.short_by}, "
        f"but only {eligible_count} eligible people exist to ask. "
        f"Even if everyone says yes you are still {gap.short_by - eligible_count} short.\n\n"
        f"Decide now rather than on the day: reduce the calls booked, "
        f"move some to another day, or bring in someone outside the usual team."
    )
    return Draft(
        to_name="You",
        to_phone="",
        channel="internal",
        subject=f"PARTIAL COVER: {gap.day.isoformat()} {gap.shift} can only fill {eligible_count}/{gap.short_by}",
        body=body,
        about=f"gap {gap.day.isoformat()} {gap.shift}",
    )


def build_drafts(gaps: list[Gap], business_name: str) -> list[Draft]:
    """One draft per person we'd ask, plus a flag wherever the maths can't work."""
    drafts: list[Draft] = []
    for gap in gaps:
        eligible = [c for c in gap.candidates if c.eligible]
        if not eligible:
            drafts.append(draft_escalation(gap, business_name))
            continue
        if len(eligible) < gap.short_by:
            drafts.append(draft_partial_cover(gap, len(eligible), business_name))
        # Ask enough people to cover the shortfall, with a couple in reserve.
        asks = min(len(eligible), max(gap.short_by, 1) + MAX_ASKS_PER_GAP - 1)
        for index in range(asks):
            draft = draft_cover_request(gap, index, business_name)
            if draft:
                drafts.append(draft)
    return drafts

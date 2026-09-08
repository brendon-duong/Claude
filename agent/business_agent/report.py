"""The daily brief: one file you read in 60 seconds.

Ordered by what needs a decision, not by what the code happened to compute.
"""

from __future__ import annotations

from datetime import date

from .audit import AuditRecord
from .models import Draft, Event, Gap, Person, Shift
from .performance import StaffPerformance, find_possible_duplicates


def _day_label(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def build_brief(
    *,
    business_name: str,
    today: date,
    gaps: list[Gap],
    drafts: list[Draft],
    events: list[Event],
    unresolved: list[Event],
    people: dict[str, Person],
    shifts: list[Shift],
    performance: dict[str, StaffPerformance] | None = None,
    audits: list[AuditRecord] | None = None,
    working_days: list[str] | None = None,
) -> str:
    dropouts = [e for e in events if e.kind == "dropout"]
    offers = [e for e in events if e.kind == "offer"]
    requests = [e for e in events if e.kind == "client_request"]
    urgent = [g for g in gaps if (g.day - today).days <= 2]
    urgent_slots = {(g.day, g.shift) for g in urgent}

    lines: list[str] = [
        f"# {business_name} — roster brief",
        f"_{today:%A %d %B %Y}_",
        "",
        "## Bottom line",
    ]

    if not gaps:
        lines.append("- Every shift in the horizon is covered. Nothing needs you.")
    else:
        short = sum(g.short_by for g in gaps)
        lines.append(f"- **{short} slot(s) unfilled** across {len(gaps)} shift(s).")
        if urgent:
            lines.append(
                f"- **{len(urgent)} of them are within 48 hours** — these are the ones to action now."
            )
        askable = sum(1 for d in drafts if d.channel == "whatsapp")
        lines.append(f"- {askable} cover request(s) drafted, ready for you to send.")

        no_cover = [g for g in gaps if not any(c.eligible for c in g.candidates)]
        partial = [
            g for g in gaps
            if 0 < sum(1 for c in g.candidates if c.eligible) < g.short_by
        ]
        if no_cover:
            lines.append(
                f"- {len(no_cover)} shift(s) have **no eligible cover at all** — these need a decision from you."
            )
        if partial:
            lines.append(
                f"- {len(partial)} shift(s) **cannot be fully filled** even if everyone says yes."
            )

    if working_days:
        allowed = {day.strip().lower() for day in working_days}
        outside = sorted({g.day for g in gaps if f"{g.day:%A}".lower() not in allowed})
        if outside:
            lines.append(
                "- ⚠️ Work scheduled outside the Sunday–Thursday week: "
                + ", ".join(_day_label(d) for d in outside)
            )

    lines += ["", "## What changed since the last run"]
    if not (dropouts or offers or requests):
        lines.append("- No roster-relevant messages.")
    for event in dropouts:
        who = people[event.person_id].name if event.person_id in people else event.message.sender
        when = _day_label(event.day) if event.day else "date unclear"
        lines.append(f"- 🔴 **{who} dropped out** — {when} · _\"{event.message.text[:90]}\"_")
    for event in offers:
        who = people[event.person_id].name if event.person_id in people else event.message.sender
        when = _day_label(event.day) if event.day else "date unclear"
        lines.append(f"- 🟢 **{who} offered to cover** — {when} · _\"{event.message.text[:90]}\"_")
    for event in requests:
        when = _day_label(event.day) if event.day else "date unclear"
        lines.append(
            f"- 🔵 **Client request** from {event.message.sender} — +{event.calls} calls, {when}"
        )

    performance = performance or {}
    audits = audits or []
    scored = [p for p in performance.values() if p.audits]
    if scored:
        barred = sorted(
            (p for p in scored if not p.rosterable), key=lambda p: p.score
        )
        watch = sorted(
            (p for p in scored if p.rosterable and p.tier == "watch"), key=lambda p: p.score
        )
        trusted = [p for p in scored if p.tier == "trusted"]

        lines += [
            "",
            "## What the audits say",
            "",
            f"_{len(audits)} audits across {len(scored)} callers. "
            f"{len(trusted)} trusted, {len(watch)} to watch, {len(barred)} not to roster._",
        ]

        if barred:
            lines.append("\n**Do not roster** — the agent will not offer these people a shift:\n")
            for record in barred:
                lines.append(f"- **{record.name}** (score {record.score:.2f}) — {record.headline}")
                for concern in record.concerns[:3]:
                    lines.append(f"  - {concern}")

        if watch:
            lines.append("\n**Watch** — rosterable, but keep an eye on them:\n")
            for record in watch:
                lines.append(f"- **{record.name}** (score {record.score:.2f}) — {record.headline}")

        duplicates = find_possible_duplicates(performance)
        if duplicates:
            lines += [
                "",
                f"**{len(duplicates)} pair(s) of names look like the same caller twice.** "
                "Each variant splits that person's audit history, which flatters the half "
                "without the failures. Nothing is merged automatically — confirm and fix "
                "the spelling in the sheet:",
                "",
            ]
            for name_a, name_b, why in duplicates[:12]:
                a = performance.get(name_a.strip().lower())
                b = performance.get(name_b.strip().lower())
                counts = (
                    f" ({a.audits} + {b.audits} audits)" if a and b else ""
                )
                lines.append(f"- **{name_a}** / **{name_b}**{counts} — {why}")
            if len(duplicates) > 12:
                lines.append(f"- …and {len(duplicates) - 12} more")

        disputed = [a for a in audits if a.reviewer_disagrees]
        if disputed:
            lines += [
                "",
                f"**{len(disputed)} audit row(s) where the Y/N column disagrees with the "
                "numbers** — worth a look, in both directions:",
                "",
            ]
            for record in disputed[:10]:
                said = "Y" if record.reviewer_flagged else "N"
                if record.over_declared:
                    what = (
                        f"declared {record.declared_completes}, logs show "
                        f"{record.actual_completes}"
                    )
                elif record.off_phone_minutes:
                    what = f"{record.off_phone_minutes} min off the phone"
                elif record.short_by_minutes:
                    what = f"{record.short_by_minutes} min short of the declared shift"
                elif record.time_discrepancies:
                    what = "start/finish time mismatch"
                else:
                    what = "nothing found in the numbers"
                lines.append(
                    f"- {_day_label(record.day)} **{record.name}** — marked *{said}*, but {what}"
                )

    lines += ["", "## Gaps and who to ask"]
    if not gaps:
        lines.append("_None._")
    for gap in gaps:
        flag = " ⚠️" if (gap.day, gap.shift) in urgent_slots else ""
        lines.append(
            f"\n### {_day_label(gap.day)} — {gap.shift}{flag}\n"
            f"Need {gap.needed}, have {gap.covered}, **short {gap.short_by}**."
        )
        if gap.dropouts:
            lines.append(
                "Dropped: " + ", ".join(f"{s.person_id} ({s.notes})" for s in gap.dropouts)
            )
        eligible = [c for c in gap.candidates if c.eligible][:5]
        if eligible:
            lines.append("\n| # | Who | Score | Why them |\n|---|---|---|---|")
            for rank, candidate in enumerate(eligible, 1):
                lines.append(
                    f"| {rank} | {candidate.person.name} | {candidate.score:.2f} | "
                    f"{'; '.join(candidate.reasons) or '—'} |"
                )
        else:
            lines.append("\n**Nobody is eligible.** Blocked because:")
            for candidate in gap.candidates[:6]:
                lines.append(f"- {candidate.person.name}: {'; '.join(candidate.blockers)}")

    if unresolved:
        lines += ["", "## Needs your eyes (agent wasn't confident)"]
        for event in unresolved:
            lines.append(
                f"- **{event.message.sender}** ({event.kind}, {event.confidence:.0%} sure): "
                f"_\"{event.message.text[:110]}\"_ — {event.rationale}"
            )

    lines += ["", "## Drafted messages", "", "_Nothing below has been sent._"]
    for index, draft in enumerate(drafts, 1):
        target = f"{draft.to_name}" + (f" · {draft.to_phone}" if draft.to_phone else "")
        lines += [
            f"\n**{index}. {draft.subject}**",
            f"To: {target} ({draft.channel})",
            "",
            "```",
            draft.body,
            "```",
        ]

    active = sum(1 for s in shifts if s.counts_toward_cover)
    lines += [
        "",
        "---",
        f"_{len(people)} team members · {active} confirmed shifts on the books · "
        f"{len(events)} messages read._",
        "",
    ]
    return "\n".join(lines)

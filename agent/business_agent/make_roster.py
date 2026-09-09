"""Build a week's roster page.

    python3 -m business_agent.make_roster --config config.json \
        --start 2026-09-13 --end 2026-09-17 --poll poll.txt

Reads the schedule and the audit history, picks the callers, and writes an
HTML page. With --poll it picks from the people who put their hand up in the
WhatsApp poll; without it, from everyone still active.

With --announce it also writes the WhatsApp messages for the week, with every
rostered caller @-tagged. Those are drafts. Nothing here sends anything.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from .announce import render_roster_announcement
from .audit import load_audits
from .availability import Availability, from_form_responses, parse_availability
from .config import Config
from .curia import load_schedule
from .directory import Directory
from .loaders import load_demand_rows  # noqa: F401  (kept for config validation)
from .page import render_roster_page
from .performance import Thresholds, find_possible_duplicates, score_all
from .roster_plan import build_roster
from .sheets import load_table


def _day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a roster page for one week.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--start", required=True, help="first day, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="last day, YYYY-MM-DD")
    parser.add_argument(
        "--poll", default="", help="file of pasted poll results (overrides the form sheet)"
    )
    parser.add_argument("--today", default="", help="override today's date")
    parser.add_argument("--max-shifts", type=int, default=5, help="cap per person per week")
    parser.add_argument("--out", default="", help="where to write the page")
    parser.add_argument(
        "--announce",
        default="",
        help="WhatsApp group snapshot; writes the tagged roster messages alongside the page",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2
    base_dir = config_path.parent
    config = Config.load(config_path)

    if not config.audit.path:
        print("no audit source configured — nothing to rank callers on", file=sys.stderr)
        return 2

    today = _day(args.today) if args.today else date.today()
    start, end = _day(args.start), _day(args.end)

    audits = load_audits(load_table(config.audit, config, base_dir))
    if not audits:
        print("the audit sheet produced no records", file=sys.stderr)
        return 1
    polls, _non_polls = load_schedule(load_table(config.demand, config, base_dir))
    people = score_all(audits, today, Thresholds(**config.performance))

    known = {p.key: p.name for p in people.values() if p.audits}
    # Days the roster covers, so the form can tell "nobody ticked this" apart
    # from "the form never asked about this".
    offered = sorted({p.day for p in polls if start <= p.day <= end})

    availability: Availability | None = None
    if args.poll:
        poll_path = Path(args.poll)
        if not poll_path.is_absolute():
            poll_path = base_dir / poll_path
        availability = parse_availability(
            poll_path.read_text(encoding="utf-8"), known, today
        )
    elif config.availability.path:
        availability = from_form_responses(
            load_table(config.availability, config, base_dir),
            known,
            today,
            offered_days=offered,
        )

    plan = build_roster(
        polls,
        people,
        start=start,
        end=end,
        today=today,
        working_days=config.working_days,
        max_shifts_per_week=args.max_shifts,
        availability=availability,
    )

    duplicates = find_possible_duplicates(people)
    page = render_roster_page(
        plan,
        business_name=config.business_name,
        audit_count=len(audits),
        audit_from=min(a.day for a in audits),
        audit_to=max(a.day for a in audits),
        duplicates=duplicates[:8],
        duplicate_total=len(duplicates),
    )

    out_dir = base_dir / config.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / f"roster_{start:%Y-%m-%d}.html"
    out_path.write_text(page, encoding="utf-8")

    if args.announce:
        _write_announcements(plan, Path(args.announce), out_path)

    print(
        f"{plan.total_filled}/{plan.total_needed} slots filled across {len(plan.shifts)} poll(s), "
        f"{len(plan.shifts_per_person())} callers used, {len(plan.excluded)} barred -> {out_path}"
    )
    if availability is not None:
        print(
            f"  {availability.volunteer_count} caller(s) replied, covering "
            f"{len(availability.days)} day(s)"
        )
    for day in plan.days_without_a_poll:
        print(f"  note: the poll said nothing about {day:%a %d %b}; picked from everyone active")
    for day, person in plan.volunteered_but_barred:
        print(f"  note: {person.name} volunteered for {day:%a %d %b} but is barred")
    for day, name in plan.unmatched_names:
        print(f"  note: '{name}' ({day:%a %d %b}) matches nobody in the audit history")
    if plan.total_shortfall:
        print(f"  {plan.total_shortfall} slot(s) could not be filled")
    return 0


def _write_announcements(plan, snapshot: Path, page_path: Path) -> None:
    """Write the week's WhatsApp messages next to the page.

    Two files: the bodies as they would be sent, phone numbers and all, and a
    preview with names written back in. The preview is the one to read; the
    other is only readable by WhatsApp.
    """
    directory = Directory.load(snapshot)
    sendable: list[str] = []
    preview: list[str] = []
    untagged: set[str] = set()

    for shift in plan.shifts:
        names = [person.name for person in shift.assigned]
        if not names:
            continue
        message = render_roster_announcement(
            shift.day, names, directory, poll=shift.poll
        )
        untagged |= set(message.untagged)
        sendable.append(message.text)
        preview.append(
            f"--- {shift.day:%a %d %b} · {shift.poll} · "
            f"{len(message.mentions)}/{len(names)} tagged ---\n{message.preview}"
        )

    stem = page_path.with_suffix("")
    Path(f"{stem}_messages.txt").write_text("\n\n".join(sendable) + "\n", encoding="utf-8")
    Path(f"{stem}_messages_preview.txt").write_text(
        "\n\n".join(preview) + "\n", encoding="utf-8"
    )
    print(f"  drafted {len(sendable)} WhatsApp message(s) -> {stem}_messages_preview.txt")
    for name in sorted(untagged):
        print(f"  note: {name} has no WhatsApp match and will not be notified")


if __name__ == "__main__":
    raise SystemExit(main())

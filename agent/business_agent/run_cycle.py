"""One pass of the agent. Run it on a schedule and you have a looping agent.

    python3 -m business_agent.run_cycle --config config.json

Every run is self-contained: read the current state of the world, work out what
needs doing, write it down, exit. No daemon, no in-memory state to corrupt, and
a crash costs you one cycle instead of the whole agent. This is the shape you
want for anything unattended.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from .config import Config
from .drafts import build_drafts
from .loaders import load_all
from .messages import load_inbox
from .report import build_brief
from .roster import apply_events, build_gaps
from .triage import triage


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def run(config_path: Path, today: date, quiet: bool = False) -> Path:
    """Execute one cycle. Returns the path of the brief it wrote."""
    base_dir = config_path.parent
    config = Config.load(config_path)

    people, shifts, demand = load_all(config, base_dir)
    messages = load_inbox(_resolve(base_dir, config.messages_dir))
    events = triage(messages, people, today, config)
    shifts, demand, unresolved = apply_events(shifts, demand, events)
    gaps = build_gaps(people, shifts, demand, events, config, today)
    drafts = build_drafts(gaps, config.business_name)

    brief = build_brief(
        business_name=config.business_name,
        today=today,
        gaps=gaps,
        drafts=drafts,
        events=events,
        unresolved=unresolved,
        people=people,
        shifts=shifts,
    )

    out_dir = _resolve(base_dir, config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    brief_path = out_dir / f"brief_{stamp}.md"
    brief_path.write_text(brief, encoding="utf-8")
    (out_dir / "latest_brief.md").write_text(brief, encoding="utf-8")

    # A machine-readable copy, so a later step (a Sheet writer, a dashboard,
    # a Claude follow-up) never has to re-parse the markdown.
    (out_dir / "latest_drafts.json").write_text(
        json.dumps([asdict(draft) for draft in drafts], indent=2), encoding="utf-8"
    )

    if not quiet:
        short = sum(gap.short_by for gap in gaps)
        print(f"[{stamp}] {len(messages)} messages, {len(gaps)} gaps, {short} slots short, "
              f"{len(drafts)} drafts -> {brief_path}")
    return brief_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one agent cycle.")
    parser.add_argument("--config", default="config.json", help="path to config JSON")
    parser.add_argument("--today", default="", help="override today's date (YYYY-MM-DD)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    )
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        run(config_path, today, quiet=args.quiet)
    except Exception:  # noqa: BLE001 - an unattended run must log, not vanish
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

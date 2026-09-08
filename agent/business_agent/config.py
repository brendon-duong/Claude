"""Configuration loading.

One JSON file drives the whole agent so you can change how your business works
without touching code. See config.example.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceConfig:
    """Where a table of data lives.

    kind "csv"    -> path is a local file (demo mode, or an exported sheet)
    kind "xlsx"   -> path is a local .xlsx file, tab is the worksheet name.
                     Needed for sheets uploaded to Drive rather than converted:
                     they stay as Excel files and the Sheets API cannot read them.
    kind "gsheet" -> path is the Google Sheet ID, tab is the worksheet name
    """

    kind: str = "csv"
    path: str = ""
    tab: str = ""


@dataclass
class Config:
    business_name: str = "My Business"
    timezone: str = "Australia/Sydney"

    # How many calls one person handles in a shift. Used to turn "I need 40
    # calls on Tuesday" into "I need 4 people on Tuesday".
    calls_per_person: int = 10

    # How many days ahead to plan. Dropouts next week matter more than today's.
    horizon_days: int = 14

    # Skills a shift needs, keyed by shift name. Empty means anyone can do it.
    shift_skills: dict[str, list[str]] = field(default_factory=dict)

    team: SourceConfig = field(default_factory=SourceConfig)
    # The roster is optional: while it lives in WhatsApp there is no sheet to
    # read, and every confirmed slot is simply unfilled until messages say
    # otherwise. Leave path empty to run without one.
    roster: SourceConfig = field(default_factory=SourceConfig)
    demand: SourceConfig = field(default_factory=SourceConfig)

    # "curia"  -> the Curia schedule layout: one row per poll, continuation
    #             rows for a second poll the same day, PL Staff Confirmed as
    #             the headcount.
    # "simple" -> the plain date/shift/calls_required layout.
    demand_format: str = "simple"

    # The Audit - PL sheet. Optional: without it everyone is treated as
    # unaudited rather than as untrustworthy.
    audit: SourceConfig = field(default_factory=SourceConfig)

    # Overrides for performance.Thresholds — the rules about off-phone time,
    # integrity failures and how quickly old audits stop counting.
    performance: dict[str, float] = field(default_factory=dict)

    # The business runs Sunday to Thursday. Work scheduled outside these days
    # is surfaced as an anomaly rather than silently rostered.
    working_days: list[str] = field(
        default_factory=lambda: ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    )

    # Where inbound messages are read from.
    messages_dir: str = "inbox"

    # How far back to read them. A WhatsApp export contains the whole chat
    # history, so without a window the agent would act on a dropout from
    # months ago every time you drop in a fresh export.
    message_lookback_days: int = 7

    # Where the agent writes its output. Nothing is ever sent from here.
    out_dir: str = "out"

    # Use the Claude CLI to triage messy messages. Falls back to rules if the
    # CLI is missing or errors, so the agent never hard-fails on this.
    use_claude_triage: bool = True
    claude_command: str = "claude"
    claude_timeout_seconds: int = 120

    # Google service-account JSON, for kind="gsheet" sources.
    google_credentials_path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = json.loads(Path(path).read_text())
        sources = {
            key: SourceConfig(**raw.pop(key))
            for key in ("team", "roster", "demand", "audit")
            if key in raw
        }
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown config key(s): {', '.join(sorted(unknown))}")
        return cls(**raw, **sources)

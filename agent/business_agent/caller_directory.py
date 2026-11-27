"""Join Slack, Zoom and call history into one roster-wide caller directory.

Built 24 Sep 2026 by hand, ad hoc, from three live calls (`slack_list_channel_members`
on #roster-pacificlinkglobal, `GET /v2/phone/users`, and `calllogs.calls_for_day` over
24 days) with nowhere for the join logic itself to live. That meant every refresh was a
from-scratch rebuild in whatever session happened to do it, and nobody did one again for
13 days.

This module is that join, as code: feed it the three plain inputs and it does the
identity resolution, using `names.match` rather than a second, parallel name matcher -
the roster already has one, and the duplicate-name rule ("a name that could be two
people is matched to neither") only has to be obeyed in one place.

It does not call Slack, Zoom or Sheets itself. A caller (interactive session or Routine)
fetches the three lists live and passes them in; this module only joins and classifies.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import names

ACTIVE_SHIFTS = 8  # shifts in the window -> "active", per the 24 Sep directory build
WINDOW_DAYS = 24

STATUS_ACTIVE = "active"
STATUS_OCCASIONAL = "occasional"
STATUS_NONE = "none"


@dataclass(frozen=True)
class SlackMember:
    user_id: str
    real_name: str
    email: str


@dataclass(frozen=True)
class ZoomUser:
    extension: str
    display_name: str
    email: str
    did: str | None = None
    has_calling_plan: bool = False


@dataclass(frozen=True)
class CallHistory:
    """One caller's activity over the trailing window, keyed by Zoom display name."""

    display_name: str
    shifts: int
    last_worked: dt.date | None = None


@dataclass
class CallerRow:
    name: str  # canonical roster name where resolved, else the Slack real name
    slack_user_id: str | None = None
    email: str | None = None
    zoom_ext: str | None = None
    zoom_did: str | None = None
    has_calling_plan: bool = False
    shifts: int = 0
    last_worked: dt.date | None = None
    status: str = STATUS_NONE
    notes: str = ""


def status_for(shifts: int) -> str:
    if shifts >= ACTIVE_SHIFTS:
        return STATUS_ACTIVE
    if shifts >= 1:
        return STATUS_OCCASIONAL
    return STATUS_NONE


def _resolved_canonical(display_name: str) -> str | None:
    """The roster name this display name confidently is, or None.

    Only `exact` and `settled` count as confident. `candidate` and `ambiguous`
    are exactly the cases the project's standing rule says to report, never
    guess past - so they fall through to None here too, same as `unmatched`.
    """
    result = names.match(display_name)
    return result.roster if result.how in ("exact", "settled") else None


def build_directory(
    slack_members: list[SlackMember],
    zoom_users: list[ZoomUser],
    call_history: list[CallHistory],
) -> list[CallerRow]:
    """Join the three inputs into one row per Slack member.

    Email is the primary key - CLAUDE.md calls it the first unambiguous join key
    this project has had. Where a Slack member's Zoom email differs (two callers
    are already known to do this: Eunilyn Lisondra, Lovely Salva), the fallback is
    resolving both the Slack real name and the Zoom display name to the same
    canonical roster name via `names.match`, never a second ad hoc string compare.
    """
    zoom_by_email = {z.email.strip().lower(): z for z in zoom_users if z.email}
    zoom_by_canonical: dict[str, ZoomUser] = {}
    for z in zoom_users:
        canonical = _resolved_canonical(z.display_name)
        if canonical and canonical not in zoom_by_canonical:
            zoom_by_canonical[canonical] = z

    history_by_canonical: dict[str, CallHistory] = {}
    for h in call_history:
        canonical = _resolved_canonical(h.display_name)
        if canonical:
            history_by_canonical[canonical] = h

    # First pass: tentatively resolve each member's canonical roster name.
    tentative: list[tuple[SlackMember, ZoomUser | None, str | None]] = []
    for member in slack_members:
        zoom = zoom_by_email.get(member.email.strip().lower())
        canonical: str | None = None
        if zoom is not None:
            canonical = _resolved_canonical(zoom.display_name)
        else:
            canonical = _resolved_canonical(member.real_name)
            if canonical:
                zoom = zoom_by_canonical.get(canonical)
        tentative.append((member, zoom, canonical))

    # A canonical name claimed by more than one Slack member is the duplicate
    # case every other matcher in this project treats as "match neither" - so
    # it is unresolved here too, flagged for a person rather than guessed at.
    claim_counts: dict[str, int] = {}
    for _, _, canonical in tentative:
        if canonical:
            claim_counts[canonical] = claim_counts.get(canonical, 0) + 1

    rows: list[CallerRow] = []
    for member, zoom, canonical in tentative:
        notes = ""
        if canonical and claim_counts.get(canonical, 0) > 1:
            notes = f"shared match on '{canonical}' with another Slack member - needs a person"
            canonical, zoom = None, None
        elif canonical is None and zoom is None:
            notes = "no Zoom match found - check email and name by hand"

        history = history_by_canonical.get(canonical) if canonical else None
        shifts = history.shifts if history else 0
        rows.append(
            CallerRow(
                name=canonical or member.real_name,
                slack_user_id=member.user_id,
                email=member.email or None,
                zoom_ext=zoom.extension if zoom else None,
                zoom_did=zoom.did if zoom else None,
                has_calling_plan=bool(zoom and zoom.has_calling_plan),
                shifts=shifts,
                last_worked=history.last_worked if history else None,
                status=status_for(shifts),
                notes=notes,
            )
        )
    return rows


CSV_HEADER = [
    "Name", "Slack ID", "Email", "Zoom Ext", "Zoom DID",
    "Calling Plan", f"Shifts ({WINDOW_DAYS}d)", "Last Worked", "Status", "Notes",
]


def to_rows(directory: list[CallerRow]) -> list[list[str]]:
    """The directory as a header row plus one row per caller, name-sorted.

    Shaped for `scripts/sheets.mjs write` - a plain list of lists, nothing a
    tool argument can't carry.
    """
    rows = [list(CSV_HEADER)]
    for row in sorted(directory, key=lambda r: r.name.lower()):
        rows.append(
            [
                row.name,
                row.slack_user_id or "",
                row.email or "",
                row.zoom_ext or "",
                row.zoom_did or "",
                "yes" if row.has_calling_plan else "no",
                str(row.shifts),
                row.last_worked.isoformat() if row.last_worked else "",
                row.status,
                row.notes,
            ]
        )
    return rows

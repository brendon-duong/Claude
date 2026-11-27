"""Reading the "Curia 2026 Schedule" sheet.

This is the demand side of the business: which poll runs on which day, and how
many PL callers are confirmed for it. Who those callers actually are lives in
WhatsApp, not here.

The sheet is maintained by hand over several years, so this module is built
around its real quirks rather than an idealised version of it:

  * A second poll on the same day sits on a *continuation row* with the Date
    cell left blank. The date carries down from the row above.
  * Non-poll days (weekends, gaps) are present but empty.
  * Holidays put a name in the Poll column with no staffing numbers at all.
  * Computed columns can hold #DIV/0! and other spreadsheet errors.
  * Line endings are CRLF and the text is UTF-8 (poll names include "Māori").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from .models import Demand
from .sheets import Row

# "Tuesday 08-Sep-26", and the same thing with the weekday missing.
_DATE_PATTERN = re.compile(
    r"(?:(?P<weekday>[A-Za-z]+)\s+)?(?P<rest>\d{1,2}[-/][A-Za-z]{3,}[-/]\d{2,4})"
)
_DATE_FORMATS = ("%d-%b-%y", "%d-%b-%Y", "%d/%b/%y", "%d-%B-%y", "%d-%B-%Y")

# Cells that mean "no number here", including spreadsheet error values.
_NOT_A_NUMBER = {"", "-", "n/a", "na", "tbc", "tbd", "#div/0!", "#ref!", "#value!", "#n/a"}

_STAFFING_COLUMNS = (
    "online target",
    "phone target",
    "curia staff wanted",
    "pl staff confirmed",
    "extra pl staff required day of shift",
    "pl staff total worked",
)


@dataclass(frozen=True)
class PollDay:
    """One poll running on one day, as the schedule describes it."""

    day: date
    poll: str
    online_target: int | None = None
    phone_target: int | None = None
    curia_staff_wanted: int | None = None
    pl_staff_confirmed: int | None = None
    extra_pl_required: int | None = None
    pl_staff_worked: int | None = None

    @property
    def slot(self) -> str:
        """The poll name, normalised, used as the shift identifier."""
        return re.sub(r"\s+", " ", self.poll).strip().lower()

    @property
    def pl_staff_needed(self) -> int:
        """Callers PL must supply: those confirmed, plus any extra asked for
        on the day. Extra is how the sheet records 'we came up short'."""
        return (self.pl_staff_confirmed or 0) + (self.extra_pl_required or 0)


@dataclass(frozen=True)
class NonPollDay:
    """A day with a label but no staffing -- a holiday, or a note."""

    day: date
    label: str


def parse_schedule_date(value: str) -> date | None:
    """Parse "Tuesday 08-Sep-26". Returns None for blanks and continuation rows."""
    text = (value or "").strip()
    if not text:
        return None
    match = _DATE_PATTERN.search(text)
    if not match:
        return None
    rest = match.group("rest").replace("/", "-")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(rest, fmt).date()
        except ValueError:
            continue
    return None


def to_int(value: str) -> int | None:
    """Sheet cell to int, tolerating blanks, errors and stray formatting."""
    text = (value or "").strip().lower()
    if text in _NOT_A_NUMBER:
        return None
    text = text.replace(",", "").replace("$", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def _has_staffing_numbers(row: Row) -> bool:
    return any(to_int(row.get(column, "")) is not None for column in _STAFFING_COLUMNS)


def load_schedule(rows: list[Row]) -> tuple[list[PollDay], list[NonPollDay]]:
    """Parse the whole schedule into poll days and labelled non-poll days.

    Returns both, because "Good Friday, no poll" and "nobody has filled this
    row in yet" look identical to a gap-finder but mean opposite things.
    """
    polls: list[PollDay] = []
    non_polls: list[NonPollDay] = []
    current_day: date | None = None

    for row in rows:
        parsed = parse_schedule_date(row.get("date", ""))
        if parsed is not None:
            current_day = parsed
        # else: continuation row -- another poll on current_day.

        if current_day is None:
            continue  # header junk above the first real date

        poll = (row.get("poll") or "").strip()
        if not poll:
            continue  # an empty day: no poll scheduled, nothing to staff

        if not _has_staffing_numbers(row):
            non_polls.append(NonPollDay(day=current_day, label=poll))
            continue

        polls.append(
            PollDay(
                day=current_day,
                poll=poll,
                online_target=to_int(row.get("online target", "")),
                phone_target=to_int(row.get("phone target", "")),
                curia_staff_wanted=to_int(row.get("curia staff wanted", "")),
                pl_staff_confirmed=to_int(row.get("pl staff confirmed", "")),
                extra_pl_required=to_int(
                    row.get("extra pl staff required day of shift", "")
                ),
                pl_staff_worked=to_int(row.get("pl staff total worked", "")),
            )
        )

    return polls, non_polls


def to_demand(polls: list[PollDay]) -> list[Demand]:
    """Convert poll days into the agent's demand records.

    `PL Staff Confirmed` is a headcount, so it is passed through as
    staff_required directly -- there is no calls-per-person division to do.
    Polls needing no PL callers are dropped rather than becoming zero-staff
    rows that would look like satisfied demand.
    """
    demand: list[Demand] = []
    for poll in polls:
        needed = poll.pl_staff_needed
        if needed <= 0:
            continue
        note = poll.poll
        if poll.extra_pl_required:
            note += f" (+{poll.extra_pl_required} extra requested on the day)"
        demand.append(
            Demand(
                day=poll.day,
                shift=poll.slot,
                calls_required=poll.phone_target or 0,
                staff_required=needed,
                notes=note,
            )
        )
    return demand

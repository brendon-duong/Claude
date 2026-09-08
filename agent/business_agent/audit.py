"""Reading the "Audit - PL" sheet.

Each row compares what a caller declared in WhatsApp against what the call logs
actually show, for one person on one audited day. Two things matter:

**Integrity.** If the call logs show at least as many completed surveys as the
person declared, they were truthful. Declaring six and having three found is
not a rounding error -- it is the most serious signal in the whole system, and
it is judged from the numbers, never from the reviewer's Y/N column.

**Time on the phone.** The standing ask is not to be away for more than five
minutes at a stretch. Fifteen or twenty minutes now and then is tolerated. An
hour off the phone is not. Breaks the caller declared in advance are excused.

Sheet shape: a date on its own row ("March 9, 2026") opens a section, and every
row beneath it is one person audited on that date until the next date row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .sheets import Row

# Column names after normalisation (header text wraps in the real sheet).
_NAME = ""
_DECLARED_COMPLETES = "numbers of completed surveys in whatsapp"
_ACTUAL_COMPLETES = "numbers of completed surveys in call logs"
_DECLARED_CALLS = "total number of calls in whatsapp"
_ACTUAL_CALLS = "total number of calls in call logs"
_REVIEWER_FLAG = "discrepancy identified? y/n"
_DETAILS = "details"

_SECTION_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y")

# "10 mins off the phone between 6:33 - 6:42", and the shorthand
# "5 mins between 6:12 - 6:17" that appears when it follows another break.
_BREAK = re.compile(
    r"(?P<minutes>\d{1,3})\s*min(?:ute)?s?\s+(?:off\s+the\s+phone\s+)?between\s+"
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)
_TIME_DISCREPANCY = re.compile(
    r"Declared\s+(?:Start\s+Time|Time\s+In\s*&\s*Out|Time\s+In|Time\s+Out|End\s+Time)\s*:[^\n]*",
    re.IGNORECASE,
)
_NO_CALL_LOGS = re.compile(r"no\s+call\s+logs", re.IGNORECASE)
_DECLARED_BREAK = re.compile(r"declared\s+break", re.IGNORECASE)


def normalise_name(name: str) -> str:
    """Collapse the spelling variants a hand-kept sheet accumulates.

    "Elaine  Abugan" and "Elaine Abugan" are one person; without this they
    score as two people with half the audit history each.
    """
    return re.sub(r"\s+", " ", (name or "")).strip().lower()


def parse_section_date(value: str) -> date | None:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if not text:
        return None
    for fmt in _SECTION_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_int(value: str) -> int | None:
    text = (value or "").strip()
    if not text or text in {"-", "\\-"}:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


@dataclass(frozen=True)
class Break:
    """One stretch away from the phone."""

    minutes: int
    window: str
    declared: bool = False


@dataclass
class AuditRecord:
    """One person, one audited day."""

    day: date
    name: str
    declared_completes: int | None = None
    actual_completes: int | None = None
    declared_calls: int | None = None
    actual_calls: int | None = None
    reviewer_flagged: bool | None = None
    details: str = ""
    breaks: list[Break] = field(default_factory=list)
    time_discrepancies: list[str] = field(default_factory=list)
    no_call_logs: bool = False

    @property
    def person_key(self) -> str:
        return normalise_name(self.name)

    # -- Integrity ---------------------------------------------------------

    @property
    def over_declared(self) -> int:
        """Completes claimed that the call logs do not support."""
        if self.declared_completes is None or self.actual_completes is None:
            return 0
        return max(0, self.declared_completes - self.actual_completes)

    @property
    def truthful(self) -> bool:
        """True when the logs back up the claim -- equal counts, or more."""
        if self.no_call_logs:
            return False
        return self.over_declared == 0

    # -- Time on the phone -------------------------------------------------

    @property
    def unexcused_breaks(self) -> list[Break]:
        return [b for b in self.breaks if not b.declared]

    @property
    def off_phone_minutes(self) -> int:
        return sum(b.minutes for b in self.unexcused_breaks)

    @property
    def longest_break_minutes(self) -> int:
        return max((b.minutes for b in self.unexcused_breaks), default=0)

    @property
    def has_any_finding(self) -> bool:
        return bool(
            self.over_declared
            or self.no_call_logs
            or self.unexcused_breaks
            or self.time_discrepancies
        )

    @property
    def reviewer_disagrees(self) -> bool:
        """The reviewer's Y/N column contradicts what the numbers say.

        Both directions matter: a missed over-declaration is a caller getting
        away with it, and a false alarm erodes trust in the audit itself.
        """
        if self.reviewer_flagged is None:
            return False
        return self.reviewer_flagged != self.has_any_finding


def parse_breaks(details: str) -> list[Break]:
    """Pull every stretch off the phone out of the free-text details.

    A break is excused when "Declared Break" appears alongside it — checked
    against the text between this break and the next, so one declared break
    does not excuse the others in a list.
    """
    breaks: list[Break] = []
    matches = list(_BREAK.finditer(details or ""))
    for index, match in enumerate(matches):
        tail_end = matches[index + 1].start() if index + 1 < len(matches) else len(details)
        trailing = details[match.end() : tail_end]
        breaks.append(
            Break(
                minutes=int(match.group("minutes")),
                window=f"{match.group('start')} - {match.group('end')}",
                declared=bool(_DECLARED_BREAK.search(trailing)),
            )
        )
    return breaks


def parse_reviewer_flag(value: str) -> bool | None:
    text = (value or "").strip().lower()
    if text in {"y", "yes"}:
        return True
    if text in {"n", "no"}:
        return False
    return None


def load_audits(rows: list[Row]) -> list[AuditRecord]:
    """Parse the audit sheet into one record per person per audited day."""
    records: list[AuditRecord] = []
    current_day: date | None = None

    for row in rows:
        first = row.get(_NAME, "")
        section = parse_section_date(first)
        if section is not None:
            current_day = section
            continue
        name = re.sub(r"\s+", " ", first).strip()
        if not name or current_day is None:
            continue

        details = row.get(_DETAILS, "")
        records.append(
            AuditRecord(
                day=current_day,
                name=name,
                declared_completes=to_int(row.get(_DECLARED_COMPLETES, "")),
                actual_completes=to_int(row.get(_ACTUAL_COMPLETES, "")),
                declared_calls=to_int(row.get(_DECLARED_CALLS, "")),
                actual_calls=to_int(row.get(_ACTUAL_CALLS, "")),
                reviewer_flagged=parse_reviewer_flag(row.get(_REVIEWER_FLAG, "")),
                details=details,
                breaks=parse_breaks(details),
                time_discrepancies=[m.group(0).strip() for m in _TIME_DISCREPANCY.finditer(details)],
                no_call_logs=bool(_NO_CALL_LOGS.search(details)),
            )
        )
    return records

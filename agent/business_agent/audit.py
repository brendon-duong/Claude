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

_TIME = r"\d{1,2}:\d{2}(?::\d{2})?"

# The sheet writes a break several ways, and gained new phrasings over time:
#   "10 mins off the phone between 6:33 - 6:42"
#   "5 mins between 6:12 - 6:17"        (shorthand, following another break)
#   "12 min break between 17:00 - 17:12"
#   "7 min break"                       (no window given)
# One of "off the phone", "break" or "between" must be present, so that
# "after a 15 mins call" is never mistaken for time away from the phone.
_BREAK = re.compile(
    rf"(?P<minutes>\d{{1,3}})\s*min(?:ute)?s?\s+"
    rf"(?:"
    rf"(?:off\s+the\s+phone|break)"
    rf"(?:\s+between\s+(?P<start1>{_TIME})\s*-\s*(?P<end1>{_TIME}))?"
    rf"|between\s+(?P<start2>{_TIME})\s*-\s*(?P<end2>{_TIME})"
    rf")",
    re.IGNORECASE,
)

# "45 min cumulative off-phone time throughout shift"
# "1 hour & 5 min cumulative off-phone time throughout shift"
# When the sheet states a total directly it is authoritative — it is the
# reviewer's own sum, and beats adding up the individual breaks.
_CUMULATIVE = re.compile(
    r"(?:(?P<hours>\d{1,2})\s*hours?\s*&\s*)?(?P<minutes>\d{1,3})\s*min(?:ute)?s?\s+"
    r"cumulative\s+off[-\s]?phone",
    re.IGNORECASE,
)

# "3 min & 20 sec over break", "2 mins over break"
_OVER_BREAK = re.compile(
    r"(?P<minutes>\d{1,3})\s*min(?:ute)?s?(?:\s*&\s*\d{1,2}\s*sec)?\s+over\s+break",
    re.IGNORECASE,
)

# The caller took a break without declaring it.
_NO_BREAK_DECLARED = re.compile(r"no\s+break\s+declared", re.IGNORECASE)

# "short by 0:21:13" — a shortfall written as a duration.
_SHORT_BY_CLOCK = re.compile(
    r"short\s+by\s+(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?", re.IGNORECASE
)
# "Declared Time In & Out 1:30 - 4:30 VS. Time In & Out on Call Log: ..."
# The colon after the label is optional -- the sheet writes it both ways -- but
# the "VS." is what makes it a discrepancy rather than a plain statement.
_TIME_DISCREPANCY = re.compile(
    r"Declared\s+(?:Start\s+Time|End\s+Time|Time\s+In\s*&?\s*Out|Time\s+In|Time\s+Out|Break)"
    r"\s*:?[^\n]*?\bVS\.?[^\n]*",
    re.IGNORECASE,
)
_NO_CALL_LOGS = re.compile(r"no\s+call\s+logs", re.IGNORECASE)
_DECLARED_BREAK = re.compile(r"declared\s+break", re.IGNORECASE)
# "(Declared Break is only 5 mins)" -- the break was declared but overrun, so
# it is NOT excused. Without this the overrun is silently forgiven.
_DECLARED_BREAK_OVERRUN = re.compile(r"declared\s+break\s+is\s+only", re.IGNORECASE)
# "Suspicious Entry - For Investigation (caller has been dialing other callers)"
_SUSPICIOUS = re.compile(
    r"suspicious\s+entry|for\s+investigation|dial(?:l)?ing\s+other\s+callers", re.IGNORECASE
)
# "Short by 21 mins", "Short by 1 and a half hour", "Short by 1 minute & 40 sec"
_SHORT_BY = re.compile(
    r"short\s+by\s+(?P<value>\d+)\s*(?P<half>and\s+a\s+half\s+)?(?P<unit>hour|hr|min)",
    re.IGNORECASE,
)


def normalise_name(name: str) -> str:
    """Collapse the spelling variants a hand-kept sheet accumulates.

    "Elaine  Abugan" and "Elaine Abugan" are one person; without this they
    score as two people with half the audit history each.
    """
    return re.sub(r"\s+", " ", (name or "")).strip().lower()


def parse_short_by(details: str) -> int:
    """Minutes the caller fell short of the shift they declared.

    The sheet writes this as "Short by 21 mins", "Short by 1 and a half hour"
    and "Short by 1 minute & 40 sec". The largest figure mentioned wins, since
    a row can list a shortfall per leg of the shift.
    """
    minutes = 0
    for match in _SHORT_BY_CLOCK.finditer(details or ""):
        minutes = max(minutes, int(match.group("h")) * 60 + int(match.group("m")))
    for match in _SHORT_BY.finditer(details or ""):
        value = int(match.group("value"))
        if match.group("unit").lower() in {"hour", "hr"}:
            value *= 60
            if match.group("half"):
                value += 30
        minutes = max(minutes, value)
    return minutes


def parse_cumulative(details: str) -> int | None:
    """The shift's stated total time off the phone, if the sheet gives one."""
    total: int | None = None
    for match in _CUMULATIVE.finditer(details or ""):
        minutes = int(match.group("minutes"))
        if match.group("hours"):
            minutes += int(match.group("hours")) * 60
        total = minutes if total is None else max(total, minutes)
    return total


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
    suspicious: bool = False
    short_by_minutes: int = 0
    # The reviewer's own total for the shift, when they stated one.
    cumulative_off_phone_minutes: int | None = None
    over_break_minutes: int = 0
    undeclared_break: bool = False

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
        if self.no_call_logs or self.suspicious:
            return False
        return self.over_declared == 0

    # -- Time on the phone -------------------------------------------------

    @property
    def unexcused_breaks(self) -> list[Break]:
        return [b for b in self.breaks if not b.declared]

    @property
    def off_phone_minutes(self) -> int:
        """Total time away from the phone this shift.

        A stated cumulative total wins over adding up individual breaks: it is
        the reviewer's own sum for the whole shift, and later rows give only
        that total rather than listing each break.
        """
        if self.cumulative_off_phone_minutes is not None:
            return self.cumulative_off_phone_minutes
        return sum(b.minutes for b in self.unexcused_breaks) + self.over_break_minutes

    @property
    def longest_break_minutes(self) -> int:
        return max((b.minutes for b in self.unexcused_breaks), default=0)

    @property
    def stated_total_only(self) -> bool:
        """A cumulative total with no individual breaks listed — so the
        longest single absence is unknown and must not be read as zero."""
        return self.cumulative_off_phone_minutes is not None and not self.breaks

    @property
    def has_any_finding(self) -> bool:
        return bool(
            self.over_declared
            or self.no_call_logs
            or self.suspicious
            or self.short_by_minutes
            or self.over_break_minutes
            or self.undeclared_break
            or self.off_phone_minutes
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
        declared = bool(_DECLARED_BREAK.search(trailing)) and not _DECLARED_BREAK_OVERRUN.search(
            trailing
        )
        start = match.group("start1") or match.group("start2")
        end = match.group("end1") or match.group("end2")
        breaks.append(
            Break(
                minutes=int(match.group("minutes")),
                window=f"{start} - {end}" if start and end else "",
                declared=declared,
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

        declared = to_int(row.get(_DECLARED_COMPLETES, ""))
        actual = to_int(row.get(_ACTUAL_COMPLETES, ""))
        if declared is None and actual is None:
            # A name with no numbers beside it is a shift nobody has audited
            # yet. Counting it as a clean audit would quietly inflate that
            # person's score — the exact opposite of what the sheet means.
            continue

        details = row.get(_DETAILS, "")
        records.append(
            AuditRecord(
                day=current_day,
                name=name,
                declared_completes=declared,
                actual_completes=actual,
                declared_calls=to_int(row.get(_DECLARED_CALLS, "")),
                actual_calls=to_int(row.get(_ACTUAL_CALLS, "")),
                reviewer_flagged=parse_reviewer_flag(row.get(_REVIEWER_FLAG, "")),
                details=details,
                breaks=parse_breaks(details),
                time_discrepancies=[m.group(0).strip() for m in _TIME_DISCREPANCY.finditer(details)],
                no_call_logs=bool(_NO_CALL_LOGS.search(details)),
                suspicious=bool(_SUSPICIOUS.search(details)),
                short_by_minutes=parse_short_by(details),
                cumulative_off_phone_minutes=parse_cumulative(details),
                over_break_minutes=sum(
                    int(m.group("minutes")) for m in _OVER_BREAK.finditer(details)
                ),
                undeclared_break=bool(_NO_BREAK_DECLARED.search(details)),
            )
        )
    return records

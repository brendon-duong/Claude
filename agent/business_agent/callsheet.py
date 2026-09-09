"""Building the day's call sheet workbook.

One workbook per day, one tab per rostered caller, matching how Pacific Link
already works:

    A: ID          the number's id from the pool
    B: Number      the phone number
    C: (blank)     the caller's own outcome tag - GNA, RB, Refused, Completed
    D: (blank)     room for a sub-reason - vm, ringing, not interested
    F/G/H:         the shift summary the caller fills in and the audit checks

Numbers are issued in contiguous blocks of 200 per caller, in the order the
pool lists them, continuing from wherever the pool was last drawn down to.
That block scheme is what has kept two callers from ever ringing the same
person, so it is preserved exactly rather than improved on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

DEFAULT_BLOCK_SIZE = 200

# The colour the source sheet uses to mark numbers already handed out.
USED_FILL = "C6EFCE"

# The summary block, as the callers already fill it in. Left column is the
# label; the caller types this shift's figure beside it, and the previous
# sheet's figure beside that.
SUMMARY_ROWS = (
    "COMPLETED",
    "REFUSED",
    "RINGBACK",
    "GNA",
    "INCOMPLETE",
    "# INVALID/NOT ACTIVE",
    "Total Calls",
)


@dataclass(frozen=True)
class PoolNumber:
    """One number in a pool, with whatever outcome it last received."""

    number_id: int
    number: str
    outcome: str = ""

    @property
    def called(self) -> bool:
        return bool(self.outcome.strip())


@dataclass(frozen=True)
class Block:
    """A contiguous run of numbers issued to one caller."""

    caller: str
    numbers: list[PoolNumber]

    @property
    def first_id(self) -> int:
        return self.numbers[0].number_id

    @property
    def last_id(self) -> int:
        return self.numbers[-1].number_id

    @property
    def size(self) -> int:
        return len(self.numbers)

    @property
    def label(self) -> str:
        return f"{self.first_id}-{self.last_id}"


@dataclass
class Allocation:
    """The result of drawing blocks for one day's callers."""

    poll: str
    day: date
    blocks: list[Block] = field(default_factory=list)
    # Callers who got nothing because the pool ran dry.
    unserved: list[str] = field(default_factory=list)
    high_water: int | None = None

    @property
    def issued(self) -> int:
        return sum(block.size for block in self.blocks)


# "RB", "Ring Back", "RINGBACK" — a number worth trying again.
_RINGBACK = re.compile(r"^\s*(rb|ring\s*back)\b", re.IGNORECASE)


def is_reusable(number: PoolNumber) -> bool:
    """Can this number go onto a future call sheet?

    Two cases: never called at all, or marked as a ringback — nobody picked
    up, so it is still a live prospect. A refusal, a completed survey or a
    dead line is finished with, and re-issuing it would mean ringing someone
    who already said no.
    """
    if not number.called:
        return True
    return bool(_RINGBACK.match(number.outcome))


# The title only carries a high-water mark when it says so. Without this,
# "ACT 1000 Rural Numbers - 10/06/2026" reads as a mark of 2026 and drawing
# starts near the top of the pool, re-issuing numbers already called.
_MARK_PHRASE = re.compile(
    r"\b(?P<kind>use\s+from|start\s+(?:at|from)|from|up\s+to|used\s+to|through)\b"
    r"[^\d]{0,12}(?P<mark>\d{3,})",
    re.IGNORECASE,
)
_INCLUSIVE_START = ("use from", "start at", "start from", "from")


def parse_high_water(title: str) -> int | None:
    """The mark recorded in the pool file's title, or None if it carries one.

    Pacific Link records progress by renaming the file, so the title is the
    authoritative record of how far down the pool has been used. A title with
    no such phrase has no mark — a bare year is not a position in the pool,
    and guessing one would re-issue numbers that have already been called.
    """
    match = _MARK_PHRASE.search(title or "")
    return int(match.group("mark")) if match else None


def title_mark_is_inclusive(title: str) -> bool:
    """True when the title names the next number to use rather than the last
    one used — "USE FROM 340199" starts at 340199, "up to 340198" starts after."""
    match = _MARK_PHRASE.search(title or "")
    if not match:
        return False
    kind = re.sub(r"\s+", " ", match.group("kind").strip().lower())
    return kind in _INCLUSIVE_START


def start_after_from_title(title: str) -> int | None:
    """Where to resume drawing, from the pool file's title.

    The convention matters: "USE FROM 340199" means start *at* 340199, so the
    first number drawn is 340199 itself. Reading it as "after 340199" would
    skip one number every single time; reading an "up to" title as inclusive
    would re-issue one. One off-by-one here is a respondent getting two calls.
    """
    mark = parse_high_water(title)
    if mark is None:
        return None
    return mark - 1 if title_mark_is_inclusive(title) else mark


def next_title(title: str, last_issued_id: int) -> str:
    """The pool file's title after issuing up to `last_issued_id`.

    The convention is handled here rather than at the call site, because the
    two forms need opposite arithmetic: a "USE FROM" title must name the next
    unused number, an "up to" title the last used one. Getting it backwards
    either skips a number or hands the same one out twice.
    """
    match = _MARK_PHRASE.search(title or "")
    if match is None:
        return f"{title.rstrip()} - USE FROM {last_issued_id + 1}"
    mark = last_issued_id + 1 if title_mark_is_inclusive(title) else last_issued_id
    return title[: match.start("mark")] + str(mark) + title[match.end("mark") :]


def allocate(
    pool: list[PoolNumber],
    callers: list[str],
    *,
    poll: str,
    day: date,
    block_size: int = DEFAULT_BLOCK_SIZE,
    start_after: int | None = None,
    reusable_only: bool = True,
) -> Allocation:
    """Cut the pool into one contiguous block per caller.

    `start_after` is the last id already issued, so drawing resumes below it
    rather than re-issuing numbers that are already out on someone's sheet.
    """
    if block_size <= 0:
        raise ValueError("block_size must be positive")

    ordered = sorted(pool, key=lambda item: item.number_id)
    if start_after is not None:
        ordered = [item for item in ordered if item.number_id > start_after]
    if reusable_only:
        ordered = [item for item in ordered if is_reusable(item)]

    allocation = Allocation(poll=poll, day=day)
    cursor = 0
    for caller in callers:
        chunk = ordered[cursor : cursor + block_size]
        if not chunk:
            allocation.unserved.append(caller)
            continue
        allocation.blocks.append(Block(caller=caller, numbers=chunk))
        cursor += len(chunk)

    if allocation.blocks:
        allocation.high_water = max(block.last_id for block in allocation.blocks)
    return allocation


def _tab_name(caller: str, taken: set[str]) -> str:
    """A worksheet name Excel and Sheets will both accept, and unique.

    Tabs are named by first name, which is what the existing sheets do, so
    two callers sharing one get a distinguishing initial rather than one
    silently overwriting the other.
    """
    cleaned = re.sub(r"[\[\]:*?/\\]", " ", caller).strip()
    parts = cleaned.split()
    name = parts[0] if parts else "Caller"
    if name.lower() in taken and len(parts) > 1:
        name = f"{parts[0]} {parts[1][0]}"
    candidate, suffix = name[:31], 2
    while candidate.lower() in taken:
        candidate = f"{name[:28]} {suffix}"
        suffix += 1
    taken.add(candidate.lower())
    return candidate


def build_workbook(allocation: Allocation, *, business_name: str = "Pacific Link Global"):
    """Render an allocation as an .xlsx workbook, one tab per caller.

    Built as a real workbook rather than CSV because a call sheet needs one
    tab per caller, which a single CSV cannot carry. Uploading the .xlsx to
    Drive converts it to a native Google Sheet with the tabs intact.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "Building call sheets needs openpyxl: pip install -r requirements.txt"
        ) from exc

    workbook = Workbook()
    workbook.remove(workbook.active)
    taken: set[str] = set()
    bold = Font(bold=True)

    for block in allocation.blocks:
        sheet = workbook.create_sheet(_tab_name(block.caller, taken))
        sheet["A1"] = "ID"
        sheet["B1"] = "Number"
        sheet["C1"] = "Outcome"
        sheet["D1"] = "Notes"
        for cell in ("A1", "B1", "C1", "D1"):
            sheet[cell].font = bold

        for offset, item in enumerate(block.numbers, start=2):
            sheet.cell(row=offset, column=1, value=item.number_id)
            sheet.cell(row=offset, column=2, value=item.number)
            # Columns C and D stay empty: they are the caller's to fill in.

        # The shift summary, to the right of the caller's working columns.
        header = [
            (f"{allocation.poll} — {allocation.day:%d/%m/%Y}", True),
            (block.caller.upper(), True),
            (f"{allocation.day:%B %d, %Y}", False),
        ]
        for index, (text, is_bold) in enumerate(header, start=1):
            cell = sheet.cell(row=index, column=6, value=text)
            if is_bold:
                cell.font = bold

        for index, label in enumerate(("Time in", "Time out", "Break"), start=5):
            sheet.cell(row=index, column=6, value=label)

        sheet.cell(row=9, column=7, value="This shift").font = bold
        sheet.cell(row=9, column=8, value="Prev. sheet").font = bold
        for index, label in enumerate(SUMMARY_ROWS, start=10):
            sheet.cell(row=index, column=6, value=label)
        sheet.cell(row=9 + len(SUMMARY_ROWS), column=6).font = bold

        sheet.cell(row=11 + len(SUMMARY_ROWS), column=6, value="Numbers issued")
        sheet.cell(row=11 + len(SUMMARY_ROWS), column=7, value=block.label)

        sheet.column_dimensions["A"].width = 9
        sheet.column_dimensions["B"].width = 16
        sheet.column_dimensions["C"].width = 14
        sheet.column_dimensions["D"].width = 22
        sheet.column_dimensions["F"].width = 24
        sheet.column_dimensions["G"].width = 12
        sheet.column_dimensions["H"].width = 12
        sheet.freeze_panes = "A2"
        sheet["A1"].alignment = Alignment(horizontal="left")

    return workbook

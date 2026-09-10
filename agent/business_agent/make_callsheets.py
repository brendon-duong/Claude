"""Cut a day's call sheets from the number pools.

    python3 -m business_agent.make_callsheets \
        --poll "Wellington Bays 400" --day 2026-09-10 \
        --pool "Wellington Bays Numbers - USE FROM 1.xlsx" \
        --pool "Wellington Bays Numbers 2.xlsx" \
        --callers callers.txt \
        --out "Wellington Bays 400 - 10-09-2026.xlsx"

Each caller gets one contiguous block — 200 numbers by default — and the
blocks run consecutively, so nobody is handed a number already out on
somebody else's sheet.

Several pools can be given. They are drawn in the order named: the first is
emptied before the second is touched, which keeps a day's numbers as close
together as the pools allow and leaves the later pool intact for next time.

A pool whose title carries a mark — "USE FROM 17382", "up to 4000" — resumes
below it rather than starting at the top. Curia writes that mark by hand, and
"USE FROM n" means n is still available while "up to n" means n is spent, so
the two are read differently. Where a pool has no mark, everything already
called is skipped, except ringbacks: nobody picked up, so those are still live.

Nothing is uploaded. It writes a local .xlsx for you to check and upload.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

from .callsheet import (
    DEFAULT_BLOCK_SIZE,
    Allocation,
    Block,
    PoolNumber,
    allocate,
    build_workbook,
    is_reusable,
    next_title,
    start_after_from_title,
)


def _day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


# Curia's number files are not a tidy ID/Number list. They are whatever
# extract the data came out of, with the phone buried among a dozen other
# columns, and the layout changes between files — even between two files for
# the same poll on the same day. So the columns are found by their headings.
#
# "Phone" beats "Mobile" beats "Home Phone": an electoral-roll extract carries
# all three, and the plain "Phone" column is the one already consolidated to
# the best number for that person. Picking "Mobile" instead would silently
# drop everyone who only has a landline.
_PHONE_HEADERS = (
    ("phone number", "phone", "contact number", "number"),
    ("mobile", "cell"),
    ("home phone", "landline"),
)
_NOT_A_PHONE = ("source", "type", "id", "code", "count")


def _phone_column(headers: list[str]) -> int | None:
    """Which column holds the number to ring."""
    cleaned = [(index, (name or "").strip().lower()) for index, name in enumerate(headers)]
    for tier in _PHONE_HEADERS:
        # An exact heading wins over one that merely contains the word, so
        # "Phone" is not beaten by "Home Phone Source" appearing first.
        for index, name in cleaned:
            if name in tier:
                return index
        for index, name in cleaned:
            if any(word in name for word in tier) and not any(
                bad in name for bad in _NOT_A_PHONE
            ):
                return index
    return None


def _clean_number(value) -> str:
    """A phone number as text, whatever Excel decided it was."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    # A leading zero survives in a text cell and is lost in a numeric one.
    # "212507803" is a mangled "0212507803", so put it back.
    digits = re.sub(r"[^\d]", "", text)
    if digits and not text.startswith("0") and len(digits) in (8, 9, 10):
        if digits.startswith("2") or digits.startswith("4"):
            text = "0" + text
    return text


def load_pool(path: Path) -> tuple[list[PoolNumber], str]:
    """Read a number pool from an .xlsx, with the sheet's own title.

    The title matters as much as the rows: it is where the high-water mark
    lives, and reading the rows without it means starting from the top of a
    pool that is half spent.

    Column A is the id — every file Curia sends is numbered that way, and the
    id is what gets written back as "USED TO n". The phone column is found by
    its heading, because its position is not stable between files.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:  # pragma: no cover - environment dependent
        raise SystemExit("openpyxl is needed to read number pools: pip install openpyxl")

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]

    numbers: list[PoolNumber] = []
    phone_at: int | None = None
    outcome_at: int | None = None

    for index, row in enumerate(sheet.iter_rows(values_only=True)):
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        first = str(row[0]).strip() if row[0] is not None else ""
        is_header = not first.replace(".0", "").replace(".", "").isdigit()
        if is_header and phone_at is None:
            headers = [str(cell) if cell is not None else "" for cell in row]
            phone_at = _phone_column(headers)
            for position, name in enumerate(headers):
                if (name or "").strip().lower() in ("outcome", "result", "status", "call result"):
                    outcome_at = position
            continue
        if is_header:
            continue

        try:
            number_id = int(float(first))
        except (TypeError, ValueError):
            continue

        # No header row at all: fall back to the second column.
        column = phone_at if phone_at is not None else 1
        number = _clean_number(row[column] if len(row) > column else None)
        if not number:
            continue

        outcome = ""
        if outcome_at is not None and len(row) > outcome_at:
            outcome = str(row[outcome_at] or "").strip()
        numbers.append(PoolNumber(number_id=number_id, number=number, outcome=outcome))

    workbook.close()
    # The file name is the title Curia writes the mark into.
    return numbers, path.stem


def load_callers(path: Path) -> list[str]:
    """One caller per line. Blanks and # comments ignored."""
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            names.append(name)
    return names


def allocate_across_pools(
    pools: list[tuple[list[PoolNumber], str]],
    callers: list[str],
    *,
    poll: str,
    day: date,
    block_size: int,
) -> tuple[Allocation, list[tuple[str, int]], dict[str, str]]:
    """Draw every caller a block, moving to the next pool as each runs dry.

    A caller is never given a block split across two pools. A part-block is
    worse than a smaller sheet: the caller works down the list, hits a number
    from a different survey's pool, and has no way to know.
    """
    combined = Allocation(poll=poll, day=day)
    marks: list[tuple[str, int]] = []
    # Which pool each caller's block came from. Number ids restart in every
    # pool, so "1-200" alone is ambiguous once a second pool is in play.
    sources: dict[str, str] = {}
    remaining = list(callers)

    for index, (numbers, title) in enumerate(pools):
        if not remaining:
            break
        last_pool = index == len(pools) - 1
        drawn = allocate(
            numbers,
            remaining,
            poll=poll,
            day=day,
            block_size=block_size,
            start_after=start_after_from_title(title),
        )

        kept: list[Block] = []
        deferred: list[str] = []
        for block in drawn.blocks:
            # A short block means this pool ran out mid-caller. Send them to
            # the next pool for a whole one instead; only on the last pool,
            # where there is nothing better, is a part-block worth having.
            if block.size == block_size or last_pool:
                kept.append(block)
            else:
                deferred.append(block.caller)

        combined.blocks.extend(kept)
        for block in kept:
            sources[block.caller] = title
        if kept:
            marks.append((title, max(block.last_id for block in kept)))
        remaining = deferred + list(drawn.unserved)

    combined.unserved = remaining
    if combined.blocks:
        combined.high_water = max(block.last_id for block in combined.blocks)
    return combined, marks, sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one day's call sheets.")
    parser.add_argument("--poll", required=True, help='e.g. "Wellington Bays 400"')
    parser.add_argument("--day", required=True, type=_day, help="YYYY-MM-DD")
    parser.add_argument(
        "--pool",
        action="append",
        required=True,
        metavar="XLSX",
        help="a number pool; repeat to draw from more than one, in order",
    )
    parser.add_argument("--callers", required=True, help="file of caller names, one per line")
    parser.add_argument("--per-caller", type=int, default=DEFAULT_BLOCK_SIZE)
    parser.add_argument("--out", default="", help="where to write the workbook")
    args = parser.parse_args(argv)

    callers = load_callers(Path(args.callers))
    if not callers:
        print(f"no caller names in {args.callers}", file=sys.stderr)
        return 2

    pools = []
    for name in args.pool:
        path = Path(name)
        if not path.exists():
            print(f"pool not found: {path}", file=sys.stderr)
            return 2
        numbers, title = load_pool(path)
        live = sum(1 for number in numbers if is_reusable(number))
        resume = start_after_from_title(title)
        print(
            f"{path.name}: {len(numbers)} row(s), {live} still usable"
            + (f", resuming after {resume}" if resume is not None else ", no mark in the title")
        )
        pools.append((numbers, title))

    allocation, marks, sources = allocate_across_pools(
        pools, callers, poll=args.poll, day=args.day, block_size=args.per_caller
    )
    multiple = len({title for _, title in pools}) > 1

    out = Path(args.out) if args.out else Path(
        f"{args.poll} - {args.day:%d-%m-%Y}.xlsx".replace("/", "-")
    )
    build_workbook(allocation).save(out)

    print()
    for block in allocation.blocks:
        origin = f"   from {sources[block.caller]}" if multiple else ""
        print(f"  {block.caller:28} {block.size:4} numbers   {block.label}{origin}")
    print()
    print(f"{allocation.issued} number(s) to {len(allocation.blocks)} caller(s) -> {out}")
    for caller in allocation.unserved:
        print(f"  !! {caller} got nothing: the pools ran out")
    for title, mark in marks:
        print(f"  rename the pool to: {next_title(title, mark)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

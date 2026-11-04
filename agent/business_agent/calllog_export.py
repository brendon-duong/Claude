"""Zoom Phone call logs as CSV, one file per caller per day, for Curia's auditor.

Curia audit Pacific Link independently and need to see the raw phone records.
They live in Drive as Year / Month / D-M / "<Caller>.csv" — Elaine has been
exporting them from the Zoom web console by hand, one caller at a time, after
every shift. This builds the same files from the API.

This is NOT the shift audit. Nothing here judges anyone: it is the call log,
reproduced. `audit_day` is the module that scores a shift.

WHAT MATCHES THE HAND EXPORT AND WHAT DOES NOT
Row counts match exactly — 170 rows for Eunilyn Lisondra on 10 September 2026,
against 170 in Elaine's file — because both group by the Zoom user who owns the
call. Sixteen of the eighteen columns are reproduced. Two are not:

  Device   Zoom's export names the softphone build, e.g.
           `Windows_Client(7.1.5.43453)`. **The call_logs API does not return
           it in any field.** The column is written empty rather than guessed.
  Result   The API spells two values differently from the export — `Call
           Cancel` for `Call Cancelled`, `Call connected` for `Call
           Connected`. `EXPORT_RESULT` maps them so the CSV reads like the
           console's.

Phone numbers are the other soft spot. Zoom's console formats them the way a
New Zealander writes them (`0210 610 372`, `04 887 6902`) and its exact
grouping is libphonenumber's, not a rule anyone can restate. `format_nz`
reproduces the common shapes and falls back to printing the number unchanged
rather than inventing a grouping. `check_formatting` measures how close it
gets against a real exported file.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone

from .calllogs import MANILA, calls_for_day  # noqa: F401  (MANILA re-exported for callers)

# The account's Zoom console renders times in New Zealand time, so the files
# Curia already hold are in NZ time and these must match. September is NZST.
NZ = timezone(timedelta(hours=12))

COLUMNS = (
    "NO.", "Direction", "From", "To", "Forward to", "Device", "Time", "Result",
    "Path", "Duration (hh:mm:ss)", "Client Code", "Department", "Cost Center",
    "Charge", "Type", "End-to-End Encryption", "FAC Required",
)

# Zoom's API vocabulary against its own console's. Anything not listed is
# already spelt the same in both.
EXPORT_RESULT = {
    "Call Cancel": "Call Cancelled",
    "Call connected": "Call Connected",
}

# What the console prints where a field is empty: a space and two hyphens.
BLANK = " --"

# Four-digit NZ prefixes the console keeps whole before grouping the rest.
# Only these two are observed in real exports: 0210 and 0274 group as four,
# while 0211, 0212 and 0273 group as three (`021 169 2062`, `027 332 4487`).
# Do not add a prefix here on a hunch — check it against an exported file.
_FOUR_DIGIT = ("0210", "0274")
# Two-digit landline area codes.
_AREA = ("03", "04", "06", "07", "09")


def format_nz(number: str, location: str = "") -> str:
    """A number as the Zoom console writes it, with its country appended.

    `+64210610372` becomes `0210 610 372 - New Zealand`. An extension stays a
    bare number. Anything that is not a recognisable NZ number is returned
    unchanged, because a wrong grouping in an auditor's file is worse than an
    unformatted one.
    """
    raw = (number or "").strip()
    if not raw:
        return ""
    suffix = f" - {location}" if location else ""
    if not raw.startswith("+64"):
        # An extension (four digits, no plus) or a number from elsewhere.
        return raw if not suffix else f"{raw}{suffix}"

    national = "0" + raw[3:]
    groups = _group_nz(national) if national.isdigit() else ""
    if groups:
        return f"{groups}{suffix}"
    # The console prints a number it cannot group with a leading space and no
    # country — ` +6410091`. Copied because these files sit next to hers.
    return f" {raw}"


def _group_nz(national: str) -> str:
    """Split an 0-prefixed NZ number the way the console does, or "" if unsure."""
    n = len(national)
    if national[:4] in _FOUR_DIGIT and n in (10, 11):
        # 0210 816 2010 as well as 0210 610 372 — the prefix stays whole and
        # the rest splits 3 then whatever is left.
        return f"{national[:4]} {national[4:7]} {national[7:]}"
    if national[:2] in _AREA and n == 9:
        return f"{national[:2]} {national[2:5]} {national[5:]}"
    if national[:3] in ("020", "021", "022", "027", "028", "029"):
        if n == 10:
            return f"{national[:3]} {national[3:6]} {national[6:]}"
        if n == 11:
            # 020 is its own numbering scheme and splits 3-4-4
            # (`020 4005 3130`); the rest split 3-3-5 (`027 365 36523`,
            # `029 020 40106`). Both shapes come from real exports.
            if national[:3] == "020":
                return f"{national[:3]} {national[3:7]} {national[7:]}"
            return f"{national[:3]} {national[3:6]} {national[6:]}"
        if n == 9:
            return f"{national[:3]} {national[3:6]} {national[6:]}"
    return ""


def hhmmss(seconds: int) -> str:
    """A duration as the console writes it, or its blank marker at zero."""
    if not seconds:
        return BLANK
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _party(row: dict, side: str) -> str:
    """One end of a call: the agent as name + extension + DID, or a number.

    The agent is written under their full name, not their Zoom display name.
    Zoom shows one caller as `Khars -`, trailing hyphen and all, which renders
    as `Khars - - Ext. 1030` — an auditor should not have to decode that.
    """
    from .names import export_filename

    owner = row.get("owner") or {}
    number = row.get(f"{side}_number") or ""
    # The agent's own leg carries the extension as its number.
    if number and owner.get("extension_number") and str(number) == str(owner["extension_number"]):
        did = row.get(f"{side}_did_number") or ""
        parts = [export_filename(owner.get("name", "")), f"Ext. {owner['extension_number']}"]
        if did:
            parts.append(format_nz(did).split(" - ")[0])
        return " - ".join(p for p in parts if p)
    return format_nz(number, row.get(f"{side}_location") or "")


def rows_to_csv(rows: list[dict]) -> str:
    """One caller's day as the console would export it: newest call first."""
    ordered = sorted(rows, key=lambda r: r.get("date_time") or "", reverse=True)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for index, row in enumerate(ordered, start=1):
        started = datetime.fromisoformat(
            (row.get("date_time") or "").replace("Z", "+00:00")
        ).astimezone(NZ)
        result = row.get("result", "")
        writer.writerow([
            index,
            (row.get("direction") or "").capitalize(),
            _party(row, "caller"),
            _party(row, "callee"),
            "",                                   # Forward to — unused here
            "",                                   # Device — not in the API
            started.strftime("%Y-%m-%d %H:%M:%S"),
            EXPORT_RESULT.get(result, result),
            (row.get("path") or "").upper(),
            hhmmss(int(row.get("duration") or 0)),
            BLANK,                                # Client Code
            row.get("department") or "",
            row.get("cost_center") or "",
            BLANK,                                # Charge
            "Normal",
            "No",
            "No",
        ])
    return out.getvalue()


def by_agent(rows: list[dict]) -> dict[str, list[dict]]:
    """A day's raw rows split per Zoom user, the way the console exports them."""
    out: dict[str, list[dict]] = {}
    for row in rows:
        name = ((row.get("owner") or {}).get("name") or "").strip()
        if name:
            out.setdefault(name, []).append(row)
    return out


def folder_name(day: date) -> str:
    """The day folder Elaine uses: "10/9", no leading zeros."""
    return f"{day.day}/{day.month}"


_NUM = re.compile(r"^(.*?)(?: - [A-Za-z ]+)?$")


def check_formatting(exported_csv: str, rebuilt_csv: str) -> dict:
    """How closely a rebuilt file matches a real console export.

    Compares row for row on the columns the API can supply, so a change to the
    formatter can be measured rather than argued about.
    """
    want = list(csv.reader(io.StringIO(exported_csv.strip())))
    got = list(csv.reader(io.StringIO(rebuilt_csv.strip())))
    checked = ("Direction", "From", "To", "Time", "Result", "Path", "Duration (hh:mm:ss)")
    idx = {c: COLUMNS.index(c) for c in checked}
    result = {"rows_expected": len(want) - 1, "rows_got": len(got) - 1,
              "mismatches": {c: 0 for c in checked}, "examples": []}
    for w, g in zip(want[1:], got[1:]):
        for col, i in idx.items():
            a, b = (w[i] if i < len(w) else "").strip(), (g[i] if i < len(g) else "").strip()
            if a != b:
                result["mismatches"][col] += 1
                if len(result["examples"]) < 8:
                    result["examples"].append({"column": col, "export": a, "rebuilt": b})
    return result


def write_day(day: date, out_dir: str, *, on_shift_only: bool = True,
              fetch=None, token: str = "") -> list[str]:
    """One CSV per caller for `day`, written into `out_dir`. Returns the paths.

    Filenames come from `names.export_filename`, which matches what Curia
    already hold. `on_shift_only` keeps it to the people who actually worked,
    the way Elaine uploads it; pass False for every extension the phone system
    saw.
    """
    import os

    from .calllogs import _zoom_fetch, access_token

    from .calllogs import by_caller, parse_call
    from .names import export_filename

    fetcher = fetch or _zoom_fetch
    if fetch is None and not token:
        token = access_token()
    rows = fetcher(day, token)

    if on_shift_only:
        # Elaine uploads the people who worked the shift, not everyone the
        # phone system saw. On 10 September that is 22 of 28: six others made
        # a single call each, hours before the window, and were never rostered.
        calls = [c for c in (parse_call(r) for r in rows) if c]
        working = {
            name for name, shift in by_caller(calls, day).items() if shift.on_shift
        }
        keep = {n for n in by_agent(rows) if n.strip().lower() in working}
    else:
        keep = set(by_agent(rows))

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, agent_rows in sorted(by_agent(rows).items()):
        if name not in keep:
            continue
        safe = export_filename(name).replace("/", "-").strip()
        path = os.path.join(out_dir, f"{safe}.csv")
        with open(path, "w", newline="") as fh:
            fh.write(rows_to_csv(agent_rows))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    from .audit_day import today_manila

    ap = argparse.ArgumentParser(
        description="Zoom Phone call logs as per-caller CSVs, for Curia's auditor."
    )
    ap.add_argument("day", nargs="?", help="YYYY-MM-DD, Manila. Default: today in Manila.")
    ap.add_argument("--out", default=".", help="directory to write the CSVs into")
    ap.add_argument("--everyone", action="store_true",
                    help="include people who made calls but never worked the shift")
    args = ap.parse_args(argv)
    day = date.fromisoformat(args.day) if args.day else today_manila()
    paths = write_day(day, args.out, on_shift_only=not args.everyone)
    print(f"{day.isoformat()} — {len(paths)} caller(s), Drive folder {folder_name(day)}/")
    for path in paths:
        with open(path) as fh:
            calls = sum(1 for _ in fh) - 1
        print(f"  {path}  ({calls} calls)")
    if not paths:
        print("  no calls that day", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

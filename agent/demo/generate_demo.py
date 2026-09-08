"""Regenerate the demo dataset relative to today, so the demo is never stale.

    python3 demo/generate_demo.py

Writes team.csv, roster.csv, demand.csv and a fake WhatsApp export into
demo/ and demo/inbox/. Safe to re-run; it overwrites.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
INBOX = HERE / "inbox"

TEAM = [
    # id, name, phone, skills, cap, unavailable_offsets, preferred, reliability
    ("sarah",  "Sarah Chen",     "+61400111222", "calls;onboarding", 5, [],  "morning",   0.95),
    ("dan",    "Dan Okafor",     "+61400333444", "calls",            4, [],  "morning",   0.80),
    ("priya",  "Priya Nair",     "+61400555666", "calls;compliance", 5, [],  "afternoon", 0.92),
    ("tom",    "Tom Reilly",     "+61400777888", "calls",            3, [3], "afternoon", 0.70),
    ("mei",    "Mei Lin",        "+61400999000", "calls;compliance", 5, [],  "morning",   0.88),
    ("jack",   "Jack Moreau",    "+61400121314", "calls;onboarding", 5, [],  "afternoon", 0.75),
]

# offset from today -> (shift, [person_ids], calls_required)
PLAN = [
    (0, "morning",   ["sarah", "dan"],    20),
    (0, "afternoon", ["priya", "tom"],    20),
    (1, "morning",   ["sarah", "mei"],    20),
    (1, "afternoon", ["priya", "jack"],   25),
    (2, "morning",   ["dan", "mei"],      30),
    (2, "afternoon", ["priya", "tom"],    20),
    (3, "morning",   ["sarah", "dan"],    20),
    (3, "afternoon", ["jack", "mei"],     20),
    (4, "morning",   ["sarah", "mei"],    25),
    (4, "afternoon", ["tom", "jack"],     20),
]


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    today = date.today()
    INBOX.mkdir(parents=True, exist_ok=True)

    def day(offset: int) -> date:
        return today + timedelta(days=offset)

    write_csv(
        HERE / "team.csv",
        ["person_id", "name", "phone", "skills", "max_shifts_per_week",
         "unavailable", "preferred_shifts", "reliability"],
        [
            [pid, name, phone, skills, cap,
             ";".join(day(o).isoformat() for o in unavailable), preferred, reliability]
            for pid, name, phone, skills, cap, unavailable, preferred, reliability in TEAM
        ],
    )

    write_csv(
        HERE / "roster.csv",
        ["date", "shift", "person_id", "status", "notes"],
        [
            [day(offset).isoformat(), shift, person_id, "confirmed", ""]
            for offset, shift, people, _ in PLAN
            for person_id in people
        ],
    )

    write_csv(
        HERE / "demand.csv",
        ["date", "shift", "calls_required", "staff_required", "notes"],
        [
            [day(offset).isoformat(), shift, calls, "", ""]
            for offset, shift, _, calls in PLAN
        ],
    )

    # A believable team chat: one clear dropout, one vague one, an offer,
    # a client request, and noise that must NOT become an action.
    def stamp(offset: int, hour: int, minute: int) -> str:
        moment = datetime.combine(day(offset), datetime.min.time()).replace(
            hour=hour, minute=minute
        )
        return moment.strftime("%d/%m/%Y, %I:%M:%S %p")

    drop_day = day(3).strftime("%A")   # the shift Dan pulls out of
    busy_day = day(4).strftime("%A")   # the day the client wants more calls
    chat = "\n".join(
        [
            f"[{stamp(0, 7, 12)}] Sarah Chen: Morning all, heading in now",
            f"[{stamp(0, 8, 3)}] Dan Okafor: Sorry team, I can't make {drop_day} anymore, "
            "got a clash with my other job",
            f"[{stamp(0, 8, 15)}] Priya Nair: I'm free {drop_day} if you need cover, happy to take the morning",
            f"[{stamp(0, 9, 40)}] Mei Lin: Is the new script in the drive folder yet?",
            f"[{stamp(0, 10, 5)}] Jack Moreau: might be running late tomorrow, dentist",
            f"[{stamp(0, 11, 30)}] Rachel (Northside Client): Hi, we need 20 more calls "
            f"on {busy_day} if you can fit them in",
            f"[{stamp(0, 14, 2)}] Tom Reilly: all good on my end today, 12 done so far",
        ]
    )
    (INBOX / "team-group-chat.txt").write_text(chat + "\n", encoding="utf-8")

    print(f"demo data regenerated for {today.isoformat()} in {HERE}")


if __name__ == "__main__":
    main()

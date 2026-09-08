"""Turning spreadsheet rows into typed objects.

This is the layer that tolerates humans: missing columns, blank cells, "Yes"
instead of "confirmed", semicolon lists with stray spaces. Fail loudly on the
things that would silently corrupt the roster (bad dates, unknown people) and
quietly on the things that don't matter.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import Config
from .models import Demand, Person, Shift
from .sheets import Row, load_table, parse_date


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dates(value: str) -> frozenset[date]:
    out = set()
    for item in _split_list(value):
        try:
            out.add(parse_date(item))
        except ValueError:
            continue  # a note like "school holidays" is not a date; ignore it
    return frozenset(out)


_STATUS_ALIASES = {
    "confirmed": "confirmed", "yes": "confirmed", "y": "confirmed", "": "confirmed",
    "ok": "confirmed", "working": "confirmed",
    "tentative": "tentative", "maybe": "tentative", "pending": "tentative",
    "dropped": "dropped", "drop": "dropped", "no": "dropped", "cancelled": "dropped",
    "canceled": "dropped", "sick": "dropped", "out": "dropped", "unavailable": "dropped",
}


def normalise_status(value: str) -> str:
    key = (value or "").strip().lower()
    return _STATUS_ALIASES.get(key, "confirmed")


def load_people(rows: list[Row]) -> dict[str, Person]:
    people: dict[str, Person] = {}
    for row in rows:
        person_id = row.get("person_id") or row.get("id") or row.get("name", "")
        if not person_id:
            continue
        person_id = person_id.strip()
        people[person_id] = Person(
            person_id=person_id,
            name=row.get("name") or person_id,
            phone=row.get("phone", ""),
            skills=frozenset(s.lower() for s in _split_list(row.get("skills", ""))),
            max_shifts_per_week=_to_int(row.get("max_shifts_per_week", ""), 5) or 5,
            unavailable=_dates(row.get("unavailable", "")),
            preferred_shifts=frozenset(
                s.lower() for s in _split_list(row.get("preferred_shifts", ""))
            ),
            reliability=_to_float(row.get("reliability", ""), 0.8),
        )
    return people


def load_shifts(rows: list[Row], known_people: dict[str, Person]) -> list[Shift]:
    shifts: list[Shift] = []
    unknown: set[str] = set()
    for row in rows:
        person_id = (row.get("person_id") or row.get("name") or "").strip()
        if not person_id:
            continue
        if person_id not in known_people:
            unknown.add(person_id)
        shifts.append(
            Shift(
                day=parse_date(row.get("date", "")),
                shift=(row.get("shift") or "day").strip().lower(),
                person_id=person_id,
                status=normalise_status(row.get("status", "")),  # type: ignore[arg-type]
                notes=row.get("notes", ""),
            )
        )
    if unknown:
        raise ValueError(
            "roster references people missing from the team sheet: "
            + ", ".join(sorted(unknown))
        )
    return shifts


def load_demand(rows: list[Row]) -> list[Demand]:
    demand: list[Demand] = []
    for row in rows:
        staff_required = row.get("staff_required", "")
        demand.append(
            Demand(
                day=parse_date(row.get("date", "")),
                shift=(row.get("shift") or "day").strip().lower(),
                calls_required=_to_int(row.get("calls_required") or row.get("calls", "")),
                staff_required=_to_int(staff_required) if staff_required else None,
                notes=row.get("notes", ""),
            )
        )
    return demand


def load_all(
    config: Config, base_dir: Path
) -> tuple[dict[str, Person], list[Shift], list[Demand]]:
    people = load_people(load_table(config.team, config, base_dir))
    shifts = load_shifts(load_table(config.roster, config, base_dir), people)
    demand = load_demand(load_table(config.demand, config, base_dir))
    return people, shifts, demand

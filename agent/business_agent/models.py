"""Core data types shared across the agent.

Everything the agent reasons about is one of these. Keeping them dumb and
explicit means the roster maths is testable without Google, WhatsApp or Claude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

ShiftStatus = Literal["confirmed", "tentative", "dropped"]
EventKind = Literal["dropout", "offer", "client_request", "noise"]


@dataclass(frozen=True)
class Person:
    """A team member who can be rostered."""

    person_id: str
    name: str
    phone: str = ""
    skills: frozenset[str] = frozenset()
    max_shifts_per_week: int = 5
    unavailable: frozenset[date] = frozenset()
    preferred_shifts: frozenset[str] = frozenset()
    # 0.0-1.0, how often they turn up when they said they would.
    reliability: float = 0.8

    def can_work(self, day: date, shift: str, required_skills: frozenset[str]) -> tuple[bool, str]:
        """Hard eligibility. Returns (ok, reason_if_not)."""
        if day in self.unavailable:
            return False, "marked unavailable that day"
        missing = required_skills - self.skills
        if missing:
            return False, f"missing skill(s): {', '.join(sorted(missing))}"
        return True, ""


@dataclass(frozen=True)
class Shift:
    """One person's assignment to one slot on one day."""

    day: date
    shift: str
    person_id: str
    status: ShiftStatus = "confirmed"
    notes: str = ""

    @property
    def counts_toward_cover(self) -> bool:
        return self.status == "confirmed"


@dataclass(frozen=True)
class Demand:
    """How much work exists on a given day/slot."""

    day: date
    shift: str
    calls_required: int = 0
    staff_required: int | None = None
    notes: str = ""

    def staff_needed(self, calls_per_person: int) -> int:
        """Explicit staff count wins; otherwise derive it from call volume."""
        if self.staff_required is not None:
            return self.staff_required
        if calls_per_person <= 0:
            raise ValueError("calls_per_person must be positive")
        return -(-self.calls_required // calls_per_person)  # ceil division


@dataclass(frozen=True)
class Message:
    """A normalised inbound message, whatever channel it arrived on."""

    sent_at: datetime
    sender: str
    text: str
    channel: str = "whatsapp"
    chat: str = ""
    message_id: str = ""


@dataclass
class Event:
    """Something a message *means* for the roster."""

    kind: EventKind
    message: Message
    person_id: str | None = None
    day: date | None = None
    shift: str | None = None
    calls: int | None = None
    confidence: float = 0.5
    rationale: str = ""
    source: str = "rules"  # "rules" or "claude"


@dataclass
class Candidate:
    """A possible replacement, with the reasoning kept attached."""

    person: Person
    score: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return not self.blockers


@dataclass
class Gap:
    """A shift that is short-staffed, plus who could fill it."""

    day: date
    shift: str
    needed: int
    covered: int
    dropouts: list[Shift] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def short_by(self) -> int:
        return max(0, self.needed - self.covered)


@dataclass
class Draft:
    """An outbound message the agent has written but must not send."""

    to_name: str
    to_phone: str
    channel: str
    subject: str
    body: str
    about: str

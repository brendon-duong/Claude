"""Turning audit history into a rostering signal.

Two separate concerns, deliberately not averaged into one mush:

**Integrity** — declaring more completed surveys than the call logs support.
This is a trust question, not a performance one, so it dominates the score and
can block someone from the roster on its own.

**Time on the phone** — the standing ask is no more than five minutes away at a
stretch. Occasional fifteen or twenty minute absences are tolerated; an hour is
not. Declared breaks don't count against anyone.

Recent audits count for more than old ones, because the question being answered
is "who should I roster this week", not "who has ever slipped up". Penalties are
averaged across a person's audits rather than summed, so being audited often
never makes someone look worse than someone barely checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from .audit import AuditRecord, normalise_name

Tier = Literal["trusted", "watch", "do_not_roster"]
TimeVerdict = Literal["clean", "minor", "serious", "severe"]


@dataclass(frozen=True)
class Thresholds:
    """The rules of the business, in one place so they are easy to change."""

    # No more than this away from the phone at a stretch — the standing ask.
    break_ok_minutes: int = 5
    # Beyond the ask, but tolerated now and then.
    break_tolerable_minutes: int = 20
    # Total time off the phone across one shift.
    shift_off_phone_serious_minutes: int = 30
    shift_off_phone_severe_minutes: int = 60

    # Working less of the shift than was declared.
    shortfall_ok_minutes: int = 5
    shortfall_serious_minutes: int = 30
    shortfall_severe_minutes: int = 60

    # How quickly an old audit stops mattering.
    half_life_days: int = 90
    lookback_days: int = 240

    # Score bands.
    trusted_score: float = 0.75
    do_not_roster_score: float = 0.50
    # Integrity is judged as a rate as well as a count: four slips in
    # seventy-nine audits is a different person from four in seven.
    max_integrity_rate: float = 0.25
    min_audits_for_rate: int = 3
    # Repeat failures inside this recent window bar someone regardless of rate.
    recent_window_days: int = 60
    max_recent_integrity_fails: int = 2
    # Shifts with an unacceptable amount of time off the phone.
    max_severe_events: int = 2
    # A low average needs more than one audit behind it before it bans anyone.
    # One bad day is a conversation, not a verdict.
    min_audits_to_bar_on_score: int = 2

    # Penalties, applied per audit then averaged.
    integrity_penalty: float = 0.45
    shortfall_severe_penalty: float = 0.25
    shortfall_serious_penalty: float = 0.14
    shortfall_minor_penalty: float = 0.04
    integrity_penalty_per_extra: float = 0.15
    severe_time_penalty: float = 0.30
    serious_time_penalty: float = 0.18
    minor_time_penalty: float = 0.05
    time_discrepancy_penalty: float = 0.04


def time_verdict(record: AuditRecord, thresholds: Thresholds) -> TimeVerdict:
    """How bad was this person's time off the phone on this shift?"""
    total = record.off_phone_minutes
    longest = record.longest_break_minutes
    if total >= thresholds.shift_off_phone_severe_minutes:
        return "severe"
    if (
        longest > thresholds.break_tolerable_minutes
        or total >= thresholds.shift_off_phone_serious_minutes
    ):
        return "serious"
    # Where the sheet gives only a shift total, the longest single absence is
    # unknown — so judge the total rather than reading the unknown as zero.
    if longest > thresholds.break_ok_minutes or (
        record.stated_total_only and total > thresholds.break_ok_minutes
    ):
        return "minor"
    return "clean"


def shortfall_verdict(record: AuditRecord, thresholds: Thresholds) -> TimeVerdict:
    """How much of the declared shift went unworked?"""
    minutes = record.short_by_minutes
    if minutes >= thresholds.shortfall_severe_minutes:
        return "severe"
    if minutes >= thresholds.shortfall_serious_minutes:
        return "serious"
    if minutes > thresholds.shortfall_ok_minutes:
        return "minor"
    return "clean"


def audit_penalty(record: AuditRecord, thresholds: Thresholds) -> tuple[float, list[str]]:
    """Penalty for one audit, with the reasons that produced it."""
    penalty = 0.0
    notes: list[str] = []

    if record.no_call_logs:
        penalty += thresholds.integrity_penalty
        notes.append(f"no call logs at all ({record.day:%d %b})")
    elif record.suspicious:
        penalty += thresholds.integrity_penalty
        notes.append(f"flagged for investigation ({record.day:%d %b})")
    elif record.over_declared:
        extra = record.over_declared - 1
        penalty += thresholds.integrity_penalty + extra * thresholds.integrity_penalty_per_extra
        notes.append(
            f"declared {record.declared_completes} completes, logs show "
            f"{record.actual_completes} ({record.day:%d %b})"
        )

    verdict = time_verdict(record, thresholds)
    if verdict == "severe":
        penalty += thresholds.severe_time_penalty
        notes.append(f"{record.off_phone_minutes} min off the phone ({record.day:%d %b})")
    elif verdict == "serious":
        penalty += thresholds.serious_time_penalty
        # Only mention the longest single absence when the sheet listed the
        # individual breaks; a stated shift total does not tell us that.
        detail = (
            f", longest {record.longest_break_minutes} min"
            if record.longest_break_minutes
            else ""
        )
        notes.append(
            f"{record.off_phone_minutes} min off the phone{detail} ({record.day:%d %b})"
        )
    elif verdict == "minor":
        penalty += thresholds.minor_time_penalty

    shortfall = shortfall_verdict(record, thresholds)
    if shortfall == "severe":
        penalty += thresholds.shortfall_severe_penalty
        notes.append(f"{record.short_by_minutes} min short of the declared shift ({record.day:%d %b})")
    elif shortfall == "serious":
        penalty += thresholds.shortfall_serious_penalty
        notes.append(f"{record.short_by_minutes} min short of the declared shift ({record.day:%d %b})")
    elif shortfall == "minor":
        penalty += thresholds.shortfall_minor_penalty

    if record.undeclared_break:
        penalty += thresholds.minor_time_penalty

    if record.time_discrepancies:
        penalty += thresholds.time_discrepancy_penalty
        notes.append(f"start/finish time did not match the logs ({record.day:%d %b})")

    return min(penalty, 1.0), notes


@dataclass
class StaffPerformance:
    """What the audits say about one caller."""

    key: str
    name: str
    audits: int = 0
    score: float = 1.0
    tier: Tier = "trusted"
    integrity_fails: int = 0
    total_over_declared: int = 0
    severe_events: int = 0
    serious_events: int = 0
    recent_integrity_fails: int = 0
    shortfall_events: int = 0
    clean_audits: int = 0
    worst_off_phone_minutes: int = 0
    last_audit: date | None = None
    concerns: list[str] = field(default_factory=list)

    @property
    def rosterable(self) -> bool:
        return self.tier != "do_not_roster"

    @property
    def headline(self) -> str:
        if not self.audits:
            return "never audited"
        parts = [f"{self.clean_audits}/{self.audits} audits clean"]
        if self.integrity_fails:
            parts.append(f"{self.integrity_fails} integrity failure(s)")
        if self.severe_events:
            parts.append(f"{self.severe_events} shift(s) badly off the phone")
        if self.shortfall_events:
            parts.append(f"{self.shortfall_events} shift(s) cut short")
        return ", ".join(parts)


def _weight(record_day: date, today: date, thresholds: Thresholds) -> float:
    """Exponential recency weighting: an audit's influence halves every
    half_life_days, so last month outweighs last year without ever being
    thrown away entirely."""
    days = max(0, (today - record_day).days)
    return 0.5 ** (days / thresholds.half_life_days)


def score_person(
    records: list[AuditRecord], today: date, thresholds: Thresholds
) -> StaffPerformance:
    """Aggregate one person's audits into a score and a tier."""
    name = records[0].name if records else ""
    performance = StaffPerformance(key=normalise_name(name), name=name)
    in_scope = [
        r for r in records if (today - r.day).days <= thresholds.lookback_days and r.day <= today
    ]
    if not in_scope:
        performance.audits = 0
        performance.score = 1.0
        performance.tier = "trusted"
        return performance

    weighted_penalty = 0.0
    total_weight = 0.0
    concerns: list[str] = []

    for record in in_scope:
        weight = _weight(record.day, today, thresholds)
        penalty, notes = audit_penalty(record, thresholds)
        weighted_penalty += weight * penalty
        total_weight += weight
        concerns.extend(notes)

        if record.no_call_logs or record.over_declared or record.suspicious:
            performance.integrity_fails += 1
            performance.total_over_declared += record.over_declared
            if (today - record.day).days <= thresholds.recent_window_days:
                performance.recent_integrity_fails += 1
        if shortfall_verdict(record, thresholds) in {"serious", "severe"}:
            performance.shortfall_events += 1
        verdict = time_verdict(record, thresholds)
        if verdict == "severe":
            performance.severe_events += 1
        elif verdict == "serious":
            performance.serious_events += 1
        if not record.has_any_finding:
            performance.clean_audits += 1
        performance.worst_off_phone_minutes = max(
            performance.worst_off_phone_minutes, record.off_phone_minutes
        )

    performance.audits = len(in_scope)
    performance.last_audit = max(r.day for r in in_scope)
    performance.score = round(max(0.0, 1.0 - weighted_penalty / total_weight), 3)
    performance.concerns = concerns[:6]

    # Tiering is deliberately not just the score. Averaging is the right way to
    # compare people, but it buries two things that must not be buried: a single
    # unacceptable shift, and a pattern of small repeated over-declarations that
    # each barely move an average.
    barred_on_score = (
        performance.score < thresholds.do_not_roster_score
        and performance.audits >= thresholds.min_audits_to_bar_on_score
    )
    # Integrity as a proportion, not a tally: two slips in forty audits is a
    # different person from two in four, and a raw count barred the wrong ones.
    integrity_rate = performance.integrity_fails / performance.audits
    barred_on_rate = (
        integrity_rate >= thresholds.max_integrity_rate
        and performance.audits >= thresholds.min_audits_for_rate
    )
    # However often they are audited, repeat failures in the last few weeks
    # are a live problem rather than history.
    barred_on_recency = (
        performance.recent_integrity_fails >= thresholds.max_recent_integrity_fails
    )
    if (
        barred_on_score
        or barred_on_rate
        or barred_on_recency
        or performance.severe_events >= thresholds.max_severe_events
    ):
        performance.tier = "do_not_roster"
    elif (
        performance.score < thresholds.trusted_score
        or performance.integrity_fails
        or performance.severe_events
    ):
        performance.tier = "watch"
    else:
        performance.tier = "trusted"

    return performance


def find_possible_duplicates(
    performances: dict[str, StaffPerformance]
) -> list[tuple[str, str, str]]:
    """Names that are probably the same person spelled two ways.

    A hand-kept sheet accumulates these, and every variant splits one person's
    audit history in two — which flatters the half without the failures. These
    are *reported*, never merged automatically: wrongly merging two real people
    would attach one person's integrity failures to another, which is far worse
    than asking someone to check a list.
    """
    names = sorted((p.key, p.name) for p in performances.values() if p.audits)
    found: list[tuple[str, str, str]] = []

    for index, (key_a, name_a) in enumerate(names):
        tokens_a = set(key_a.split())
        for key_b, name_b in names[index + 1 :]:
            tokens_b = set(key_b.split())
            if not tokens_a or not tokens_b:
                continue

            # One name's words are wholly contained in the other's, and they
            # share a surname: "Jane Wary Espanueva" / "Jane Wary Rose Espanueva".
            if tokens_a < tokens_b or tokens_b < tokens_a:
                found.append((name_a, name_b, "one name is contained in the other"))
                continue

            # Same surname, and the given names differ by a single character:
            # "Kingsly Cajilig" / "Kingsy Cajilig".
            surname_a, surname_b = key_a.split()[-1], key_b.split()[-1]
            first_a, first_b = key_a.split()[0], key_b.split()[0]
            if surname_a == surname_b and _one_edit_apart(first_a, first_b):
                found.append((name_a, name_b, "same surname, given name differs by a letter"))
                continue

            # Same given names, surname differs by a single character:
            # "Cherry Jean Raagas" / "Cherry Jean Ragaas".
            if (
                key_a.split()[:-1] == key_b.split()[:-1]
                and _one_edit_apart(surname_a, surname_b)
            ):
                found.append((name_a, name_b, "same given name, surname differs by a letter"))

    return found


def _one_edit_apart(left: str, right: str) -> bool:
    """True when two words differ by at most one insertion, deletion or swap.

    Deliberately strict: anything looser starts merging siblings.
    """
    if left == right:
        return False
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        diffs = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        if len(diffs) == 1:
            return True
        # A transposition, as in "Raagas" / "Ragaas".
        if len(diffs) == 2 and diffs[1] == diffs[0] + 1:
            i = diffs[0]
            return left[i] == right[i + 1] and left[i + 1] == right[i]
        return False
    longer, shorter = (left, right) if len(left) > len(right) else (right, left)
    for index in range(len(longer)):
        if longer[:index] + longer[index + 1 :] == shorter:
            return True
    return False


def score_all(
    records: list[AuditRecord], today: date, thresholds: Thresholds | None = None
) -> dict[str, StaffPerformance]:
    """Score everyone who appears in the audits, keyed by normalised name."""
    thresholds = thresholds or Thresholds()
    grouped: dict[str, list[AuditRecord]] = {}
    for record in records:
        grouped.setdefault(record.person_key, []).append(record)
    return {key: score_person(rows, today, thresholds) for key, rows in grouped.items()}

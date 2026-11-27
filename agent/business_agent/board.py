"""The Week Ahead Board: what next week looks like on the votes as they stand.

Brendon asked on 26 Sep 2026 for the board to move "as someone votes". A
published page cannot read Slack itself, so this module is the half that can be
written down: given the votes, the schedule and a fortnight of call history, it
produces the exact JSON the page renders from. A Routine collects the three
inputs hourly and calls `build`.

THE SCORE IS BRENDON'S, SET 12 SEP 2026, AND IS NOT TO BE TUNED HERE:

    0.75 x scaled(completes per shift) + 0.25 x (1 - scaled(minutes away per shift))

Both min-max scaled across the callers in the window, so each runs 0 to 1 and
less time away scores higher. The away half is the measure that still reads up
to 4x Elaine's manual audit, which is why it carries only a quarter of the
weight and never reaches a caller in any form.

TWO RULES THAT LOOK LIKE BUGS AND ARE NOT
-----------------------------------------
A SNAKE DRAFT, NEVER ROUND-ROBIN. With n polls the pick order reverses every n
picks. Straight alternation hands every odd-numbered pick to the same poll and
that poll ends up ahead by roughly half a rank every round; the reversal is what
cancels it. Filling poll A to capacity and then poll B is worse again - it is
exactly the "all the good callers on one" outcome Brendon ruled out.

A YES FROM SOMEONE WITH NO CALL HISTORY IS STILL A YES. Unrankable is a property
of the scoring window, not of the person, and a pure ranking can never give
anybody a first shift. So ranked callers are placed first, then the rest in
joining order, newest first. What is never relaxed is the vote itself: nobody is
placed on a day they did not tick.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Brendon's weights, 12 Sep 2026. Do not change without him.
COMPLETES_WEIGHT = 0.75
AWAY_WEIGHT = 0.25


def _scale(values: dict[str, float], *, higher_is_better: bool) -> dict[str, float]:
    """Min-max each value to 0..1, with 1 always meaning good.

    The direction is baked in here rather than flipped by the caller, because a
    FLAT SPREAD has to read as good on both axes. Scaling a flat away-time to 1
    and then subtracting it gave every caller the maximum away penalty when all
    of them were equally tidy - one window where nobody took a break scored the
    whole roster 0.75 instead of 1.00.
    """
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-9:
        return {k: 1.0 for k in values}
    if higher_is_better:
        return {k: (v - lo) / (hi - lo) for k, v in values.items()}
    return {k: (hi - v) / (hi - lo) for k, v in values.items()}


def scores(history: dict[str, tuple[float, float]]) -> dict[str, float]:
    """Rank score per caller from {name: (completes_per_shift, minutes_away_per_shift)}.

    Scaling happens across whoever is in `history`, so the same caller scores
    differently in a different window. That is intended: the score answers "who
    is strongest among the people available", not "how good is this person".
    """
    comps = _scale({k: v[0] for k, v in history.items()}, higher_is_better=True)
    away = _scale({k: v[1] for k, v in history.items()}, higher_is_better=False)
    return {k: round(COMPLETES_WEIGHT * comps[k] + AWAY_WEIGHT * away[k], 3)
            for k in history}


def snake_draft(ranked: list[str], caps: dict[str, int]) -> dict[str, list[str]]:
    """Distribute `ranked` (best first) across polls, reversing every round.

    A poll that fills early drops out of the order, so uneven headcounts still
    work. One poll degenerates to a plain ranked fill.
    """
    out: dict[str, list[str]] = {p: [] for p in caps}
    order = list(caps)
    i = 0
    forward = True
    while i < len(ranked):
        live = [p for p in order if len(out[p]) < caps[p]]
        if not live:
            break
        for poll in (live if forward else list(reversed(live))):
            if i >= len(ranked):
                break
            out[poll].append(ranked[i])
            i += 1
        forward = not forward
    return out


@dataclass
class Day:
    """One shift day as the board shows it."""

    need: int
    yes: int
    no: int
    caps: dict[str, int]
    polls: dict[str, list[tuple[str, float | None, bool]]] = field(default_factory=dict)
    firsts: list[str] = field(default_factory=list)

    @property
    def filled(self) -> int:
        return sum(len(v) for v in self.polls.values())

    @property
    def gap(self) -> int:
        return max(0, self.need - self.filled)

    @property
    def rankable(self) -> int:
        return sum(1 for v in self.polls.values() for c in v if not c[2]) + self._unplaced_ranked

    _unplaced_ranked: int = 0


def plan_day(voters: list[str], caps: dict[str, int], score: dict[str, float],
             joined: dict[str, int] | None = None, no: int = 0) -> Day:
    """Place one day's yes-voters across its polls.

    `voters` is everyone who ticked this day. `score` holds a rank score for
    whoever has call history; anyone missing from it is a first-shift caller.
    `joined` orders those by how recently they joined (higher = newer), so the
    newest person waiting for a first shift is the first one to get one.
    """
    joined = joined or {}
    ranked = sorted((v for v in voters if v in score),
                    key=lambda v: (-score[v], v))
    fresh = sorted((v for v in voters if v not in score),
                   key=lambda v: (-joined.get(v, 0), v))

    need = sum(caps.values())
    placed = (ranked + fresh)[:need]
    drawn = snake_draft(placed, caps)

    day = Day(need=need, yes=len(voters), no=no, caps=dict(caps))
    day.polls = {p: [(n, score.get(n), n not in score) for n in names]
                 for p, names in drawn.items()}
    day.firsts = [n for n in placed if n not in score]
    day._unplaced_ranked = sum(1 for n in ranked if n not in placed)
    return day


def poll_balance(day: Day) -> dict[str, float]:
    """Mean rank score per poll - the check that the snake draft did its job.

    First-shift callers carry no score and are left out of the mean, so a poll
    is compared on the people there is something to compare. A wide spread here
    means the draft was skipped or the caps changed underneath it.
    """
    out = {}
    for poll, people in day.polls.items():
        vals = [s for _, s, isnew in people if not isnew and s is not None]
        out[poll] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return out


#: What Curia pay per caller-shift: 3 hours at $19.50.
PER_SHIFT = 58.50


def build(days: dict[str, Day], *, as_at: dict, changes: list, new_joiners: list[str],
          per_shift: float = PER_SHIFT) -> dict:
    """The exact JSON the Week Ahead Board page renders from.

    Kept here rather than in the page so the figures and the arithmetic live in
    one tested place; the page only draws what this returns.
    """
    need = sum(d.need for d in days.values())
    filled = sum(d.filled for d in days.values())
    return {
        'asAt': as_at,
        'week': {name: {
            'need': d.need, 'yes': d.yes, 'no': d.no,
            'rankable': d.rankable, 'unranked': len(d.firsts),
            'filled': d.filled, 'gap': d.gap,
            'polls': {p: [list(c) for c in v] for p, v in d.polls.items()},
            'caps': d.caps, 'firsts': d.firsts,
            'balance': poll_balance(d),
        } for name, d in days.items()},
        'votes': {name: [d.yes, d.no] for name, d in days.items()},
        'totals': {'need': need, 'filled': filled, 'gap': need - filled,
                   'firsts': sum(len(d.firsts) for d in days.values())},
        'rate': {'hourly': 19.5, 'shift_hours': 3.0, 'per_shift': per_shift},
        'revenue': {
            'per_shift': per_shift,
            'week_full': round(need * per_shift, 2),
            'week_secured': round(filled * per_shift, 2),
            'week_at_risk': round((need - filled) * per_shift, 2),
        },
        'changes': changes,
        'newJoiners': new_joiners,
    }

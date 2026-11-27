"""Which spreadsheet a poll's numbers come from.

Brendon, 25 Sep 2026: "some of the callsheets you are always drawn from the same
spreadsheet and that's the ACT 1000 and NZNP 500 which can always be drawn from
the same spreadsheet. All the other ones are depending on the day and the
spreadsheet."

So a poll is one of two kinds:

  STANDING  the pool is the same file every time. The builder can run unattended
            because it already knows where the numbers are.
  PER_DAY   Curia send a fresh spreadsheet for that poll, usually by email on the
            day. The builder CANNOT invent it and must stop and ask.

Matching is on a normalised poll name with the sample size dropped, because Curia
vary it: NZNP 500, NZNP 333 and NZNP 1000 are the same master list at different
sample sizes, and ACT 1000 / ACT 500 likewise.
"""
from __future__ import annotations
import re

# The whole-year master list. NZNP and ACT both draw from it - one file, not two
# - and Brendon confirmed NZNP 333 is the same master too (27 Sep 2026): "NZNP
# 333 is also with NZ Numbers."
#
# THIS IS BRENDON'S OWN COPY, NOT CURIA'S ORIGINAL .xlsx. Curia's own master
# (the 6.3MB .xlsx owned by curiaresearch@gmail.com, '1DWugvAGB2uPoUXlLZpSglFRxWG0Zjh7C')
# cannot be shaded - it is an Office file, the Sheets API refuses those outright,
# and Brendon holds edit but not sharing rights on it so sheets-bot cannot be
# added either. This ID is "NZ Numbers 2026 - 2027" sitting in the shareable
# Drive folder (0AA2IL8tCFjvlUk9PVA) as a native Google Sheet, where sheets-bot
# already has access and shading/renaming works directly (used live 7 Oct 2026
# for the NZNP 333 draw - rows shaded, retitled "USE FROM ROW 61167").
# If this ever needs re-pointing, confirm the replacement is a native Google
# Sheet sheets-bot can write to, not another .xlsx - that mistake is exactly
# what made the original unshadeable.
NZ_MASTER = '1rB4tzZTg8cGr7OUR2H-009L1YmwLO9-SqvUhVh-YmAE'

STANDING: dict[str, str] = {
    'nznp': NZ_MASTER,
    'act': NZ_MASTER,
}

_SIZE = re.compile(r'\s*\d+\s*$')


def normalise(poll: str) -> str:
    """"ACT 1000" -> "act";  "NZNP 333" -> "nznp";  "Te Tai Tonga 500" -> "te tai tonga"."""
    return _SIZE.sub('', (poll or '').strip()).strip().lower()


def pool_for(poll: str) -> str | None:
    """The file id of a standing pool, or None when Curia must send one for the day."""
    return STANDING.get(normalise(poll))


def is_standing(poll: str) -> bool:
    return pool_for(poll) is not None


# Polls whose number pool Curia's OWN staff also draw from, past whatever is
# already marked as their usage. Brendon, 20 Oct 2026, after Curia found the
# entire remaining Under 30 Maori pool had been drawn by Pacific Link alone
# across two nights, leaving them nothing: "You need to save numbers for
# Curia." This must never again be left to a human noticing after the fact -
# `max_safe_draw` is the enforcement, called from `callsheet.allocate` and
# `callsheet.allocate_with_ringbacks` on every draw.
#
# Extend this set only on a decision from Brendon, the same way ALIASES in
# names.py only grows on his say-so - guessing a poll onto this list wastes
# capacity PL did not need to hold back; guessing one off it repeats this
# incident.
#
# 'nz maori' / 'gen maori' added 20 Oct 2026, pending Brendon's confirmation
# but applied now rather than left unguarded overnight. Evidence, not a
# guess: the Drive file "Maori Numbers Oct 26" (found while sourcing
# tomorrow's NZ Maori 500 draw) is ID-for-ID and phone-for-phone identical,
# on every row sampled, to the now-exhausted "Under 30 Maori Numbers Oct 26"
# pool that caused the original incident - same master list, re-exported
# under a new name with none of Pacific Link's usage stripped out. Drawing
# from it as if it were a fresh pool would have re-issued numbers already
# dialled AND re-drawn the 454 numbers just handed back to Curia. The pool
# also has ~5,274 phone numbers appearing at more than one ID, so a draw
# must be deduplicated by phone, never by ID alone - see
# business_agent.tests or the 20 Oct build notes for the method. Flag to
# Brendon: if "NZ Maori" / "Young Maori" / "Gen Maori" turn out NOT to be one
# shared resource after all, remove the extra two entries below.
#
# 'ak ctl' added 20 Oct 2026, Brendon's own words, directly: "You need to
# save some numbers for Curia for Auckland central." Confirmed, not
# inferred.
SHARED_WITH_CURIA: frozenset[str] = frozenset({'young maori', 'nz maori', 'gen maori', 'ak ctl'})

# Confirmed by Brendon, 20 Oct 2026, after Curia's complaint - half of
# whatever remains, not the whole pool, every single draw.
CURIA_RESERVE_FRACTION = 0.5


def is_shared_with_curia(poll: str) -> bool:
    return normalise(poll) in SHARED_WITH_CURIA


def max_safe_draw(available: int, poll: str, *, fraction: float = CURIA_RESERVE_FRACTION) -> int:
    """How many numbers Pacific Link may draw from `available` without eating
    into Curia's share.

    Non-shared polls are unaffected - `available` is returned unchanged, same
    as before this existed. A pool shared with Curia is capped at `fraction`
    of what's there, floored, so the cap can never accidentally read as "draw
    everything" on a small remainder and Curia's half never goes negative.

    This is deliberately blind to how much Curia has already taken - it caps
    PL's draw at half of what is UNUSED right now, not half of the pool's
    original size. If Curia already drew their expected share and this still
    leaves PL short, that is a real capacity shortfall to raise with Brendon,
    not something to route around by drawing past the cap.
    """
    if not is_shared_with_curia(poll):
        return available
    return int(available * fraction)

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

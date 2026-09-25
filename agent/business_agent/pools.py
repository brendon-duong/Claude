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

# The whole-year master list. NZNP and ACT both draw from it - one file, not two.
# Checked live 25 Sep 2026: still an .xlsx owned by curiaresearch@gmail.com,
# 6.3 MB, titled "NZ Numbers 2026 - 2027 - USE FROM 15002.xlsx".
#
# TWO LIMITS THAT ARE NOT SOLVED, both proved live, so do not assume otherwise:
#   * it CANNOT be shaded green - an .xlsx cannot be touched by the Sheets API,
#     and Brendon holds edit but not sharing rights so sheets-bot cannot be added.
#     The filename mark is the only mark available on it.
#   * reading it is UNRELIABLE - at 6.3 MB download_file_content dropped the Drive
#     connector three times running on 19 Sep. Retry, and if it keeps failing say
#     so rather than falling back to a stale local copy.
NZ_MASTER = '1DWugvAGB2uPoUXlLZpSglFRxWG0Zjh7C'

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

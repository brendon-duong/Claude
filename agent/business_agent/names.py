"""Which person a Zoom display name is.

Four systems spell every caller differently — Zoom Phone, the call sheet
folders on SharePoint, Elaine's audit sheet and Slack — and none of them is
the roster. Until the caller directory exists this module is the settled
knowledge: the roster as it stands, and the name decisions Brendon has already
made, so no session asks him twice.

Names only. No email, no phone, nothing that belongs in the directory that is
deliberately kept out of this repo.

THE RULE THAT MATTERS
A name that could be two people is matched to neither. Two Jeans, four
Boisers, two Laboras. Tagging the wrong one puts the wrong person on a shift
and the wrong number against someone's pay. `match` returns every plausible
candidate and gives an answer only when there is exactly one.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

# The call sheet folders under /sites/callsheets, listed live 11 Sep 2026, plus
# two people Elaine audits who have no folder yet. Folder names carry the
# nickname in brackets; that is how they are spelt on SharePoint and it stays.
KNOWN_CALLERS: tuple[str, ...] = (
    "Alie Mae Ybanez", "Althea Francesca Rejante", "Bryan Canton", "Charlotte Gimpes",
    "Cherry Jean Raagas", "CJ Peralta", "Elaine Abugan", "Erika Jane Boiser",
    "Evamae Pepito", "Farah Mae Auxtero", "Gerard Siason", "Goldy Kaye Maglasang",
    "Hermi Jeb Edroso", "Ian Christopher Gumalal", "Jane Labora", "Jasmine Magdayao",
    "Jasyl Novida", "Jayzel Gabunada Pureza", "Jean", "Jean Carla Sumarago",
    "Jellame Malicay", "Jess Burgos", "Josephus Parages", "Juvylyn Abe", "Karen Boiser",
    "Katherine Boiser", "Kharen Mae Pihana", "Kiezel Candido", "Kim Rikka Tumbiga",
    "Kris Dolz", "Leizel Chun", "Lovely Salva", "Mariel Angelica Aresco",
    "Mary Joy Tongson (Mary T)", "Mary Joy Villacura (Mary V)", "Marynel Joy Reanturco",
    "Melburne Ando Baliad", "Mercjoy Tibandal", "Nalu Sabroso", "Nilyn Lisondra",
    "Pernelia Villapaz (Lia)", "Princess Matildo", "Rechiell Wagas", "Richelle Mino",
    "Sheery Del Rosario", "Stefany Fojas", "Tristan Philip", "Yvonne Eusebio",
    # No call sheet folder, but real: Elaine audits both by name.
    "Jane Wary Rose Espanueva", "Florence Bularon",
)

# Display names Brendon has confirmed, keyed lowercase. Each of these was a
# guess once; none of them is now. Do not extend this by inference — only by
# a decision from him.
ALIASES: dict[str, str] = {
    "khars -": "Kharen Mae Pihana",              # Zoom, trailing hyphen and all
    "kharen ybas": "Kharen Mae Pihana",          # Elaine's spelling; surname differs, same person
    "jean sumarago": "Jean Carla Sumarago",      # NOT the roster's bare Jean, who is Jean Labora
    "jayzel pureza": "Jayzel Gabunada Pureza",
    "tristan philip bustamante": "Tristan Philip",
    "tristan bustamante": "Tristan Philip",       # Elaine's spelling
    "karen redaniel boiser": "Karen Boiser",
    "melburne baliad": "Melburne Ando Baliad",
    "josephus chris parages": "Josephus Parages",
    "eunilyn lisondra": "Nilyn Lisondra",
    "eunilyn": "Nilyn Lisondra",                  # Elaine's spelling
    "lia villapaz": "Pernelia Villapaz (Lia)",   # what she goes by
    "jane wary espanueva": "Jane Wary Rose Espanueva",  # Elaine's spelling
}


# What each caller's CSV is called in Curia's Drive folder. Their auditor reads
# these next to the files Elaine has been uploading since March, so the spelling
# has to match hers or the same person appears twice across two days.
#
# Hers are the Zoom display name in every case but one, and two of them arrive
# lowercase because that is how the caller set their Zoom profile. Brendon asked
# for full names, so those two are title-cased here and everything else is left
# exactly as Curia already have it.
EXPORT_FILENAME: dict[str, str] = {
    "katherine boiser": "Katherine Boiser",
    "richelle mino": "Richelle Mino",
    # Elaine files Khars under Ybas; the roster folder says Kharen Mae Pihana.
    # Both come from a person, neither from a guess, and they disagree on the
    # surname. Curia's existing files say Ybas, so that is what keeps their
    # folder consistent — but it is NOT settled. See CLAUDE.md.
    "khars -": "Kharen Ybas",
}


def export_filename(zoom_name: str) -> str:
    """The name this caller's CSV carries in Curia's Drive folder."""
    return EXPORT_FILENAME.get(zoom_name.strip().lower(), zoom_name.strip())


def base(name: str) -> str:
    """A name without its bracketed nickname, lowercased, for comparison."""
    return name.split("(")[0].strip().lower()


_ROSTER = {base(n): n for n in KNOWN_CALLERS}


@dataclass(frozen=True)
class Match:
    """What a display name resolved to, and how sure that is."""

    zoom: str
    roster: str | None
    # exact · settled · candidate · ambiguous · unmatched
    how: str
    candidates: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_a_person(self) -> bool:
        return self.how in ("candidate", "ambiguous", "unmatched")


def candidates_for(key: str) -> tuple[str, ...]:
    """Every roster name a display name could plausibly be.

    Two ways in: one name is a word-prefix of the other (`Tristan Philip` /
    `Tristan Philip Bustamante`), or they share a word and are close overall
    (`Eunilyn Lisondra` / `Nilyn Lisondra`). Neither is a decision — it is a
    shortlist for a person.
    """
    found = set()
    for rk, rv in _ROSTER.items():
        if rk.startswith(key + " ") or key.startswith(rk + " "):
            found.add(rv)
        elif set(key.split()) & set(rk.split()) and \
                difflib.SequenceMatcher(None, key, rk).ratio() >= 0.72:
            found.add(rv)
    # A shared first name is the trap. The roster has a bare "Jean" and a
    # "Jean Carla Sumarago"; a prefix rule hands any "Jean X" to the bare one.
    # If more than one roster name starts with this first name, every one of
    # them is a candidate, which makes the answer "neither" — as it should be.
    first = key.split()[0] if key else ""
    same_first = [rv for rk, rv in _ROSTER.items() if rk.split()[0] == first]
    if len(same_first) > 1:
        found.update(same_first)
    return tuple(sorted(found))


def match(zoom_name: str) -> Match:
    key = zoom_name.strip().lower()
    if key in ALIASES:
        return Match(zoom_name, ALIASES[key], "settled")
    if key in _ROSTER:
        return Match(zoom_name, _ROSTER[key], "exact")
    cands = candidates_for(key)
    if len(cands) == 1:
        return Match(zoom_name, None, "candidate", cands)
    if len(cands) > 1:
        return Match(zoom_name, None, "ambiguous", cands)
    return Match(zoom_name, None, "unmatched")

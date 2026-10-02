"""The WhatsApp group as an address book.

Everything else in this agent talks about callers by the name written in the
audit sheet. WhatsApp knows them by a phone number and whatever the group
saved them as — "Kharen" for Kharen Ybas, "Jasmine" for Jasmine Magdayao,
"Lorraine Sabroso" for the person the audit sheet sometimes spells Loraine.

To @-tag someone in a WhatsApp message you need their number, not their name,
so this module is the bridge: it takes a snapshot of the group's participant
list exactly as the WhatsApp connector returns it and answers "which number is
this caller?".

The rule it will not break is the one that governs duplicate names everywhere
else in this codebase: when a name could be two people, say so and match
nobody. Tagging the wrong Florence is worse than tagging no Florence, because
the wrong one turns up to a shift she was never given and the right one does
not turn up at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .audit import normalise_name
from .performance import _one_edit_apart

# WhatsApp prefixes a name it only knows from the sender's own profile (rather
# than from your contacts) with a tilde: "~Alalyn".
_PUSHNAME_MARK = "~"


@dataclass(frozen=True)
class Participant:
    """One member of the WhatsApp group."""

    jid: str  # "639275044990@c.us"
    name: str
    is_admin: bool = False

    @property
    def phone(self) -> str:
        """The bare number, which is what a mention has to be written as."""
        return self.jid.split("@", 1)[0]

    @property
    def key(self) -> str:
        return normalise_name(self.name)


@dataclass
class Match:
    """A caller resolved to a WhatsApp number."""

    participant: Participant
    how: str  # "alias", "exact", "contained" or "typo"


@dataclass
class Directory:
    """The group's participants, searchable by caller name."""

    participants: list[Participant] = field(default_factory=list)
    # Caller name -> phone number, for the handful the matcher will never get
    # on its own: "Lia Villapaz" is saved in WhatsApp as "Pernelia Villapaz",
    # and no rule safe enough to run unattended will connect those two. A
    # person decides once and writes it down; the agent never guesses it.
    aliases: dict[str, str] = field(default_factory=dict)
    # Group members whose saved name is shared with another member. Kept so a
    # report can name them: these are the people who can never be tagged
    # automatically until somebody renames one of the contacts.
    collisions: dict[str, list[Participant]] = field(default_factory=dict)

    # -- loading ------------------------------------------------------------

    @classmethod
    def from_records(
        cls, records: list[dict], aliases: dict[str, str] | None = None
    ) -> "Directory":
        """Build from the connector's participant list, unchanged.

        The shape is what `chats.get_participants` returns: a list of
        ``{"chatId": ..., "name": ..., "isAdmin": ...}``. Taking it verbatim
        means refreshing the directory is a copy-and-paste rather than a
        reformatting job.
        """
        people: list[Participant] = []
        for record in records or ():
            jid = (record.get("chatId") or record.get("jid") or "").strip()
            name = (record.get("name") or "").strip().lstrip(_PUSHNAME_MARK).strip()
            if not jid or not name:
                continue
            people.append(
                Participant(jid=jid, name=name, is_admin=bool(record.get("isAdmin")))
            )

        by_key: dict[str, list[Participant]] = {}
        for person in people:
            if person.key:
                by_key.setdefault(person.key, []).append(person)
        collisions = {key: group for key, group in by_key.items() if len(group) > 1}

        known = {p.phone for p in people}
        resolved: dict[str, str] = {}
        for name, target in (aliases or {}).items():
            key = normalise_name(name)
            phone = str(target).split("@", 1)[0].strip()
            if not key or phone not in known:
                # An alias pointing at a number that has left the group is
                # worse than no alias: it silently tags a stranger. Drop it.
                continue
            resolved[key] = phone
        return cls(participants=people, collisions=collisions, aliases=resolved)

    @classmethod
    def load(cls, path: str | Path) -> "Directory":
        """Read a saved snapshot.

        Accepts either the bare list or the whole connector response with its
        ``{"data": [...]}`` wrapper, so a saved API response works as-is.
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}
        if isinstance(raw, dict):
            aliases = raw.get("aliases") or {}
            raw = raw.get("data") or raw.get("participants") or []
        return cls.from_records(raw, aliases)

    def save(self, path: str | Path) -> None:
        records = [
            {"chatId": p.jid, "name": p.name, "isAdmin": p.is_admin}
            for p in self.participants
        ]
        Path(path).write_text(
            json.dumps(
                {"aliases": self.aliases, "data": records},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    # -- lookup -------------------------------------------------------------

    def candidates(self, name: str) -> list[Match]:
        """Every participant this caller name could plausibly be.

        More than one means the name is not usable for tagging. The tiers are
        deliberately ordered: an exact match ends the search, so "Karen"
        matching the participant literally saved as "Karen" is not made
        ambiguous by "Karen Ybañez Redaniel" also existing.
        """
        key = normalise_name(name)
        if not key:
            return []

        # A name a person has already settled is not re-litigated, and it wins
        # over every rule below — including an exact match on somebody else's
        # contact name, which is the case an alias most often exists to fix.
        phone = self.aliases.get(key)
        if phone:
            return [Match(p, "alias") for p in self.participants if p.phone == phone]

        exact = [Match(p, "exact") for p in self.participants if p.key == key]
        if exact:
            return exact

        tokens = set(key.split())
        contained = [
            Match(p, "contained")
            for p in self.participants
            if p.key
            and (tokens < set(p.key.split()) or set(p.key.split()) < tokens)
        ]
        if contained:
            return contained

        parts = key.split()
        typo: list[Match] = []
        for person in self.participants:
            other = person.key.split()
            if len(parts) != len(other) or not other:
                continue
            differences = [i for i, (a, b) in enumerate(zip(parts, other)) if a != b]
            if len(differences) == 1 and _one_edit_apart(
                parts[differences[0]], other[differences[0]]
            ):
                typo.append(Match(person, "typo"))
        return typo

    def find(self, name: str) -> Match | None:
        """The one participant this caller is, or None if that is not certain.

        None covers both "nobody in the group looks like this" and "two people
        do" — from the caller's point of view the outcome is the same, they do
        not get tagged, and both cases are worth a human's attention.
        """
        found = self.candidates(name)
        return found[0] if len(found) == 1 else None

    def resolve(self, names: list[str]) -> tuple[dict[str, Participant], list[str]]:
        """Resolve a roster's worth of names in one go.

        Returns the ones that matched and a list of the ones that did not, in
        the order given, so the caller can print "these four could not be
        tagged" instead of silently dropping them off the announcement.

        A participant already claimed by an earlier name is not handed out
        again: two spellings of the same caller on one roster is a bug
        upstream, and tagging the same number twice in one message would make
        it look deliberate.
        """
        matched: dict[str, Participant] = {}
        missing: list[str] = []
        claimed: set[str] = set()
        for name in names:
            found = self.find(name)
            if found is None or found.participant.jid in claimed:
                missing.append(name)
                continue
            matched[name] = found.participant
            claimed.add(found.participant.jid)
        return matched, missing

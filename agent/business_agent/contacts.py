"""One row per caller: the name, the number, the address.

Four systems each know these people by a different handle. The audit sheet
calls her "Kharen Ybas". WhatsApp calls her "Kharen" and files her under
639260813435. Her email is something else again. Nothing joins them up, so
every automation has been stuck at the last step — the agent knows who should
work Tuesday and cannot reach them.

This is that join. You give it a spreadsheet with three columns; it lines every
row up against the audit history and the WhatsApp group, and tells you exactly
which rows it could not place. The rows it cannot place are the deliverable:
that list is short, a person fixes it once, and then the whole thing runs.

Column headings are matched loosely, because nobody should have to rename a
column to make software work. Anything resembling a name, a number or an email
is found wherever it sits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .audit import normalise_name
from .availability import match_caller
from .directory import Directory
from .sheets import Row

_NAME_HINTS = ("name", "caller", "staff", "person", "surveyor", "agent")
_PHONE_HINTS = ("whatsapp", "phone", "mobile", "number", "contact", "cell")
_EMAIL_HINTS = ("email", "e-mail", "mail", "address")

# A Philippine mobile is 63 + 10 digits; New Zealand numbers are shorter. Rather
# than encode either, accept anything of a plausible length and normalise the
# shape, because the alternative is silently dropping a real person's number.
_MIN_DIGITS = 7
_MAX_DIGITS = 15
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalise_phone(raw: str, *, default_country: str = "63") -> str:
    """A number as WhatsApp writes it: digits only, country code included.

    Handles what people actually type into a spreadsheet — "+63 927 504 4990",
    "0927 504 4990", "639275044990", and the same again after Excel has helpfully
    turned it into a float.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    # "639275044990.0" — Excel read the column as a number.
    text = re.sub(r"\.0$", "", text)

    plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""

    if not plus:
        # A leading 0 is a national trunk prefix: "0927..." is "63927...".
        if digits.startswith("0"):
            digits = default_country + digits.lstrip("0")
        elif not digits.startswith(default_country) and len(digits) <= 10:
            digits = default_country + digits

    if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
        return ""
    return digits


def normalise_email(raw: str) -> str:
    text = (raw or "").strip().lower()
    return text if _EMAIL.match(text) else ""


@dataclass(frozen=True)
class Contact:
    """One caller, everywhere at once."""

    name: str
    phone: str = ""
    email: str = ""

    @property
    def key(self) -> str:
        return normalise_name(self.name)

    @property
    def can_whatsapp(self) -> bool:
        return bool(self.phone)

    @property
    def can_email(self) -> bool:
        return bool(self.email)


@dataclass
class ContactBook:
    """Every caller's contact details, joined to the other systems."""

    contacts: dict[str, Contact] = field(default_factory=dict)

    # Rows that did not survive the join, each with a reason. This is the list
    # a person actually works through.
    problems: list[tuple[str, str]] = field(default_factory=list)
    # Contact rows whose name matches nobody in the audit history: a new
    # starter, or a spelling nobody has reconciled yet.
    unknown_to_audits: list[str] = field(default_factory=list)
    # Callers in the audit history with no row here at all — the people who
    # cannot be reached, which is the gap that matters most.
    missing_contacts: list[str] = field(default_factory=list)
    # Rows whose number disagrees with the number WhatsApp has for that person.
    phone_conflicts: list[tuple[str, str, str]] = field(default_factory=list)

    def get(self, name: str) -> Contact | None:
        """The contact for a caller name, matched the same way as everywhere else."""
        key = normalise_name(name)
        if key in self.contacts:
            return self.contacts[key]
        matched = match_caller(name, {k: c.name for k, c in self.contacts.items()})
        return self.contacts.get(matched) if matched else None

    def emails_for(self, names: list[str]) -> tuple[dict[str, str], list[str]]:
        """Addresses for a day's callers, and who has none.

        Same contract as the WhatsApp directory's resolve: what worked, and
        what did not, so nobody is dropped in silence.
        """
        found: dict[str, str] = {}
        missing: list[str] = []
        for name in names:
            contact = self.get(name)
            if contact and contact.can_email:
                found[name] = contact.email
            else:
                missing.append(name)
        return found, missing

    @property
    def reachable(self) -> int:
        return sum(1 for c in self.contacts.values() if c.can_email or c.can_whatsapp)


def _find_column(rows: list[Row], hints: tuple[str, ...]) -> str | None:
    """The first column whose heading mentions any of these words.

    Every row's keys are considered, not just the first row's: a sheet whose
    top row happens to leave a cell empty must not make the whole column
    invisible.
    """
    seen: list[str] = []
    for row in rows:
        for column in row:
            if column not in seen:
                seen.append(column)
    for column in seen:
        if any(hint in column.lower() for hint in hints):
            return column
    return None


def load_contacts(
    rows: list[Row],
    *,
    name_column: str | None = None,
    phone_column: str | None = None,
    email_column: str | None = None,
    known_callers: dict[str, str] | None = None,
    directory: Directory | None = None,
    default_country: str = "63",
) -> ContactBook:
    """Read the contact spreadsheet and join it to everything else.

    Pass ``known_callers`` (the audit history) and ``directory`` (the WhatsApp
    group) to have the join checked in both directions: rows that match nobody,
    and people who match no row.
    """
    book = ContactBook()
    if not rows:
        return book

    name_column = name_column or _find_column(rows, _NAME_HINTS)
    if not name_column:
        raise ValueError(
            "could not find a name column in the contact sheet; "
            f"columns present: {', '.join(rows[0])}"
        )

    # Email before phone: a column headed "Contact" should not swallow the
    # address, and "email address" contains both hint words.
    email_column = email_column or _find_column(rows, _EMAIL_HINTS)
    phone_column = phone_column or _find_column(
        [{k: v for k, v in row.items() if k != email_column} for row in rows],
        _PHONE_HINTS,
    )

    for row in rows:
        raw_name = (row.get(name_column) or "").strip()
        if not raw_name:
            continue
        key = normalise_name(raw_name)

        phone = normalise_phone(row.get(phone_column, ""), default_country=default_country) if phone_column else ""
        email = normalise_email(row.get(email_column, "")) if email_column else ""

        if phone_column and (row.get(phone_column) or "").strip() and not phone:
            book.problems.append((raw_name, f"unreadable number: {row[phone_column]!r}"))
        if email_column and (row.get(email_column) or "").strip() and not email:
            book.problems.append((raw_name, f"unreadable email: {row[email_column]!r}"))
        if not phone and not email:
            book.problems.append((raw_name, "no way to reach them"))

        if key in book.contacts:
            # The same person twice. Keep the first and say so, rather than
            # letting the later row silently win.
            book.problems.append((raw_name, "listed more than once"))
            continue
        book.contacts[key] = Contact(name=raw_name, phone=phone, email=email)

    if known_callers is not None:
        contact_names = {k: c.name for k, c in book.contacts.items()}
        for key, contact in book.contacts.items():
            if not match_caller(contact.name, known_callers):
                book.unknown_to_audits.append(contact.name)
        for caller_key, caller_name in known_callers.items():
            if not match_caller(caller_name, contact_names):
                book.missing_contacts.append(caller_name)
        book.unknown_to_audits.sort()
        book.missing_contacts.sort()

    if directory is not None:
        for contact in book.contacts.values():
            found = directory.find(contact.name)
            if found and contact.phone and found.participant.phone != contact.phone:
                book.phone_conflicts.append(
                    (contact.name, contact.phone, found.participant.phone)
                )

    return book

"""The two messages that close the loop in WhatsApp.

One asks the team which days they can work. The other tells them what they
got. Between them they replace the Google Form: the question goes out as a
normal group message, the answers come back as normal replies that
``availability.from_chat_replies`` can read, and the roster goes back out with
everyone @-tagged so it lands as a notification rather than as another message
in a group most people have muted.

A WhatsApp mention is not the text "@Pernelia". The body has to carry the
person's phone number — "@639275044990" — and the send has to carry the
matching JID in its mentions list; the app then draws the contact's name over
the top. So every announcement here comes in two forms: ``text``, which is
what gets sent, and ``preview``, which is the same thing with names written
back in so a person can check it before it goes anywhere.

Nothing in this module sends. It builds the draft and hands it over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .directory import Directory, Participant

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_WEEKDAY_NAMES = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)


def ordinal(number: int) -> str:
    """13 -> "13th". The way a person writes a date in a message."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def long_date(day: date) -> str:
    """"Sunday 13th September"."""
    return (
        f"{_WEEKDAY_NAMES[day.weekday()]} {ordinal(day.day)} "
        f"{_MONTH_NAMES[day.month - 1]}"
    )


@dataclass
class Announcement:
    """A message ready to be reviewed, and then sent by a human decision."""

    text: str
    mentions: list[str] = field(default_factory=list)
    # Rostered callers with no matching WhatsApp number, or whose name matches
    # two members of the group. They appear in the message as plain text, and
    # they are listed here because somebody has to tell them another way.
    untagged: list[str] = field(default_factory=list)
    preview: str = ""

    @property
    def is_complete(self) -> bool:
        """True when every name in the message will actually notify someone."""
        return not self.untagged


def _mention_lines(
    names: list[str], directory: Directory
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Turn rostered names into mention text, preview text and JIDs."""
    matched, missing = directory.resolve(names)
    body: list[str] = []
    shown: list[str] = []
    jids: list[str] = []
    for name in names:
        person: Participant | None = matched.get(name)
        if person is None:
            # Still name them. Being left out of the message entirely is worse
            # than being named without a notification — at least this way the
            # rest of the group can see who is on and chase them.
            body.append(name)
            shown.append(name)
            continue
        body.append(f"@{person.phone}")
        shown.append(f"@{person.name}")
        jids.append(person.jid)
    return body, shown, jids, missing


def render_roster_announcement(
    day: date,
    names: list[str],
    directory: Directory,
    *,
    start_time: str = "2pm",
    end_time: str = "5pm",
    timezone_label: str = "Manila Time",
    poll: str = "",
    footer: str = "",
) -> Announcement:
    """The message that tells one day's callers they are on.

    Names are written one per line rather than run together: a list of twenty
    mentions in a paragraph is unreadable on a phone, and people scanning for
    their own name need it at the start of a line.
    """
    heading = f"Roster {long_date(day)} ({start_time} - {end_time} {timezone_label}):"
    if poll:
        heading = f"{heading[:-1]} — {poll}:"

    body, shown, jids, missing = _mention_lines(names, directory)
    tail = f"\n\n{footer}" if footer else ""

    return Announcement(
        text=heading + "\n" + "\n".join(body) + tail,
        mentions=jids,
        untagged=missing,
        preview=heading + "\n" + "\n".join(shown) + tail,
    )


def render_week_announcements(
    days: list[date],
    names_by_day: dict[date, list[str]],
    directory: Directory,
    **kwargs,
) -> list[Announcement]:
    """One announcement per day, in date order.

    Deliberately not one message for the whole week: a caller who is on for
    Tuesday only should be able to see Tuesday's message and stop reading, and
    a day that changes can be re-sent on its own.
    """
    return [
        render_roster_announcement(day, names_by_day.get(day, []), directory, **kwargs)
        for day in sorted(days)
        if names_by_day.get(day)
    ]


def render_availability_request(
    days: list[date],
    *,
    start_time: str = "2pm",
    end_time: str = "5pm",
    timezone_label: str = "Manila Time",
    deadline: str = "",
) -> Announcement:
    """The question that starts the week.

    The wording carries real weight, because it is what the reply parser has
    to cope with. Asking for the day numbers gives people something short and
    unambiguous to type, while still reading fine if they answer with weekday
    names or "all week" instead.
    """
    if not days:
        raise ValueError("no days to ask about")

    ordered = sorted(days)
    span = f"{long_date(ordered[0])} to {long_date(ordered[-1])}"
    listing = "\n".join(
        f"{ordinal(day.day)} - {_WEEKDAY_NAMES[day.weekday()]}" for day in ordered
    )
    when = f"Shifts are {start_time} - {end_time} {timezone_label}."
    by = f" Please reply by {deadline}." if deadline else ""

    text = (
        f"Availability for {span}\n\n"
        f"{when}{by}\n\n"
        f"Reply to this message with the days you can work:\n\n"
        f"{listing}\n\n"
        f'You can just send the numbers ("13 14 16"), the day names '
        f'("Sun Mon Wed"), or "all week". If you cannot work at all this week, '
        f'reply "not available" so we know you have seen it.'
    )
    return Announcement(text=text, preview=text)


_MENTION = re.compile(r"@(\d{7,15})\b")


def mentioned_numbers(text: str) -> list[str]:
    """The phone numbers a message body tags, for checking a draft."""
    return _MENTION.findall(text or "")

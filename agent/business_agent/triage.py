"""Turning messages into roster events.

Two passes, deliberately in this order:

1. Rules. Fast, free, deterministic, and right most of the time because people
   announce dropouts in a very small number of ways ("can't make Thursday").
2. Claude, for anything the rules found ambiguous. Language is the one job an
   LLM is genuinely better at than a regex. It never does arithmetic here and
   it never picks the replacement -- it only reads intent off a sentence.

If the Claude CLI is missing or fails, the rules result stands. The agent
degrades, it does not stop.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta

from .config import Config
from .models import Event, Message, Person

_DROPOUT = re.compile(
    r"\b(can'?t\s+(?:make|do|work|come|cover)|cannot\s+(?:make|do|work)|won'?t\s+be\s+able"
    r"|not\s+going\s+to\s+make|need\s+to\s+(?:pull\s+out|drop|cancel)|pulling\s+out"
    r"|have\s+to\s+cancel|calling\s+in\s+sick|i'?m\s+sick|off\s+sick|unwell"
    r"|double[- ]booked|can'?t\s+anymore|no\s+longer\s+available)\b",
    re.IGNORECASE,
)
_OFFER = re.compile(
    r"\b(i'?m\s+(?:free|available|around)|i\s+can\s+(?:cover|take|do|help)|happy\s+to\s+(?:cover|take|help)"
    r"|put\s+me\s+down|count\s+me\s+in|available\s+(?:on|for|this|next)|can\s+pick\s+(?:it|that)\s+up"
    r"|i'?ll\s+take\s+it)\b",
    re.IGNORECASE,
)
_CLIENT_CALLS = re.compile(
    r"\b(?:need|want|book|schedule|add)\b[^.\n]{0,40}?\b(?P<n>\d{1,3})\s*(?:more\s+)?calls?\b",
    re.IGNORECASE,
)

_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


def extract_date(text: str, reference: date) -> date | None:
    """Best-effort date from natural language, relative to the run date."""
    lowered = text.lower()

    if re.search(r"\btoday\b|\btonight\b|\bthis\s+(?:morning|arvo|afternoon|evening)\b", lowered):
        return reference
    if re.search(r"\btomorrow\b|\btmr\b|\btmrw\b", lowered):
        return reference + timedelta(days=1)

    explicit = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", lowered)
    if explicit:
        day, month, year = explicit.groups()
        year_int = int(year) if year else reference.year
        if year_int < 100:
            year_int += 2000
        try:
            found = date(year_int, int(month), int(day))
        except ValueError:
            found = None
        if found:
            # A bare "5/3" in the past almost always means next year's occurrence.
            if not year and found < reference - timedelta(days=180):
                try:
                    found = found.replace(year=found.year + 1)
                except ValueError:
                    pass
            return found

    weekday = re.search(
        r"\b(this|next)?\s*(" + "|".join(_WEEKDAYS) + r")\b", lowered
    )
    if weekday:
        qualifier, name = weekday.groups()
        target = _WEEKDAYS[name]
        ahead = (target - reference.weekday()) % 7
        if ahead == 0:
            ahead = 7  # "Thursday" said on a Thursday means the next one
        result = reference + timedelta(days=ahead)
        if qualifier == "next" and ahead < 7:
            result += timedelta(days=7)
        return result

    return None


def _match_person(sender: str, people: dict[str, Person]) -> str | None:
    """Map a WhatsApp display name or phone number onto a team member."""
    needle = sender.strip().lower()
    digits = re.sub(r"\D", "", needle)
    for person in people.values():
        if person.person_id.lower() == needle or person.name.lower() == needle:
            return person.person_id
        if digits and person.phone:
            person_digits = re.sub(r"\D", "", person.phone)
            if person_digits and person_digits[-8:] == digits[-8:]:
                return person.person_id
    first = needle.split()[0] if needle else ""
    if first:
        matches = [p for p in people.values() if p.name.lower().split()[:1] == [first]]
        if len(matches) == 1:
            return matches[0].person_id
    return None


def triage_rules(
    messages: list[Message], people: dict[str, Person], reference: date
) -> list[Event]:
    """Pass 1: cheap, deterministic intent detection."""
    events: list[Event] = []
    for message in messages:
        person_id = _match_person(message.sender, people)
        day = extract_date(message.text, reference)

        calls = _CLIENT_CALLS.search(message.text)
        if calls and person_id is None:
            events.append(
                Event(
                    kind="client_request",
                    message=message,
                    day=day,
                    calls=int(calls.group("n")),
                    confidence=0.7 if day else 0.4,
                    rationale="mentions a number of calls",
                )
            )
            continue

        if _DROPOUT.search(message.text):
            events.append(
                Event(
                    kind="dropout",
                    message=message,
                    person_id=person_id,
                    day=day,
                    confidence=0.85 if (person_id and day) else 0.45,
                    rationale="phrasing indicates they cannot work",
                )
            )
            continue

        if _OFFER.search(message.text):
            events.append(
                Event(
                    kind="offer",
                    message=message,
                    person_id=person_id,
                    day=day,
                    confidence=0.8 if (person_id and day) else 0.45,
                    rationale="phrasing indicates availability",
                )
            )
            continue

        events.append(Event(kind="noise", message=message, confidence=0.9, rationale="no roster signal"))
    return events


def _claude_prompt(events: list[Event], people: dict[str, Person], reference: date) -> str:
    roster_names = ", ".join(f"{p.person_id} ({p.name})" for p in people.values())
    lines = []
    for index, event in enumerate(events):
        lines.append(
            f'{index}. from="{event.message.sender}" '
            f'sent={event.message.sent_at.isoformat()} text="""{event.message.text}"""'
        )
    listing = "\n".join(lines)
    return f"""You are triaging staff and client messages for a call-scheduling business.
Today is {reference.isoformat()}. Team members: {roster_names}

For each numbered message below, decide what it means for the roster.

kind must be one of:
  dropout        - a rostered person says they cannot work a shift
  offer          - someone says they are available or can cover a shift
  client_request - a client asks for a number of calls, or changes their booking
  noise          - anything else (chit-chat, logistics, questions)

Return ONLY a JSON array, one object per message, in the same order:
[{{"index": 0, "kind": "dropout", "person_id": "<id or null>",
   "date": "YYYY-MM-DD or null", "calls": <int or null>,
   "confidence": 0.0-1.0, "rationale": "<8 words max>"}}]

Resolve relative dates ("tomorrow", "next Thursday") against today's date.
Use null when a field is genuinely not stated. Do not invent people or dates.

Messages:
{listing}
"""


def triage_with_claude(
    events: list[Event], people: dict[str, Person], reference: date, config: Config
) -> list[Event]:
    """Pass 2: re-read the low-confidence messages with an LLM.

    Only events the rules were unsure about are sent, which keeps the prompt
    small and the cost near zero on a quiet day.
    """
    unsure = [e for e in events if e.confidence < 0.8 and e.kind != "noise"]
    unsure += [e for e in events if e.kind == "noise" and len(e.message.text) > 40]
    if not unsure or not config.use_claude_triage:
        return events
    if shutil.which(config.claude_command) is None:
        return events

    prompt = _claude_prompt(unsure, people, reference)
    try:
        completed = subprocess.run(
            [config.claude_command, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=config.claude_timeout_seconds,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return events
    if completed.returncode != 0:
        return events

    payload = _extract_json_array(completed.stdout)
    if payload is None:
        return events

    valid_ids = set(people)
    for item in payload:
        try:
            index = int(item["index"])
            target = unsure[index]
        except (KeyError, ValueError, TypeError, IndexError):
            continue
        kind = item.get("kind")
        if kind not in ("dropout", "offer", "client_request", "noise"):
            continue
        target.kind = kind
        target.source = "claude"
        target.rationale = str(item.get("rationale", ""))[:80]
        target.confidence = float(item.get("confidence", 0.6))
        person_id = item.get("person_id")
        if person_id in valid_ids:  # never accept an invented name
            target.person_id = person_id
        raw_date = item.get("date")
        if isinstance(raw_date, str):
            try:
                target.day = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        calls = item.get("calls")
        if isinstance(calls, int):
            target.calls = calls
    return events


def _extract_json_array(text: str) -> list[dict] | None:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def triage(
    messages: list[Message], people: dict[str, Person], reference: date, config: Config
) -> list[Event]:
    events = triage_rules(messages, people, reference)
    return triage_with_claude(events, people, reference, config)

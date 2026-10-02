"""Reading inbound messages into a single normalised stream.

Two formats are supported, both landing in the same inbox directory:

  *.txt   -- a WhatsApp "Export chat" file (iOS or Android layout)
  *.jsonl -- one JSON object per line, written by an API/webhook ingest

Adding a channel means writing a parser that yields Message objects. Nothing
downstream knows or cares where a message came from.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from .models import Message

# iOS:     [12/03/2024, 9:41:13 AM] Sarah Chen: text
# Android: 12/03/2024, 9:41 am - Sarah Chen: text
_IOS = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s*(?P<sender>[^:]{1,80}?):\s?(?P<text>.*)$"
)
_ANDROID = re.compile(
    r"^(?P<ts>\d{1,2}[/-]\d{1,2}[/-]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:[APap]\.?[Mm]\.?)?)"
    r"\s*-\s*(?P<sender>[^:]{1,80}?):\s?(?P<text>.*)$"
)

_TS_FORMATS = (
    "%d/%m/%Y, %I:%M:%S %p", "%d/%m/%Y, %I:%M %p",
    "%d/%m/%Y, %H:%M:%S", "%d/%m/%Y, %H:%M",
    "%d/%m/%y, %I:%M:%S %p", "%d/%m/%y, %I:%M %p",
    "%d/%m/%y, %H:%M:%S", "%d/%m/%y, %H:%M",
    "%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y, %I:%M %p",
)

# Lines WhatsApp inserts that are not from a human.
_SYSTEM_NOISE = (
    "messages and calls are end-to-end encrypted",
    "you deleted this message",
    "this message was deleted",
    "<media omitted>",
    "image omitted",
    "video omitted",
    "joined using this group",
    "changed the subject",
    "changed this group's icon",
)


def _clean(line: str) -> str:
    """Strip the invisible bidi marks WhatsApp sprinkles into exports."""
    return line.replace("‎", "").replace("‏", "").replace(" ", " ").rstrip("\n")


def _parse_timestamp(raw: str) -> datetime | None:
    text = _clean(raw).strip().replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    normalised = re.sub(r"(?i)\b([ap])\.?m\.?\b", lambda m: m.group(1).upper() + "M", text)
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(normalised, fmt)
        except ValueError:
            continue
    return None


def parse_whatsapp_export(text: str, chat: str = "") -> list[Message]:
    """Parse an exported WhatsApp chat, joining wrapped multi-line messages."""
    messages: list[Message] = []
    pending: list[str] = []

    def flush() -> None:
        if pending and messages:
            joined = "\n".join([messages[-1].text, *pending]).strip()
            messages[-1] = Message(
                sent_at=messages[-1].sent_at,
                sender=messages[-1].sender,
                text=joined,
                channel=messages[-1].channel,
                chat=messages[-1].chat,
                message_id=messages[-1].message_id,
            )
        pending.clear()

    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line.strip():
            continue
        match = _IOS.match(line) or _ANDROID.match(line)
        if not match:
            pending.append(line.strip())  # continuation of the previous message
            continue
        flush()
        sent_at = _parse_timestamp(match.group("ts"))
        if sent_at is None:
            continue
        body = match.group("text").strip()
        if not body or any(noise in body.lower() for noise in _SYSTEM_NOISE):
            continue
        messages.append(
            Message(
                sent_at=sent_at,
                sender=match.group("sender").strip(),
                text=body,
                channel="whatsapp",
                chat=chat,
            )
        )
    flush()
    return messages


def parse_jsonl(text: str, chat: str = "") -> list[Message]:
    """Parse newline-delimited JSON written by an API ingest.

    Expected keys: sent_at (ISO 8601), sender, text; optional channel, chat, id.
    """
    messages: list[Message] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        raw_ts = str(record.get("sent_at", "")).replace("Z", "+00:00")
        try:
            sent_at = datetime.fromisoformat(raw_ts)
        except ValueError:
            continue
        if sent_at.tzinfo is not None:
            sent_at = sent_at.replace(tzinfo=None)
        body = str(record.get("text", "")).strip()
        if not body:
            continue
        messages.append(
            Message(
                sent_at=sent_at,
                sender=str(record.get("sender", "unknown")).strip(),
                text=body,
                channel=str(record.get("channel", "whatsapp")),
                chat=str(record.get("chat", chat)),
                message_id=str(record.get("id", "")),
            )
        )
    return messages


def deduplicate(messages: list[Message]) -> list[Message]:
    """Drop messages already seen.

    A WhatsApp export is a snapshot of the *entire* chat, so two exports taken
    on different days overlap almost completely. Without this, every message in
    the overlap is read again and one dropout becomes several.
    """
    seen: set[tuple] = set()
    unique: list[Message] = []
    for message in messages:
        fingerprint = (
            message.message_id
            if message.message_id
            else (message.channel, message.sender, message.sent_at, message.text)
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(message)
    return unique


def load_inbox(inbox_dir: Path, since: date | None = None) -> list[Message]:
    """Read every message file in the inbox, oldest first, without repeats.

    `since` drops anything older than that date. An export carries months of
    history, and a dropout from March must not be acted on as though it were
    today's news.
    """
    if not inbox_dir.exists():
        return []
    messages: list[Message] = []
    for path in sorted(inbox_dir.iterdir()):
        if path.suffix.lower() == ".txt":
            messages.extend(parse_whatsapp_export(path.read_text(encoding="utf-8"), path.stem))
        elif path.suffix.lower() == ".jsonl":
            messages.extend(parse_jsonl(path.read_text(encoding="utf-8"), path.stem))
    if since is not None:
        messages = [m for m in messages if m.sent_at.date() >= since]
    messages.sort(key=lambda m: m.sent_at)
    return deduplicate(messages)

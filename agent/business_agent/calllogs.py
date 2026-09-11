"""Zoom Phone call logs — the raw material for auditing a shift.

Elaine's audit compares what a caller declared against what the phone system
actually recorded. This module fetches the second half of that comparison.

WHY NOT THE ZOOM CONNECTOR
The Claude Zoom connector exposes a `zoom_phone_call` datasource whose schema is
exactly right — caller, callee, start time, duration, status. It returns nothing
for this account, and asking it directly gives the reason:

    403 {"status":"FAILED","error_message":"User does not have a valid license"}

That is the connector's search API needing a licence tier Pacific Link does not
have. Zoom Meetings fails identically, so it is not specific to phone data.

The Phone API is a different entitlement — it needs a Zoom Phone licence, and
there are 53 of those. So the agent goes to `/phone/call_logs` directly with a
Server-to-Server OAuth credential, which also gets it account-wide access rather
than one user's own calls.

CREDENTIALS
Create a Server-to-Server OAuth app in the Zoom admin console with the
`phone:read:admin` scope, then set:

    ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET

Nothing here reads a credential from anywhere but the environment, and no
credential is ever logged.

TESTABLE WITHOUT ZOOM
Every function takes an optional `fetch` callable. The default one talks to
Zoom; the tests pass a stub. None of the parsing, grouping or shift-window
logic needs the network.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

TOKEN_URL = "https://zoom.us/oauth/token"
API_ROOT = "https://api.zoom.us/v2"

# Zoom reports a call's result in `result`. These are the ones that mean a human
# picked up — the only calls that can possibly have produced a completed survey.
ANSWERED = frozenset({"Connected", "Answered", "Call connected"})

# Manila. Curia's shifts are quoted in Manila time and Zoom returns UTC, so the
# day boundary has to be moved or a 2pm-5pm shift spills across two UTC dates.
MANILA = timezone(timedelta(hours=8))

# How long a connected call has to run before it is treated as a finished
# survey. Zoom cannot say whether a questionnaire was completed — only that
# someone picked up and stayed on the line — so length stands in for it.
#
# This is a threshold, not a measurement. Set it too low and a polite refusal
# counts as a complete; too high and genuinely quick respondents are thrown
# away. 150s is Brendon's figure and it is a parameter for a reason: it should
# be calibrated against a week where the real completes are already known.
COMPLETE_SECONDS = 150

# A gap between calls shorter than this is not "away from the phone" — it is
# hanging up, reading the next number and dialling. Counting those would make
# a fast caller look idle, because a fast caller has more of them.
IDLE_SECONDS = 120


class ZoomError(RuntimeError):
    """Zoom refused. The message carries its own words, not a guess at them."""


@dataclass(frozen=True)
class Call:
    """One call, as the phone system recorded it."""

    caller: str
    caller_number: str
    callee_number: str
    started: datetime
    seconds: int
    result: str
    direction: str = "outbound"

    @property
    def answered(self) -> bool:
        return self.result in ANSWERED

    @property
    def day(self) -> date:
        """The Manila date this call belongs to, not the UTC one."""
        return self.started.astimezone(MANILA).date()


@dataclass(frozen=True)
class ShiftCalls:
    """Everything the phone system saw from one caller on one day."""

    caller: str
    day: date
    calls: tuple[Call, ...]

    @property
    def attempts(self) -> int:
        return len(self.calls)

    @property
    def answered(self) -> int:
        return sum(1 for call in self.calls if call.answered)

    @property
    def talk_seconds(self) -> int:
        return sum(call.seconds for call in self.calls if call.answered)

    @property
    def first_call(self) -> datetime | None:
        return min((c.started for c in self.calls), default=None)

    @property
    def last_call(self) -> datetime | None:
        return max((c.started for c in self.calls), default=None)

    def completes(self, threshold: int = COMPLETE_SECONDS) -> int:
        """Answered calls long enough to have been a finished survey.

        An estimate, and deliberately a conservative one: a call has to be
        both answered and at least `threshold` seconds long. A twenty-second
        answered call is a refusal or a wrong number, not a survey.
        """
        return sum(
            1 for call in self.calls if call.answered and call.seconds >= threshold
        )

    def short_answers(self, threshold: int = COMPLETE_SECONDS) -> int:
        """Answered, but too short to be a survey.

        Worth counting separately rather than lumping in with no-answers: a
        caller with many of these reached people and lost them, which is a
        different problem from a caller nobody picked up for.
        """
        return sum(
            1 for call in self.calls if call.answered and call.seconds < threshold
        )

    def _gaps(self) -> list[tuple[datetime, datetime]]:
        """Every stretch between calls, as (from, to).

        Measured from the END of one call to the START of the next, which is
        the whole point: a caller on a six-minute call is working, not absent.
        Measuring start-to-start would report that six minutes as time away.

        A running latest-end is used rather than comparing neighbouring pairs,
        so a call that finishes inside a longer one cannot invent a gap that
        never happened.
        """
        if len(self.calls) < 2:
            return []
        ordered = sorted(self.calls, key=lambda c: c.started)
        spans: list[tuple[datetime, datetime]] = []
        latest_end = ordered[0].started + timedelta(seconds=ordered[0].seconds)
        for call in ordered[1:]:
            if call.started > latest_end:
                spans.append((latest_end, call.started))
            finished = call.started + timedelta(seconds=call.seconds)
            if finished > latest_end:
                latest_end = finished
        return spans

    def breaks(self, minimum: int = IDLE_SECONDS) -> list[tuple[datetime, timedelta]]:
        """Each stretch away from the phone worth counting, as (when, how long).

        Returned rather than only totalled so a shift can be looked at: three
        twenty-minute breaks and forty two-minute ones add to the same number
        and mean completely different things.
        """
        floor = timedelta(seconds=minimum)
        return [
            (start, finish - start)
            for start, finish in self._gaps()
            if finish - start >= floor
        ]

    def idle_time(self, minimum: int = IDLE_SECONDS) -> timedelta:
        """Total time away from the phone, counting only real breaks.

        Time inside a call is never counted, however long the call ran.
        """
        return sum((length for _, length in self.breaks(minimum)), timedelta(0))

    def longest_gap(self, minimum: int = 0) -> timedelta:
        """The single biggest stretch away from the phone."""
        return max(
            (length for _, length in self.breaks(minimum)), default=timedelta(0)
        )


def _post_form(url: str, form: dict[str, str], headers: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(form).encode()
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:  # pragma: no cover - network
        raise ZoomError(f"{error.code} from Zoom: {error.read().decode()[:400]}") from None


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:  # pragma: no cover - network
        raise ZoomError(f"{error.code} from Zoom: {error.read().decode()[:400]}") from None


def access_token(
    account_id: str = "", client_id: str = "", client_secret: str = ""
) -> str:  # pragma: no cover - network
    """Swap the Server-to-Server credentials for a token.

    Falls back to the environment so a caller never has to handle the secret.
    """
    account_id = account_id or os.environ.get("ZOOM_ACCOUNT_ID", "")
    client_id = client_id or os.environ.get("ZOOM_CLIENT_ID", "")
    client_secret = client_secret or os.environ.get("ZOOM_CLIENT_SECRET", "")
    missing = [
        name
        for name, value in (
            ("ZOOM_ACCOUNT_ID", account_id),
            ("ZOOM_CLIENT_ID", client_id),
            ("ZOOM_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        raise ZoomError("not set: " + ", ".join(missing))

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = _post_form(
        TOKEN_URL,
        {"grant_type": "account_credentials", "account_id": account_id},
        {"Authorization": f"Basic {basic}",
         "Content-Type": "application/x-www-form-urlencoded"},
    )
    token = payload.get("access_token", "")
    if not token:
        raise ZoomError("Zoom returned no access_token")
    return token


def _zoom_fetch(day: date, token: str) -> list[dict]:  # pragma: no cover - network
    """Every call log for one Manila day, following Zoom's paging."""
    # Manila 00:00 to 23:59:59, expressed in UTC, so a 2pm-5pm shift stays whole.
    start = datetime.combine(day, datetime.min.time(), MANILA).astimezone(timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=1)

    rows: list[dict] = []
    token_param = ""
    while True:
        query = urllib.parse.urlencode(
            {
                "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "page_size": 300,
                **({"next_page_token": token_param} if token_param else {}),
            }
        )
        payload = _get_json(f"{API_ROOT}/phone/call_logs?{query}", token)
        rows.extend(payload.get("call_logs", []))
        token_param = payload.get("next_page_token", "")
        if not token_param:
            return rows


def parse_call(row: dict) -> Call | None:
    """One Zoom call-log row as a Call, or None if it is not usable.

    Zoom's field names have drifted between API versions, so each value is read
    from the first key that is present rather than one hard-coded name.
    """

    def first(*keys: str, default: str = "") -> str:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
        return default

    started_raw = first("date_time", "start_time")
    if not started_raw:
        return None
    try:
        started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    try:
        seconds = int(float(first("duration", "duration_seconds", default="0")))
    except ValueError:
        seconds = 0

    return Call(
        caller=first("caller_name", "caller_did_number", "owner_name"),
        caller_number=first("caller_number", "caller_did_number"),
        callee_number=first("callee_number", "callee_did_number"),
        started=started,
        seconds=max(seconds, 0),
        result=first("result", "status", "call_result"),
        direction=first("direction", default="outbound"),
    )


def calls_for_day(day: date, *, fetch=None, token: str = "") -> list[Call]:
    """Every parseable call on one Manila day.

    `fetch(day, token)` is swapped out in tests. Rows Zoom sends that cannot be
    parsed are dropped rather than raising: one malformed row must not lose a
    whole shift's audit.
    """
    fetcher = fetch or _zoom_fetch
    rows = fetcher(day, token)
    return [call for call in (parse_call(row) for row in rows) if call is not None]


def by_caller(calls: list[Call], day: date) -> dict[str, ShiftCalls]:
    """Group a day's calls by who made them."""
    grouped: dict[str, list[Call]] = {}
    for call in calls:
        if not call.caller:
            continue
        grouped.setdefault(call.caller.strip().lower(), []).append(call)
    return {
        key: ShiftCalls(caller=rows[0].caller, day=day, calls=tuple(rows))
        for key, rows in grouped.items()
    }


def for_rostered(
    day: date, rostered: list[str], *, fetch=None, token: str = ""
) -> tuple[dict[str, ShiftCalls], list[str]]:
    """The day's calls for the people who were meant to be working.

    Returns what each rostered caller did, and the names with no calls at all.
    That second list is the point: someone rostered with zero calls either did
    not turn up or is logged under a different name, and both need a person to
    look. Silently returning "no calls" for them would hide a dropout.
    """
    grouped = by_caller(calls_for_day(day, fetch=fetch, token=token), day)
    found: dict[str, ShiftCalls] = {}
    silent: list[str] = []
    for name in rostered:
        key = name.strip().lower()
        if key in grouped:
            found[name] = grouped[key]
        else:
            silent.append(name)
    return found, silent

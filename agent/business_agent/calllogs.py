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

# Zoom reports a call's outcome in `result`. These are the values that mean a
# human picked up — the only calls that can possibly have produced a completed
# survey.
#
# The obvious guess at these names was wrong, and wrong in the quietest possible
# way: it scored zero completes for every caller on every day. Counted over
# 33,875 real calls, 1-11 September 2026:
#
#     result            n        median    max     what it is
#     Auto Recorded     15,669   14s       2,841s  a human picked up
#     Call Cancel       11,457   0s        0s      hung up before ring-out
#     Call connected     5,579   3s        7s      a dialler state, never a call
#     Call failed            5   0s        0s      -
#
# So `Auto Recorded` is the answered state, and `Call connected` is not: capped
# at 7 seconds, it cannot be a conversation, and counting it would invent 5,579
# answered calls a day-ish that nobody ever spoke on. "Connected" and "Answered"
# never appear at all; they are kept only because Zoom's field names have
# drifted between API versions and a tenant on another one may send them.
#
# STILL TO CONFIRM: that `Auto Recorded` matches what Zoom's own reporting calls
# answered. Everything downstream of `Call.answered` moves when this set does.
ANSWERED = frozenset({"Auto Recorded", "Connected", "Answered"})

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
IDLE_SECONDS = 60

# A shift is three hours of calling. It is not a fixed clock window: callers
# start when they start, and what is owed is the length, not the times. So the
# shift is measured from a caller's own first call rather than against 2pm.
SHIFT_HOURS = 3

# The earliest a shift may begin, Manila time. Calls before this do not start
# the clock — otherwise someone could dial once at noon, stop, and have their
# three hours run out before the work began.
EARLIEST_START = (13, 30)


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
    # The Zoom Phone user whose leg of the call this is — the agent, whichever
    # way the call went. `caller` is not that: see `agent` below.
    owner: str = ""

    @property
    def answered(self) -> bool:
        return self.result in ANSWERED

    @property
    def agent(self) -> str:
        """The person this call is scored against.

        Zoom names an outbound call after the agent and an inbound one after
        whoever rang in. So `caller` is the agent only half the time, and on
        10 September 2026 five inbound calls from a withheld number were
        collected into a caller called "Anonymous" who does not exist.

        `owner` is the agent every time. Grouping on it reproduces Elaine's
        manual call counts on 21 of 22 callers for that day; grouping on
        `caller` reads low on every one of them. `caller` remains the fallback
        for an outbound row from an API version that sends no owner at all —
        and an inbound row with no owner belongs to nobody.
        """
        if self.owner:
            return self.owner
        return self.caller if self.direction == "outbound" else ""

    @property
    def presence(self) -> bool:
        """Whether this call proves the caller was at the phone.

        An outbound call does — someone dialled it. An inbound call does only
        if it was answered. A missed or failed inbound call is the phone
        ringing at an empty desk; on 10 September 2026 one of those at 7:53am
        and another at 6:18pm turned a full shift into "488 min break, 0
        minutes worked" the moment inbound rows started counting toward the
        agent. Counts use every call; anything to do with time uses these.
        """
        return self.direction == "outbound" or self.answered

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
        ordered = sorted(self.present, key=lambda c: c.started)
        if not ordered:
            return []
        spans: list[tuple[datetime, datetime]] = []
        # The clock may start before the first call — a stray noon call pins
        # it to 1:30pm — and that stretch is time away like any other. The
        # start is treated as a zero-length call so it is measured the same way.
        latest_end = self.started_at()
        for call in ordered:
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

    @staticmethod
    def _floor(when: datetime) -> datetime:
        """The earliest permitted start on the Manila day of `when`."""
        local = when.astimezone(MANILA)
        return local.replace(
            hour=EARLIEST_START[0], minute=EARLIEST_START[1], second=0, microsecond=0
        )

    @property
    def present(self) -> tuple[Call, ...]:
        """The calls that prove the caller was there, inside the window.

        Everything about time — breaks, idle, span, worked, shortfall — is
        measured on these and nothing else. A missed inbound call at 7:53am is
        not a break that ran until 1:25pm; a test call at 10:37 is not the
        start of a shift.
        """
        return tuple(
            c for c in self.calls if c.presence and c.started >= self._floor(c.started)
        )

    @property
    def activity(self) -> int:
        """How many calls prove presence at all, any time of day."""
        return sum(1 for c in self.calls if c.presence)

    @property
    def on_shift(self) -> bool:
        """Whether the caller was at the phone inside the window at all.

        On 10 September 2026 two people each made one call at 10:37 Manila —
        to the same number, a second apart, a phone test — and came out with
        the window 13:30–10:37 and a three-hour shortfall. They had not worked
        the shift; they had not been rostered. A report lists them and does
        not score them, and this is what it branches on.
        """
        return bool(self.present)

    def started_at(self) -> datetime | None:
        """When the shift clock starts, in Manila time.

        A caller's own first call, or the earliest permitted start if they
        began before it. Dialling once at noon and stopping must not let the
        three hours expire before the work begins. Someone who never reached
        the window at all has no start: see `on_shift`.
        """
        if not self.on_shift:
            return None
        first = min(c.started for c in self.calls if c.presence).astimezone(MANILA)
        return max(first, self._floor(first))

    def finished_at(self) -> datetime | None:
        """The end of the last call, in Manila time — not the start of it.

        None when the shift never started, so a window can never read
        backwards.
        """
        if not self.on_shift:
            return None
        return max(
            (c.started + timedelta(seconds=c.seconds) for c in self.present)
        ).astimezone(MANILA)

    def span(self) -> timedelta:
        """First call to the end of the last one: the shift as it happened."""
        start, finish = self.started_at(), self.finished_at()
        if start is None or finish is None:
            return timedelta(0)
        return max(finish - start, timedelta(0))

    def worked(self, minimum: int = IDLE_SECONDS) -> timedelta:
        """The span with the breaks taken out — time actually on the phone."""
        return max(self.span() - self.idle_time(minimum), timedelta(0))

    def shortfall(
        self, hours: int = SHIFT_HOURS, minimum: int = IDLE_SECONDS
    ) -> timedelta:
        """How far short of a full shift, counting only time on the phone.

        Measured against `worked` rather than `span`, so a caller cannot cover
        three hours by making one call, disappearing, and making another.

        A caller who never reached the window is short by all of it — that
        is true, and it is not the same as a three-hour no-show by someone
        rostered. Check `on_shift` before reading this as one.
        """
        return max(timedelta(hours=hours) - self.worked(minimum), timedelta(0))


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

    # The live API nests the owner: {"owner": {"name": ..., "extension_number": ...}}.
    # An older shape sends it flat as owner_name. Either is the agent.
    owner_raw = row.get("owner")
    owner = str(owner_raw.get("name") or "") if isinstance(owner_raw, dict) else ""
    if not owner:
        owner = first("owner_name")

    return Call(
        caller=first("caller_name", "caller_did_number", "owner_name"),
        caller_number=first("caller_number", "caller_did_number"),
        callee_number=first("callee_number", "callee_did_number"),
        started=started,
        seconds=max(seconds, 0),
        result=first("result", "status", "call_result"),
        direction=first("direction", default="outbound"),
        owner=owner,
    )


def calls_for_day(day: date, *, fetch=None, token: str = "") -> list[Call]:
    """Every parseable call on one Manila day.

    `fetch(day, token)` is swapped out in tests. Rows Zoom sends that cannot be
    parsed are dropped rather than raising: one malformed row must not lose a
    whole shift's audit.
    """
    fetcher = fetch or _zoom_fetch
    if fetch is None and not token:
        # Without this the real fetcher sends `Bearer ` and Zoom answers 401,
        # which reads like a bad credential rather than a missing one. A stub
        # fetcher is left alone so the tests never reach for a token.
        token = access_token()
    rows = fetcher(day, token)
    return [call for call in (parse_call(row) for row in rows) if call is not None]


def by_caller(calls: list[Call], day: date) -> dict[str, ShiftCalls]:
    """Group a day's calls by the agent they belong to.

    Keyed on `Call.agent` — the Zoom owner — not on who Zoom lists as the
    caller. Both directions are kept: that is how Elaine counts a caller's
    total calls, and it is the count her audit compares against.
    """
    grouped: dict[str, list[Call]] = {}
    for call in calls:
        if not call.agent:
            continue
        grouped.setdefault(call.agent.strip().lower(), []).append(call)
    return {
        key: ShiftCalls(caller=rows[0].agent, day=day, calls=tuple(rows))
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

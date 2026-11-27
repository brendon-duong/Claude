"""What to invoice Curia for, each week — derived from the Zoom call logs.

Brendon invoices David Farrar every Friday for the week just finished and
currently has to work out the dollar figure by hand. This module answers
"how many caller-shifts actually happened, and what does that come to" the
same way the shift audit already does — from the call logs, not from the
roster plan and not from Curia's own schedule figures, which lag same-day
asks (CLAUDE.md, "The schedule sheet lags real-time asks from Curia").

A caller-shift is counted by `ShiftCalls.on_shift` (business_agent.calllogs):
someone whose calls actually land inside the 6pm-NZ-derived shift window that
day. That is deliberately the one ground truth the shift audit, the weekly
performance review and this module all share, so a caller who was never
rostered but covered a pull-out — an "extra" — is counted automatically,
and nobody who was rostered but never dialled in is counted by mistake.

THE RATE AND THE LINE SHAPE ARE BOTH READ OFF REAL XERO INVOICES, NOT
ASSUMED. Pulled live from Xero on 7 Oct 2026 (contact "David Farrar",
`get_invoices` with line items): every invoice from INV-0141 (2 Apr 2026)
onward bills at **$19.50/hour**, one line per caller, `quantity` always an
exact multiple of 3 — e.g. "Market Research Phone Polller - Jess", qty 15.0,
unit $19.50. So Curia are billed per-caller, in whole 3-hour shift units, not
one aggregate line and not the caller's precise worked span. (Invoices
before that date billed $18.50/hour — INV-0116 through INV-0139 — confirming
the rate itself changed on a real date rather than being a typo either side
of it.) GST is 15% on every invoice checked, net x 1.15 = total exactly.

A caller-shift is counted by `ShiftCalls.on_shift` (business_agent.calllogs):
someone whose calls actually land inside the 6pm-NZ-derived shift window
that day. That is deliberately the one ground truth the shift audit, the
weekly performance review and this module all share, so a caller who was
never rostered but covered a pull-out — an "extra" — is counted
automatically, and nobody who was rostered but never dialled in is counted
by mistake.

CALIBRATION, 7 Oct 2026. `week_revenue(date(2026, 9, 27))` (the week INV-0178,
issued 2 Oct, most plausibly bills) reads 264 caller-shifts, net $15,444.00;
the real invoice is 269 shifts, net $15,736.50 off Xero's own `amount_net`.
98.1% — the same order of agreement the shift audit itself has against
Elaine's manual process (96.6% on completes), and the five-shift gap is
exactly the kind of boundary/duplicate-name slack already documented
elsewhere in this project (CLAUDE.md: duplicate Zoom display names for one
person are reported, never silently merged). This is a confident estimate
Brendon checks, not a number guaranteed to match Curia's own figure to the
cent.

THE WEEK. Shift weeks run Sunday to Saturday, matching
`business_agent.invoices.week_of` — the module that already reconciles
*callers'* invoices to Brendon on this same weekly boundary. A week is
whatever seven days that gives, not an assumption that only Sunday-Thursday
ever runs: Curia have added Fridays and Saturdays before and the schedule
changes without notice, so every day of the week is read, and a day with no
calls at all simply contributes zero. Run on a Friday morning, before that
day's own shift, Friday and Saturday will correctly read zero until they
happen — the caller breakdown and the headline total both just show what
has actually occurred by the time this runs.

This module does not touch Slack, Drive, Xero or email — it only reads
Zoom. It produces the figure and the breakdown; sending it is a separate
job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .calllogs import SHIFT_HOURS, by_caller, calls_for_day
from .names import export_filename

#: Confirmed live against Xero on 7 Oct 2026 — see the module docstring.
RATE_PER_HOUR = 19.50

#: $19.50/hour x a 3-hour shift, Curia's own billing unit (every real
#: invoice line's quantity is an exact multiple of 3).
RATE_PER_SHIFT = round(RATE_PER_HOUR * SHIFT_HOURS, 2)

#: NZ GST, read off Brendon's real Xero invoices to Curia.
GST_RATE = 0.15

#: What the invoice line item is called for every caller, on every real
#: Xero invoice checked.
LINE_DESCRIPTION = "Market Research Phone Polller"


def _display_name(zoom_name: str) -> str:
    """A readable name for the invoice line.

    `names.export_filename` already carries the handful of confirmed
    Zoom-display-name -> real-name mappings (e.g. "khars -" -> "Kharen
    Ybas"); anything it doesn't know is just title-cased rather than left as
    the raw lowercase Zoom string.
    """
    mapped = export_filename(zoom_name)
    stripped = zoom_name.strip()
    return mapped if mapped != stripped else stripped.title()


@dataclass(frozen=True)
class DayRevenue:
    """One day's worth of actual caller-shifts, read from the call logs."""

    day: date
    callers: tuple[str, ...]

    @property
    def caller_shifts(self) -> int:
        return len(self.callers)

    @property
    def net(self) -> float:
        return round(self.caller_shifts * RATE_PER_SHIFT, 2)


@dataclass(frozen=True)
class WeekRevenue:
    """A Sunday-to-Saturday week, one `DayRevenue` per day."""

    week_start: date
    days: tuple[DayRevenue, ...]

    @property
    def caller_shifts(self) -> int:
        return sum(d.caller_shifts for d in self.days)

    @property
    def net(self) -> float:
        return round(sum(d.net for d in self.days), 2)

    @property
    def gst(self) -> float:
        return round(self.net * GST_RATE, 2)

    @property
    def total(self) -> float:
        return round(self.net + self.gst, 2)


@dataclass(frozen=True)
class CallerLine:
    """One caller's week, as a single paste-ready Xero invoice line."""

    name: str
    shift_days: int

    @property
    def hours(self) -> float:
        return self.shift_days * SHIFT_HOURS

    @property
    def net(self) -> float:
        return round(self.hours * RATE_PER_HOUR, 2)


def week_of(d: date) -> date:
    """The Sunday that starts `d`'s shift week.

    Matches `business_agent.invoices.week_of` exactly, so a caller's own
    invoice week and the Curia invoice week are never off by one day from
    each other.
    """
    return d - timedelta(days=(d.weekday() + 1) % 7)


def day_revenue(day: date, *, fetch=None, token: str = "") -> DayRevenue:
    """Actual caller-shifts worked on `day`, read from the Zoom call logs.

    Counts `ShiftCalls.on_shift` — present inside the derived shift window —
    never the roster, never a Slack declaration, and never who was *meant*
    to work. A day nobody worked (a no-poll day, or one read before any
    calls landed) comes back with zero callers rather than raising.
    """
    grouped = by_caller(calls_for_day(day, fetch=fetch, token=token), day)
    working = tuple(sorted(name for name, shift in grouped.items() if shift.on_shift))
    return DayRevenue(day=day, callers=working)


def week_revenue(week_start: date, *, fetch=None, token: str = "") -> WeekRevenue:
    """The Sunday-starting week containing `week_start`'s own seven days.

    `week_start` must itself be a Sunday — callers that want "the week
    containing this date" should pass `week_of(d)` first, the same split
    `invoices.week_of` already uses for a caller's own invoice.
    """
    days = tuple(
        day_revenue(week_start + timedelta(days=i), fetch=fetch, token=token)
        for i in range(7)
    )
    return WeekRevenue(week_start=week_start, days=days)


def caller_lines(week: WeekRevenue) -> tuple[CallerLine, ...]:
    """Per-caller shift-day counts for the week, as paste-ready Xero lines.

    Built from the `WeekRevenue` already fetched — each `DayRevenue` already
    carries its own callers, so this needs no second read of the call logs.
    Sorted by display name, matching the order Brendon would type them.
    """
    counts: dict[str, int] = {}
    for d in week.days:
        for zoom_name in d.callers:
            counts[zoom_name] = counts.get(zoom_name, 0) + 1
    lines = [CallerLine(name=_display_name(z), shift_days=n) for z, n in counts.items()]
    return tuple(sorted(lines, key=lambda c: c.name.lower()))


def invoice_lines_text(week: WeekRevenue) -> str:
    """The per-caller lines, tab-separated, ready to paste straight into
    Xero's own line-item grid: description, quantity (hours), rate, amount.

    This is the half of the ask the headline total alone doesn't cover —
    Brendon's invoices to Curia are one line per caller, not one aggregate
    line, and this reproduces that shape exactly (see the module docstring
    for how it was checked against real invoices).
    """
    rows = [
        f"{LINE_DESCRIPTION} - {c.name}\t{c.hours:g}\t${RATE_PER_HOUR:.2f}\t${c.net:,.2f}"
        for c in caller_lines(week)
    ]
    return "\n".join(rows)


def invoice_text(week: WeekRevenue) -> str:
    """A copy-paste-ready block in the net / GST / total shape of a real
    Xero invoice — the figure Brendon drops straight into the invoice to
    David every Friday.

    A day with zero caller-shifts (no poll, or a day that hasn't happened
    yet) is left off the breakdown rather than printed as a zero line.
    """
    lines = [
        f"Pacific Link Global — week of {week.week_start:%d %b %Y}",
        "",
    ]
    for d in week.days:
        if d.caller_shifts:
            lines.append(
                f"{d.day:%A %d %b}: {d.caller_shifts} caller-shifts "
                f"x ${RATE_PER_SHIFT:.2f} = ${d.net:,.2f}"
            )
    lines += [
        "",
        f"Caller-shifts: {week.caller_shifts}",
        f"Net: ${week.net:,.2f}",
        f"GST (15%): ${week.gst:,.2f}",
        f"Total: ${week.total:,.2f}",
        "",
        "GST here is 15% of the net total; Xero applies it per line, so the "
        "real invoice can differ by a few cents. A day still to come reads "
        "as zero until it's actually worked.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the week's invoice figure and per-caller lines.

    No date given, this is the week containing today — NZ time, because
    that is the calendar the Friday run and Brendon both work on. Pass a
    date to recompute any other week.
    """
    import argparse
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ap = argparse.ArgumentParser(
        description="The Curia invoice figure for one week, from the Zoom call logs."
    )
    ap.add_argument("day", nargs="?",
                    help="YYYY-MM-DD, any day in the target week. Default: today, NZ time.")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.day) if args.day else (
        datetime.now(ZoneInfo("Pacific/Auckland")).date()
    )
    week = week_revenue(week_of(today))
    print(invoice_text(week))
    print()
    print("--- per-caller lines, paste straight into Xero ---")
    print(invoice_lines_text(week))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

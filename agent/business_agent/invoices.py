"""Reconcile a caller's invoice against the Zoom call logs.

Callers bill Brendon on a copy of `Pacific Link Global Invoice Template`: a row
per shift with DATE OF SHIFT, HOURS WORKED, PRICE, AMOUNT, and a TOTAL. They
email it as a PDF or xlsx attachment from their own address. Nothing currently
checks any of it, so an invoice for a shift nobody worked is paid, and a shift
worked but never invoiced is never paid.

WHAT THIS MODULE WILL AND WILL NOT SAY
--------------------------------------
Money reaches a real person, so every finding here has to be defensible from a
hard fact. Three are:

  NOT_WORKED      the invoice bills a date on which the caller made no calls at
                  all. Zoom is ground truth for that.
  NOT_INVOICED    they worked a shift and no invoice covers it. This is money
                  owed TO them and is the most useful finding in practice.
  ARITHMETIC      hours x price does not equal the amount, or the rows do not
                  sum to the stated total. No judgement needed at all.
  DUPLICATE       the same shift date appears on two invoices.

One is reported but never used as an accusation:

  SHORT_SPAN      the caller's first-to-last-call span is materially less than
                  the hours billed. This is the (B) category from the weekly
                  performance review - solid, because it comes from their own
                  calls - but it is still a span, not a timesheet.

And one is deliberately NOT computed here at all: TIME OFF THE PHONE. That
measure reads up to 4x the manual audit (CLAUDE.md), and an over-billing
accusation built on it would be indefensible. `breaks` and `idle_time` are not
read by this module. Do not add them.

THE RATE IS READ FROM THE INVOICE, NEVER ASSUMED. The template ships $5.00/hr
and every invoice seen so far uses it, but rates are per-caller and Brendon has
not confirmed they are uniform. A missing or unreadable price is reported as
unknown rather than defaulted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# parsing the invoice text
# ---------------------------------------------------------------------------

_MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9, 'oct': 10,
    'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
}

# "WEDNESDAY 16TH SEPT 2026", "Tuesday 27th August 2024", "16 Sept 2026"
_LONG_DATE = re.compile(
    r'(?:(?:mon|tues?|wed(?:nes)?|thur?s?|fri|sat(?:ur)?|sun)[a-z]*\s+)?'
    r'(\d{1,2})\s*(?:st|nd|rd|th)?\s+([a-z]+)\.?\s+(\d{4})',
    re.I)
# "9/17/26" and "9/17/2026" - the template's own examples are US month/day.
_SLASH_DATE = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b')

_MONEY = re.compile(r'\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)')


def _money(text: str) -> float | None:
    m = _MONEY.search(text or '')
    if not m:
        return None
    return float(m.group(1).replace(',', ''))


def parse_long_date(text: str) -> date | None:
    """The DATE OF SHIFT form callers actually type: "WEDNESDAY 16TH SEPT 2026"."""
    m = _LONG_DATE.search(text or '')
    if not m:
        return None
    day, month_word, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTHS.get(month_word)
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def parse_slash_date(text: str, *, month_first: bool = True) -> date | None:
    """The DATE / DUE DATE form, which the template writes month-first."""
    m = _SLASH_DATE.search(text or '')
    if not m:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    month, day = (a, b) if month_first else (b, a)
    try:
        return date(y, month, day)
    except ValueError:
        return None


@dataclass
class InvoiceLine:
    """One billed shift."""
    shift_date: date | None
    hours: float | None
    price: float | None
    amount: float | None
    raw: str = ''

    @property
    def expected_amount(self) -> float | None:
        if self.hours is None or self.price is None:
            return None
        return round(self.hours * self.price, 2)


@dataclass
class Invoice:
    caller_email: str
    number: str | None = None
    created: date | None = None
    lines: list[InvoiceLine] = field(default_factory=list)
    stated_total: float | None = None
    source: str = ''

    @property
    def billed_dates(self) -> list[date]:
        return [l.shift_date for l in self.lines if l.shift_date]

    @property
    def line_total(self) -> float:
        return round(sum(l.amount or 0.0 for l in self.lines), 2)


def parse_invoice(text: str, *, caller_email: str, source: str = '') -> Invoice:
    """Read an invoice out of the flat text an attachment read returns.

    The layout is a table flattened to one long string, so this works line by
    line and keeps only rows that carry BOTH a date and a non-zero amount. The
    template ships ten blank MARKET RESEARCH rows at $0.00 and every caller
    leaves the unused ones in; counting those as billed shifts would invent
    lines that were never charged for.
    """
    inv = Invoice(caller_email=caller_email, source=source)

    m = re.search(r'INVOICE\s*#\s*(?:.*?)\b(\d{1,4})\b', text or '', re.I | re.S)
    if m:
        inv.number = m.group(1)

    # The first slash-date after "DATE" is the creation date.
    after_date = re.split(r'\bDATE\b', text or '', maxsplit=1, flags=re.I)
    if len(after_date) > 1:
        inv.created = parse_slash_date(after_date[1])

    # THE SHIFT DATE COMES BEFORE THE ITEM LABEL, NOT AFTER IT. The row reads
    #   <date>  MARKET RESEARCH PHONE CALLS  <description>  <hours> $<price> ... $<amount>
    # so splitting on the label orphans every date onto the previous row. Walk
    # the dates instead, and take each row as the window from one date to the
    # next. The window for the last row would otherwise swallow the TOTAL, so
    # the items region is cut at the footer first.
    body = text or ''
    head = re.search(r'\bAMOUNT\b', body, re.I)
    if head:
        body = body[head.end():]
    foot = re.search(r'WISE\s*ACCOUNT|\bTOTAL\b', body, re.I)
    if foot:
        body = body[:foot.start()]

    marks = list(_LONG_DATE.finditer(body))
    for i, m in enumerate(marks):
        window = body[m.start():marks[i + 1].start() if i + 1 < len(marks) else len(body)]
        d = parse_long_date(window)
        # TAKE THE FIRST PRICE/AMOUNT PAIR IN THE WINDOW, NOT THE LAST. Every
        # caller leaves the template's ten unused $0.00 rows in place, and those
        # fall inside the window of whichever real row precedes them - so the
        # last money on a window is almost always a blank row's $0.00, which
        # reads as a row billed for nothing and drops the real line silently.
        monies = _MONEY.findall(window)
        price = amount = None
        if len(monies) >= 2:
            price = float(monies[0].replace(',', ''))
            amount = float(monies[1].replace(',', ''))
        elif len(monies) == 1:
            price = float(monies[0].replace(',', ''))
        # Hours sit immediately before the price, as a bare number.
        hours = None
        hm = re.search(r'(\d+(?:\.\d+)?)\s*\$', window)
        if hm:
            hours = float(hm.group(1))
        if d is not None and amount:
            inv.lines.append(InvoiceLine(shift_date=d, hours=hours, price=price,
                                         amount=amount, raw=window.strip()[:160]))

    tm = re.search(r'TOTAL(.*)$', text or '', re.I | re.S)
    if tm:
        inv.stated_total = _money(tm.group(1))
    return inv


# ---------------------------------------------------------------------------
# reconciling against what Zoom says
# ---------------------------------------------------------------------------

@dataclass
class Worked:
    """What the call logs say about one caller on one day."""
    shift_date: date
    on_shift: bool
    calls: int
    span_hours: float | None


@dataclass
class Finding:
    kind: str
    shift_date: date | None
    detail: str
    money: float | None = None


#: how far short of the billed hours a span has to fall before it is reported.
#: A caller who starts two minutes late has not done anything wrong.
SPAN_TOLERANCE_HOURS = 0.5


def reconcile(invoice: Invoice, worked: dict[date, Worked],
              *, seen_dates: dict[date, str] | None = None) -> list[Finding]:
    """Compare one invoice against the logs. Returns findings, worst first.

    `worked` maps a date to what the logs say. A date absent from `worked` is a
    date with no calls at all.

    `seen_dates` maps a date already billed on another invoice to that invoice's
    identifier, so double-billing is caught across invoices rather than only
    within one.
    """
    out: list[Finding] = []

    for line in invoice.lines:
        d = line.shift_date
        if d is None:
            continue
        w = worked.get(d)

        if w is None or w.calls == 0:
            out.append(Finding('NOT_WORKED', d,
                               'billed but no calls at all in the Zoom logs',
                               line.amount))
            continue

        if not w.on_shift:
            out.append(Finding('NOT_ON_SHIFT', d,
                               f'{w.calls} call(s) but none after the 1:30pm floor, '
                               'so this does not read as a worked shift',
                               line.amount))
            continue

        if (seen_dates or {}).get(d):
            out.append(Finding('DUPLICATE', d,
                               f'already billed on invoice {seen_dates[d]}',
                               line.amount))

        exp = line.expected_amount
        if exp is not None and line.amount is not None and abs(exp - line.amount) > 0.005:
            out.append(Finding('ARITHMETIC', d,
                               f'{line.hours} h x ${line.price:.2f} = ${exp:.2f}, '
                               f'invoice says ${line.amount:.2f}',
                               round(line.amount - exp, 2)))

        if (line.hours is not None and w.span_hours is not None
                and line.hours - w.span_hours > SPAN_TOLERANCE_HOURS):
            out.append(Finding('SHORT_SPAN', d,
                               f'billed {line.hours:g} h; first call to last call '
                               f'spans {w.span_hours:.2f} h',
                               None))

    if invoice.stated_total is not None and abs(invoice.line_total - invoice.stated_total) > 0.005:
        out.append(Finding('ARITHMETIC', None,
                           f'rows add to ${invoice.line_total:.2f}, '
                           f'stated total is ${invoice.stated_total:.2f}',
                           round(invoice.stated_total - invoice.line_total, 2)))

    order = {'NOT_WORKED': 0, 'DUPLICATE': 1, 'NOT_ON_SHIFT': 2,
             'ARITHMETIC': 3, 'SHORT_SPAN': 4}
    out.sort(key=lambda f: (order.get(f.kind, 9), f.shift_date or date.min))
    return out


def unbilled(worked: dict[date, Worked], billed: set[date]) -> list[Finding]:
    """Shifts the logs show but no invoice covers - money owed to the caller.

    This is the half of reconciliation that favours the caller, and it is the
    reason to run it at all rather than only chasing over-billing.
    """
    out = []
    for d, w in sorted(worked.items()):
        if w.on_shift and w.calls and d not in billed:
            out.append(Finding('NOT_INVOICED', d,
                               f'worked ({w.calls} calls) and no invoice covers it', None))
    return out


def week_of(d: date) -> date:
    """The Sunday that starts d's shift week. Shift weeks run Sun-Sat here."""
    return d - timedelta(days=(d.weekday() + 1) % 7)

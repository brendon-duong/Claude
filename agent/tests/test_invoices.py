import unittest
from datetime import date

from business_agent import invoices as iv


# A real invoice, flattened the way an attachment read returns it. Jasyl Novida
# #2, received 18 Sep 2026. Note the ten unused template rows at $0.00 - those
# are what the parser has to NOT count as billed shifts.
JASYL = (
    "JASYL YBANEZ Invoice PRK. 23 BRGY. STO NINO TUGBOK DAVAO CITY N/A PHILIPPINES 8000 "
    "BILL TO: INVOICE # Pacific Link Global 2 <------ UPDATE THIS NUMBER WEEKLY IN SEQUENCE "
    "Address: 5A Whiorau Grove DATE City: Lowry Bay 9/17/26 Country: New Zealand "
    "INVOICE DUE DATE Postal: 5013 9/17/26 "
    "DATE OF SHIFT ITEMS DESCRIPTION HOURS WORKED PRICE CURRENCY TAX AMOUNT "
    "WEDNESDAY 16TH SEPT 2026 MARKET RESEARCH PHONE CALLS Contracted Hours 3 $5.00 NZD 0.00% $15.00 "
    "MARKET RESEARCH PHONE CALLS Contracted Hours $5.00 NZD 0.00% $0.00 "
    "MARKET RESEARCH PHONE CALLS Contracted Hours $5.00 NZD 0.00% $0.00 "
    "0 $0.00 WISE ACCOUNT: TOTAL @jasylnervidaj $15.00 NZD"
)


class DateParsingTest(unittest.TestCase):
    def test_the_form_callers_type_on_the_shift_row(self):
        self.assertEqual(iv.parse_long_date('WEDNESDAY 16TH SEPT 2026'), date(2026, 9, 16))
        self.assertEqual(iv.parse_long_date('Tuesday 27th August 2024'), date(2024, 8, 27))
        self.assertEqual(iv.parse_long_date('MONDAY 1ST DECEMBER 2026'), date(2026, 12, 1))

    def test_without_a_weekday(self):
        self.assertEqual(iv.parse_long_date('16 Sept 2026'), date(2026, 9, 16))

    def test_rejects_rubbish(self):
        self.assertIsNone(iv.parse_long_date('MARKET RESEARCH PHONE CALLS'))
        self.assertIsNone(iv.parse_long_date(''))
        self.assertIsNone(iv.parse_long_date('32nd Septober 2026'))

    def test_the_template_writes_slash_dates_month_first(self):
        self.assertEqual(iv.parse_slash_date('9/17/26'), date(2026, 9, 17))
        self.assertEqual(iv.parse_slash_date('9/17/2026'), date(2026, 9, 17))

    def test_day_first_when_told_so(self):
        self.assertEqual(iv.parse_slash_date('17/9/26', month_first=False), date(2026, 9, 17))


class ParseInvoiceTest(unittest.TestCase):
    def setUp(self):
        self.inv = iv.parse_invoice(JASYL, caller_email='jasylnovida16@gmail.com', source='#2')

    def test_header(self):
        self.assertEqual(self.inv.number, '2')
        self.assertEqual(self.inv.created, date(2026, 9, 17))
        self.assertEqual(self.inv.caller_email, 'jasylnovida16@gmail.com')

    def test_the_blank_template_rows_are_not_billed_shifts(self):
        # Three MARKET RESEARCH rows appear; only one carries a date and an amount.
        self.assertEqual(len(self.inv.lines), 1)

    def test_the_billed_line(self):
        line = self.inv.lines[0]
        self.assertEqual(line.shift_date, date(2026, 9, 16))
        self.assertEqual(line.hours, 3.0)
        self.assertEqual(line.price, 5.0)
        self.assertEqual(line.amount, 15.0)
        self.assertEqual(line.expected_amount, 15.0)

    def test_totals(self):
        self.assertEqual(self.inv.line_total, 15.0)
        self.assertEqual(self.inv.stated_total, 15.0)
        self.assertEqual(self.inv.billed_dates, [date(2026, 9, 16)])

    def test_the_amount_is_the_first_pair_not_the_last(self):
        # Regression: the last money in a row's window is a blank template row's
        # $0.00, which silently dropped the real line and reported zero billed.
        self.assertNotEqual(self.inv.lines[0].amount, 0.0)


class RateIsReadNotAssumedTest(unittest.TestCase):
    """Rates are per-caller: CJ invoices at $5.50 where the template ships $5.00."""

    HIGHER = (
        "A B INVOICE # Pacific Link Global 3 DATE 9/24/26 AMOUNT "
        "TUESDAY 22ND SEPT 2026 MARKET RESEARCH PHONE CALLS d 3 $5.50 NZD 0.00% $16.50 "
        "WEDNESDAY 23RD SEPT 2026 MARKET RESEARCH PHONE CALLS d 3 $5.50 NZD 0.00% $16.50 "
        "MARKET RESEARCH PHONE CALLS d $5.50 NZD 0.00% $0.00 "
        "WISE ACCOUNT: TOTAL x $33.00"
    )

    def test_a_higher_rate_parses_and_is_not_a_finding(self):
        inv = iv.parse_invoice(self.HIGHER, caller_email='x@y.com')
        self.assertEqual(len(inv.lines), 2)
        self.assertEqual({l.price for l in inv.lines}, {5.50})
        self.assertEqual(inv.line_total, 33.0)
        worked = {d: iv.Worked(d, True, 180, 3.05)
                  for d in (date(2026, 9, 22), date(2026, 9, 23))}
        self.assertEqual(iv.reconcile(inv, worked), [])

    def test_a_partial_shift_is_not_a_finding(self):
        text = ("A INVOICE # 4 DATE 9/18/26 AMOUNT THURSDAY 17TH SEPT 2026 "
                "MARKET RESEARCH PHONE CALLS d 1.75 $5.00 NZD 0.00% $8.75 "
                "WISE ACCOUNT: TOTAL x $8.75")
        inv = iv.parse_invoice(text, caller_email='x@y.com')
        self.assertEqual(inv.lines[0].hours, 1.75)
        self.assertEqual(inv.lines[0].amount, 8.75)
        worked = {date(2026, 9, 17): iv.Worked(date(2026, 9, 17), True, 90, 1.8)}
        self.assertEqual(iv.reconcile(inv, worked), [])


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.inv = iv.parse_invoice(JASYL, caller_email='j@x.com', source='#2')
        self.day = date(2026, 9, 16)

    def test_clean_when_the_shift_was_worked(self):
        worked = {self.day: iv.Worked(self.day, True, 180, 3.05)}
        self.assertEqual(iv.reconcile(self.inv, worked), [])

    def test_billed_a_day_with_no_calls(self):
        found = iv.reconcile(self.inv, {})
        self.assertEqual([f.kind for f in found], ['NOT_WORKED'])
        self.assertEqual(found[0].money, 15.0)
        self.assertEqual(found[0].shift_date, self.day)

    def test_calls_but_none_on_shift(self):
        worked = {self.day: iv.Worked(self.day, False, 2, None)}
        self.assertEqual([f.kind for f in iv.reconcile(self.inv, worked)], ['NOT_ON_SHIFT'])

    def test_short_span_is_reported(self):
        worked = {self.day: iv.Worked(self.day, True, 90, 1.4)}
        found = iv.reconcile(self.inv, worked)
        self.assertEqual([f.kind for f in found], ['SHORT_SPAN'])
        self.assertIsNone(found[0].money, 'a span must never carry a money claim')

    def test_a_few_minutes_short_is_not_reported(self):
        worked = {self.day: iv.Worked(self.day, True, 170, 2.8)}
        self.assertEqual(iv.reconcile(self.inv, worked), [])

    def test_duplicate_across_invoices(self):
        worked = {self.day: iv.Worked(self.day, True, 180, 3.05)}
        found = iv.reconcile(self.inv, worked, seen_dates={self.day: '#1'})
        self.assertEqual([f.kind for f in found], ['DUPLICATE'])
        self.assertIn('#1', found[0].detail)

    def test_row_arithmetic(self):
        bad = JASYL.replace('0.00% $15.00', '0.00% $18.00').replace('TOTAL @jasylnervidaj $15.00',
                                                                   'TOTAL @jasylnervidaj $18.00')
        inv = iv.parse_invoice(bad, caller_email='j@x.com')
        worked = {self.day: iv.Worked(self.day, True, 180, 3.05)}
        found = iv.reconcile(inv, worked)
        self.assertEqual([f.kind for f in found], ['ARITHMETIC'])
        self.assertEqual(found[0].money, 3.0)

    def test_total_that_does_not_match_the_rows(self):
        bad = JASYL.replace('TOTAL @jasylnervidaj $15.00', 'TOTAL @jasylnervidaj $30.00')
        inv = iv.parse_invoice(bad, caller_email='j@x.com')
        worked = {self.day: iv.Worked(self.day, True, 180, 3.05)}
        found = [f for f in iv.reconcile(inv, worked) if f.shift_date is None]
        self.assertEqual([f.kind for f in found], ['ARITHMETIC'])
        self.assertEqual(found[0].money, 15.0)

    def test_worst_first(self):
        worked = {self.day: iv.Worked(self.day, True, 90, 1.4)}
        found = iv.reconcile(self.inv, worked, seen_dates={self.day: '#1'})
        self.assertEqual([f.kind for f in found], ['DUPLICATE', 'SHORT_SPAN'])

    def test_off_phone_time_is_never_read(self):
        # The gate from CLAUDE.md: that measure reads up to 4x the manual audit,
        # so no finding may depend on it. Worked carries no break field at all.
        self.assertNotIn('breaks', iv.Worked.__dataclass_fields__)
        self.assertNotIn('idle_time', iv.Worked.__dataclass_fields__)
        self.assertNotIn('away', iv.Worked.__dataclass_fields__)


class UnbilledTest(unittest.TestCase):
    def test_a_worked_shift_nobody_invoiced(self):
        d = date(2026, 9, 17)
        found = iv.unbilled({d: iv.Worked(d, True, 150, 3.0)}, billed=set())
        self.assertEqual([f.kind for f in found], ['NOT_INVOICED'])
        self.assertEqual(found[0].shift_date, d)

    def test_a_billed_shift_is_not_reported(self):
        d = date(2026, 9, 17)
        self.assertEqual(iv.unbilled({d: iv.Worked(d, True, 150, 3.0)}, billed={d}), [])

    def test_an_off_shift_day_is_not_money_owed(self):
        d = date(2026, 9, 17)
        self.assertEqual(iv.unbilled({d: iv.Worked(d, False, 2, None)}, billed=set()), [])

    def test_sorted_by_date(self):
        days = [date(2026, 9, 17), date(2026, 9, 14), date(2026, 9, 16)]
        worked = {d: iv.Worked(d, True, 150, 3.0) for d in days}
        found = iv.unbilled(worked, billed=set())
        self.assertEqual([f.shift_date for f in found], sorted(days))


class WeekOfTest(unittest.TestCase):
    def test_shift_weeks_start_on_sunday(self):
        self.assertEqual(iv.week_of(date(2026, 9, 27)), date(2026, 9, 27))  # a Sunday
        self.assertEqual(iv.week_of(date(2026, 9, 30)), date(2026, 9, 27))  # Wednesday
        self.assertEqual(iv.week_of(date(2026, 10, 2)), date(2026, 9, 27))  # Friday

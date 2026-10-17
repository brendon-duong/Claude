"""The weekly Curia invoice figure, derived from the Zoom call logs, without Zoom."""

from __future__ import annotations

import unittest
from datetime import date

from business_agent import revenue as rv

SUNDAY = date(2026, 9, 13)  # a real Sunday, pre-DST (Manila shift 2pm-5pm)


def row(caller, when, seconds=180, result="Auto Recorded"):
    return {
        "caller_name": caller,
        "caller_number": "+63288001",
        "callee_number": "+6421234567",
        "date_time": when,
        "duration": seconds,
        "result": result,
        "direction": "outbound",
    }


class DayRevenueTest(unittest.TestCase):
    def stub(self, rows):
        return lambda day, token: rows

    def test_counts_each_caller_once(self):
        rows = [
            row("Lia Villapaz", "2026-09-13T06:05:00Z"),
            row("Lia Villapaz", "2026-09-13T06:10:00Z"),
            row("Leizel Chun", "2026-09-13T06:20:00Z"),
        ]
        d = rv.day_revenue(SUNDAY, fetch=self.stub(rows))
        self.assertEqual(d.callers, ("leizel chun", "lia villapaz"))
        self.assertEqual(d.caller_shifts, 2)

    def test_net_is_shifts_times_the_rate(self):
        rows = [row("Lia Villapaz", "2026-09-13T06:05:00Z")]
        d = rv.day_revenue(SUNDAY, fetch=self.stub(rows))
        self.assertEqual(d.net, 58.50)

    def test_an_empty_day_is_zero_not_an_error(self):
        d = rv.day_revenue(SUNDAY, fetch=self.stub([]))
        self.assertEqual(d.caller_shifts, 0)
        self.assertEqual(d.net, 0.0)

    def test_a_call_before_the_shift_window_does_not_count(self):
        # Well before the 1:30pm Manila floor for a pre-DST day.
        rows = [row("Early Bird", "2026-09-12T23:30:00Z")]  # 7:30am Manila on the 13th
        d = rv.day_revenue(SUNDAY, fetch=self.stub(rows))
        self.assertEqual(d.caller_shifts, 0)


class WeekRevenueTest(unittest.TestCase):
    def test_sums_seven_days(self):
        def fetch(day, token):
            # Only the Sunday and the Wednesday have anyone working.
            if day == SUNDAY:
                return [row("A", "2026-09-13T06:05:00Z"), row("B", "2026-09-13T06:10:00Z")]
            if day == date(2026, 9, 16):
                return [row("C", "2026-09-16T06:05:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        self.assertEqual(len(week.days), 7)
        self.assertEqual(week.caller_shifts, 3)
        self.assertEqual(week.net, 175.50)

    def test_gst_and_total(self):
        week = rv.week_revenue(SUNDAY, fetch=lambda day, token: (
            [row("A", "2026-09-13T06:05:00Z")] if day == SUNDAY else []
        ))
        self.assertEqual(week.net, 58.50)
        self.assertEqual(week.gst, 8.78)  # 58.50 * 0.15 = 8.775, rounds to 8.78
        self.assertEqual(week.total, 67.28)

    def test_a_week_with_nothing_worked_is_all_zero(self):
        week = rv.week_revenue(SUNDAY, fetch=lambda day, token: [])
        self.assertEqual(week.caller_shifts, 0)
        self.assertEqual(week.net, 0.0)
        self.assertEqual(week.gst, 0.0)
        self.assertEqual(week.total, 0.0)


class WeekOfTest(unittest.TestCase):
    def test_matches_the_caller_invoice_weeks(self):
        from business_agent import invoices as iv

        for d in (date(2026, 9, 27), date(2026, 9, 30), date(2026, 10, 2)):
            self.assertEqual(rv.week_of(d), iv.week_of(d))


class CallerLinesTest(unittest.TestCase):
    def test_one_shift_each(self):
        def fetch(day, token):
            if day == SUNDAY:
                return [row("Lia Villapaz", "2026-09-13T06:05:00Z"),
                        row("Leizel Chun", "2026-09-13T06:10:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        lines = rv.caller_lines(week)
        self.assertEqual([c.name for c in lines], ["Leizel Chun", "Lia Villapaz"])
        self.assertEqual([c.shift_days for c in lines], [1, 1])
        self.assertEqual([c.hours for c in lines], [3, 3])
        self.assertEqual([c.net for c in lines], [58.50, 58.50])

    def test_the_same_caller_across_days_accumulates_shift_days(self):
        def fetch(day, token):
            return [row("Lia Villapaz", f"{day.isoformat()}T06:05:00Z")]

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        lines = rv.caller_lines(week)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].shift_days, 7)
        self.assertEqual(lines[0].hours, 21)
        self.assertEqual(lines[0].net, 409.50)

    def test_known_zoom_quirk_name_is_mapped_not_titlecased(self):
        def fetch(day, token):
            if day == SUNDAY:
                return [row("Khars -", "2026-09-13T06:05:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        self.assertEqual(rv.caller_lines(week)[0].name, "Kharen Ybas")

    def test_caller_net_sums_to_the_week_net(self):
        def fetch(day, token):
            if day in (SUNDAY, date(2026, 9, 16)):
                return [row("A", f"{day.isoformat()}T06:05:00Z"),
                        row("B", f"{day.isoformat()}T06:10:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        self.assertEqual(round(sum(c.net for c in rv.caller_lines(week)), 2), week.net)


class InvoiceLinesTextTest(unittest.TestCase):
    def test_tab_separated_xero_shape(self):
        def fetch(day, token):
            if day == SUNDAY:
                return [row("Lia Villapaz", "2026-09-13T06:05:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        text = rv.invoice_lines_text(week)
        self.assertEqual(
            text,
            "Market Research Phone Polller - Lia Villapaz\t3\t$19.50\t$58.50",
        )

    def test_a_caller_working_five_days_bills_fifteen_hours(self):
        def fetch(day, token):
            if day.weekday() in (6, 0, 1, 2, 3):  # Sun-Thu
                return [row("Lia Villapaz", f"{day.isoformat()}T06:05:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        text = rv.invoice_lines_text(week)
        self.assertEqual(
            text,
            "Market Research Phone Polller - Lia Villapaz\t15\t$19.50\t$292.50",
        )


class InvoiceTextTest(unittest.TestCase):
    def test_copy_paste_block_has_the_net_gst_total_shape(self):
        def fetch(day, token):
            if day == SUNDAY:
                return [row("A", "2026-09-13T06:05:00Z"), row("B", "2026-09-13T06:10:00Z")]
            return []

        week = rv.week_revenue(SUNDAY, fetch=fetch)
        text = rv.invoice_text(week)
        self.assertIn("Sunday 13 Sep: 2 caller-shifts x $58.50 = $117.00", text)
        self.assertIn("Caller-shifts: 2", text)
        self.assertIn("Net: $117.00", text)
        self.assertIn("GST (15%): $17.55", text)
        self.assertIn("Total: $134.55", text)

    def test_a_day_with_nobody_working_is_not_printed(self):
        week = rv.week_revenue(SUNDAY, fetch=lambda day, token: [])
        text = rv.invoice_text(week)
        for d in week.days:
            self.assertNotIn(f"{d.day:%A %d %b}", text)


if __name__ == "__main__":
    unittest.main()

"""Tests for the Curia schedule loader.

The fixture is a synthetic sheet that reproduces the real one's quirks —
continuation rows, holidays, CRLF endings, #DIV/0! cells, blank days — without
putting client data in the repository.
"""

import unittest
from datetime import date
from pathlib import Path

from business_agent.curia import (
    NonPollDay,
    PollDay,
    load_schedule,
    parse_schedule_date,
    to_demand,
    to_int,
)
from business_agent.sheets import _read_csv

FIXTURE = Path(__file__).parent / "fixtures" / "curia_schedule_sample.csv"


class TestParseScheduleDate(unittest.TestCase):
    def test_weekday_and_short_month(self):
        self.assertEqual(parse_schedule_date("Tuesday 08-Sep-26"), date(2026, 9, 8))

    def test_without_the_weekday(self):
        self.assertEqual(parse_schedule_date("08-Sep-26"), date(2026, 9, 8))

    def test_blank_is_a_continuation_row_not_an_error(self):
        self.assertIsNone(parse_schedule_date(""))
        self.assertIsNone(parse_schedule_date("   "))

    def test_a_label_is_not_a_date(self):
        self.assertIsNone(parse_schedule_date("Good Friday"))


class TestToInt(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(to_int("20"), 20)

    def test_spreadsheet_errors_are_not_numbers(self):
        for value in ("#DIV/0!", "#REF!", "#N/A", ""):
            self.assertIsNone(to_int(value), value)

    def test_tbc_is_not_zero(self):
        self.assertIsNone(to_int("TBC"))

    def test_tolerates_thousands_separators_and_decimals(self):
        self.assertEqual(to_int("1,000"), 1000)
        self.assertEqual(to_int("17.0"), 17)


class TestLoadSchedule(unittest.TestCase):
    def setUp(self):
        self.polls, self.non_polls = load_schedule(_read_csv(FIXTURE))
        self.by_day = {}
        for poll in self.polls:
            self.by_day.setdefault(poll.day, []).append(poll)

    def test_continuation_rows_inherit_the_date_above(self):
        second = [p for p in self.by_day[date(2026, 4, 5)] if p.poll == "Maori 1000"]
        self.assertEqual(len(second), 1)

    def test_both_polls_on_a_shared_day_are_kept(self):
        self.assertEqual(
            [p.poll for p in self.by_day[date(2026, 4, 7)]],
            ["Whanganui 400", "ACT 1000"],
        )

    def test_holidays_are_separated_from_polls(self):
        self.assertIn(NonPollDay(day=date(2026, 4, 3), label="Good Friday"), self.non_polls)
        self.assertNotIn(date(2026, 4, 3), self.by_day)

    def test_empty_days_produce_nothing_at_all(self):
        self.assertNotIn(date(2026, 4, 4), self.by_day)
        self.assertNotIn(date(2026, 4, 8), self.by_day)
        self.assertFalse(any(n.day == date(2026, 4, 4) for n in self.non_polls))

    def test_reads_the_pl_staff_confirmed_column(self):
        (poll,) = [p for p in self.by_day[date(2026, 4, 6)] if p.poll == "NZNP 500"]
        self.assertEqual(poll.pl_staff_confirmed, 20)
        self.assertEqual(poll.curia_staff_wanted, 3)

    def test_div_zero_cells_do_not_break_the_row(self):
        (poll,) = [p for p in self.by_day[date(2026, 4, 7)] if p.poll == "ACT 1000"]
        self.assertEqual(poll.pl_staff_confirmed, 25)
        self.assertEqual(poll.extra_pl_required, 5)

    def test_blank_pl_confirmed_is_none_not_zero(self):
        (poll,) = [p for p in self.by_day[date(2026, 4, 6)] if p.poll == "Maori 1000"]
        self.assertIsNone(poll.pl_staff_confirmed)


class TestPollDay(unittest.TestCase):
    def test_extra_staff_requested_on_the_day_counts_toward_need(self):
        poll = PollDay(date(2026, 4, 7), "ACT 1000", pl_staff_confirmed=25, extra_pl_required=5)
        self.assertEqual(poll.pl_staff_needed, 30)

    def test_slot_normalises_the_poll_name(self):
        self.assertEqual(PollDay(date(2026, 4, 7), "  ACT   1000 ").slot, "act 1000")

    def test_no_pl_staff_confirmed_means_no_need(self):
        self.assertEqual(PollDay(date(2026, 4, 7), "Maori 1000").pl_staff_needed, 0)


class TestToDemand(unittest.TestCase):
    def setUp(self):
        polls, _ = load_schedule(_read_csv(FIXTURE))
        self.demand = to_demand(polls)
        self.slots = {(d.day, d.shift): d for d in self.demand}

    def test_staff_required_comes_straight_from_the_sheet(self):
        demand = self.slots[(date(2026, 4, 6), "nznp 500")]
        self.assertEqual(demand.staff_required, 20)
        self.assertEqual(demand.staff_needed(calls_per_person=10), 20)

    def test_polls_needing_no_pl_staff_are_dropped(self):
        self.assertNotIn((date(2026, 4, 6), "maori 1000"), self.slots)

    def test_extra_requested_is_visible_in_the_notes(self):
        demand = self.slots[(date(2026, 4, 7), "act 1000")]
        self.assertEqual(demand.staff_required, 30)
        self.assertIn("+5 extra", demand.notes)

    def test_phone_target_is_carried_through(self):
        self.assertEqual(self.slots[(date(2026, 4, 6), "nznp 500")].calls_required, 175)


if __name__ == "__main__":
    unittest.main()

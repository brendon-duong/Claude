import unittest
from datetime import date

from business_agent.schedule_value import (
    HOURLY_RATE, SHIFT_HOURS, describe, diff, parse_schedule, snapshot, totals, window,
)

HEADER = ("Date,Poll,Online target,Phone target,Curia Staff Wanted,"
          "PL Staff Confirmed,Extra PL Staff Required Day of Shift\n")


class ParseSchedule(unittest.TestCase):
    def test_a_blank_pl_cell_means_the_poll_is_curias(self):
        # The 21 Sep failure: NZNP 500 is Curia's own team that day, and
        # reading the last number on the row put ten of our best callers on it.
        days = parse_schedule(HEADER + (
            "Monday 21-Sep-26,NZNP 500,75,175,10,,0\n"
            ",Tamaki ACT 750,33,400,,30,3\n"))
        self.assertEqual(len(days), 1)
        self.assertEqual([p.poll for p in days[0].polls], ["Tamaki ACT 750"])
        self.assertEqual(days[0].slots, 30)

    def test_a_continuation_row_carries_the_date_forward(self):
        days = parse_schedule(HEADER + (
            "Wednesday 30-Sep-26,NZNP 333,,,7,7,\n"
            ",Waiariki 500,,,8,10,\n"
            ",Rangitikei 400,,,0,10,\n"))
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].day, date(2026, 9, 30))
        self.assertEqual(days[0].slots, 27)

    def test_a_day_with_no_poll_of_ours_does_not_appear(self):
        days = parse_schedule(HEADER + "Saturday 26-Sep-26,,,,,,\n")
        self.assertEqual(days, [])

    def test_the_weekday_comes_from_curias_own_wording(self):
        days = parse_schedule(HEADER + "Friday 25-Sep-26,Waitaki 400,,,0,20,\n")
        self.assertEqual(days[0].weekday, "Friday")


class Money(unittest.TestCase):
    def test_a_caller_shift_is_three_hours_at_the_hourly_rate(self):
        days = parse_schedule(HEADER + "Friday 25-Sep-26,Waitaki 400,,,0,20,\n")
        self.assertEqual(days[0].hours, 20 * SHIFT_HOURS)
        self.assertEqual(days[0].value, round(20 * SHIFT_HOURS * HOURLY_RATE, 2))

    def test_totals_add_the_days_up(self):
        days = parse_schedule(HEADER + (
            "Thursday 24-Sep-26,Te Tai Tonga 500,,,8,10,\n"
            ",Te Tai Hauauru 500,,,7,11,\n"
            "Friday 25-Sep-26,Waitaki 400,,,0,20,\n"))
        self.assertEqual(totals(days), {
            "slots": 41, "hours": 123.0, "value": 2398.5,
            "rate": HOURLY_RATE, "shift_hours": SHIFT_HOURS})

    def test_window_keeps_only_the_dates_asked_for(self):
        days = parse_schedule(HEADER + (
            "Friday 25-Sep-26,Waitaki 400,,,0,20,\n"
            "Sunday 27-Sep-26,NZNP 333,,,7,7,\n"))
        kept = window(days, date(2026, 9, 27), date(2026, 10, 3))
        self.assertEqual([d.day for d in kept], [date(2026, 9, 27)])


class Diff(unittest.TestCase):
    def test_it_reports_the_poll_that_changed_not_just_the_day(self):
        # "Wednesday went from 17 to 42" hides which poll arrived, and the
        # poll is what a roster is built on.
        changes = diff(
            {"2026-09-30": {"NZNP 333": 7, "Waiariki 500": 10}},
            {"2026-09-30": {"NZNP 333": 7, "Waiariki 500": 10, "Rangitikei 400": 10}},
        )
        self.assertEqual(changes, [{"day": "2026-09-30", "poll": "Rangitikei 400",
                                    "kind": "added", "was": None, "now": 10}])

    def test_it_reports_a_removal_and_a_headcount_move(self):
        changes = diff(
            {"2026-09-28": {"ACT 1000": 22, "Hauraki-Waikato 500": 18}},
            {"2026-09-28": {"ACT 1000": 18}},
        )
        self.assertEqual(
            sorted((c["poll"], c["kind"], c["was"], c["now"]) for c in changes),
            [("ACT 1000", "changed", 22, 18),
             ("Hauraki-Waikato 500", "removed", 18, None)])

    def test_no_change_reports_nothing(self):
        same = {"2026-09-25": {"Waitaki 400": 20}}
        self.assertEqual(diff(same, dict(same)), [])

    def test_a_whole_new_day_shows_as_added_polls(self):
        changes = diff({}, {"2026-10-02": {"Wgtn 1000": 13}})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "added")

    def test_describe_is_readable_in_a_slack_dm(self):
        self.assertIn("+", describe({"day": "2026-10-02", "poll": "Wgtn 1000",
                                     "kind": "added", "was": None, "now": 13}))
        self.assertIn("-> 18", describe({"day": "2026-09-28", "poll": "ACT 1000",
                                         "kind": "changed", "was": 22, "now": 18}))


class Snapshot(unittest.TestCase):
    def test_a_snapshot_round_trips_through_diff_unchanged(self):
        days = parse_schedule(HEADER + (
            "Monday 21-Sep-26,NZNP 500,75,175,10,,0\n"
            ",Tamaki ACT 750,33,400,,30,3\n"))
        self.assertEqual(diff(snapshot(days), snapshot(days)), [])
        self.assertEqual(snapshot(days), {"2026-09-21": {"Tamaki ACT 750": 30}})


if __name__ == "__main__":
    unittest.main()

"""Reading standing availability out of what people actually did."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from business_agent.availability import Availability
from business_agent.patterns import (
    Exception_,
    apply_exceptions,
    derive_patterns,
    who_to_ask,
)

MON, TUE, WED, THU, SUN = 0, 1, 2, 3, 6


class FakeAudit:
    """Only the two fields patterns cares about."""

    def __init__(self, name: str, day: date) -> None:
        self.name = name
        self.day = day


def shifts(name: str, start: date, weeks: int, weekdays: list[int]) -> list[FakeAudit]:
    """One caller working the same weekdays for a run of weeks."""
    out = []
    for week in range(weeks):
        monday = start + timedelta(days=7 * week)
        for weekday in weekdays:
            out.append(FakeAudit(name, monday + timedelta(days=weekday)))
    return out


# A Monday, so the weeks line up cleanly.
START = date(2026, 7, 13)
AS_OF = date(2026, 9, 3)  # a Thursday, eight weeks later


class TestDerivingPatterns(unittest.TestCase):
    def test_a_steady_caller_gets_their_weekdays(self) -> None:
        patterns = derive_patterns(
            shifts("Leizel Chun", START, 8, [MON, TUE, THU]), as_of=AS_OF
        )
        self.assertEqual(patterns.patterns["leizel chun"].label, "Mon Tue Thu")

    def test_an_occasional_day_is_left_out(self) -> None:
        # Every Monday, but only two Wednesdays in eight weeks.
        records = shifts("Kharen Ybas", START, 8, [MON])
        records += shifts("Kharen Ybas", START, 2, [WED])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertEqual(patterns.patterns["kharen ybas"].label, "Mon")
        self.assertAlmostEqual(patterns.patterns["kharen ybas"].rates[WED], 0.25)

    def test_a_day_worked_in_exactly_half_the_weeks_counts(self) -> None:
        records = shifts("Jane Espanuva", START, 8, [MON])
        records += shifts("Jane Espanuva", START, 4, [TUE])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertEqual(patterns.patterns["jane espanuva"].label, "Mon Tue")

    def test_too_few_shifts_is_unknown_not_unavailable(self) -> None:
        # Two shifts is not a pattern. Saying so is different from saying the
        # person cannot work, and the difference decides who gets asked.
        patterns = derive_patterns(
            [FakeAudit("New Starter", START), FakeAudit("New Starter", START + timedelta(days=1))],
            as_of=AS_OF,
        )
        self.assertNotIn("new starter", patterns.patterns)
        self.assertEqual(patterns.too_few_shifts, ["New Starter"])

    def test_time_off_does_not_read_as_unreliability(self) -> None:
        # Every Monday either side of a fortnight's leave. Rates are per
        # active week, so this is a full Monday pattern, not two thirds of one.
        records = shifts("Lovely Salva", START, 3, [MON])
        records += shifts("Lovely Salva", START + timedelta(days=35), 3, [MON])
        patterns = derive_patterns(records, as_of=AS_OF)
        pattern = patterns.patterns["lovely salva"]
        self.assertEqual(pattern.label, "Mon")
        self.assertEqual(pattern.active_weeks, 6)
        self.assertEqual(pattern.confidence, 1.0)

    def test_history_outside_the_window_is_ignored(self) -> None:
        old = shifts("Old Hand", date(2026, 1, 5), 8, [MON, TUE, WED])
        patterns = derive_patterns(old, as_of=AS_OF)
        self.assertEqual(patterns.patterns, {})

    def test_a_caller_not_seen_recently_is_marked_stale(self) -> None:
        records = shifts("Gone Quiet", START, 4, [MON, TUE])
        patterns = derive_patterns(records, as_of=AS_OF, stale_days=21)
        self.assertTrue(patterns.patterns["gone quiet"].stale)
        self.assertNotIn("gone quiet", patterns.fresh)

    def test_a_recent_caller_is_not_stale(self) -> None:
        records = shifts("Still Here", AS_OF - timedelta(days=28), 4, [MON, TUE])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertFalse(patterns.patterns["still here"].stale)

    def test_two_audits_on_one_day_are_one_shift(self) -> None:
        records = shifts("Twice Audited", START, 6, [MON])
        records += shifts("Twice Audited", START, 6, [MON])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertEqual(patterns.patterns["twice audited"].shifts, 6)
        self.assertEqual(patterns.patterns["twice audited"].rates[MON], 1.0)

    def test_name_spellings_are_normalised_together(self) -> None:
        records = shifts("Leizel Chun", START, 4, [MON])
        records += shifts("  LEIZEL   CHUN  ", START + timedelta(days=28), 4, [MON])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns.patterns["leizel chun"].active_weeks, 8)

    def test_confidence_reports_the_weakest_day(self) -> None:
        # The weakest day is the one that lets you down.
        records = shifts("Mixed", START, 8, [MON])
        records += shifts("Mixed", START, 5, [TUE])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertAlmostEqual(patterns.patterns["mixed"].confidence, 5 / 8)

    def test_no_audits_at_all(self) -> None:
        patterns = derive_patterns([], as_of=AS_OF)
        self.assertEqual(len(patterns), 0)
        self.assertEqual(patterns.too_few_shifts, [])

    def test_the_window_is_reported(self) -> None:
        patterns = derive_patterns(shifts("A Caller", START, 8, [MON]), as_of=AS_OF)
        self.assertEqual(patterns.window_to, AS_OF)
        self.assertEqual(patterns.window_from, AS_OF - timedelta(days=56))


class TestUsingPatterns(unittest.TestCase):
    def setUp(self) -> None:
        records = shifts("Mon Tue Person", START, 8, [MON, TUE])
        records += shifts("Thu Person", START, 8, [THU])
        records += shifts("Sunday Person", START, 8, [SUN])
        self.patterns = derive_patterns(records, as_of=AS_OF)
        # The business week: Sunday 13 September through Thursday the 17th.
        self.week = [date(2026, 9, 13) + timedelta(days=i) for i in range(5)]

    def test_who_would_normally_be_on(self) -> None:
        self.assertEqual(self.patterns.on(date(2026, 9, 14)), {"mon tue person"})
        self.assertEqual(self.patterns.on(date(2026, 9, 17)), {"thu person"})
        self.assertEqual(self.patterns.on(date(2026, 9, 13)), {"sunday person"})

    def test_cover_counts_each_day(self) -> None:
        self.assertEqual(
            self.patterns.cover(self.week),
            {
                date(2026, 9, 13): 1,
                date(2026, 9, 14): 1,
                date(2026, 9, 15): 1,
                date(2026, 9, 16): 0,
                date(2026, 9, 17): 1,
            },
        )

    def test_becomes_an_availability_the_roster_builder_accepts(self) -> None:
        availability = self.patterns.to_availability(self.week)
        self.assertEqual(availability.days, self.week)
        self.assertEqual(availability.on(date(2026, 9, 14)), {"mon tue person"})
        # A day nobody normally works is empty, not absent: an unstaffed shift
        # rather than a day the question never covered.
        self.assertEqual(availability.on(date(2026, 9, 16)), set())

    def test_display_names_are_carried_through(self) -> None:
        availability = self.patterns.to_availability(self.week)
        self.assertEqual(availability.display_names["thu person"], "Thu Person")

    def test_stale_patterns_are_left_out_unless_asked_for(self) -> None:
        records = shifts("Gone Quiet", START, 4, [MON])
        patterns = derive_patterns(records, as_of=AS_OF)
        self.assertEqual(patterns.on(date(2026, 9, 14)), set())
        self.assertEqual(
            patterns.on(date(2026, 9, 14), include_stale=True), {"gone quiet"}
        )

    def test_who_to_ask_names_only_the_short_days(self) -> None:
        needed = {day: 1 for day in self.week}
        gaps = who_to_ask(self.patterns, self.week, needed)
        self.assertEqual(gaps[date(2026, 9, 16)], 1)
        self.assertEqual(gaps[date(2026, 9, 14)], 0)

    def test_a_day_with_spare_cover_is_never_negative(self) -> None:
        gaps = who_to_ask(self.patterns, self.week, {self.week[1]: 0})
        self.assertEqual(gaps[self.week[1]], 0)


class TestExceptions(unittest.TestCase):
    """This week's deviations, overlaid on the standing default."""

    def setUp(self) -> None:
        self.week = [date(2026, 9, 13) + timedelta(days=i) for i in range(5)]
        self.availability = Availability(
            by_day={day: {"regular"} for day in self.week},
            display_names={"regular": "Regular Caller"},
        )

    def test_an_off_day_is_removed(self) -> None:
        updated = apply_exceptions(
            self.availability,
            [Exception_("regular", date(2026, 9, 15), available=False)],
        )
        self.assertEqual(updated.on(date(2026, 9, 15)), set())
        self.assertEqual(updated.on(date(2026, 9, 14)), {"regular"})

    def test_an_extra_day_is_added(self) -> None:
        availability = Availability(by_day={day: set() for day in self.week})
        updated = apply_exceptions(
            availability,
            [Exception_("keen", date(2026, 9, 13), available=True)],
            known={"keen": "Keen Caller"},
        )
        self.assertEqual(updated.on(date(2026, 9, 13)), {"keen"})
        self.assertEqual(updated.display_names["keen"], "Keen Caller")

    def test_the_standing_availability_is_not_mutated(self) -> None:
        # The difference between what they normally do and what they said this
        # week has to stay inspectable.
        apply_exceptions(
            self.availability,
            [Exception_("regular", date(2026, 9, 15), available=False)],
        )
        self.assertEqual(self.availability.on(date(2026, 9, 15)), {"regular"})

    def test_an_exception_for_an_unplanned_day_is_ignored(self) -> None:
        # A date outside the week is a typo or a message about a different
        # week; adding it would invent a shift nobody is planning.
        updated = apply_exceptions(
            self.availability,
            [Exception_("regular", date(2026, 10, 4), available=True)],
        )
        self.assertNotIn(date(2026, 10, 4), updated.by_day)

    def test_removing_someone_who_was_not_on_is_harmless(self) -> None:
        updated = apply_exceptions(
            self.availability,
            [Exception_("stranger", date(2026, 9, 15), available=False)],
        )
        self.assertEqual(updated.on(date(2026, 9, 15)), {"regular"})

    def test_exceptions_apply_in_order(self) -> None:
        updated = apply_exceptions(
            self.availability,
            [
                Exception_("regular", date(2026, 9, 15), available=False),
                Exception_("regular", date(2026, 9, 15), available=True),
            ],
        )
        self.assertEqual(updated.on(date(2026, 9, 15)), {"regular"})


if __name__ == "__main__":
    unittest.main()

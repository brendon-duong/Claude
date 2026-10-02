"""Tests for building a week's roster from audit performance."""

import unittest
from datetime import date, timedelta

from business_agent.audit import AuditRecord
from business_agent.availability import parse_availability
from business_agent.curia import PollDay
from business_agent.performance import Thresholds, score_all
from business_agent.roster_plan import build_roster, business_week_start, group_duplicates

TODAY = date(2026, 9, 8)
SUNDAY = date(2026, 9, 13)
WORKING = ["sunday", "monday", "tuesday", "wednesday", "thursday"]


def audits_for(name, count=6, completes=5, declared=None, day=TODAY):
    """A caller with `count` recent audits."""
    return [
        AuditRecord(
            day=day - timedelta(days=index * 2),
            name=name,
            declared_completes=completes if declared is None else declared,
            actual_completes=completes,
        )
        for index in range(count)
    ]


def poll(day, name="NZNP 500", needed=2):
    return PollDay(day=day, poll=name, pl_staff_confirmed=needed)


class TestBusinessWeekStart(unittest.TestCase):
    """The week runs Sunday to Thursday, so it straddles two ISO weeks —
    counting by ISO week would split Sunday off from the rest of the roster."""

    def test_sunday_starts_its_own_week(self):
        self.assertEqual(business_week_start(SUNDAY), SUNDAY)

    def test_the_following_thursday_is_the_same_business_week(self):
        self.assertEqual(business_week_start(date(2026, 9, 17)), SUNDAY)

    def test_the_saturday_before_is_the_previous_week(self):
        self.assertEqual(business_week_start(date(2026, 9, 12)), date(2026, 9, 6))


class TestBuildRoster(unittest.TestCase):
    def plan(self, records, polls, **kwargs):
        people = score_all(records, TODAY, Thresholds())
        options = dict(
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
            max_shifts_per_week=5,
        )
        options.update(kwargs)
        return build_roster(polls, people, **options)

    def test_fills_a_shift_to_the_number_the_schedule_asks_for(self):
        records = sum((audits_for(f"Caller {i}") for i in range(5)), [])
        plan = self.plan(records, [poll(SUNDAY, needed=3)])
        self.assertEqual(plan.total_filled, 3)
        self.assertEqual(plan.total_shortfall, 0)

    def test_the_best_callers_go_first(self):
        records = audits_for("Slow Caller", completes=2) + audits_for("Fast Caller", completes=9)
        plan = self.plan(records, [poll(SUNDAY, needed=1)])
        self.assertEqual(plan.shifts[0].assigned[0].name, "Fast Caller")

    def test_productivity_cannot_be_bought_by_over_declaring(self):
        """Declaring more must not promote you above an honest producer."""
        records = audits_for("Honest", completes=8) + audits_for(
            "Inflater", completes=4, declared=20
        )
        plan = self.plan(records, [poll(SUNDAY, needed=1)])
        self.assertEqual(plan.shifts[0].assigned[0].name, "Honest")

    def test_barred_callers_are_never_rostered(self):
        records = audits_for("Good", completes=3) + audits_for(
            "Barred", count=4, completes=9, declared=20
        )
        plan = self.plan(records, [poll(SUNDAY, needed=2)])
        names = [a.name for a in plan.shifts[0].assigned]
        self.assertIn("Good", names)
        self.assertNotIn("Barred", names)
        self.assertIn("Barred", [p.name for p in plan.excluded])

    def test_a_barred_caller_can_be_cleared_by_hand(self):
        # Brendon overrules the audit gate — someone explained a bad audit, or
        # he judges the failure not worth losing them over. It is his call.
        records = audits_for("Good", completes=3) + audits_for(
            "Barred", count=4, completes=9, declared=20
        )
        people = score_all(records, TODAY, Thresholds())
        key = next(k for k, p in people.items() if p.name == "Barred")
        plan = self.plan(records, [poll(SUNDAY, needed=2)], cleared={key})
        self.assertIn("Barred", [a.name for a in plan.shifts[0].assigned])

    def test_a_cleared_caller_is_named_rather_than_quietly_included(self):
        # The override has to leave a trace. Folding them silently into the
        # roster is how the reason for the barring gets lost.
        records = audits_for("Good", completes=3) + audits_for(
            "Barred", count=4, completes=9, declared=20
        )
        people = score_all(records, TODAY, Thresholds())
        key = next(k for k, p in people.items() if p.name == "Barred")
        plan = self.plan(records, [poll(SUNDAY, needed=2)], cleared={key})
        self.assertEqual([p.name for p in plan.manually_cleared], ["Barred"])
        self.assertNotIn("Barred", [p.name for p in plan.excluded])

    def test_clearing_one_person_does_not_clear_the_rest(self):
        records = (
            audits_for("Good", completes=3)
            + audits_for("Barred A", count=4, completes=9, declared=20)
            + audits_for("Barred B", count=4, completes=9, declared=20)
        )
        people = score_all(records, TODAY, Thresholds())
        key = next(k for k, p in people.items() if p.name == "Barred A")
        plan = self.plan(records, [poll(SUNDAY, needed=3)], cleared={key})
        names = [a.name for a in plan.shifts[0].assigned]
        self.assertIn("Barred A", names)
        self.assertNotIn("Barred B", names)
        self.assertEqual([p.name for p in plan.excluded], ["Barred B"])

    def test_a_cleared_caller_is_actually_placed_on_a_shift(self):
        # Entering the pool is not enough. A barred caller sorts below every
        # other tier, so without lifting the ranking tier the clearance is
        # hollow — they show as cleared and never get a shift.
        records = (
            sum((audits_for(f"Filler {i}", completes=6) for i in range(3)), [])
            + audits_for("Barred", count=4, completes=9, declared=20)
        )
        people = score_all(records, TODAY, Thresholds())
        key = next(k for k, p in people.items() if p.name == "Barred")
        plan = self.plan(records, [poll(SUNDAY, needed=4)], cleared={key})
        self.assertIn("Barred", [a.name for a in plan.shifts[0].assigned])

    def test_clearing_does_not_promote_someone_above_a_trusted_caller(self):
        # Cleared means "eligible again", not "top of the list". A trusted
        # caller still outranks them.
        records = audits_for("Trusted", completes=9) + audits_for(
            "Barred", count=4, completes=9, declared=20
        )
        people = score_all(records, TODAY, Thresholds())
        key = next(k for k, p in people.items() if p.name == "Barred")
        plan = self.plan(records, [poll(SUNDAY, needed=1)], cleared={key})
        self.assertEqual([a.name for a in plan.shifts[0].assigned], ["Trusted"])

    def test_clearing_nobody_leaves_the_gate_exactly_as_it_was(self):
        records = audits_for("Good", completes=3) + audits_for(
            "Barred", count=4, completes=9, declared=20
        )
        plan = self.plan(records, [poll(SUNDAY, needed=2)], cleared=set())
        self.assertNotIn("Barred", [a.name for a in plan.shifts[0].assigned])
        self.assertEqual(plan.manually_cleared, [])

    def test_callers_not_audited_recently_are_treated_as_gone(self):
        records = audits_for("Current") + audits_for("Departed", day=TODAY - timedelta(days=200))
        plan = self.plan(records, [poll(SUNDAY, needed=5)], active_within_days=45)
        self.assertEqual([a.name for a in plan.shifts[0].assigned], ["Current"])

    def test_nobody_works_two_polls_on_the_same_day(self):
        records = sum((audits_for(f"Caller {i}") for i in range(4)), [])
        plan = self.plan(
            records,
            [poll(SUNDAY, "Poll A", needed=2), poll(SUNDAY, "Poll B", needed=2)],
        )
        first = {a.name for a in plan.shifts[0].assigned}
        second = {a.name for a in plan.shifts[1].assigned}
        self.assertEqual(first & second, set())

    def test_the_weekly_cap_is_respected_across_the_sunday_boundary(self):
        records = sum((audits_for(f"Caller {i}") for i in range(3)), [])
        days = [SUNDAY + timedelta(days=offset) for offset in range(5)]
        plan = self.plan(
            records, [poll(day, needed=1) for day in days], max_shifts_per_week=2
        )
        self.assertTrue(all(count <= 2 for count in plan.shifts_per_person().values()))

    def test_a_short_pool_leaves_the_shift_short_rather_than_inventing_people(self):
        plan = self.plan(audits_for("Only One"), [poll(SUNDAY, needed=4)])
        self.assertEqual(plan.total_filled, 1)
        self.assertEqual(plan.total_shortfall, 3)

    def test_polls_outside_the_working_week_are_flagged_not_rostered(self):
        friday = date(2026, 9, 18)
        records = sum((audits_for(f"Caller {i}") for i in range(3)), [])
        plan = self.plan(records, [poll(friday, needed=2)], end=friday)
        self.assertEqual(plan.shifts, [])
        self.assertEqual(plan.skipped_non_working_days, [friday])

    def test_polls_outside_the_date_range_are_ignored(self):
        records = sum((audits_for(f"Caller {i}") for i in range(3)), [])
        plan = self.plan(records, [poll(date(2026, 9, 21), needed=2)])
        self.assertEqual(plan.shifts, [])

    def test_unused_callers_land_on_the_bench(self):
        records = sum((audits_for(f"Caller {i}") for i in range(5)), [])
        plan = self.plan(records, [poll(SUNDAY, needed=2)])
        self.assertEqual(len(plan.bench), 3)


class TestDuplicateNamesInScheduling(unittest.TestCase):
    """Scoring keeps name variants apart on purpose. Scheduling must not:
    one human can only be in one place, and rostering two spellings of them
    onto the same day sends that shift out a caller short."""

    def plan_with(self, records, polls, **kwargs):
        people = score_all(records, TODAY, Thresholds())
        return build_roster(
            polls,
            people,
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
            **kwargs,
        )

    def test_variants_are_grouped_for_scheduling(self):
        people = score_all(
            audits_for("Loraine Sabroso") + audits_for("Lorraine Sabroso"), TODAY, Thresholds()
        )
        groups = group_duplicates(people)
        self.assertEqual(len({groups["loraine sabroso"], groups["lorraine sabroso"]}), 1)

    def test_two_spellings_are_not_both_rostered_on_one_day(self):
        records = audits_for("Loraine Sabroso") + audits_for("Lorraine Sabroso")
        plan = self.plan_with(records, [poll(SUNDAY, needed=2)])
        self.assertEqual(plan.shifts[0].filled, 1)
        self.assertTrue(plan.duplicate_conflicts)

    def test_the_conflict_names_both_spellings_so_it_can_be_fixed(self):
        records = audits_for("Mary Villacura") + audits_for("Mary Joy Villacura")
        plan = self.plan_with(
            records, [poll(SUNDAY, "Poll A", needed=1), poll(SUNDAY, "Poll B", needed=1)]
        )
        _, kept, blocked = plan.duplicate_conflicts[0]
        self.assertEqual({kept, blocked}, {"Mary Villacura", "Mary Joy Villacura"})

    def test_variants_share_one_weekly_cap(self):
        records = audits_for("Loraine Sabroso") + audits_for("Lorraine Sabroso")
        days = [SUNDAY + timedelta(days=offset) for offset in range(4)]
        plan = self.plan_with(
            records, [poll(day, needed=1) for day in days], max_shifts_per_week=2
        )
        self.assertEqual(plan.total_filled, 2)

    def test_genuinely_different_people_are_both_rostered(self):
        records = audits_for("Ana Reyes") + audits_for("Ben Cruz")
        plan = self.plan_with(records, [poll(SUNDAY, needed=2)])
        self.assertEqual(plan.shifts[0].filled, 2)
        self.assertEqual(plan.duplicate_conflicts, [])


if __name__ == "__main__":
    unittest.main()


class TestRosteringFromAPoll(unittest.TestCase):
    """With a poll, the pool for a day is the people who said they can work
    it — not everyone on the books."""

    def setUp(self):
        self.records = (
            audits_for("Ana Reyes", completes=9)
            + audits_for("Ben Cruz", completes=7)
            + audits_for("Cara Lim", completes=5)
            + audits_for("Dan Silva", completes=3)
        )
        self.people = score_all(self.records, TODAY, Thresholds())
        self.known = {p.key: p.name for p in self.people.values()}

    def plan(self, poll_text, polls, **kwargs):
        availability = parse_availability(poll_text, self.known, TODAY)
        return build_roster(
            polls,
            self.people,
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
            availability=availability,
            **kwargs,
        )

    def test_only_volunteers_are_rostered(self):
        plan = self.plan(
            "Sunday 13 Sep\nCara Lim\nDan Silva", [poll(SUNDAY, needed=2)]
        )
        self.assertEqual(
            {a.name for a in plan.shifts[0].assigned}, {"Cara Lim", "Dan Silva"}
        )

    def test_the_best_of_the_volunteers_is_picked_not_the_best_overall(self):
        plan = self.plan("Sunday 13 Sep\nCara Lim\nDan Silva", [poll(SUNDAY, needed=1)])
        self.assertEqual(plan.shifts[0].assigned[0].name, "Cara Lim")
        self.assertNotIn("Ana Reyes", [a.name for a in plan.shifts[0].assigned])

    def test_volunteers_who_missed_out_are_listed(self):
        plan = self.plan(
            "Sunday 13 Sep\nAna Reyes\nBen Cruz\nCara Lim", [poll(SUNDAY, needed=1)]
        )
        self.assertEqual(
            [p.name for p in plan.shifts[0].passed_over], ["Ben Cruz", "Cara Lim"]
        )

    def test_the_volunteer_count_is_recorded(self):
        plan = self.plan("Sunday 13 Sep\nAna Reyes\nBen Cruz", [poll(SUNDAY, needed=1)])
        self.assertEqual(plan.shifts[0].volunteers, 2)
        self.assertTrue(plan.shifts[0].from_poll)

    def test_too_few_volunteers_leaves_the_shift_short(self):
        plan = self.plan("Sunday 13 Sep\nAna Reyes", [poll(SUNDAY, needed=4)])
        self.assertEqual(plan.shifts[0].filled, 1)
        self.assertEqual(plan.shifts[0].shortfall, 3)

    def test_a_day_the_poll_did_not_cover_falls_back_and_is_flagged(self):
        """Silently treating an uncovered day as "nobody available" would
        empty a shift that simply was not polled."""
        plan = self.plan(
            "Sunday 13 Sep\nAna Reyes",
            [poll(SUNDAY, needed=1), poll(date(2026, 9, 14), needed=2)],
        )
        self.assertEqual(plan.shifts[1].filled, 2)
        self.assertEqual(plan.days_without_a_poll, [date(2026, 9, 14)])

    def test_a_polled_day_with_no_votes_stays_empty(self):
        plan = self.plan(
            "Sunday 13 Sep\n\nMonday 14 Sep\nAna Reyes",
            [poll(SUNDAY, needed=2), poll(date(2026, 9, 14), needed=1)],
        )
        self.assertEqual(plan.shifts[0].filled, 0)
        self.assertEqual(plan.shifts[0].shortfall, 2)

    def test_a_barred_volunteer_is_named_rather_than_silently_skipped(self):
        records = self.records + audits_for("Liar Jones", count=4, completes=2, declared=9)
        people = score_all(records, TODAY, Thresholds())
        known = {p.key: p.name for p in people.values()}
        availability = parse_availability(
            "Sunday 13 Sep\nLiar Jones\nAna Reyes", known, TODAY
        )
        plan = build_roster(
            [poll(SUNDAY, needed=2)],
            people,
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
            availability=availability,
        )
        self.assertNotIn("Liar Jones", [a.name for a in plan.shifts[0].assigned])
        self.assertIn("Liar Jones", [p.name for _, p in plan.volunteered_but_barred])

    def test_unknown_poll_names_reach_the_plan(self):
        plan = self.plan(
            "Sunday 13 Sep\nAna Reyes\nSomebody Unknown", [poll(SUNDAY, needed=1)]
        )
        self.assertEqual(plan.unmatched_names, [(SUNDAY, "Somebody Unknown")])

    def test_weekly_caps_still_apply_to_volunteers(self):
        days = [SUNDAY + timedelta(days=offset) for offset in range(4)]
        text = "\n".join(f"{d:%d %b}\nAna Reyes\nBen Cruz" for d in days)
        plan = self.plan(text, [poll(d, needed=1) for d in days], max_shifts_per_week=2)
        self.assertTrue(all(c <= 2 for c in plan.shifts_per_person().values()))

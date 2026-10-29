import unittest
from datetime import date, datetime

from business_agent.config import Config
from business_agent.models import Demand, Event, Message, Person, Shift
from business_agent.roster import (
    apply_events,
    build_gaps,
    declines_by_person,
    rank_candidates,
    week_key,
)

MON = date(2024, 3, 11)
TUE = date(2024, 3, 12)


def person(person_id, **kwargs):
    defaults = dict(name=person_id.title(), skills=frozenset({"calls"}))
    defaults.update(kwargs)
    return Person(person_id=person_id, **defaults)


TEAM = {
    "sarah": person("sarah", reliability=0.95, preferred_shifts=frozenset({"morning"})),
    "dan": person("dan", reliability=0.80, max_shifts_per_week=2),
    "priya": person("priya", reliability=0.90),
    "mei": person("mei", skills=frozenset({"onboarding"})),
    "tom": person("tom", unavailable=frozenset({TUE})),
}


def message(text="", sender="someone"):
    return Message(sent_at=datetime(2024, 3, 11, 9, 0), sender=sender, text=text)


class TestDemand(unittest.TestCase):
    def test_calls_round_up_to_whole_people(self):
        self.assertEqual(Demand(MON, "morning", calls_required=21).staff_needed(10), 3)

    def test_exact_multiple(self):
        self.assertEqual(Demand(MON, "morning", calls_required=20).staff_needed(10), 2)

    def test_explicit_staff_count_wins(self):
        demand = Demand(MON, "morning", calls_required=100, staff_required=2)
        self.assertEqual(demand.staff_needed(10), 2)

    def test_rejects_zero_capacity(self):
        with self.assertRaises(ValueError):
            Demand(MON, "morning", calls_required=10).staff_needed(0)


class TestWeekKey(unittest.TestCase):
    def test_same_week_across_days(self):
        self.assertEqual(week_key(MON), week_key(date(2024, 3, 15)))

    def test_different_week(self):
        self.assertNotEqual(week_key(MON), week_key(date(2024, 3, 18)))


class TestApplyEvents(unittest.TestCase):
    def test_dropout_marks_the_shift_dropped(self):
        shifts = [Shift(TUE, "morning", "sarah")]
        event = Event(kind="dropout", message=message(), person_id="sarah", day=TUE, confidence=0.9)
        updated, _, unresolved = apply_events(shifts, [], [event])
        self.assertEqual(updated[0].status, "dropped")
        self.assertEqual(unresolved, [])

    def test_dropout_without_a_date_is_escalated_not_guessed(self):
        shifts = [Shift(TUE, "morning", "sarah")]
        event = Event(kind="dropout", message=message(), person_id="sarah", confidence=0.9)
        updated, _, unresolved = apply_events(shifts, [], [event])
        self.assertEqual(updated[0].status, "confirmed")
        self.assertEqual(len(unresolved), 1)

    def test_low_confidence_event_is_escalated_not_applied(self):
        shifts = [Shift(TUE, "morning", "sarah")]
        event = Event(kind="dropout", message=message(), person_id="sarah", day=TUE, confidence=0.3)
        updated, _, unresolved = apply_events(shifts, [], [event])
        self.assertEqual(updated[0].status, "confirmed")
        self.assertEqual(len(unresolved), 1)

    def test_dropout_for_a_shift_they_were_never_on_is_escalated(self):
        shifts = [Shift(MON, "morning", "sarah")]
        event = Event(kind="dropout", message=message(), person_id="sarah", day=TUE, confidence=0.9)
        _, _, unresolved = apply_events(shifts, [], [event])
        self.assertEqual(len(unresolved), 1)

    def test_client_request_increases_demand(self):
        demand = [Demand(TUE, "morning", calls_required=20)]
        event = Event(kind="client_request", message=message(), day=TUE, calls=20, confidence=0.8)
        _, updated, _ = apply_events([], demand, [event])
        self.assertEqual(updated[0].calls_required, 40)

    def test_noise_is_ignored_entirely(self):
        _, _, unresolved = apply_events([], [], [Event(kind="noise", message=message())])
        self.assertEqual(unresolved, [])


class TestRankCandidates(unittest.TestCase):
    def rank(self, shifts, offers=None, skills=frozenset({"calls"}), declines=None):
        return {
            c.person.person_id: c
            for c in rank_candidates(
                TUE, "morning", TEAM, shifts, offers or {}, skills, declines
            )
        }

    def test_person_who_dropped_this_day_is_never_asked(self):
        shifts = [Shift(TUE, "morning", "sarah", status="dropped")]
        candidate = self.rank(shifts)["sarah"]
        self.assertFalse(candidate.eligible)
        self.assertIn("dropped out of this day", candidate.blockers)

    def test_already_rostered_that_day_is_blocked(self):
        shifts = [Shift(TUE, "afternoon", "priya")]
        self.assertFalse(self.rank(shifts)["priya"].eligible)

    def test_missing_skill_is_blocked(self):
        candidate = self.rank([])["mei"]
        self.assertFalse(candidate.eligible)
        self.assertIn("missing skill(s): calls", candidate.blockers)

    def test_marked_unavailable_is_blocked(self):
        self.assertFalse(self.rank([])["tom"].eligible)

    def test_weekly_cap_is_blocked(self):
        shifts = [Shift(MON, "morning", "dan"), Shift(date(2024, 3, 13), "morning", "dan")]
        candidate = self.rank(shifts)["dan"]
        self.assertFalse(candidate.eligible)
        self.assertIn("at weekly cap (2/2)", candidate.blockers)

    def test_an_offer_outranks_raw_reliability(self):
        offers = {("dan", TUE): Event(kind="offer", message=message(), person_id="dan", day=TUE)}
        ranked = self.rank([], offers=offers)
        self.assertGreater(ranked["dan"].score, ranked["sarah"].score)

    def test_a_dropout_message_blocks_them_even_with_no_roster_row(self):
        """The roster lives in WhatsApp, so a message is the only record."""
        declines = {
            ("dan", TUE): Event(
                kind="dropout", message=message("can't make Tuesday"), person_id="dan", day=TUE
            )
        }
        candidate = self.rank([], declines=declines)["dan"]
        self.assertFalse(candidate.eligible)
        self.assertTrue(any("said they can't work" in b for b in candidate.blockers))

    def test_a_dropout_on_another_day_does_not_block_them(self):
        declines = {
            ("dan", MON): Event(
                kind="dropout", message=message("can't make Monday"), person_id="dan", day=MON
            )
        }
        self.assertTrue(self.rank([], declines=declines)["dan"].eligible)

    def test_eligible_people_sort_above_blocked_ones(self):
        ordered = rank_candidates(TUE, "morning", TEAM, [], {}, frozenset({"calls"}))
        first_blocked = next(i for i, c in enumerate(ordered) if not c.eligible)
        self.assertTrue(all(c.eligible for c in ordered[:first_blocked]))
        self.assertTrue(all(not c.eligible for c in ordered[first_blocked:]))


class TestBuildGaps(unittest.TestCase):
    def setUp(self):
        self.config = Config(calls_per_person=10, horizon_days=14)

    def test_no_gap_when_fully_covered(self):
        gaps = build_gaps(
            TEAM,
            [Shift(TUE, "morning", "sarah"), Shift(TUE, "morning", "priya")],
            [Demand(TUE, "morning", calls_required=20)],
            [],
            self.config,
            MON,
        )
        self.assertEqual(gaps, [])

    def test_dropped_shift_creates_a_gap(self):
        gaps = build_gaps(
            TEAM,
            [Shift(TUE, "morning", "sarah"), Shift(TUE, "morning", "priya", status="dropped")],
            [Demand(TUE, "morning", calls_required=20)],
            [],
            self.config,
            MON,
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].short_by, 1)
        self.assertEqual([s.person_id for s in gaps[0].dropouts], ["priya"])

    def test_demand_beyond_the_horizon_is_ignored(self):
        far = date(2024, 4, 1)  # horizon_days=14 from Mon 11 Mar ends 25 Mar
        gaps = build_gaps(TEAM, [], [Demand(far, "morning", calls_required=20)], [], self.config, MON)
        self.assertEqual(gaps, [])

    def test_past_demand_is_ignored(self):
        past = date(2024, 3, 1)
        gaps = build_gaps(TEAM, [], [Demand(past, "morning", calls_required=20)], [], self.config, MON)
        self.assertEqual(gaps, [])


if __name__ == "__main__":
    unittest.main()


class TestDeclinesByPerson(unittest.TestCase):
    def test_indexes_dropouts_by_person_and_day(self):
        event = Event(kind="dropout", message=message(), person_id="dan", day=TUE)
        self.assertEqual(declines_by_person([event]), {("dan", TUE): event})

    def test_ignores_dropouts_missing_a_person_or_a_date(self):
        vague = Event(kind="dropout", message=message(), person_id="dan")
        anon = Event(kind="dropout", message=message(), day=TUE)
        self.assertEqual(declines_by_person([vague, anon]), {})

    def test_ignores_offers(self):
        offer = Event(kind="offer", message=message(), person_id="dan", day=TUE)
        self.assertEqual(declines_by_person([offer]), {})

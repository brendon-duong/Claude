"""Tests for turning audit history into a rostering decision.

These encode the business rules as stated: no more than five minutes off the
phone at a stretch, fifteen or twenty minutes tolerated now and then, an hour
not acceptable; and declaring more completes than the call logs show is the
most serious signal there is.
"""

import unittest
from datetime import date, timedelta

from business_agent.audit import AuditRecord, Break
from business_agent.performance import (
    Thresholds,
    _one_edit_apart,
    audit_penalty,
    find_possible_duplicates,
    score_all,
    score_person,
    time_verdict,
)

TODAY = date(2026, 4, 1)
T = Thresholds()


def record(day=TODAY, name="Ana Reyes", declared=5, actual=5, breaks=(), **kwargs):
    return AuditRecord(
        day=day,
        name=name,
        declared_completes=declared,
        actual_completes=actual,
        breaks=[Break(minutes=m, window="x", declared=d) for m, d in breaks],
        **kwargs,
    )


class TestTimeVerdict(unittest.TestCase):
    def test_no_breaks_is_clean(self):
        self.assertEqual(time_verdict(record(), T), "clean")

    def test_five_minutes_is_within_the_ask(self):
        self.assertEqual(time_verdict(record(breaks=[(5, False)]), T), "clean")

    def test_six_minutes_is_over_the_ask_but_minor(self):
        self.assertEqual(time_verdict(record(breaks=[(6, False)]), T), "minor")

    def test_fifteen_to_twenty_minutes_is_tolerated(self):
        self.assertEqual(time_verdict(record(breaks=[(20, False)]), T), "minor")

    def test_more_than_twenty_at_a_stretch_is_serious(self):
        self.assertEqual(time_verdict(record(breaks=[(25, False)]), T), "serious")

    def test_lots_of_small_breaks_add_up_to_serious(self):
        breaks = [(8, False)] * 4  # 32 minutes total, none individually serious
        self.assertEqual(time_verdict(record(breaks=breaks), T), "serious")

    def test_an_hour_off_the_phone_is_severe(self):
        self.assertEqual(time_verdict(record(breaks=[(60, False)]), T), "severe")

    def test_declared_breaks_do_not_count_against_anyone(self):
        self.assertEqual(time_verdict(record(breaks=[(60, True)]), T), "clean")


class TestAuditPenalty(unittest.TestCase):
    def test_a_clean_audit_costs_nothing(self):
        penalty, notes = audit_penalty(record(), T)
        self.assertEqual(penalty, 0.0)
        self.assertEqual(notes, [])

    def test_over_declaring_costs_more_the_bigger_the_gap(self):
        small, _ = audit_penalty(record(declared=6, actual=5), T)
        large, _ = audit_penalty(record(declared=8, actual=4), T)
        self.assertGreater(large, small)

    def test_under_declaring_is_not_penalised(self):
        penalty, _ = audit_penalty(record(declared=6, actual=7), T)
        self.assertEqual(penalty, 0.0)

    def test_missing_call_logs_is_an_integrity_failure(self):
        penalty, notes = audit_penalty(record(no_call_logs=True), T)
        self.assertGreaterEqual(penalty, T.integrity_penalty)
        self.assertTrue(any("no call logs" in n for n in notes))

    def test_integrity_outweighs_time_off_the_phone(self):
        dishonest, _ = audit_penalty(record(declared=6, actual=5), T)
        absent, _ = audit_penalty(record(breaks=[(60, False)]), T)
        self.assertGreater(dishonest, absent)


class TestScorePerson(unittest.TestCase):
    def test_never_audited_is_not_penalised(self):
        performance = score_person([], TODAY, T)
        self.assertEqual(performance.score, 1.0)
        self.assertEqual(performance.tier, "trusted")
        self.assertEqual(performance.audits, 0)

    def test_all_clean_audits_score_one(self):
        performance = score_person([record(), record()], TODAY, T)
        self.assertEqual(performance.score, 1.0)
        self.assertEqual(performance.tier, "trusted")

    def test_being_audited_more_does_not_lower_a_clean_score(self):
        few = score_person([record()], TODAY, T)
        many = score_person([record() for _ in range(8)], TODAY, T)
        self.assertEqual(few.score, many.score)

    def test_two_integrity_failures_bar_someone_from_the_roster(self):
        performance = score_person(
            [record(declared=6, actual=5), record(declared=4, actual=3)], TODAY, T
        )
        self.assertEqual(performance.tier, "do_not_roster")
        self.assertFalse(performance.rosterable)

    def test_small_repeated_over_declarations_are_caught_despite_a_high_score(self):
        """Averaging hides a pattern of one-complete lies; the tier must not."""
        audits = [record() for _ in range(6)] + [
            record(declared=6, actual=5),
            record(declared=6, actual=5),
        ]
        performance = score_person(audits, TODAY, T)
        self.assertGreater(performance.score, T.do_not_roster_score)
        self.assertEqual(performance.tier, "do_not_roster")

    def test_one_bad_audit_is_a_conversation_not_a_ban(self):
        performance = score_person([record(declared=3, actual=2, breaks=[(38, False)])], TODAY, T)
        self.assertLess(performance.score, T.do_not_roster_score)
        self.assertEqual(performance.tier, "watch")

    def test_a_single_unacceptable_shift_is_never_averaged_away(self):
        audits = [record() for _ in range(5)] + [record(breaks=[(104, False)])]
        performance = score_person(audits, TODAY, T)
        self.assertGreater(performance.score, T.trusted_score)
        self.assertEqual(performance.tier, "watch")
        self.assertEqual(performance.severe_events, 1)

    def test_two_unacceptable_shifts_bar_someone(self):
        audits = [record(breaks=[(70, False)]), record(breaks=[(80, False)])]
        self.assertEqual(score_person(audits, TODAY, T).tier, "do_not_roster")

    def test_recent_audits_weigh_more_than_old_ones(self):
        old = record(day=TODAY - timedelta(days=300), declared=6, actual=5)
        recent = record(day=TODAY, declared=6, actual=5)
        long_ago = score_person([old, record()], TODAY, T)
        just_now = score_person([recent, record()], TODAY, T)
        self.assertGreater(long_ago.score, just_now.score)

    def test_audits_beyond_the_lookback_are_ignored(self):
        stale = record(day=TODAY - timedelta(days=T.lookback_days + 30), declared=9, actual=1)
        performance = score_person([stale], TODAY, T)
        self.assertEqual(performance.audits, 0)
        self.assertEqual(performance.tier, "trusted")

    def test_future_dated_rows_are_ignored(self):
        ahead = record(day=TODAY + timedelta(days=5), declared=9, actual=1)
        self.assertEqual(score_person([ahead], TODAY, T).audits, 0)

    def test_concerns_explain_the_verdict(self):
        performance = score_person([record(declared=8, actual=4)], TODAY, T)
        self.assertTrue(any("declared 8" in c for c in performance.concerns))


class TestScoreAll(unittest.TestCase):
    def test_groups_name_variants_into_one_person(self):
        people = score_all(
            [record(name="Eve Santos"), record(name="Eve  Santos")], TODAY, T
        )
        self.assertEqual(list(people), ["eve santos"])
        self.assertEqual(people["eve santos"].audits, 2)

    def test_scores_each_person_separately(self):
        people = score_all(
            [record(name="Ana Reyes"), record(name="Cara Lim", declared=6, actual=5)],
            TODAY,
            T,
        )
        self.assertEqual(people["ana reyes"].tier, "trusted")
        self.assertEqual(people["cara lim"].tier, "watch")


if __name__ == "__main__":
    unittest.main()


class TestFindPossibleDuplicates(unittest.TestCase):
    """Name variants split one person's history in two, which flatters the
    half without the failures. These are reported, never merged: wrongly
    merging two real people would pin one person's dishonesty on another."""

    def build(self, *names):
        return score_all([record(name=n) for n in names], TODAY, T)

    def pairs(self, *names):
        return {(a, b) for a, b, _ in find_possible_duplicates(self.build(*names))}

    def test_a_middle_name_added(self):
        self.assertIn(
            ("Jane Wary Espanueva", "Jane Wary Rose Espanueva"),
            self.pairs("Jane Wary Espanueva", "Jane Wary Rose Espanueva"),
        )

    def test_given_name_typo_with_the_same_surname(self):
        self.assertIn(
            ("Kingsly Cajilig", "Kingsy Cajilig"),
            self.pairs("Kingsly Cajilig", "Kingsy Cajilig"),
        )

    def test_transposed_letters_in_a_surname(self):
        self.assertIn(
            ("Cherry Jean Raagas", "Cherry Jean Ragaas"),
            self.pairs("Cherry Jean Raagas", "Cherry Jean Ragaas"),
        )

    def test_case_and_spacing_are_already_one_person(self):
        people = self.build("Elaine Abugan", "ELAINE  ABUGAN")
        self.assertEqual(len(people), 1)

    def test_genuinely_different_people_are_left_alone(self):
        self.assertEqual(self.pairs("Ana Reyes", "Ben Cruz", "Cara Lim"), set())

    def test_siblings_sharing_a_surname_are_not_merged(self):
        self.assertEqual(self.pairs("Karen Boiser", "Erika Jane Boiser"), set())

    def test_unaudited_people_are_not_reported(self):
        self.assertEqual(find_possible_duplicates({}), [])


class TestOneEditApart(unittest.TestCase):
    def test_substitution(self):
        self.assertTrue(_one_edit_apart("leizel", "liezel"))

    def test_deletion(self):
        self.assertTrue(_one_edit_apart("kingsly", "kingsy"))

    def test_transposition(self):
        self.assertTrue(_one_edit_apart("raagas", "ragaas"))

    def test_identical_words_are_not_an_edit(self):
        self.assertFalse(_one_edit_apart("reyes", "reyes"))

    def test_two_edits_is_too_far(self):
        self.assertFalse(_one_edit_apart("reyes", "royas"))

    def test_very_different_lengths(self):
        self.assertFalse(_one_edit_apart("ana", "anabelle"))

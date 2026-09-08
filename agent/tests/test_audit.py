"""Tests for reading the Audit - PL sheet.

The fixture reproduces the real sheet's quirks — wrapped header text, date
section rows, multi-line free-text details, declared breaks, missing call logs
— using invented names, so no client data lives in the repository.
"""

import unittest
from datetime import date
from pathlib import Path

from business_agent.audit import (
    load_audits,
    normalise_name,
    parse_breaks,
    parse_reviewer_flag,
    parse_section_date,
)
from business_agent.sheets import _read_csv

FIXTURE = Path(__file__).parent / "fixtures" / "audit_pl_sample.csv"


class TestNormaliseName(unittest.TestCase):
    def test_collapses_doubled_spaces(self):
        self.assertEqual(normalise_name("Eve  Santos"), normalise_name("Eve Santos"))

    def test_is_case_insensitive_and_trims(self):
        self.assertEqual(normalise_name("  ANA reyes "), "ana reyes")


class TestParseSectionDate(unittest.TestCase):
    def test_long_month_form(self):
        self.assertEqual(parse_section_date("March 9, 2026"), date(2026, 3, 9))

    def test_a_person_name_is_not_a_date(self):
        self.assertIsNone(parse_section_date("Ana Reyes"))

    def test_blank(self):
        self.assertIsNone(parse_section_date(""))


class TestParseReviewerFlag(unittest.TestCase):
    def test_y_and_n(self):
        self.assertIs(parse_reviewer_flag("Y"), True)
        self.assertIs(parse_reviewer_flag("n"), False)

    def test_blank_is_unknown_not_false(self):
        self.assertIsNone(parse_reviewer_flag(""))


class TestParseBreaks(unittest.TestCase):
    def test_single_break(self):
        (brk,) = parse_breaks("5 mins off the phone between 5:37 - 5:42")
        self.assertEqual(brk.minutes, 5)
        self.assertEqual(brk.window, "5:37 - 5:42")
        self.assertFalse(brk.declared)

    def test_shorthand_second_break_without_off_the_phone(self):
        breaks = parse_breaks(
            "10 mins off the phone between 5:50 - 6:00\n5 mins between 6:12 - 6:17"
        )
        self.assertEqual([b.minutes for b in breaks], [10, 5])

    def test_declared_break_is_marked_excused(self):
        (brk,) = parse_breaks(
            "9 mins off the phone between 18:18:26 - 18:27:39 (Declared Break)"
        )
        self.assertTrue(brk.declared)

    def test_one_declared_break_does_not_excuse_the_others(self):
        breaks = parse_breaks(
            "9 mins off the phone between 18:18:26 - 18:27:39 (Declared Break)\n"
            "22 mins off the phone between 19:00:00 - 19:22:00"
        )
        self.assertEqual([b.declared for b in breaks], [True, False])

    def test_a_long_call_is_not_a_break(self):
        """"after a 15 mins call" describes the call, not time away."""
        breaks = parse_breaks(
            "12 mins off the phone between 17:46:20 - 18:14:10 after a 15 mins call"
        )
        self.assertEqual([b.minutes for b in breaks], [12])

    def test_no_breaks_in_a_dash(self):
        self.assertEqual(parse_breaks("-"), [])


class TestLoadAudits(unittest.TestCase):
    def setUp(self):
        self.records = load_audits(_read_csv(FIXTURE))
        self.by_key = {}
        for record in self.records:
            self.by_key[(record.day, record.person_key)] = record

    def test_reads_every_person_row_and_no_date_rows(self):
        self.assertEqual(len(self.records), 13)
        self.assertNotIn("march 9, 2026", {r.person_key for r in self.records})

    def test_wrapped_header_columns_are_matched(self):
        record = self.by_key[(date(2026, 3, 9), "ana reyes")]
        self.assertEqual(record.declared_completes, 8)
        self.assertEqual(record.actual_completes, 8)

    def test_rows_inherit_the_date_section_above_them(self):
        self.assertEqual(
            sorted({r.day for r in self.records}),
            [date(2026, 3, 9), date(2026, 3, 16), date(2026, 3, 17)],
        )

    def test_name_variants_resolve_to_one_person(self):
        keys = {r.person_key for r in self.records if "santos" in r.person_key}
        self.assertEqual(keys, {"eve santos"})

    # -- integrity ---------------------------------------------------------

    def test_matching_counts_are_truthful(self):
        self.assertTrue(self.by_key[(date(2026, 3, 9), "ana reyes")].truthful)

    def test_more_in_the_logs_than_declared_is_truthful(self):
        record = self.by_key[(date(2026, 3, 9), "ben cruz")]
        self.assertTrue(record.truthful)
        self.assertEqual(record.over_declared, 0)

    def test_fewer_in_the_logs_than_declared_is_not(self):
        record = self.by_key[(date(2026, 3, 9), "cara lim")]
        self.assertFalse(record.truthful)
        self.assertEqual(record.over_declared, 1)

    def test_no_call_logs_is_never_truthful(self):
        record = self.by_key[(date(2026, 3, 17), "finn ocampo")]
        self.assertTrue(record.no_call_logs)
        self.assertFalse(record.truthful)

    # -- time on the phone -------------------------------------------------

    def test_a_break_within_the_five_minute_ask_is_recorded_but_short(self):
        record = self.by_key[(date(2026, 3, 9), "gus tan")]
        self.assertEqual(record.off_phone_minutes, 5)
        self.assertEqual(record.longest_break_minutes, 5)

    def test_off_phone_total_excludes_declared_breaks(self):
        record = self.by_key[(date(2026, 3, 16), "ben cruz")]
        self.assertEqual(record.off_phone_minutes, 0)
        self.assertFalse(record.has_any_finding)

    def test_off_phone_total_and_longest_break(self):
        record = self.by_key[(date(2026, 3, 16), "cara lim")]
        self.assertEqual(record.off_phone_minutes, 95)
        self.assertEqual(record.longest_break_minutes, 60)

    def test_time_discrepancy_is_captured(self):
        record = self.by_key[(date(2026, 3, 16), "eve santos")]
        self.assertEqual(len(record.time_discrepancies), 1)
        self.assertIn("Declared Start Time", record.time_discrepancies[0])

    # -- reviewer cross-check ----------------------------------------------

    def test_reviewer_missing_an_over_declaration_is_flagged(self):
        record = self.by_key[(date(2026, 3, 9), "dev patel")]
        self.assertIs(record.reviewer_flagged, False)
        self.assertTrue(record.over_declared)
        self.assertTrue(record.reviewer_disagrees)

    def test_reviewer_flagging_an_excused_break_is_also_flagged(self):
        record = self.by_key[(date(2026, 3, 16), "ben cruz")]
        self.assertIs(record.reviewer_flagged, True)
        self.assertTrue(record.reviewer_disagrees)

    def test_agreement_is_not_flagged(self):
        self.assertFalse(self.by_key[(date(2026, 3, 9), "ana reyes")].reviewer_disagrees)

    def test_a_blank_reviewer_cell_never_disagrees(self):
        record = self.by_key[(date(2026, 3, 17), "ben cruz")]
        self.assertIsNone(record.reviewer_flagged)
        self.assertFalse(record.reviewer_disagrees)


if __name__ == "__main__":
    unittest.main()

"""Tests for reading WhatsApp poll results into per-day volunteer lists.

The input is pasted by a person in a hurry, so the parser has to cope with
bullets, numbering, vote counts and inconsistent date formats.
"""

import unittest
from datetime import date

from business_agent.availability import (
    from_form_responses,
    match_caller,
    parse_availability,
    parse_heading_date,
)

REFERENCE = date(2026, 9, 8)
KNOWN = {
    "lia villapaz": "Lia Villapaz",
    "kharen ybas": "Kharen Ybas",
    "jane wary rose espanueva": "Jane Wary Rose Espanueva",
    "tristan bustamante": "Tristan Bustamante",
}


class TestParseHeadingDate(unittest.TestCase):
    def test_weekday_and_month_name(self):
        self.assertEqual(parse_heading_date("Sunday 13 Sep", REFERENCE), date(2026, 9, 13))

    def test_without_a_weekday(self):
        self.assertEqual(parse_heading_date("13 September 2026", REFERENCE), date(2026, 9, 13))

    def test_with_a_vote_count_attached(self):
        self.assertEqual(
            parse_heading_date("Monday 14 Sep (12 votes)", REFERENCE), date(2026, 9, 14)
        )

    def test_numeric_day_first(self):
        self.assertEqual(parse_heading_date("13/9", REFERENCE), date(2026, 9, 13))
        self.assertEqual(parse_heading_date("13/09/2026", REFERENCE), date(2026, 9, 13))

    def test_ordinal_suffix(self):
        self.assertEqual(parse_heading_date("Sun 13th Sep", REFERENCE), date(2026, 9, 13))

    def test_a_name_is_not_a_date(self):
        self.assertIsNone(parse_heading_date("Lia Villapaz", REFERENCE))

    def test_an_impossible_date_is_rejected(self):
        self.assertIsNone(parse_heading_date("31 Feb", REFERENCE))

    def test_a_bare_date_far_in_the_past_rolls_to_next_year(self):
        self.assertEqual(
            parse_heading_date("13 Jan", date(2026, 12, 1)), date(2027, 1, 13)
        )


class TestMatchCaller(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(match_caller("Lia Villapaz", KNOWN), "lia villapaz")

    def test_case_and_spacing_do_not_matter(self):
        self.assertEqual(match_caller("  LIA   VILLAPAZ ", KNOWN), "lia villapaz")

    def test_a_shortened_name_matches_the_full_one(self):
        self.assertEqual(
            match_caller("Jane Wary Espanueva", KNOWN), "jane wary rose espanueva"
        )

    def test_a_single_letter_typo_matches(self):
        self.assertEqual(match_caller("Kharen Ybaz", KNOWN), "kharen ybas")

    def test_an_unknown_name_matches_nothing(self):
        self.assertIsNone(match_caller("Brand New Starter", KNOWN))


class TestParseAvailability(unittest.TestCase):
    def parse(self, text):
        return parse_availability(text, KNOWN, REFERENCE)

    def test_names_are_grouped_under_the_day_above_them(self):
        result = self.parse(
            "Sunday 13 Sep\nLia Villapaz\nKharen Ybas\n\nMonday 14 Sep\nTristan Bustamante"
        )
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz", "kharen ybas"})
        self.assertEqual(result.on(date(2026, 9, 14)), {"tristan bustamante"})

    def test_bullets_and_numbering_are_stripped(self):
        result = self.parse("Sunday 13 Sep\n1. Lia Villapaz\n- Kharen Ybas\n• Tristan Bustamante")
        self.assertEqual(len(result.on(date(2026, 9, 13))), 3)

    def test_poll_scaffolding_is_ignored(self):
        result = self.parse(
            "POLL\nWhich days can you work?\nSunday 13 Sep (2 votes)\nLia Villapaz\n2 votes"
        )
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})

    def test_names_before_the_first_day_are_ignored(self):
        result = self.parse("Lia Villapaz\nSunday 13 Sep\nKharen Ybas")
        self.assertEqual(result.on(date(2026, 9, 13)), {"kharen ybas"})

    def test_a_day_with_no_votes_is_recorded_as_empty_not_missing(self):
        """An empty poll option means nobody is available — which is very
        different from the poll not covering that day at all."""
        result = self.parse("Sunday 13 Sep\n\nMonday 14 Sep\nLia Villapaz")
        self.assertEqual(result.on(date(2026, 9, 13)), set())
        self.assertIsNotNone(result.on(date(2026, 9, 13)))

    def test_a_day_the_poll_never_mentioned_is_none(self):
        result = self.parse("Sunday 13 Sep\nLia Villapaz")
        self.assertIsNone(result.on(date(2026, 9, 17)))

    def test_unknown_names_are_reported_not_dropped(self):
        result = self.parse("Sunday 13 Sep\nLia Villapaz\nBrand New Starter")
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})
        self.assertEqual(result.unmatched, [(date(2026, 9, 13), "Brand New Starter")])

    def test_the_same_person_listed_twice_counts_once(self):
        result = self.parse("Sunday 13 Sep\nLia Villapaz\nlia villapaz")
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})

    def test_someone_available_on_several_days(self):
        result = self.parse(
            "Sunday 13 Sep\nLia Villapaz\nMonday 14 Sep\nLia Villapaz\nTuesday 15 Sep\nKharen Ybas"
        )
        self.assertEqual(result.volunteer_count, 2)
        self.assertEqual(len(result.days), 3)

    def test_empty_input(self):
        result = self.parse("")
        self.assertEqual(result.by_day, {})


if __name__ == "__main__":
    unittest.main()


class TestFromFormResponses(unittest.TestCase):
    """Google Form responses. The name is a dropdown, so callers pick
    themselves off a list rather than typing — which is the point."""

    def rows(self, *entries):
        return [
            {
                "timestamp": "09/09/2026 14:02:11",
                "your name": name,
                "which days can you work next week?": days,
            }
            for name, days in entries
        ]

    def parse(self, *entries, **kwargs):
        return from_form_responses(self.rows(*entries), KNOWN, REFERENCE, **kwargs)

    def test_one_response_with_several_days(self):
        result = self.parse(("Lia Villapaz", "Sunday 13 Sep, Monday 14 Sep"))
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})
        self.assertEqual(result.on(date(2026, 9, 14)), {"lia villapaz"})

    def test_several_people_on_one_day(self):
        result = self.parse(
            ("Lia Villapaz", "Sunday 13 Sep"), ("Kharen Ybas", "Sunday 13 Sep")
        )
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz", "kharen ybas"})

    def test_a_resubmission_replaces_the_earlier_answer(self):
        """People change their minds; the last answer is the one they meant."""
        result = self.parse(
            ("Lia Villapaz", "Sunday 13 Sep, Monday 14 Sep"),
            ("Lia Villapaz", "Monday 14 Sep"),
        )
        self.assertEqual(result.on(date(2026, 9, 13)), set())
        self.assertEqual(result.on(date(2026, 9, 14)), {"lia villapaz"})

    def test_semicolon_and_newline_separators_work_too(self):
        result = self.parse(("Lia Villapaz", "Sunday 13 Sep; Monday 14 Sep"))
        self.assertEqual(len(result.days), 2)

    def test_a_day_the_form_offered_that_nobody_ticked_stays_empty(self):
        result = self.parse(
            ("Lia Villapaz", "Monday 14 Sep"),
            offered_days=[date(2026, 9, 13), date(2026, 9, 14)],
        )
        self.assertEqual(result.on(date(2026, 9, 13)), set())

    def test_a_day_the_form_never_asked_about_is_none(self):
        result = self.parse(
            ("Lia Villapaz", "Monday 14 Sep"), offered_days=[date(2026, 9, 14)]
        )
        self.assertIsNone(result.on(date(2026, 9, 17)))

    def test_an_unknown_respondent_is_reported(self):
        result = self.parse(("Brand New Starter", "Sunday 13 Sep"))
        self.assertEqual(result.on(date(2026, 9, 13)), set())
        self.assertEqual(result.unmatched, [(date(2026, 9, 13), "Brand New Starter")])

    def test_blank_names_are_skipped(self):
        result = self.parse(("", "Sunday 13 Sep"), ("Lia Villapaz", "Sunday 13 Sep"))
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})

    def test_someone_who_ticked_nothing_volunteers_for_nothing(self):
        result = self.parse(("Lia Villapaz", ""))
        self.assertEqual(result.by_day, {})

    def test_columns_are_found_by_meaning_not_exact_wording(self):
        rows = [{"timestamp": "x", "full name": "Lia Villapaz", "available shifts": "Sunday 13 Sep"}]
        result = from_form_responses(rows, KNOWN, REFERENCE)
        self.assertEqual(result.on(date(2026, 9, 13)), {"lia villapaz"})

    def test_a_missing_column_fails_loudly(self):
        with self.assertRaises(ValueError):
            from_form_responses([{"timestamp": "x", "notes": "y"}], KNOWN, REFERENCE)

    def test_no_responses_yet_is_not_an_error(self):
        self.assertEqual(from_form_responses([], KNOWN, REFERENCE).by_day, {})

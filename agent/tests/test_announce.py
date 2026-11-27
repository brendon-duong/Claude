"""Building the two WhatsApp messages, and tagging the right numbers."""

from __future__ import annotations

import unittest
from datetime import date

from business_agent.announce import (
    long_date,
    mentioned_numbers,
    ordinal,
    render_availability_request,
    render_roster_announcement,
    render_week_announcements,
)
from business_agent.directory import Directory

GROUP = [
    {"chatId": "639275044990@c.us", "name": "Pernelia Villapaz"},
    {"chatId": "639260813435@c.us", "name": "Kharen"},
    {"chatId": "639497821558@c.us", "name": "Leizel"},
    {"chatId": "639971981713@c.us", "name": "Jean Labora"},
    {"chatId": "639101692301@c.us", "name": "Jean Sumarago"},
]
WEEK = [date(2026, 9, 13), date(2026, 9, 14), date(2026, 9, 15),
        date(2026, 9, 16), date(2026, 9, 17)]


class TestDateWording(unittest.TestCase):
    def test_ordinals(self) -> None:
        got = [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 30, 31)]
        self.assertEqual(
            got,
            ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th",
             "21st", "22nd", "23rd", "30th", "31st"],
        )

    def test_long_date(self) -> None:
        self.assertEqual(long_date(date(2026, 9, 13)), "Sunday 13th September")
        self.assertEqual(long_date(date(2026, 9, 17)), "Thursday 17th September")


class TestRosterAnnouncement(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Directory.from_records(GROUP)

    def test_heading_matches_the_house_style(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz"], self.directory
        )
        self.assertTrue(
            announcement.text.startswith(
                "Roster Sunday 13th September (2pm - 5pm Manila Time):"
            )
        )

    def test_body_carries_numbers_and_the_send_carries_jids(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz", "Kharen Ybas"], self.directory
        )
        self.assertIn("@639275044990", announcement.text)
        self.assertIn("@639260813435", announcement.text)
        self.assertEqual(
            announcement.mentions,
            ["639275044990@c.us", "639260813435@c.us"],
        )

    def test_preview_reads_as_names(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz"], self.directory
        )
        self.assertIn("@Pernelia Villapaz", announcement.preview)
        self.assertNotIn("639275044990", announcement.preview)

    def test_one_name_per_line(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz", "Kharen Ybas"], self.directory
        )
        self.assertEqual(len(announcement.text.splitlines()), 3)

    def test_untaggable_callers_are_still_named_and_reported(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13),
            ["Pernelia Villapaz", "Jean", "New Starter"],
            self.directory,
        )
        self.assertEqual(announcement.untagged, ["Jean", "New Starter"])
        self.assertIn("Jean", announcement.text)
        self.assertIn("New Starter", announcement.text)
        self.assertFalse(announcement.is_complete)

    def test_a_fully_tagged_roster_reports_complete(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz", "Leizel Chun"], self.directory
        )
        self.assertTrue(announcement.is_complete)

    def test_shift_times_and_poll_name_are_settable(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 16),
            ["Leizel Chun"],
            self.directory,
            start_time="1pm",
            end_time="6pm",
            timezone_label="PH Time",
            poll="Rotorua 400",
        )
        self.assertIn("(1pm - 6pm PH Time)", announcement.text)
        self.assertIn("Rotorua 400", announcement.text)

    def test_footer_is_appended_once(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Leizel Chun"], self.directory,
            footer="Call sheets will be shared an hour before.",
        )
        self.assertTrue(announcement.text.endswith("shared an hour before."))
        self.assertEqual(announcement.text.count("Call sheets"), 1)

    def test_mentions_can_be_read_back_out_of_the_body(self) -> None:
        announcement = render_roster_announcement(
            date(2026, 9, 13), ["Pernelia Villapaz", "Kharen Ybas"], self.directory
        )
        self.assertEqual(
            mentioned_numbers(announcement.text), ["639275044990", "639260813435"]
        )

    def test_every_mention_in_the_body_has_a_matching_jid(self) -> None:
        # The two have to agree or WhatsApp renders a raw phone number in the
        # message and notifies nobody.
        announcement = render_roster_announcement(
            date(2026, 9, 13),
            ["Pernelia Villapaz", "Kharen Ybas", "Leizel Chun", "Jean"],
            self.directory,
        )
        numbers = mentioned_numbers(announcement.text)
        self.assertEqual(
            numbers, [jid.split("@")[0] for jid in announcement.mentions]
        )


class TestWeekAnnouncements(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Directory.from_records(GROUP)

    def test_one_message_per_staffed_day_in_order(self) -> None:
        announcements = render_week_announcements(
            WEEK,
            {
                date(2026, 9, 14): ["Kharen Ybas"],
                date(2026, 9, 13): ["Pernelia Villapaz"],
            },
            self.directory,
        )
        self.assertEqual(len(announcements), 2)
        self.assertIn("Sunday 13th", announcements[0].text)
        self.assertIn("Monday 14th", announcements[1].text)

    def test_days_with_nobody_on_produce_no_message(self) -> None:
        announcements = render_week_announcements(
            WEEK, {date(2026, 9, 13): [], date(2026, 9, 14): ["Kharen Ybas"]},
            self.directory,
        )
        self.assertEqual(len(announcements), 1)


class TestAvailabilityRequest(unittest.TestCase):
    def test_lists_every_day_with_its_number_and_weekday(self) -> None:
        request = render_availability_request(WEEK)
        for fragment in ("13th - Sunday", "14th - Monday", "15th - Tuesday",
                         "16th - Wednesday", "17th - Thursday"):
            self.assertIn(fragment, request.text)

    def test_names_the_span_and_the_shift_times(self) -> None:
        request = render_availability_request(WEEK)
        self.assertIn("Sunday 13th September to Thursday 17th September", request.text)
        self.assertIn("2pm - 5pm Manila Time", request.text)

    def test_asks_for_a_reply_even_from_people_who_cannot_work(self) -> None:
        # Silence is the thing that breaks the loop: it is indistinguishable
        # from "has not read it yet", so the question has to ask for a no.
        self.assertIn("not available", render_availability_request(WEEK).text)

    def test_deadline_is_included_when_given(self) -> None:
        request = render_availability_request(WEEK, deadline="Friday 6pm")
        self.assertIn("Friday 6pm", request.text)

    def test_no_days_is_an_error_rather_than_an_empty_message(self) -> None:
        with self.assertRaises(ValueError):
            render_availability_request([])

    def test_the_question_tags_nobody(self) -> None:
        self.assertEqual(render_availability_request(WEEK).mentions, [])


if __name__ == "__main__":
    unittest.main()

"""Joining the contact sheet to the audit history and the WhatsApp group."""

from __future__ import annotations

import unittest

from business_agent.contacts import (
    load_contacts,
    normalise_email,
    normalise_phone,
)
from business_agent.directory import Directory

KNOWN = {
    "lia villapaz": "Lia Villapaz",
    "kharen ybas": "Kharen Ybas",
    "leizel chun": "Leizel Chun",
}
GROUP = [
    {"chatId": "639275044990@c.us", "name": "Pernelia Villapaz"},
    {"chatId": "639260813435@c.us", "name": "Kharen"},
    {"chatId": "639497821558@c.us", "name": "Leizel"},
]


class TestNormalisingNumbers(unittest.TestCase):
    def test_the_shapes_people_type(self) -> None:
        for raw in ("+63 927 504 4990", "639275044990", "0927 504 4990",
                    "+63-927-504-4990", " 639275044990 "):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_phone(raw), "639275044990")

    def test_a_number_excel_turned_into_a_float(self) -> None:
        self.assertEqual(normalise_phone("639275044990.0"), "639275044990")

    def test_a_local_number_gains_its_country_code(self) -> None:
        self.assertEqual(normalise_phone("9275044990"), "639275044990")

    def test_a_new_zealand_number_is_kept_as_given(self) -> None:
        self.assertEqual(normalise_phone("+64 27 342 6799"), "64273426799")

    def test_the_default_country_is_settable(self) -> None:
        self.assertEqual(normalise_phone("0273426799", default_country="64"),
                         "64273426799")

    def test_rubbish_is_rejected_rather_than_mangled(self) -> None:
        for raw in ("", "   ", "n/a", "-", "12", "1" * 20):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_phone(raw), "")


class TestNormalisingEmail(unittest.TestCase):
    def test_lowercased_and_trimmed(self) -> None:
        self.assertEqual(normalise_email("  Lia@Example.COM "), "lia@example.com")

    def test_anything_that_is_not_an_address_is_dropped(self) -> None:
        for raw in ("", "none", "lia@", "@example.com", "lia example.com"):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_email(raw), "")


class TestLoadingTheSheet(unittest.TestCase):
    ROWS = [
        {"Name": "Lia Villapaz", "WhatsApp Number": "+63 927 504 4990",
         "Email Address": "lia@example.com"},
        {"Name": "Kharen Ybas", "WhatsApp Number": "639260813435",
         "Email Address": "kharen@example.com"},
        {"Name": "Leizel Chun", "WhatsApp Number": "639497821558",
         "Email Address": "leizel@example.com"},
    ]

    def test_every_row_is_read(self) -> None:
        book = load_contacts(self.ROWS)
        self.assertEqual(len(book.contacts), 3)
        self.assertEqual(book.problems, [])

    def test_columns_are_found_by_heading(self) -> None:
        book = load_contacts(self.ROWS)
        contact = book.get("Lia Villapaz")
        self.assertEqual(contact.phone, "639275044990")
        self.assertEqual(contact.email, "lia@example.com")

    def test_a_contact_column_does_not_swallow_the_address(self) -> None:
        book = load_contacts(
            [{"Caller": "Lia Villapaz", "Contact": "639275044990",
              "Email": "lia@example.com"}]
        )
        contact = book.get("Lia Villapaz")
        self.assertEqual(contact.email, "lia@example.com")
        self.assertEqual(contact.phone, "639275044990")

    def test_headings_can_be_named_explicitly(self) -> None:
        book = load_contacts(
            [{"A": "Lia Villapaz", "B": "639275044990", "C": "lia@example.com"}],
            name_column="A", phone_column="B", email_column="C",
        )
        self.assertEqual(book.get("Lia Villapaz").email, "lia@example.com")

    def test_no_name_column_is_an_error_naming_the_columns_present(self) -> None:
        with self.assertRaises(ValueError) as raised:
            load_contacts([{"Foo": "x", "Bar": "y"}])
        self.assertIn("Foo", str(raised.exception))

    def test_rows_without_a_name_are_skipped(self) -> None:
        book = load_contacts(self.ROWS + [{"Name": "  ", "Email Address": "x@y.com"}])
        self.assertEqual(len(book.contacts), 3)

    def test_a_caller_with_no_way_to_reach_them_is_a_problem(self) -> None:
        book = load_contacts([{"Name": "Nobody", "WhatsApp Number": "", "Email Address": ""}])
        self.assertIn(("Nobody", "no way to reach them"), book.problems)

    def test_an_unreadable_number_is_reported_not_silently_dropped(self) -> None:
        book = load_contacts(
            [{"Name": "Typo", "WhatsApp Number": "ask her", "Email Address": "t@y.com"}]
        )
        self.assertTrue(any("unreadable number" in reason for _, reason in book.problems))
        self.assertEqual(book.get("Typo").email, "t@y.com")

    def test_an_unreadable_email_is_reported(self) -> None:
        book = load_contacts(
            [{"Name": "Typo", "WhatsApp Number": "639275044990", "Email Address": "not an email"}]
        )
        self.assertTrue(any("unreadable email" in reason for _, reason in book.problems))

    def test_a_duplicate_row_keeps_the_first_and_says_so(self) -> None:
        book = load_contacts(
            self.ROWS
            + [{"Name": "Lia Villapaz", "WhatsApp Number": "639999999999",
                "Email Address": "wrong@example.com"}]
        )
        self.assertEqual(book.get("Lia Villapaz").email, "lia@example.com")
        self.assertIn(("Lia Villapaz", "listed more than once"), book.problems)

    def test_lookup_tolerates_the_spelling_differences(self) -> None:
        book = load_contacts([{"Name": "Kharen", "Email Address": "k@example.com"}])
        self.assertIsNotNone(book.get("Kharen Ybas"))

    def test_empty_input(self) -> None:
        book = load_contacts([])
        self.assertEqual(book.contacts, {})


class TestTheJoin(unittest.TestCase):
    def test_callers_with_no_contact_row_are_named(self) -> None:
        # The people who cannot be reached: the gap that matters most.
        book = load_contacts(
            [{"Name": "Kharen Ybas", "Email Address": "k@example.com"}],
            known_callers=KNOWN,
        )
        self.assertEqual(book.missing_contacts, ["Leizel Chun", "Lia Villapaz"])

    def test_contact_rows_matching_no_caller_are_named(self) -> None:
        book = load_contacts(
            [{"Name": "Brand New Person", "Email Address": "n@example.com"}],
            known_callers=KNOWN,
        )
        self.assertEqual(book.unknown_to_audits, ["Brand New Person"])

    def test_a_clean_sheet_reports_no_gaps(self) -> None:
        rows = [{"Name": name, "Email Address": f"{key.split()[0]}@example.com"}
                for key, name in KNOWN.items()]
        book = load_contacts(rows, known_callers=KNOWN)
        self.assertEqual(book.missing_contacts, [])
        self.assertEqual(book.unknown_to_audits, [])

    def test_a_number_disagreeing_with_whatsapp_is_flagged(self) -> None:
        book = load_contacts(
            [{"Name": "Kharen Ybas", "WhatsApp Number": "639111111111",
              "Email Address": "k@example.com"}],
            directory=Directory.from_records(GROUP),
        )
        self.assertEqual(
            book.phone_conflicts, [("Kharen Ybas", "639111111111", "639260813435")]
        )

    def test_a_matching_number_is_not_flagged(self) -> None:
        book = load_contacts(
            [{"Name": "Kharen Ybas", "WhatsApp Number": "+63 926 081 3435"}],
            directory=Directory.from_records(GROUP),
        )
        self.assertEqual(book.phone_conflicts, [])


class TestReachingADaysCallers(unittest.TestCase):
    def setUp(self) -> None:
        self.book = load_contacts([
            {"Name": "Lia Villapaz", "Email Address": "lia@example.com"},
            {"Name": "Kharen Ybas", "Email Address": "kharen@example.com"},
            {"Name": "Leizel Chun", "WhatsApp Number": "639497821558"},
        ])

    def test_addresses_for_a_roster(self) -> None:
        found, missing = self.book.emails_for(
            ["Lia Villapaz", "Kharen Ybas", "Leizel Chun", "Somebody Else"]
        )
        self.assertEqual(found, {"Lia Villapaz": "lia@example.com",
                                 "Kharen Ybas": "kharen@example.com"})
        # No address is the same outcome as no row: they do not get the email.
        self.assertEqual(missing, ["Leizel Chun", "Somebody Else"])

    def test_reachable_counts_anyone_with_a_channel(self) -> None:
        self.assertEqual(self.book.reachable, 3)


if __name__ == "__main__":
    unittest.main()

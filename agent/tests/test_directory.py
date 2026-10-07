"""The WhatsApp address book, and the names it must refuse to guess at."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from business_agent.directory import Directory

# Shaped exactly like the connector's participant list, including the tilde
# WhatsApp puts in front of a name it only knows from the sender's profile,
# and two members saved under the same name.
GROUP = [
    {"chatId": "639275044990@c.us", "name": "Pernelia Villapaz", "isAdmin": False},
    {"chatId": "639260813435@c.us", "name": "Kharen", "isAdmin": False},
    {"chatId": "639497821558@c.us", "name": "Leizel", "isAdmin": False},
    {"chatId": "639605465542@c.us", "name": "Lorraine Sabroso", "isAdmin": False},
    {"chatId": "639971981713@c.us", "name": "Jean Labora", "isAdmin": False},
    {"chatId": "639101692301@c.us", "name": "Jean Sumarago", "isAdmin": False},
    {"chatId": "639124364973@c.us", "name": "Florence Bularon", "isAdmin": False},
    {"chatId": "639093759624@c.us", "name": "Florence Bularon", "isAdmin": False},
    {"chatId": "639162991771@c.us", "name": "Karen", "isAdmin": False},
    {"chatId": "639761711455@c.us", "name": "Karen Ybañez Redaniel", "isAdmin": False},
    {"chatId": "639653303493@c.us", "name": "~Alalyn", "isAdmin": False},
    {"chatId": "64273426799@c.us", "name": "Brendon", "isAdmin": True},
]


class TestLoading(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Directory.from_records(GROUP)

    def test_reads_the_connector_shape_unchanged(self) -> None:
        self.assertEqual(len(self.directory.participants), 12)

    def test_strips_the_pushname_tilde(self) -> None:
        found = self.directory.find("Alalyn")
        self.assertIsNotNone(found)
        self.assertEqual(found.participant.name, "Alalyn")

    def test_phone_is_the_number_without_the_jid_suffix(self) -> None:
        found = self.directory.find("Pernelia Villapaz")
        self.assertEqual(found.participant.phone, "639275044990")

    def test_admins_are_carried_through(self) -> None:
        found = self.directory.find("Brendon")
        self.assertTrue(found.participant.is_admin)

    def test_records_without_a_number_or_name_are_dropped(self) -> None:
        directory = Directory.from_records(
            [{"chatId": "", "name": "Ghost"}, {"chatId": "1@c.us", "name": ""}]
        )
        self.assertEqual(directory.participants, [])

    def test_round_trips_through_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "group.json"
            self.directory.save(path)
            again = Directory.load(path)
        self.assertEqual(len(again.participants), len(self.directory.participants))
        self.assertEqual(again.find("Kharen").participant.phone, "639260813435")

    def test_loads_a_raw_saved_api_response(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "group.json"
            path.write_text(json.dumps({"data": GROUP, "total": 12}), encoding="utf-8")
            directory = Directory.load(path)
        self.assertEqual(len(directory.participants), 12)

    def test_loads_a_bare_list(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "group.json"
            path.write_text(json.dumps(GROUP), encoding="utf-8")
            self.assertEqual(len(Directory.load(path).participants), 12)


class TestMatching(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Directory.from_records(GROUP)

    def test_exact_name(self) -> None:
        found = self.directory.find("Pernelia Villapaz")
        self.assertEqual(found.participant.phone, "639275044990")
        self.assertEqual(found.how, "exact")

    def test_audit_name_longer_than_the_saved_contact(self) -> None:
        # The audit sheet says "Kharen Ybas"; WhatsApp just says "Kharen".
        found = self.directory.find("Kharen Ybas")
        self.assertEqual(found.participant.phone, "639260813435")
        self.assertEqual(found.how, "contained")

    def test_single_letter_difference(self) -> None:
        # The audit sheet spells her "Loraine".
        found = self.directory.find("Loraine Sabroso")
        self.assertEqual(found.participant.phone, "639605465542")
        self.assertEqual(found.how, "typo")

    def test_case_and_spacing_are_ignored(self) -> None:
        self.assertIsNotNone(self.directory.find("  leizel   chun "))

    def test_unknown_name_matches_nobody(self) -> None:
        self.assertIsNone(self.directory.find("Somebody Entirely New"))

    def test_an_exact_match_is_not_made_ambiguous_by_a_longer_name(self) -> None:
        # "Karen" is a member in her own right as well as the start of
        # "Karen Ybañez Redaniel". The exact match has to win outright.
        found = self.directory.find("Karen")
        self.assertEqual(found.participant.phone, "639162991771")

    def test_a_name_that_could_be_two_people_matches_neither(self) -> None:
        # There are two Jeans in the group. Tagging the wrong one puts the
        # wrong person on a shift, so this must resolve to nobody.
        self.assertIsNone(self.directory.find("Jean"))
        self.assertEqual(len(self.directory.candidates("Jean")), 2)

    def test_duplicate_contacts_are_reported(self) -> None:
        self.assertIn("florence bularon", self.directory.collisions)
        self.assertEqual(len(self.directory.collisions["florence bularon"]), 2)

    def test_a_name_saved_twice_is_never_tagged(self) -> None:
        self.assertIsNone(self.directory.find("Florence Bularon"))


class TestResolvingARoster(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Directory.from_records(GROUP)

    def test_reports_who_could_not_be_tagged(self) -> None:
        matched, missing = self.directory.resolve(
            ["Pernelia Villapaz", "Kharen Ybas", "Nobody Here", "Jean"]
        )
        self.assertEqual(sorted(matched), ["Kharen Ybas", "Pernelia Villapaz"])
        self.assertEqual(missing, ["Nobody Here", "Jean"])

    def test_keeps_the_order_it_was_given(self) -> None:
        matched, _ = self.directory.resolve(["Kharen Ybas", "Pernelia Villapaz"])
        self.assertEqual(list(matched), ["Kharen Ybas", "Pernelia Villapaz"])

    def test_the_same_person_is_not_tagged_twice(self) -> None:
        # Two spellings of one caller reaching the roster is a bug upstream,
        # but it must not become one number tagged twice in one message.
        matched, missing = self.directory.resolve(["Loraine Sabroso", "Lorraine Sabroso"])
        self.assertEqual(len(matched), 1)
        self.assertEqual(missing, ["Lorraine Sabroso"])


class TestAliases(unittest.TestCase):
    """The names a matcher must never guess, and a person settles once."""

    def setUp(self) -> None:
        # "Lia Villapaz" in the audit sheet is "Pernelia Villapaz" in WhatsApp.
        # No safe rule connects those; a person says so once.
        self.directory = Directory.from_records(
            GROUP, {"Lia Villapaz": "639275044990"}
        )

    def test_an_alias_resolves_a_name_no_rule_could(self) -> None:
        found = self.directory.find("Lia Villapaz")
        self.assertEqual(found.participant.name, "Pernelia Villapaz")
        self.assertEqual(found.how, "alias")

    def test_an_alias_accepts_a_full_jid_too(self) -> None:
        directory = Directory.from_records(
            GROUP, {"Lia Villapaz": "639275044990@c.us"}
        )
        self.assertIsNotNone(directory.find("Lia Villapaz"))

    def test_an_alias_beats_an_otherwise_ambiguous_name(self) -> None:
        # Two Jeans in the group; naming one settles it.
        directory = Directory.from_records(GROUP, {"Jean": "639101692301"})
        self.assertEqual(directory.find("Jean").participant.name, "Jean Sumarago")

    def test_an_alias_pointing_at_a_departed_member_is_dropped(self) -> None:
        # Silently tagging a stranger is worse than tagging nobody.
        directory = Directory.from_records(GROUP, {"Lia Villapaz": "639000000000"})
        self.assertEqual(directory.aliases, {})
        self.assertIsNone(directory.find("Lia Villapaz"))

    def test_aliases_are_matched_regardless_of_spacing_and_case(self) -> None:
        directory = Directory.from_records(
            GROUP, {"  LIA   villapaz ": "639275044990"}
        )
        self.assertIsNotNone(directory.find("Lia Villapaz"))

    def test_aliases_survive_a_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "group.json"
            self.directory.save(path)
            again = Directory.load(path)
        self.assertEqual(again.find("Lia Villapaz").participant.phone, "639275044990")

    def test_no_aliases_leaves_the_matcher_untouched(self) -> None:
        plain = Directory.from_records(GROUP)
        self.assertIsNone(plain.find("Lia Villapaz"))
        self.assertEqual(plain.find("Kharen Ybas").how, "contained")


if __name__ == "__main__":
    unittest.main()

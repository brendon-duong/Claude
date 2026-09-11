import unittest

from business_agent.names import ALIASES, KNOWN_CALLERS, match


class TestMatchingADisplayName(unittest.TestCase):
    def test_an_exact_roster_name_matches(self):
        self.assertEqual(match("Cherry Jean Raagas").how, "exact")
        self.assertEqual(match("Cherry Jean Raagas").roster, "Cherry Jean Raagas")

    def test_case_does_not_matter(self):
        self.assertEqual(match("katherine boiser").roster, "Katherine Boiser")

    def test_the_bracketed_nickname_is_not_part_of_the_name(self):
        self.assertEqual(match("Pernelia Villapaz").roster, "Pernelia Villapaz (Lia)")
        self.assertEqual(match("Mary Joy Villacura").roster, "Mary Joy Villacura (Mary V)")

    def test_a_settled_alias_wins(self):
        m = match("Khars -")
        self.assertEqual((m.how, m.roster), ("settled", "Kharen Mae Pihana"))

    def test_one_plausible_candidate_is_offered_not_decided(self):
        m = match("Goldy Maglasang")
        self.assertEqual(m.how, "candidate")
        self.assertIsNone(m.roster)
        self.assertEqual(m.candidates, ("Goldy Kaye Maglasang",))
        self.assertTrue(m.needs_a_person)

    def test_two_jeans_means_neither(self):
        # "Jean Sumarago" is settled now. Any *other* Jean-shaped name must not
        # be handed to either of them by a prefix rule.
        m = match("Jean S")
        self.assertEqual(m.how, "ambiguous")
        self.assertIsNone(m.roster)
        self.assertEqual(m.candidates, ("Jean", "Jean Carla Sumarago"))

    def test_two_mary_joys_means_neither(self):
        m = match("Mary Joy")
        self.assertEqual(m.how, "ambiguous")
        self.assertEqual(len(m.candidates), 2)

    def test_a_name_that_resembles_nobody_says_so(self):
        m = match("Chary Jay Sanchez")
        self.assertEqual((m.how, m.roster, m.candidates), ("unmatched", None, ()))

    def test_every_alias_points_at_a_real_roster_name(self):
        for target in ALIASES.values():
            self.assertIn(target, KNOWN_CALLERS, target)

    def test_the_settled_ten_september_names_resolve(self):
        for zoom, roster in {
            "Jean Sumarago": "Jean Carla Sumarago",
            "Jayzel Pureza": "Jayzel Gabunada Pureza",
            "Tristan Philip Bustamante": "Tristan Philip",
            "Karen Redaniel Boiser": "Karen Boiser",
            "Melburne Baliad": "Melburne Ando Baliad",
            "Josephus Chris Parages": "Josephus Parages",
            "Eunilyn Lisondra": "Nilyn Lisondra",
        }.items():
            self.assertEqual(match(zoom).roster, roster, zoom)

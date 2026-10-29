import unittest
from datetime import date, datetime

from business_agent.config import Config
from business_agent.models import Message, Person
from business_agent.triage import extract_date, triage_rules

MONDAY = date(2024, 3, 11)

PEOPLE = {
    "sarah": Person(person_id="sarah", name="Sarah Chen", phone="+61400111222"),
    "dan": Person(person_id="dan", name="Dan Okafor", phone="+61400333444"),
}


def message(text: str, sender: str = "Sarah Chen") -> Message:
    return Message(sent_at=datetime(2024, 3, 11, 9, 0), sender=sender, text=text)


class TestExtractDate(unittest.TestCase):
    def test_today_and_tomorrow(self):
        self.assertEqual(extract_date("can't make it today", MONDAY), MONDAY)
        self.assertEqual(extract_date("free tomorrow", MONDAY), date(2024, 3, 12))

    def test_weekday_resolves_forward(self):
        self.assertEqual(extract_date("out on Thursday", MONDAY), date(2024, 3, 14))

    def test_same_weekday_means_next_week(self):
        self.assertEqual(extract_date("out on Monday", MONDAY), date(2024, 3, 18))

    def test_next_qualifier_skips_a_week(self):
        self.assertEqual(extract_date("next Thursday", MONDAY), date(2024, 3, 21))

    def test_day_first_numeric(self):
        self.assertEqual(extract_date("away on 14/03", MONDAY), date(2024, 3, 14))

    def test_no_date_returns_none(self):
        self.assertIsNone(extract_date("all good on my end", MONDAY))


class TestTriageRules(unittest.TestCase):
    def classify(self, text: str, sender: str = "Sarah Chen"):
        (event,) = triage_rules([message(text, sender)], PEOPLE, MONDAY)
        return event

    def test_detects_dropout(self):
        event = self.classify("Sorry, I can't make Thursday anymore")
        self.assertEqual(event.kind, "dropout")
        self.assertEqual(event.person_id, "sarah")
        self.assertEqual(event.day, date(2024, 3, 14))
        self.assertGreaterEqual(event.confidence, 0.8)

    def test_detects_sick_as_dropout(self):
        self.assertEqual(self.classify("calling in sick today").kind, "dropout")

    def test_detects_offer(self):
        event = self.classify("I'm free Thursday if you need cover")
        self.assertEqual(event.kind, "offer")
        self.assertEqual(event.day, date(2024, 3, 14))

    def test_detects_client_request_from_unknown_sender(self):
        event = self.classify("we need 20 more calls on Friday", sender="Rachel")
        self.assertEqual(event.kind, "client_request")
        self.assertEqual(event.calls, 20)
        self.assertEqual(event.day, date(2024, 3, 15))

    def test_chit_chat_is_noise(self):
        self.assertEqual(self.classify("morning all, heading in now").kind, "noise")

    def test_low_confidence_when_date_missing(self):
        event = self.classify("I can't make it, sorry")
        self.assertEqual(event.kind, "dropout")
        self.assertLess(event.confidence, 0.6)

    def test_matches_person_by_phone_number(self):
        event = self.classify("calling in sick today", sender="+61 400 333 444")
        self.assertEqual(event.person_id, "dan")

    def test_unknown_sender_stays_unmatched(self):
        event = self.classify("calling in sick today", sender="Random Person")
        self.assertIsNone(event.person_id)


class TestClaudeFallback(unittest.TestCase):
    def test_missing_claude_cli_leaves_rules_result_intact(self):
        from business_agent.triage import triage

        config = Config(use_claude_triage=True, claude_command="definitely-not-a-real-binary")
        (event,) = triage([message("I can't make it, sorry")], PEOPLE, MONDAY, config)
        self.assertEqual(event.kind, "dropout")
        self.assertEqual(event.source, "rules")


if __name__ == "__main__":
    unittest.main()


class TestRealGroupChatLanguage(unittest.TestCase):
    """Phrasings taken from the Pacific Link Global group.

    Every offer here was missed by an earlier version that only knew
    "I can cover", and the dropout read as an offer because "not able to
    work" contains "able to work". The supervisor lines are here because
    they must never be mistaken for volunteers.
    """

    def kind(self, text: str) -> str:
        (event,) = triage_rules([message(text)], PEOPLE, MONDAY)
        return event.kind

    def test_the_commonest_offer(self):
        self.assertEqual(self.kind("I can work"), "offer")

    def test_offer_variants_the_team_actually_uses(self):
        for text in (
            "I can cover",
            "i can cover",
            "I can cover too",
            "I can work too",
            "I can also work today if needed",
            "Yes sure I can cover. Thank you.",
            "Do we have the final roster for Wednesday? I can work too",
        ):
            self.assertEqual(self.kind(text), "offer", text)

    def test_not_able_to_work_is_a_dropout_not_an_offer(self):
        text = (
            "Unfortunately i am not able to work for today due an event at my "
            "Kids school, nilyn can cover for me."
        )
        self.assertEqual(self.kind(text), "dropout")

    def test_a_supervisor_asking_people_to_work_is_not_an_offer(self):
        """"Can you 4 work today please" is a request, not a volunteer."""
        self.assertEqual(self.kind("Can you 4 work today please"), "noise")

    def test_closing_the_roster_is_not_an_offer(self):
        """This one contains the word "work" and must still be noise."""
        self.assertEqual(
            self.kind("Roster is full no need for anyone else to work"), "noise"
        )

    def test_stating_how_many_are_needed_is_not_an_offer(self):
        self.assertEqual(
            self.kind("We are only needing 3 callers tonight actually"), "noise"
        )

    def test_a_bare_acknowledgement_is_too_vague_to_count(self):
        """"Likewise here" only means anything with the message above it, so
        it is left for a human rather than guessed at."""
        self.assertEqual(self.kind("Likewise here"), "noise")

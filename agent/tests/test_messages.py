import unittest
from datetime import datetime

from business_agent.messages import parse_jsonl, parse_whatsapp_export


class TestWhatsAppExport(unittest.TestCase):
    def test_parses_ios_format(self):
        text = "[12/03/2024, 9:41:13 AM] Sarah Chen: can't make Thursday"
        (message,) = parse_whatsapp_export(text)
        self.assertEqual(message.sender, "Sarah Chen")
        self.assertEqual(message.text, "can't make Thursday")
        self.assertEqual(message.sent_at, datetime(2024, 3, 12, 9, 41, 13))

    def test_parses_android_format(self):
        text = "12/03/2024, 9:41 am - Dan Okafor: running late"
        (message,) = parse_whatsapp_export(text)
        self.assertEqual(message.sender, "Dan Okafor")
        self.assertEqual(message.sent_at, datetime(2024, 3, 12, 9, 41))

    def test_joins_wrapped_lines(self):
        text = (
            "[12/03/2024, 9:41:13 AM] Sarah Chen: can't make Thursday\n"
            "sorry for the short notice\n"
            "[12/03/2024, 9:45:00 AM] Dan Okafor: no worries"
        )
        first, second = parse_whatsapp_export(text)
        self.assertEqual(first.text, "can't make Thursday\nsorry for the short notice")
        self.assertEqual(second.text, "no worries")

    def test_drops_system_lines_and_media(self):
        text = (
            "[12/03/2024, 9:00:00 AM] Sarah: Messages and calls are end-to-end encrypted.\n"
            "[12/03/2024, 9:01:00 AM] Dan: <Media omitted>\n"
            "[12/03/2024, 9:02:00 AM] Mei: real message"
        )
        messages = parse_whatsapp_export(text)
        self.assertEqual([m.text for m in messages], ["real message"])

    def test_strips_bidi_marks(self):
        text = "‎[12/03/2024, 9:41:13 AM] Sarah Chen: hello"
        (message,) = parse_whatsapp_export(text)
        self.assertEqual(message.text, "hello")

    def test_ignores_unparseable_lines_without_crashing(self):
        self.assertEqual(parse_whatsapp_export("garbage with no timestamp"), [])


class TestJsonl(unittest.TestCase):
    def test_parses_records_and_drops_empties(self):
        text = (
            '{"sent_at": "2024-03-12T09:41:13Z", "sender": "Sarah", "text": "hi"}\n'
            '{"sent_at": "2024-03-12T09:42:00Z", "sender": "Dan", "text": "  "}\n'
        )
        (message,) = parse_jsonl(text)
        self.assertEqual(message.sender, "Sarah")
        self.assertIsNone(message.sent_at.tzinfo)


if __name__ == "__main__":
    unittest.main()

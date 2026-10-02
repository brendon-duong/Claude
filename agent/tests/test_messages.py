import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from business_agent.messages import load_inbox, parse_jsonl, parse_whatsapp_export


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


class TestRepeatedExports(unittest.TestCase):
    """A WhatsApp export is a snapshot of the whole chat, so exports taken on
    different days overlap almost entirely. Both of these were real hazards:
    re-reading the overlap, and acting on months-old messages as if new."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, text: str) -> None:
        (self.inbox / name).write_text(text.strip() + "\n", encoding="utf-8")

    def test_overlapping_exports_are_not_read_twice(self):
        monday = "[09/03/2026, 8:03:00 AM] Dan Okafor: can't make Thursday"
        tuesday = "[10/03/2026, 9:00:00 AM] Priya Nair: I can cover"
        self.write("export-mon.txt", monday)
        self.write("export-tue.txt", f"{monday}\n{tuesday}")
        messages = load_inbox(self.inbox)
        self.assertEqual([m.sender for m in messages], ["Dan Okafor", "Priya Nair"])

    def test_identical_text_at_different_times_is_kept(self):
        self.write(
            "chat.txt",
            "[09/03/2026, 8:03:00 AM] Dan Okafor: running late\n"
            "[10/03/2026, 8:03:00 AM] Dan Okafor: running late",
        )
        self.assertEqual(len(load_inbox(self.inbox)), 2)

    def test_history_older_than_the_window_is_ignored(self):
        self.write(
            "chat.txt",
            "[09/01/2026, 8:03:00 AM] Dan Okafor: can't make Thursday\n"
            "[09/03/2026, 8:03:00 AM] Priya Nair: I can cover",
        )
        messages = load_inbox(self.inbox, since=date(2026, 3, 1))
        self.assertEqual([m.sender for m in messages], ["Priya Nair"])

    def test_jsonl_dedupes_on_the_message_id(self):
        record = '{"id": "wamid.1", "sent_at": "2026-03-09T08:03:00Z", "sender": "Dan", "text": "hi"}'
        self.write("a.jsonl", record)
        self.write("b.jsonl", record)
        self.assertEqual(len(load_inbox(self.inbox)), 1)

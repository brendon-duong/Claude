import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from business_agent.ingest.whatsapp_cloud import (
    append_to_inbox,
    extract_messages,
    verify_signature,
)
from business_agent.messages import load_inbox

SECRET = "top-secret"


def payload(message_id="wamid.1", text="can't make Thursday", timestamp="1710234073"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "61400000000"},
                            "contacts": [
                                {"wa_id": "61400111222", "profile": {"name": "Sarah Chen"}}
                            ],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "61400111222",
                                    "timestamp": timestamp,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


class TestSignature(unittest.TestCase):
    def sign(self, body: bytes, secret: str = SECRET) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_accepts_a_correct_signature(self):
        body = b'{"hello": "world"}'
        self.assertTrue(verify_signature(SECRET, body, self.sign(body)))

    def test_rejects_a_forged_signature(self):
        body = b'{"hello": "world"}'
        self.assertFalse(verify_signature(SECRET, body, self.sign(body, "wrong-secret")))

    def test_rejects_a_tampered_body(self):
        self.assertFalse(verify_signature(SECRET, b'{"evil": true}', self.sign(b"{}")))

    def test_rejects_a_missing_header(self):
        self.assertFalse(verify_signature(SECRET, b"{}", None))

    def test_rejects_everything_when_no_secret_is_configured(self):
        body = b"{}"
        self.assertFalse(verify_signature("", body, self.sign(body, "")))


class TestExtract(unittest.TestCase):
    def test_pulls_out_sender_name_and_text(self):
        (record,) = extract_messages(payload())
        self.assertEqual(record["sender"], "Sarah Chen")
        self.assertEqual(record["text"], "can't make Thursday")
        self.assertEqual(record["id"], "wamid.1")

    def test_skips_non_text_messages(self):
        data = payload()
        data["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        self.assertEqual(extract_messages(data), [])

    def test_tolerates_status_only_webhooks(self):
        self.assertEqual(extract_messages({"entry": [{"changes": [{"value": {}}]}]}), [])

    def test_falls_back_to_the_number_when_no_profile_name(self):
        data = payload()
        data["entry"][0]["changes"][0]["value"]["contacts"] = []
        (record,) = extract_messages(data)
        self.assertEqual(record["sender"], "61400111222")


class TestAppendToInbox(unittest.TestCase):
    def test_writes_and_then_deduplicates_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            records = extract_messages(payload())
            self.assertEqual(append_to_inbox(inbox, records), 1)
            # Meta retries the same delivery; it must not become a second event.
            self.assertEqual(append_to_inbox(inbox, records), 0)
            self.assertEqual(len(load_inbox(inbox)), 1)

    def test_distinct_messages_both_land(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            append_to_inbox(inbox, extract_messages(payload("wamid.1", "first")))
            append_to_inbox(inbox, extract_messages(payload("wamid.2", "second")))
            self.assertEqual([m.text for m in load_inbox(inbox)], ["first", "second"])

    def test_no_records_writes_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(append_to_inbox(Path(tmp) / "nope", []), 0)
            self.assertFalse((Path(tmp) / "nope").exists())


if __name__ == "__main__":
    unittest.main()

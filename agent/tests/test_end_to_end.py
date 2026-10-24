"""A whole cycle, from raw WhatsApp text to a brief on disk.

Unit tests prove each part works; this proves they work together, which is the
failure mode that actually bites an unattended agent.
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from business_agent.run_cycle import run

AGENT_DIR = Path(__file__).resolve().parent.parent
TODAY = date(2026, 3, 9)  # a Monday, so weekday maths in the fixtures is stable


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


class TestFullCycle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        def day(offset: int) -> str:
            return (TODAY + timedelta(days=offset)).isoformat()

        write(
            self.root / "team.csv",
            "person_id,name,phone,skills,max_shifts_per_week,unavailable,preferred_shifts,reliability\n"
            "sarah,Sarah Chen,+61400111222,calls,5,,morning,0.95\n"
            "dan,Dan Okafor,+61400333444,calls,5,,morning,0.80\n"
            "priya,Priya Nair,+61400555666,calls,5,,morning,0.92",
        )
        write(
            self.root / "roster.csv",
            "date,shift,person_id,status,notes\n"
            f"{day(2)},morning,sarah,confirmed,\n"
            f"{day(2)},morning,dan,confirmed,",
        )
        write(
            self.root / "demand.csv",
            f"date,shift,calls_required,staff_required,notes\n{day(2)},morning,20,,",
        )
        write(
            self.root / "inbox" / "chat.txt",
            "[09/03/2026, 8:03:00 AM] Dan Okafor: sorry all, I can't make Wednesday, "
            "got a clash\n"
            "[09/03/2026, 8:15:00 AM] Priya Nair: I'm free Wednesday, happy to cover\n"
            "[09/03/2026, 9:00:00 AM] Sarah Chen: morning all",
        )

        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "business_name": "Test Co",
                    "calls_per_person": 10,
                    "horizon_days": 14,
                    "team": {"kind": "csv", "path": "team.csv"},
                    "roster": {"kind": "csv", "path": "roster.csv"},
                    "demand": {"kind": "csv", "path": "demand.csv"},
                    "messages_dir": "inbox",
                    "out_dir": "out",
                    "use_claude_triage": False,
                }
            )
        )

    def test_dropout_becomes_a_gap_and_a_draft_to_the_person_who_offered(self):
        run(self.config_path, TODAY, quiet=True)
        brief = (self.root / "out" / "latest_brief.md").read_text()

        self.assertIn("Dan Okafor dropped out", brief)
        self.assertIn("Priya Nair offered to cover", brief)
        self.assertIn("short 1", brief)

        drafts = json.loads((self.root / "out" / "latest_drafts.json").read_text())
        recipients = [d["to_name"] for d in drafts]
        self.assertEqual(recipients, ["Priya Nair"])
        self.assertIn("+61400555666", drafts[0]["to_phone"])
        self.assertIn("cover the morning shift", drafts[0]["body"])

    def test_it_never_asks_the_person_who_dropped_out(self):
        run(self.config_path, TODAY, quiet=True)
        drafts = json.loads((self.root / "out" / "latest_drafts.json").read_text())
        self.assertNotIn("Dan Okafor", [d["to_name"] for d in drafts])

    def test_chit_chat_produces_no_action(self):
        run(self.config_path, TODAY, quiet=True)
        brief = (self.root / "out" / "latest_brief.md").read_text()
        self.assertNotIn("morning all", brief)

    def test_a_second_run_is_idempotent(self):
        run(self.config_path, TODAY, quiet=True)
        first = (self.root / "out" / "latest_drafts.json").read_text()
        run(self.config_path, TODAY, quiet=True)
        self.assertEqual(first, (self.root / "out" / "latest_drafts.json").read_text())

    def test_an_empty_inbox_still_produces_a_brief(self):
        for path in (self.root / "inbox").iterdir():
            path.unlink()
        run(self.config_path, TODAY, quiet=True)
        brief = (self.root / "out" / "latest_brief.md").read_text()
        self.assertIn("No roster-relevant messages", brief)

    def test_shipped_demo_config_runs_clean(self):
        """The demo everyone runs first must not be broken."""
        run(AGENT_DIR / "config.demo.json", date.today(), quiet=True)
        self.assertTrue((AGENT_DIR / "out" / "latest_brief.md").exists())


if __name__ == "__main__":
    unittest.main()

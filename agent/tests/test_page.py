"""Tests for rendering the roster page."""

import unittest
from datetime import date, timedelta

from business_agent.audit import AuditRecord
from business_agent.curia import PollDay
from business_agent.page import render_roster_page
from business_agent.performance import Thresholds, score_all
from business_agent.roster_plan import build_roster

TODAY = date(2026, 9, 8)
SUNDAY = date(2026, 9, 13)
WORKING = ["sunday", "monday", "tuesday", "wednesday", "thursday"]


def audits_for(name, count=6, completes=5, declared=None):
    return [
        AuditRecord(
            day=TODAY - timedelta(days=index * 2),
            name=name,
            declared_completes=completes if declared is None else declared,
            actual_completes=completes,
        )
        for index in range(count)
    ]


class TestRenderRosterPage(unittest.TestCase):
    def build(self, records, polls, **kwargs):
        people = score_all(records, TODAY, Thresholds())
        plan = build_roster(
            polls,
            people,
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
            **kwargs,
        )
        return render_roster_page(
            plan,
            business_name="Pacific Link Global",
            audit_count=len(records),
            audit_from=min(r.day for r in records),
            audit_to=max(r.day for r in records),
        )

    def setUp(self):
        self.records = audits_for("Ana Reyes", completes=8) + audits_for("Ben Cruz")
        self.polls = [PollDay(day=SUNDAY, poll="Hutt South 400", pl_staff_confirmed=2)]

    def test_names_and_poll_appear(self):
        page = self.build(self.records, self.polls)
        self.assertIn("Ana Reyes", page)
        self.assertIn("Hutt South 400", page)
        self.assertIn("Pacific Link Global", page)

    def test_the_page_has_a_title(self):
        self.assertIn("<title>", self.build(self.records, self.polls))

    def test_no_document_wrapper_tags(self):
        """The artifact host supplies the skeleton, so the page must not."""
        page = self.build(self.records, self.polls)
        for tag in ("<!doctype", "<html", "<head>", "<body"):
            self.assertNotIn(tag, page.lower())

    def test_both_themes_are_defined(self):
        page = self.build(self.records, self.polls)
        self.assertIn("prefers-color-scheme: dark", page)
        self.assertIn('[data-theme="dark"]', page)

    def test_a_shortfall_is_shown_not_hidden(self):
        polls = [PollDay(day=SUNDAY, poll="Hutt South 400", pl_staff_confirmed=9)]
        page = self.build(self.records, polls)
        self.assertIn("slot(s) unfilled", page)

    def test_a_full_roster_says_so(self):
        self.assertIn("Fully staffed", self.build(self.records, self.polls))

    def test_barred_callers_are_named_with_reasons(self):
        records = self.records + audits_for("Liar Jones", count=4, completes=2, declared=9)
        page = self.build(records, self.polls)
        self.assertIn("Not offered a shift", page)
        self.assertIn("Liar Jones", page)

    def test_names_are_escaped(self):
        records = audits_for("Ana <script>alert(1)</script> Reyes")
        page = self.build(records, self.polls)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_duplicate_warning_appears_when_pairs_are_given(self):
        people = score_all(self.records, TODAY, Thresholds())
        plan = build_roster(
            self.polls,
            people,
            start=SUNDAY,
            end=date(2026, 9, 17),
            today=TODAY,
            working_days=WORKING,
        )
        page = render_roster_page(
            plan,
            business_name="Pacific Link Global",
            audit_count=1,
            audit_from=TODAY,
            audit_to=TODAY,
            duplicates=[("Loraine Sabroso", "Lorraine Sabroso", "typo")],
            duplicate_total=43,
        )
        self.assertIn("43 names look like the same person twice", page)
        self.assertIn("Loraine Sabroso", page)

    def test_the_draft_only_notice_is_present(self):
        page = self.build(self.records, self.polls)
        self.assertIn("Nothing here has been sent", page)


if __name__ == "__main__":
    unittest.main()

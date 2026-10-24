import datetime as dt
import unittest

from business_agent.caller_directory import (
    CallHistory,
    SlackMember,
    ZoomUser,
    build_directory,
    status_for,
    to_rows,
    CSV_HEADER,
)


class TestStatusFor(unittest.TestCase):
    def test_eight_or_more_is_active(self):
        self.assertEqual(status_for(8), "active")
        self.assertEqual(status_for(20), "active")

    def test_one_to_seven_is_occasional(self):
        self.assertEqual(status_for(1), "occasional")
        self.assertEqual(status_for(7), "occasional")

    def test_zero_is_none(self):
        self.assertEqual(status_for(0), "none")


class TestBuildDirectoryEmailJoin(unittest.TestCase):
    def test_joins_on_email_when_zoom_name_is_on_the_roster(self):
        slack = [SlackMember("U1", "Gerard Siason", "gerard@example.com")]
        zoom = [ZoomUser("1010", "Gerard Siason", "gerard@example.com", did="04 000 0001",
                          has_calling_plan=True)]
        history = [CallHistory("Gerard Siason", shifts=10, last_worked=dt.date(2026, 10, 1))]

        rows = build_directory(slack, zoom, history)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.name, "Gerard Siason")
        self.assertEqual(row.zoom_ext, "1010")
        self.assertTrue(row.has_calling_plan)
        self.assertEqual(row.shifts, 10)
        self.assertEqual(row.status, "active")
        self.assertEqual(row.notes, "")

    def test_a_settled_alias_still_resolves_to_the_canonical_roster_name(self):
        # "Khars -" is the settled Zoom alias for Kharen Mae Pihana.
        slack = [SlackMember("U2", "Kharen Ybas", "kharen@example.com")]
        zoom = [ZoomUser("1030", "Khars -", "kharen@example.com")]
        history = [CallHistory("Khars -", shifts=3)]

        rows = build_directory(slack, zoom, history)

        self.assertEqual(rows[0].name, "Kharen Mae Pihana")
        self.assertEqual(rows[0].shifts, 3)
        self.assertEqual(rows[0].status, "occasional")


class TestBuildDirectoryNameFallback(unittest.TestCase):
    def test_falls_back_to_name_match_when_emails_differ(self):
        # Eunilyn Lisondra's documented case: Slack and Zoom emails differ, so
        # the join has to go through names.match on the real name / zoom name.
        slack = [SlackMember("U3", "Eunilyn Lisondra", "slack-address@example.com")]
        zoom = [ZoomUser("1040", "Nilyn Lisondra", "zoom-address@example.com",
                          has_calling_plan=True)]
        history = [CallHistory("Nilyn Lisondra", shifts=9)]

        rows = build_directory(slack, zoom, history)

        self.assertEqual(rows[0].name, "Nilyn Lisondra")
        self.assertEqual(rows[0].zoom_ext, "1040")
        self.assertEqual(rows[0].shifts, 9)
        self.assertEqual(rows[0].notes, "")


class TestBuildDirectoryUnmatched(unittest.TestCase):
    def test_no_zoom_match_is_flagged_not_dropped(self):
        slack = [SlackMember("U4", "Brand New Person", "newperson@example.com")]
        rows = build_directory(slack, zoom_users=[], call_history=[])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "Brand New Person")
        self.assertIsNone(rows[0].zoom_ext)
        self.assertEqual(rows[0].shifts, 0)
        self.assertEqual(rows[0].status, "none")
        self.assertIn("no Zoom match", rows[0].notes)

    def test_two_slack_members_resolving_to_the_same_name_are_both_flagged(self):
        # Two different Boisers whose Slack email happens to be unrecognised,
        # but whose real names both resolve to the same ambiguous-free roster
        # entry - a genuine collision must never be silently merged.
        slack = [
            SlackMember("U5", "Karen Boiser", "a@example.com"),
            SlackMember("U6", "Karen Boiser", "b@example.com"),
        ]
        zoom = [ZoomUser("1050", "Karen Redaniel Boiser", "c@example.com")]

        rows = build_directory(slack, zoom, call_history=[])

        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIsNone(row.zoom_ext)
            self.assertIn("shared match", row.notes)


class TestToRows(unittest.TestCase):
    def test_header_then_name_sorted_rows(self):
        slack = [
            SlackMember("U1", "Zed Caller", "zed@example.com"),
            SlackMember("U2", "Alie Mae Ybanez", "alie@example.com"),
        ]
        zoom = [
            ZoomUser("1001", "Zed Caller", "zed@example.com"),
            ZoomUser("1002", "Alie Mae Ybanez", "alie@example.com"),
        ]
        directory = build_directory(slack, zoom, call_history=[])

        rows = to_rows(directory)

        self.assertEqual(rows[0], CSV_HEADER)
        # "Alie Mae Ybanez" sorts before "Zed Caller".
        self.assertEqual(rows[1][0], "Alie Mae Ybanez")
        self.assertEqual(rows[2][0], "Zed Caller")

    def test_row_shape_matches_header_length(self):
        slack = [SlackMember("U1", "Gerard Siason", "gerard@example.com")]
        zoom = [ZoomUser("1010", "Gerard Siason", "gerard@example.com",
                          did="04 000 0001", has_calling_plan=True)]
        directory = build_directory(slack, zoom, call_history=[])

        rows = to_rows(directory)

        self.assertEqual(len(rows[1]), len(CSV_HEADER))


if __name__ == "__main__":
    unittest.main()

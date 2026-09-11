import unittest
from datetime import date

from business_agent.calllog_export import (
    BLANK,
    COLUMNS,
    by_agent,
    check_formatting,
    folder_name,
    format_nz,
    hhmmss,
    rows_to_csv,
)


def row(owner="Eunilyn Lisondra", ext=1025, direction="outbound",
        when="2026-09-10T08:26:28Z", seconds=12, result="Auto Recorded",
        other="+642108162010"):
    agent, external = str(ext), other
    return {
        "direction": direction,
        "caller_number": agent if direction == "outbound" else external,
        "callee_number": external if direction == "outbound" else agent,
        "caller_did_number": "+6448876902" if direction == "outbound" else None,
        "callee_did_number": external if direction == "outbound" else "+6448876902",
        "caller_location": "" if direction == "outbound" else "New Zealand",
        "callee_location": "New Zealand" if direction == "outbound" else "",
        "date_time": when, "duration": seconds, "result": result, "path": "pstn",
        "department": "", "cost_center": "",
        "owner": {"name": owner, "extension_number": ext},
    }


class TestNumbersAsTheConsoleWritesThem(unittest.TestCase):
    """Every expectation here is copied from a real exported file."""

    def test_the_shapes_seen_in_a_real_export(self):
        for raw, want in [
            ("+64210610372", "0210 610 372"),    # 0210 keeps four
            ("+64211692062", "021 169 2062"),    # 0211 does not
            ("+64274446584", "0274 446 584"),    # 0274 keeps four
            ("+64273324487", "027 332 4487"),    # 0273 does not
            ("+642108162010", "0210 816 2010"),  # eleven digits, four-digit prefix
            ("+642040053130", "020 4005 3130"),  # eleven digits, three-digit prefix
            ("+64204250543", "020 425 0543"),
            ("+6448876902", "04 887 6902"),      # landline
        ]:
            self.assertEqual(format_nz(raw, "New Zealand"), f"{want} - New Zealand", raw)

    def test_an_unrecognisable_number_is_left_alone_not_guessed(self):
        # A wrong grouping in an auditor's file is worse than none.
        self.assertEqual(format_nz("+6410091"), "+6410091")
        self.assertEqual(format_nz("+15551234567"), "+15551234567")

    def test_an_extension_stays_bare(self):
        self.assertEqual(format_nz("1025"), "1025")

    def test_nothing_in_nothing_out(self):
        self.assertEqual(format_nz(""), "")


class TestDuration(unittest.TestCase):
    def test_zero_is_the_consoles_blank_marker(self):
        self.assertEqual(hhmmss(0), BLANK)

    def test_seconds_minutes_and_hours(self):
        self.assertEqual(hhmmss(12), "00:00:12")
        self.assertEqual(hhmmss(456), "00:07:36")
        self.assertEqual(hhmmss(3661), "01:01:01")


class TestOneCallersFile(unittest.TestCase):
    def setUp(self):
        self.csv = rows_to_csv([
            row(when="2026-09-10T08:26:28Z", seconds=12),
            row(when="2026-09-10T09:07:38Z", direction="inbound", seconds=0,
                result="No Answer", other="+64210610372"),
            row(when="2026-09-10T08:24:22Z", seconds=0, result="Call Cancel",
                other="+64223270980"),
        ])
        self.lines = self.csv.strip().split("\n")

    def test_the_header_is_the_consoles_eighteen_columns(self):
        self.assertEqual(self.lines[0], ",".join(COLUMNS))

    def test_newest_call_first(self):
        self.assertIn("2026-09-10 21:07:38", self.lines[1])   # 09:07 UTC in NZ
        self.assertTrue(self.lines[1].startswith("1,Inbound,"))

    def test_times_are_new_zealand_not_manila_or_utc(self):
        # 08:26:28 UTC is 20:26:28 NZ and 16:26:28 Manila. The files Curia
        # already hold are NZ, so these must be too.
        self.assertIn("2026-09-10 20:26:28", self.csv)
        self.assertNotIn("16:26:28", self.csv)

    def test_the_agents_leg_is_name_extension_and_did(self):
        self.assertIn("Eunilyn Lisondra - Ext. 1025 - 04 887 6902", self.csv)

    def test_the_api_result_vocabulary_is_translated(self):
        self.assertIn("Call Cancelled", self.csv)
        self.assertNotIn("Call Cancel,", self.csv)

    def test_device_is_empty_because_the_api_does_not_have_it(self):
        import csv as _csv
        import io
        rows = list(_csv.reader(io.StringIO(self.csv)))
        self.assertEqual(rows[1][COLUMNS.index("Device")], "")

    def test_path_is_upper_case(self):
        self.assertIn(",PSTN,", self.csv)


class TestSplittingADay(unittest.TestCase):
    def test_rows_go_to_the_zoom_user_who_owns_them(self):
        groups = by_agent([row(owner="Eunilyn Lisondra"), row(owner="Gerard Siason", ext=1041),
                           row(owner="Eunilyn Lisondra")])
        self.assertEqual(sorted(groups), ["Eunilyn Lisondra", "Gerard Siason"])
        self.assertEqual(len(groups["Eunilyn Lisondra"]), 2)

    def test_a_row_with_no_owner_belongs_to_nobody(self):
        self.assertEqual(by_agent([{"owner": {}, "date_time": "2026-09-10T08:00:00Z"}]), {})


class TestDriveFolderName(unittest.TestCase):
    def test_no_leading_zeros_the_way_elaine_names_them(self):
        self.assertEqual(folder_name(date(2026, 9, 10)), "10/9")
        self.assertEqual(folder_name(date(2026, 9, 1)), "1/9")


class TestComparingAgainstARealExport(unittest.TestCase):
    def test_a_perfect_rebuild_reports_no_mismatches(self):
        built = rows_to_csv([row()])
        report = check_formatting(built, built)
        self.assertEqual(report["rows_expected"], 1)
        self.assertEqual(sum(report["mismatches"].values()), 0)

    def test_a_wrong_number_is_caught_and_shown(self):
        a = rows_to_csv([row(other="+64210610372")])
        b = rows_to_csv([row(other="+64211692062")])
        report = check_formatting(a, b)
        self.assertEqual(report["mismatches"]["To"], 1)
        self.assertEqual(report["examples"][0]["column"], "To")

"""Tests for issuing numbers and building the day's call sheet.

The rules encoded here come from how Pacific Link already works: contiguous
blocks of 200 per caller, the pool file's title carrying how far down it has
been drawn, and ringbacks being worth another try while refusals are not.

The title cases are real titles from the Drive, because two of them broke an
earlier version of the parser.
"""

import unittest
from datetime import date

from business_agent.callsheet import (
    Allocation,
    PoolNumber,
    allocate,
    build_workbook,
    is_reusable,
    next_title,
    parse_high_water,
    start_after_from_title,
    title_mark_is_inclusive,
)

DAY = date(2026, 9, 14)
REAL_TITLE = "NZ Numbers 2026 - USE FROM 340199.xlsx"


def pool(start=1, count=1000, outcome=""):
    return [
        PoolNumber(number_id=start + index, number=f"09 555 {index:04d}", outcome=outcome)
        for index in range(count)
    ]


class TestPoolTitle(unittest.TestCase):
    def test_reads_the_mark_from_the_real_title(self):
        self.assertEqual(parse_high_water(REAL_TITLE), 340199)

    def test_use_from_is_inclusive(self):
        self.assertTrue(title_mark_is_inclusive(REAL_TITLE))
        self.assertEqual(start_after_from_title(REAL_TITLE) + 1, 340199)

    def test_up_to_is_exclusive(self):
        title = "Epsom Numbers - up to 12500"
        self.assertFalse(title_mark_is_inclusive(title))
        self.assertEqual(start_after_from_title(title) + 1, 12501)

    def test_a_bare_year_is_not_a_mark(self):
        """"ACT 1000 Rural Numbers - 10/06/2026" must not read as mark 2026 —
        that would restart drawing near the top of the pool."""
        for title in (
            "ACT 1000 Rural Numbers - 10/06/2026",
            "Spare NZ Numbers 2025 - ALL USED",
            "Far North Numbers 18/02/2026",
        ):
            self.assertIsNone(parse_high_water(title), title)
            self.assertIsNone(start_after_from_title(title), title)

    def test_next_title_names_the_next_unused_number(self):
        self.assertEqual(
            next_title(REAL_TITLE, 340798), "NZ Numbers 2026 - USE FROM 340799.xlsx"
        )

    def test_next_title_on_an_up_to_convention_names_the_last_used(self):
        self.assertEqual(
            next_title("Epsom Numbers - up to 12500", 13100), "Epsom Numbers - up to 13100"
        )

    def test_a_title_with_no_mark_gains_one(self):
        self.assertEqual(
            next_title("Rotorua 400 Numbers", 500), "Rotorua 400 Numbers - USE FROM 501"
        )

    def test_the_rest_of_the_title_is_left_alone(self):
        self.assertTrue(next_title(REAL_TITLE, 340798).endswith(".xlsx"))
        self.assertTrue(next_title(REAL_TITLE, 340798).startswith("NZ Numbers 2026"))


class TestReusable(unittest.TestCase):
    def test_a_number_never_called_is_reusable(self):
        self.assertTrue(is_reusable(PoolNumber(1, "09 555 0000")))

    def test_a_ringback_is_worth_another_try(self):
        for outcome in ("RB", "RINGBACK", "Ring Back", "rb", "RB / VM"):
            self.assertTrue(is_reusable(PoolNumber(1, "09 555 0000", outcome)), outcome)

    def test_a_refusal_is_finished_with(self):
        for outcome in ("Refused", "REFUSED", "Completed", "GNA", "DO NOT CALL", "INVALID"):
            self.assertFalse(is_reusable(PoolNumber(1, "09 555 0000", outcome)), outcome)


class TestAllocate(unittest.TestCase):
    def test_each_caller_gets_a_contiguous_block(self):
        result = allocate(pool(), ["Ana", "Ben"], poll="ACT 1000", day=DAY)
        first, second = result.blocks
        self.assertEqual(first.size, 200)
        self.assertEqual(first.last_id + 1, second.first_id)

    def test_blocks_never_overlap(self):
        result = allocate(pool(), ["Ana", "Ben", "Cara"], poll="ACT 1000", day=DAY)
        seen: set[int] = set()
        for block in result.blocks:
            ids = {item.number_id for item in block.numbers}
            self.assertEqual(seen & ids, set(), "two callers issued the same number")
            seen |= ids

    def test_drawing_resumes_after_the_last_issued_id(self):
        result = allocate(
            pool(start=340000, count=2000),
            ["Ana"],
            poll="ACT 1000",
            day=DAY,
            start_after=start_after_from_title(REAL_TITLE),
        )
        self.assertEqual(result.blocks[0].first_id, 340199)

    def test_the_new_high_water_is_the_last_id_issued(self):
        result = allocate(pool(start=340199), ["Ana", "Ben"], poll="ACT 1000", day=DAY)
        self.assertEqual(result.high_water, 340199 + 400 - 1)

    def test_called_numbers_are_skipped_but_ringbacks_are_not(self):
        mixed = [
            PoolNumber(1, "a", "Refused"),
            PoolNumber(2, "b", "RB"),
            PoolNumber(3, "c", ""),
            PoolNumber(4, "d", "Completed"),
        ]
        result = allocate(mixed, ["Ana"], poll="ACT 1000", day=DAY, block_size=10)
        self.assertEqual([n.number_id for n in result.blocks[0].numbers], [2, 3])

    def test_a_fresh_pool_can_ignore_outcomes(self):
        mixed = [PoolNumber(1, "a", "Refused"), PoolNumber(2, "b", "")]
        result = allocate(
            mixed, ["Ana"], poll="ACT 1000", day=DAY, block_size=10, reusable_only=False
        )
        self.assertEqual(result.blocks[0].size, 2)

    def test_a_pool_that_runs_dry_leaves_callers_unserved_rather_than_short(self):
        result = allocate(pool(count=250), ["Ana", "Ben", "Cara"], poll="ACT 1000", day=DAY)
        self.assertEqual([b.caller for b in result.blocks], ["Ana", "Ben"])
        self.assertEqual(result.blocks[1].size, 50)
        self.assertEqual(result.unserved, ["Cara"])

    def test_an_empty_pool_serves_nobody(self):
        result = allocate([], ["Ana"], poll="ACT 1000", day=DAY)
        self.assertEqual(result.blocks, [])
        self.assertEqual(result.unserved, ["Ana"])
        self.assertIsNone(result.high_water)

    def test_a_zero_block_size_is_rejected(self):
        with self.assertRaises(ValueError):
            allocate(pool(), ["Ana"], poll="ACT 1000", day=DAY, block_size=0)


class TestBuildWorkbook(unittest.TestCase):
    def setUp(self):
        self.allocation = allocate(
            pool(start=340199), ["Lia Villapaz", "Kharen Ybas"], poll="ACT 1000", day=DAY
        )
        self.workbook = build_workbook(self.allocation)

    def test_one_tab_per_caller_named_by_first_name(self):
        self.assertEqual(self.workbook.sheetnames, ["Lia", "Kharen"])

    def test_columns_are_id_number_then_the_callers_own(self):
        sheet = self.workbook["Lia"]
        self.assertEqual(
            [sheet["A1"].value, sheet["B1"].value], ["ID", "Number"]
        )
        self.assertEqual(sheet["A2"].value, 340199)
        self.assertIsNone(sheet["C2"].value, "column C is the caller's to fill in")

    def test_every_issued_number_is_written(self):
        sheet = self.workbook["Lia"]
        self.assertEqual(sheet.max_row, 201)

    def test_the_summary_block_carries_the_poll_caller_and_date(self):
        sheet = self.workbook["Lia"]
        column_f = [sheet.cell(row=r, column=6).value for r in range(1, 22)]
        self.assertIn("ACT 1000 — 14/09/2026", column_f)
        self.assertIn("LIA VILLAPAZ", column_f)
        self.assertIn("Total Calls", column_f)
        self.assertIn("Time in", column_f)

    def test_the_issued_range_is_recorded_on_the_sheet(self):
        sheet = self.workbook["Kharen"]
        values = [sheet.cell(row=r, column=7).value for r in range(1, 25)]
        self.assertIn("340399-340598", values)

    def test_two_callers_sharing_a_first_name_get_distinct_tabs(self):
        allocation = allocate(
            pool(), ["Mary Joy Villacura", "Mary Tongson"], poll="ACT 1000", day=DAY
        )
        self.assertEqual(build_workbook(allocation).sheetnames, ["Mary", "Mary T"])

    def test_a_caller_with_no_numbers_gets_no_tab(self):
        allocation = allocate(pool(count=100), ["Ana", "Ben"], poll="ACT 1000", day=DAY)
        self.assertEqual(build_workbook(allocation).sheetnames, ["Ana"])


if __name__ == "__main__":
    unittest.main()

"""Cutting a day's call sheets across one pool or several."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from business_agent.callsheet import PoolNumber
from business_agent.make_callsheets import (
    allocate_across_pools,
    load_callers,
    load_pool,
)

DAY = date(2026, 9, 10)


def pool(start: int, count: int, *, outcome_every: int = 0) -> list[PoolNumber]:
    numbers = []
    for offset in range(count):
        number_id = start + offset
        outcome = "Refused" if outcome_every and offset % outcome_every == 0 else ""
        numbers.append(
            PoolNumber(number_id=number_id, number=f"0210{number_id:06d}", outcome=outcome)
        )
    return numbers


class TestAllocatingAcrossPools(unittest.TestCase):
    def test_one_pool_serves_everyone(self):
        allocation, marks, _ = allocate_across_pools(
            [(pool(1, 1000), "Wellington Bays Numbers")],
            ["Ana", "Ben", "Cara"],
            poll="Wellington Bays 400", day=DAY, block_size=200,
        )
        self.assertEqual(len(allocation.blocks), 3)
        self.assertEqual(allocation.issued, 600)
        self.assertEqual(allocation.unserved, [])
        self.assertEqual(marks, [("Wellington Bays Numbers", 600)])

    def test_blocks_are_contiguous_and_do_not_overlap(self):
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 1000), "Pool")],
            ["Ana", "Ben", "Cara"],
            poll="P", day=DAY, block_size=200,
        )
        self.assertEqual(
            [block.label for block in allocation.blocks],
            ["1-200", "201-400", "401-600"],
        )

    def test_a_second_pool_takes_over_when_the_first_runs_dry(self):
        allocation, marks, _ = allocate_across_pools(
            [(pool(1, 300), "First"), (pool(5000, 1000), "Second")],
            ["Ana", "Ben", "Cara"],
            poll="P", day=DAY, block_size=200,
        )
        self.assertEqual([block.caller for block in allocation.blocks], ["Ana", "Ben", "Cara"])
        self.assertEqual(allocation.unserved, [])
        # Ana takes the first pool's 200; Ben and Cara come from the second.
        self.assertEqual(allocation.blocks[0].label, "1-200")
        self.assertEqual(allocation.blocks[1].first_id, 5000)
        self.assertEqual(marks, [("First", 200), ("Second", 5399)])

    def test_a_caller_never_gets_a_block_split_across_two_pools(self):
        # Ben would take 100 from the first pool and 100 from the second. He
        # gets the second pool's 200 instead: a short block from two surveys
        # is worse than a whole one, because he cannot tell where it changes.
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 300), "First"), (pool(5000, 1000), "Second")],
            ["Ana", "Ben"],
            poll="P", day=DAY, block_size=200,
        )
        self.assertEqual(allocation.blocks[1].size, 200)
        self.assertEqual(allocation.blocks[1].first_id, 5000)

    def test_callers_the_pools_cannot_serve_are_named(self):
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 250), "Only")],
            ["Ana", "Ben", "Cara"],
            poll="P", day=DAY, block_size=200,
        )
        self.assertEqual(allocation.issued, 250)
        # One pool, so a part-block is the best on offer: Ben takes the 50
        # that are left and Cara is named as having got nothing.
        self.assertEqual([b.caller for b in allocation.blocks], ["Ana", "Ben"])
        self.assertEqual(allocation.unserved, ["Cara"])

    def test_nobody_is_served_by_an_empty_pool(self):
        allocation, marks, _ = allocate_across_pools(
            [([], "Empty")], ["Ana", "Ben"], poll="P", day=DAY, block_size=200
        )
        self.assertEqual(allocation.blocks, [])
        self.assertEqual(allocation.unserved, ["Ana", "Ben"])
        self.assertEqual(marks, [])

    def test_a_use_from_mark_resumes_below_it(self):
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 1000), "Wellington Bays Numbers - USE FROM 401")],
            ["Ana"],
            poll="P", day=DAY, block_size=200,
        )
        # "USE FROM 401" means 401 is still available.
        self.assertEqual(allocation.blocks[0].label, "401-600")

    def test_an_up_to_mark_resumes_past_it(self):
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 1000), "Wellington Bays Numbers up to 400")],
            ["Ana"],
            poll="P", day=DAY, block_size=200,
        )
        # "up to 400" means 400 is spent.
        self.assertEqual(allocation.blocks[0].label, "401-600")

    def test_called_numbers_are_skipped_but_ringbacks_are_not(self):
        numbers = [
            PoolNumber(1, "021000001", "Completed"),
            PoolNumber(2, "021000002", "RB"),
            PoolNumber(3, "021000003", ""),
            PoolNumber(4, "021000004", "Refused"),
            PoolNumber(5, "021000005", "Ring Back"),
        ]
        allocation, _, _ = allocate_across_pools(
            [(numbers, "Pool")], ["Ana"], poll="P", day=DAY, block_size=10
        )
        self.assertEqual([n.number_id for n in allocation.blocks[0].numbers], [2, 3, 5])

    def test_the_high_water_mark_is_the_last_number_issued(self):
        allocation, _, _ = allocate_across_pools(
            [(pool(1, 1000), "Pool")], ["Ana", "Ben"], poll="P", day=DAY, block_size=200
        )
        self.assertEqual(allocation.high_water, 400)

    def test_no_callers_draws_nothing(self):
        allocation, marks, _ = allocate_across_pools(
            [(pool(1, 1000), "Pool")], [], poll="P", day=DAY, block_size=200
        )
        self.assertEqual(allocation.blocks, [])
        self.assertIsNone(allocation.high_water)
        self.assertEqual(marks, [])


class TestLoadingCallers(unittest.TestCase):
    def test_one_name_per_line_ignoring_blanks_and_comments(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "callers.txt"
            path.write_text(
                "# tonight\nLia Villapaz\n\n  Kharen Ybas  \n\nLeizel Chun\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_callers(path), ["Lia Villapaz", "Kharen Ybas", "Leizel Chun"]
            )


class TestLoadingAPool(unittest.TestCase):
    """Reading the shapes Curia's number files actually arrive in."""

    def build(self, folder: str, name: str, rows: list[tuple]) -> Path:
        from openpyxl import Workbook

        path = Path(folder) / name
        workbook = Workbook()
        sheet = workbook.active
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        return path

    def test_reads_id_number_and_outcome(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Numbers.xlsx", [
                ("ID", "Number", "Outcome"),
                (1, "021000001", "Completed"),
                (2, "021000002", None),
            ])
            numbers, title = load_pool(path)
        self.assertEqual(title, "Numbers")
        self.assertEqual(len(numbers), 2)
        self.assertEqual(numbers[0].outcome, "Completed")
        self.assertEqual(numbers[1].outcome, "")

    def test_the_title_carries_the_mark(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Bays Numbers - USE FROM 401.xlsx", [
                ("ID", "Number"), (1, "021000001"),
            ])
            _, title = load_pool(path)
        self.assertEqual(title, "Bays Numbers - USE FROM 401")

    def test_a_number_excel_stored_as_a_float(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Numbers.xlsx", [
                ("ID", "Number"), (1, 210000001.0),
            ])
            numbers, _ = load_pool(path)
        self.assertEqual(numbers[0].number, "210000001")

    def test_blank_rows_and_rows_without_an_id_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Numbers.xlsx", [
                ("ID", "Number"),
                (1, "021000001"),
                (None, None),
                ("total", "12"),
                (3, "021000003"),
            ])
            numbers, _ = load_pool(path)
        self.assertEqual([n.number_id for n in numbers], [1, 3])

    def test_a_file_with_no_header_row_keeps_its_first_number(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Numbers.xlsx", [
                (1, "021000001"), (2, "021000002"),
            ])
            numbers, _ = load_pool(path)
        self.assertEqual(len(numbers), 2)

    def test_a_row_with_an_id_but_no_number_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.build(folder, "Numbers.xlsx", [
                ("ID", "Number"), (1, "021000001"), (2, None),
            ])
            numbers, _ = load_pool(path)
        self.assertEqual([n.number_id for n in numbers], [1])


if __name__ == "__main__":
    unittest.main()

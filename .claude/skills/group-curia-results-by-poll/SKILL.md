---
name: group-curia-results-by-poll
description: Load this whenever writing or re-checking a day's block on the "PL for Curia Staff Results Record" Google Sheet — the declared-results run, a manual correction, or any session touching that sheet. Rows within a day must be grouped by Poll, not left in whatever order they were typed or alphabetised by name.
---

# Group each day's block by Poll on Curia's results page

Found 5 Oct 2026: Sunday 4 October's block was sorted alphabetically by staff name, so
Corp 1000, Mt Albert, NZNP 333 and Wgtn 1000 rows were all interleaved — unreadable for
anyone trying to check one poll's numbers at a glance. Brendon asked for every day's
block to be grouped by poll going forward, as a standing rule, not a one-off tidy-up.

## The rule

Within a single day's block (between its date header area and its `TOTAL - <Day>` row),
rows must be **grouped by the Poll column (E)**, not by name. Order of the poll groups
themselves doesn't matter — alphabetical by poll name is fine and is what was used on
5 Oct (Corp 1000, Mt Albert 400 NZTU, NZNP 333, Wgtn 1000). Within each poll group, keep
rows in a stable order (alphabetical by Staff Member is fine, since that's what they
already come in).

**Never touch:**
- The `TOTAL - <Day>` row itself — it stays at the bottom of its block, values unchanged.
- Column L (`Status`) — Curia's own, per CLAUDE.md's standing rule.
- The grey spacer row between days.
- Any other day's block.

This is a **reorder of existing rows, not a data edit** — every cell's content (Staff
Member, Date, Phone, Poll, GNA, RB, R, C, Total, Shift Notes) moves as a unit to its new
row; nothing in any row is recalculated or retyped.

## When this applies

- **The declared-results Routine** (`trig_01STiXp444UCGUpdqWzUyxjK`), every time it writes
  a new day's block. Group by poll *before* writing the rows, not as a follow-up pass —
  cheaper and avoids a second write hitting the same classifier wall below.
- **Any manual correction or backfill** to an existing day's block, including older days
  that predate this rule (worth grouping the next time you're in that block for any other
  reason, not worth a dedicated pass just for this).

## How to do it

1. Read the day's block in full (`sheets.mjs read`) to get every row's exact values.
2. Re-order in memory, grouped by Poll, stable within each group.
3. Write back to the same row range (`sheets.mjs write '<sheet>' '<range>' @payload.json`)
   — same range, same row count, just reordered content. Formatting (white fill,
   non-bold) is uniform across all data rows in a block already, so a value-only write
   doesn't need a follow-up `copyformat` pass the way a brand-new block does.
4. Read the range back and confirm every row's data matches what you intended to write,
   per `verify-work` — a reorder is still a write to a sheet Curia reads.

## If the write gets blocked by the harness

This is a write to the same shared Curia-facing sheet as every other write on it, so it
can hit the same `[Modify Shared Resources]` classifier wall documented in CLAUDE.md for
this sheet — even though `sheets.mjs write` is pre-approved in `.claude/settings.json`.
One attempt, no blind retry (same reasoning as the Zoom capacity skill: a denial on a
pre-approved command is the classifier judging content, not a missing permission, and
retrying identically doesn't reliably clear it).

**If blocked, the fastest unblock is Brendon doing it himself in the Sheets UI** — select
the day's data rows, **Data → Sort range → Advanced range sorting options**, sort by the
Poll column, A→Z. Ten seconds, no permissions issue, and it only reorders rows so nothing
else on the sheet is at risk. Hand him the exact row range rather than promising a fix
that can't actually be delivered from a blocked session.

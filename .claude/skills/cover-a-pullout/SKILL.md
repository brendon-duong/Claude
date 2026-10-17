---
name: cover-a-pullout
description: Load this the moment a rostered caller pulls out, a poll reads short, or Brendon asks who's been contacted for an open shift. Covers the order to ask people in, the number-block trap, and the check that was skipped on 30 Sep — going straight to "who has history and is free" and never checking new hires who've never worked.
---

# Covering a pull-out

Triggered by 30 Sep 2026: Melburne, Yvonne, Lily, Angeli and Nilyn all pulled out of the
same shift. Peterson, Lester and Charlene got DM'd. Farah Mae, Lorraine and Mary Joy
Tongson got chased for phone numbers. **Not one new hire who'd never worked got asked**,
until Brendon asked directly "why have you not been asking new hires" — a rule that's
been standing since 27 Sep and was simply never checked. The miss wasn't a bad judgment
call, it was skipping a whole tier of the list.

## Posting the gap is pre-authorised — do it first, don't ask

Brendon granted this 24 Sep: post in `#shift-changes-pacificlinkglobal` naming the day,
the shift time, and the poll, the moment a spot opens. No approval needed. Do this before
anything else below, then work the tiers in parallel with it.

## The three tiers, in this order — all of them, every time

1. **Tier 1 — the bench.** Anyone who voted ✅ for that day and isn't already rostered on
   it. Rank by the 75/25 score (completes/shift, away-time/shift) over the last fortnight.
   Ask immediately, don't wait for them to volunteer.
2. **Tier 2 — new starters who have never worked.** Newest joiner first. **This is the
   tier that gets skipped** because they have no call history to rank on and don't show up
   in an "active/occasional, free tonight" query — you have to deliberately query for
   `shifts_24d == 0` (or equivalent: zero shifts in the directory) and go through them by
   hand. A missing Zoom Phone extension does NOT disqualify anyone here — Brendon
   reassigns licences from the pool on the day. Don't filter them out for it.

   **Check that day's own ❌ vote before DMing anyone in this tier.** Found 1 Oct 2026:
   batch-DM'd 13 never-worked people for today without checking today's availability
   reactions first, and 5 of them had already voted ❌ for that exact day (Jellame Malicay,
   Hermi, Clarice Anne Almodovar, Jonnelle Patric Lumactod, Jean Labora). A ❌ is the one
   real "no" this skill already treats as final — pull that day's reaction list and exclude
   anyone on it before messaging the never-worked tier, not after.
3. **Tier 3 — people with history who didn't vote.** Silence isn't refusal; chase it the
   same as any other gap.

A ❌ on that day is the only real no. Everything else — including someone with zero shift
history — is a live candidate until they say no or the day passes.

**Do all three tiers before reporting back "still open."** Reporting Tier 1 results alone
and stopping is exactly the failure this skill exists to catch.

## A pull-out is a number block, not a headcount

Before treating a poll as short — or covered — read the departing caller's own tab
(`sheets.mjs read '<sheet>' "'<Name>'!A1:B8"`, the "YOUR NUMBERS" row) for their exact ID
range. Whoever covers the spot needs to go onto *that* range, not a fresh block — a fresh
block leaves the original numbers permanently undialed and a poll can read "N of M
needed" as fully covered while a 200-number range sits completely untouched. Name the
exact range in both the `#shift-changes` post and the direct ask.

## Check what's already sitting there before asking anyone new

- **`#shift-changes-pacificlinkglobal`** for offers, swaps and withdrawals — a pickup
  offer naming specific days is narrower than a ✅ vote and the narrower one wins.
- **Brendon's own DM threads — read them directly, don't rely on a channel search to
  surface them.** Found 2 Oct 2026: Brendon said a caller (Francine Tena) "just said she
  couldn't work," but `slack_search_public_and_private` across all channel types —
  including `im` — came back empty for her name that day, twice, with different keyword
  combinations. The decline was real: a DM to Brendon at 13:44 ("sore throat... won't be
  able to take tonight's shift"), invisible to search but sitting right there in the
  thread. **The fix is `slack_read_channel` with the caller's own user ID as the
  `channel_id`** (it reads DM history when given a user_id, no separate DM-search tool
  needed) — not a keyword search, which can silently miss a real message. Before telling
  Brendon "nothing in Slack says that" about any specific caller, read that caller's DM
  thread with him directly; only report it truly unfindable once that's come up empty too.
  A caller often tells him directly rather than posting publicly, and this agent posts as
  his account, so those DMs are readable. A DM offer or decline sitting unread is not the
  same as nobody volunteering or nobody pulling out.
- **Unused volunteers from earlier in the week** ("extras") — anyone who put their hand up
  and wasn't needed that day is first in line for the next opening, not a cold ask.

## Before telling Brendon a name is "not yet asked" or "no options left"

Query the caller directory for zero-history people explicitly — don't rely on an
"active/occasional" filter, it silently excludes exactly the tier this skill is about.
If the directory itself might be stale (built on a fixed date, per its own notes), say so
rather than treating an empty query result as proof nobody's available.

## If nobody covers it same-day, say out loud that it rolls forward — don't let it just sit

"Rolls forward" is two separate things, and both need to be stated explicitly or they get
lost as an unresolved loose end in old chat history — which is what nearly happened to
Melburne's NZNP 333 block on 30 Sep (Peterson declined, Lester never replied, and the block
sat unresolved until someone went looking).

1. **The caller's own standing rolls forward.** A pull-out is never held against them —
   they go back in the pool for the *next day they're available*, ranked the same as
   anyone else on the 75/25 score. Never quietly drop them from a future roster. This part
   tends to happen naturally, because nobody's actively punishing anyone.
2. **Their specific undialled number block rolls forward too, and this part does NOT
   happen automatically.** If the three tiers above all come up empty same-day, the block
   doesn't get abandoned or left as "already tried, move on." It carries to that **same
   poll's next running day** — check the schedule for when the poll actually runs again,
   don't assume it's simply tomorrow (a poll doesn't necessarily run daily, and the
   schedule moves under you — see the Rangitikei/Nelson-to-Friday move the same week).

**Before ending coverage on any shift that had an unfilled pull-out, write down explicitly
which block carries forward and to which date** — in `#shift-changes` or wherever the gap
was originally posted, not left implicit. A block that "rolls forward" only in principle,
with no one told when or where, is a block that gets rediscovered by accident days later
or never dialled at all.

## A rolled-forward shortfall is ADDITIVE — "they're already on tomorrow's roster" does NOT cancel it

**This is the mistake that keeps recurring, stated plainly by Brendon after it happened
again on 1 Oct:** a caller already being rostered on the next day's shift is a completely
separate fact from whether their MISSED shift's shortfall has been covered. Do not let the
first fact make you think the second is resolved.

Concretely: Melburne and Yvonne pulled out of Wednesday 30 Sep's NZNP 333, and their
undialled blocks (31001–31200, 32401–32600) never got covered that night. Both of them are
*also* separately rostered on NZNP 333 for Thursday 1 Oct. **Asked "who's missing from
yesterday that needs to be added to today's total," the wrong answer is "nobody, they're
already on today's roster."** That confuses their own Thursday shift (already counted) with
Wednesday's unfilled shortfall (a separate slot that still needs a body on it, on top of
whatever Thursday already has them down for). The right answer counts the shortfall as an
**addition** to today's headcount — it can be filled by the same person doing extra on top
of their own numbers, or by someone else entirely, but either way it is additive, not
already-covered-by-coincidence.

**The general rule: when totalling who's needed "today," always ask two separate
questions per person who missed a prior shift:**
1. Are they confirmed for *today's own* roster? (a yes here answers nothing about #2)
2. Is the shortfall from the shift *they missed* covered yet? (check the specific number
   block, not just whether the person is accounted for anywhere)

Only "yes" to both means nothing needs adding for that person. A "yes" to #1 and an
unchecked or "no" on #2 still means **add it to today's total**.

---
name: reassign-zoom-capacity
description: Load this when a rostered caller has no AU/NZ Unlimited calling plan or NZ number and assigning one fails with "You do not have enough calling plan" — the account is out of spare licences. Covers finding a safe donor, moving their plan and number to the blocked caller, and verifying both ends, without asking Brendon each time.
---

# Reassigning Zoom capacity from someone idle to someone blocked

Standing authorisation granted by Brendon, 2 Oct 2026, after this was done by hand for 5
people (Angeli Christine Capuyan, Lily, Kiezel Candido, Nilyn, Jess — all blocked that
night) pulled from 5 confirmed-idle donors (Lui Jay Dawis, Mary Jane Vergara,
Alpha-Fellice Duldulao, Lorie Bernales, Ronniel Villaver). He asked for it to become a
skill so he doesn't have to authorise it each time. **This is now standing — do it without
asking first, under the conditions below.**

## When this fires

CLAUDE.md already covers the background: "Zoom Phone licences are a reassignable pool,
not a per-person right" (Brendon, 25 Sep) — a missing extension or plan is never a reason
to leave someone off a roster, because the pool gets reassigned on the day. This skill is
the mechanics of doing that reassignment yourself instead of waiting for Brendon to do it
in the Admin Portal.

Trigger: `POST /phone/users/{id}/calling_plans` with `{"type": 201}` on a rostered caller
returns `400 "You do not have enough calling plan."` That response is the proof there is
zero spare capacity — it is not a guess, so don't skip straight to asking Brendon for more
licences before checking whether idle capacity exists to move instead.

## Finding a safe donor — this is the part that matters

A donor is safe **only if they have said, themselves, in Slack, that they are not working
today.** Never infer idleness from a stale directory, from "occasional" status, or from
simply not appearing in today's roster — someone not rostered yet can still be picked up
as a Tier 1/2/3 bench cover before the shift starts (see `cover-a-pullout`), and pulling
their line out from under them mid-chase is the opposite of helpful.

Good signals, in order of confidence:
1. An explicit decline for **today specifically** in `#shift-changes-pacificlinkglobal`
   or a DM — "can't work today", a named reason (sick, travel, family matter), etc.
2. An explicit statement they're unavailable through a date range that covers today and
   the near future (e.g. "can't work Friday to Sunday").

Bad signals — do not use these as the basis for pulling a line:
- Not being on today's roster (they may still get called up as a bench cover).
- Being on today's reserve/backup list ("first in line if a spot opens") — by definition
  they might be needed in the next hour.
- Having offered to work today ("I can work today") — obviously the opposite of idle.
- A high `shifts_24d` / "active" status in the caller directory — they likely need their
  line back very soon, even if they're not confirmed for today. Prefer "occasional" or
  unlisted callers who've given an explicit reason over heavy regulars.
- Someone whose plan/number already reads empty — don't bother, there's nothing to free,
  and an empty record on someone who called in sick suggests this has already been done
  for them once.

Check the candidate's current Zoom record before touching anything
(`GET /v2/phone/users/{id}`) — confirm they actually hold an `AU/NZ Unlimited Calling
Plan` and a number, and note the plan `type` (201) and the number's `id`.

## The moves, in order — free first, then assign, then verify both ends

Direct Zoom Phone API calls (see CLAUDE.md's Zoom section for the token/environment
setup — this needs the Custom-network-allowlisted environment, not the broken connector).

1. **Free the donor:**
   - `DELETE /v2/phone/users/{donor_id}/phone_numbers/{number_id}`
   - `DELETE /v2/phone/users/{donor_id}/calling_plans/201`
   - Both should return `204`. If either 401s with "Access token has expired", refresh
     the token and retry the pair — the first attempt doesn't count as a failed removal.
2. **Assign the recipient**, reusing the exact number just freed (don't draw a fresh one
   from the unassigned pool unless you've checked it's a NZ number per the standing
   "never assign an Australian number" rule):
   - `POST /v2/phone/users/{recipient_id}/calling_plans` with `{"calling_plans":
     [{"type": 201}]}`
   - `POST /v2/phone/users/{recipient_id}/phone_numbers` with `{"phone_numbers":
     [{"id": "<freed number id>"}]}`
   - Both should return `201`.
3. **Verify both ends with a fresh `GET`** — donor now shows empty `calling_plans` and
   `phone_numbers`, recipient now shows the plan and the number, and the number starts
   `+64`. Don't report this done from the write response alone; read it back.

## Telling people

This is an internal admin action, not a message to a caller — it doesn't touch Slack and
isn't covered by draft-everything-send-nothing. But say what you did and who it came from
when you report back to Brendon (which donor, which recipient, why that donor was picked)
so he can object if a pairing was wrong — don't just report "5 blocked callers fixed."

## What this does not authorise

This is scoped to moving a plan+number **the same day**, from someone who has themselves
said they're not working that day, to a rostered caller who is otherwise ready to work.
It does not authorise reaching into tomorrow's or next week's roster to free up capacity
early, and it does not authorise pulling from someone who hasn't explicitly opted out —
if no clean donor exists, say so and tell Brendon the account needs more licences instead
of stretching the "safe donor" bar to find one.

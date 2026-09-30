---
name: verify-work
description: Verify your own output before telling Brendon something is done — call sheets, shares, roster posts, Curia-facing sheet writes, or any batch action touching multiple callers. Load this before reporting a task complete whenever it involved more than one person or a write to a shared file. Building or posting ANY call sheet requires the survey-link check below — this is the major-fuck-up item, check it every time, not just when asked.
---

# Verify before you say "done"

Triggered by the night of 29 Sep 2026: three new hires (Jennifer, Lester, Charlotte) each
opened the wrong poll's sheet and DM'd asking what to do. The instinct was to assume a
sharing bug and start re-sharing. **A full audit of all four polls' Drive permissions
found zero missing or misdirected shares — every one of the 54 rostered callers already
had the correct grant on the correct sheet.** The actual fault was never permissions: it
was that a caller told "here's your link" in a post naming four polls and 54 names has to
find their own row and their own tab, and three people didn't. The fix was a clearer
per-person message, not a re-share.

**The lesson generalises: don't guess which layer broke. Check the layer you're about to
blame before acting on it.** A confused caller looks identical whether the cause is a bad
share, a wrong link, or a cluttered post — and each has a different fix. Verifying first
costs one read call; re-sharing the wrong thing costs nothing and fixes nothing.

## The checklist, by what you just did

**Built or posted a call sheet — THE SURVEY LINK, EVERY TAB, EVERY TIME. THIS IS THE MAJOR ONE.**
Found 30 Sep 2026: all 14 tabs on that night's NZNP 333 sheet carried the SAME wrong survey
link — Tuesday's (`CD369819`), not Wednesday's (`DE393DF2`) — and had carried it since the
sheet was built that morning, before the shift even started. Every active caller had been
dialing against it for over two hours before Brendon asked "is everyone using the link
that is meant for Wednesday" and it was actually checked. Nobody had noticed, because
**every tab agreed with every other tab** — the stale link was copied consistently across
the whole sheet, so cross-tab comparison alone would have found nothing wrong. The other
four polls that same night (Rangitikei 400, Nelson 400, Hauraki-Waikato 500, Waiariki 500)
were all correct — this isn't rare enough to skip checking, and it isn't universal enough
to assume either.

**Why this is the major one and not an ordinary nit:** a wrong survey link is not an
internal inconvenience like a bad share or a confusing post. It means live call data —
real completed surveys, mid-shift — goes into Curia's WRONG dataset. That is a data
integrity problem on the client's side, not just ours, and it cannot be un-sent once a
caller has submitted through it.

**The check, before any call sheet is shared or posted, not after a complaint:** find that
poll's actual current-day `Live:` link from Curia's own source email (Gmail, search
`from:curiaresearch@gmail.com` plus the poll name — David Farrar's forward carries `Live:`
and `Test:` links; use `Live:` only, never `Test:`, and never open either — just read the
URL as text) and diff it character-for-character against the `SURVEY LINK` cell on the
sheet. Do this for every poll being built or reviewed that day, not just the one someone
flagged. If no dated source email can be found for a poll (it happens — some polls only
got one email at setup and never a daily refresh), say so explicitly rather than assuming
the sheet's existing link is current.

**If a stale link is found on a live shift:** fix the cell on every affected tab
immediately, then post to the affected callers by name in `#call-sheets-pacificlinkglobal`
telling them to stop and switch — a call sheet delivery correction, already covered by the
standing exception to post there without asking. Flag to Brendon separately, once, that
some data may already be logged against the wrong survey — whether to tell Curia is his
call, not something to act on unilaterally.

**Shared a file with someone (`share_file`):** `share_file` never reports whether the
grant landed correctly on the *right* file — it just returns success. Read the permissions
back (`get_file_permissions`) and confirm the caller's actual email — from the caller
directory or a fresh `slack_search_users`, never assumed from a display name — appears on
the file you meant, not a similarly-named one. Do this across ALL files in a batch (every
poll's sheet), not just the one that was complained about — a complaint from three people
doesn't mean the other 51 are fine, and it doesn't mean the problem IS sharing either. See
above: it wasn't.

**Posted a message with `<@USERID>` mentions:** Read the channel back and check for the
`|Name` half Slack adds to a real mention (`<@U0C1XDNFMLG|Erika Jane Boiser>`). Literal
`**@Name**` text pings nobody and looks fine to the person who wrote it.

**Wrote to a shared sheet (Curia's results page, a pool, anything `sheets.mjs write`
touches):** Read the written range back and compare cell for cell before calling it done.
`sheets.mjs`'s own write confirmation is "the API accepted this," not "the data landed
where you meant it to."

**Built a list of names from memory or a second hand-typed copy:** Don't. Read it from the
authoritative source (the call sheet tabs actually built, `slack_list_channel_members`,
the directory CSV) every time a count needs checking twice. A hand-retyped list is where
counting errors come from, not the source data — this cost a whole afternoon on 29 Sep
before it was traced.

**Told a caller which poll or sheet they're on:** Before repeating what a roster post says,
check `#shift-changes` for a swap or withdrawal that supersedes it, and check what the
caller actually asked rather than the paraphrase you were given of what they asked —
a garbled retelling ("she's requesting the wrong poll") can misname the actual problem
entirely (Jennifer's real issue was a Zoom login conflict, not a poll).

**Reported a batch operation as complete to Brendon:** State the number you verified, not
the number you intended. "54 shared" only means something if you just read 54 permissions
back, not if you called `share_file` 54 times and assume none of them silently failed.

## What this does not replace

This is a verification pass, not a substitute for the specific rules already in
`CLAUDE.md` — the order-of-operations for call sheets, the mention-format rule, the
build-register and schedule-reading corrections, and so on. Where CLAUDE.md already says
how to check something (reading a schedule, formatting a Curia row, the sheets.mjs
read-back), follow that exact method rather than reinventing a check here. This skill is
the reflex to run the check at all, before reporting done — not a new method to replace
an existing one.

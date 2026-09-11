# Pacific Link Global — agent

An agent that runs Brendon Duong's weekly operation: a NZ virtual-assistant and
call-centre business supplying phone survey callers to the polling company Curia.

Code lives in `agent/`. Python 3.11, stdlib only (openpyxl optional, used only
for reading and writing .xlsx). Tests are unittest, run with
`python3 -m unittest discover -s agent/tests`.

Develop on `claude/business-agent-dev-9jxs55`.

## Standing instruction: keep the build register current

`agent/ops/build_register.html` is the source of a published page Brendon hands
to a technical friend. It is **published at**
`https://claude.ai/code/artifact/4035704f-d01f-4d87-be18-32ac1e2db882`.

**Update it as part of the work, not when asked.** Brendon should never have to
request it. Any session that learns one of the following updates the file and
republishes to that same URL before the session ends:

- a platform limit found, confirmed, or ruled out
- a blocker resolved, or newly blocking
- something built and tested
- an item on "Waiting on you" done, or a new one needed
- **a claim in the register found to be wrong** — correct it and say so in the
  entry rather than quietly deleting it

To republish: read the artifact first (`action: "read"` with that URL), merge
your changes onto what comes back, then publish the file with `url` set to it.
Bump the date in `.eyebrow` and keep the `.tally` counts matching the sections.

Accuracy is the whole point of this document. Every constraint in it should have
been checked against the live tool, and entries say so. If something was assumed
rather than tested, label it as assumed.

## Standing instruction: there is no memory, so read the store first

A session remembers nothing from the last one. The container is wiped and
this file is the only thing that loads automatically. Treat it as the index,
not the data.

**At the start of any session that touches people — rostering, results,
availability, announcements — read the caller directory before doing
anything else.** It holds the name, email and phone of everyone currently
working, plus the name decisions that have already been settled. Without it
a session will re-derive the roster from `team.csv`, which is stale, and
re-ask questions Brendon has already answered.

    Directory location: SharePoint, "Agent Memory" folder — NOT YET CREATED.
    Brendon has to place it; a write to the PacificLinkGlobal site was
    blocked. Until it exists, ask him for the current contacts.csv rather
    than guessing, and do not rebuild the roster from team.csv.

### The call sheet library: how to list it, and what is actually in it

Checked live 11 Sep 2026.

Call sheets live at
`/sites/callsheets/Shared Documents/Call Sheets/<Caller>/<Survey> - DD-MM-YYYY.xlsx`.

**Folder names carry the nickname in brackets** — `Pernelia Villapaz (Lia)`,
`Mary Joy Tongson (Mary T)`, `Mary Joy Villacura (Mary V)`. A path built from
the plain name 404s. Do not guess these paths; list the folder instead.

To list the library with the Microsoft 365 connector, `read_resource` on
`file:///{driveId}/root` and follow the returned item IDs. A **single-segment**
path such as `file:///{driveId}/Call Sheets` is parsed as an item ID, not a
path, and fails with `invalidRequest` — the `root` alias is the way in.
The drive is
`b!lzF-7XOzRkSvOMQGD5WcR7VKtNUzQNBHpfsx_fsYCgr1NocjhVQORpyO0ObWmaU8`.

Two limits found there, both live-tested, neither worked around:

- **The library is empty.** 48 caller folders exist; 47 hold nothing. The only
  file in the whole library is `Kharen Mae Pihana/Wellington Bays 400 -
  10-09-2026.xlsx`. The move to `/sites/callsheets` is filed but unpopulated,
  so there is no declared-numbers half of an audit to read yet.
- **Graph will not extract a call sheet's contents.** Reading that one file
  returns `notSupported` — Microsoft blocks conversion for apps that cannot
  decrypt, which normally means an encrypting Purview label. Per-file and
  enforced by Microsoft; retrying does not help. Brendon can still open it in a
  browser under his own login. **Open question for him:** whether that label
  can be dropped on this library. If it cannot, declared numbers have to come
  from WhatsApp end-of-day or Curia's reporting, never from these files.

SharePoint *search* indexes only that one file in the site, so search is not a
way to survey this library — traverse from `root`.

It must **not** live in the `callsheets` site: that one has external sharing
switched on so callers can edit their own sheets, and a contact directory
cannot sit in a library strangers can reach. It is also deliberately absent
from this repo — `agent/.gitignore` excludes `data/` because it is personal
information about ~40 people. Do not commit it, and do not "fix" that
ignore rule.

When something is settled that a future session would otherwise get wrong —
a name decision, a duplicate ruled out, a process change — write it into the
directory or into this file. That is the whole of the memory.

### Already settled, do not re-ask

- **Bryan Canton and Bon Ryan Canton are two different people.** Never merge
  them, however similar the names look to duplicate detection.
- **Mary V** is Mary Joy Villacura; **Mary T** is Mary Joy Tongson. Two
  people. The short forms are what go on call sheet tabs and rosters.
- **Kris Dolz** is `dolzkris210@gmail.com` — previously unmatched.
- **Lia Villapaz and Pernelia Villapaz are the same person.** Pernelia is the
  name on record, Lia is what she goes by. Her audit history is split across
  both spellings, which flatters whichever half has fewer failures — the two
  need joining in the audit sheet.
- **Jane** is Jane **Labora** (`janewareei919@gmail.com`), not Jane Wareei —
  that was inferred from her email handle and was wrong.
- **Kendall is Hermi.** `kendall.acsva@gmail.com` is Hermi Jeb Edroso.
- **Khars is Kharen Mae Pihana.** Zoom Phone shows her display name as
  `Khars -` (trailing hyphen and all). Confirmed by Brendon, 11 Sep 2026.
- Two different Jeans: **Jean** (`jeannax23@gmail.com`) and **Jean Carla
  Sumarago** (`jeancarlasumarago@gmail.com`). Never merge. Settled 11 Sep by
  Brendon: Zoom's `Jean Sumarago` is **Jean Carla Sumarago**, and the bare
  `Jean` on the roster is **Jean Labora**. Note Jean Labora and Jane Labora
  share a surname and are two people — do not collapse them either.
- **Zoom display name → roster, all confirmed by Brendon 11 Sep 2026:**
  `Jayzel Pureza`→Jayzel Gabunada Pureza · `Tristan Philip Bustamante`→Tristan
  Philip · `Karen Redaniel Boiser`→Karen Boiser · `Melburne Baliad`→Melburne
  Ando Baliad · `Josephus Chris Parages`→Josephus Parages · `Eunilyn
  Lisondra`→Nilyn Lisondra.
- **Jane Wary Rose Espanueva is a real, separate caller.** Elaine audits her as
  `Jane Wary Espanueva`. She is not Jane Labora; she simply has no call sheet
  folder. The earlier worry about a "third Jane" is closed.
- **Elaine writes Khars as `Kharen Ybas`.** Brendon confirmed Zoom's `Khars -`
  is Kharen Mae Pihana, and her row in Elaine's sheet lines up on every figure,
  but the surname differs from the roster folder. Three spellings for one
  person; ask before writing any of them onto a contract or invoice.
- `team.csv` is stale: only 10 of its 33 names are still active, and ~33
  people invoicing now are missing from it. The invoice list is closer to
  the truth. Awaiting Brendon's decision to switch over.

## In flight: auditing shifts from Zoom Phone call logs

The goal is to make the manual audit redundant. `business_agent/calllogs.py`
reads Zoom Phone call logs and groups them per caller per day, and reports per
caller: attempts, answered, talk time, completes, short answers, each break and
their total, time actually worked and shortfall against a three-hour shift.
55 tests cover it and all run without Zoom.

**The Claude Zoom connector cannot do this.** Asking it returns
`403 "User does not have a valid license"` — its search API needs a tier this
account lacks, and Zoom Meetings fails identically, so it is not phone-specific.
Empty result sets from `zoom_phone_call` are that same wall failing quietly.
Do not spend time retrying the connector.

The route is Zoom's own Phone API with a Server-to-Server OAuth credential,
which the 53 Zoom Phone licences cover. The app is built and activated:

    ZOOM_ACCOUNT_ID=TOsH5AVeRhi_dqyWx007JQ
    ZOOM_CLIENT_ID=rkYU0tiVRfCQa9S7GpUL1g
    ZOOM_CLIENT_SECRET  — environment variable, never in a message

**This works as of 11 September**, confirmed twice from separate sessions.
The credentials above exchange for a token and `/phone/call_logs` returns
account-wide rows. 1–11 September 2026 pulled 33,875 calls (32,710 outbound,
1,165 inbound) from 37 distinct Zoom display names. The Manila day boundary is
correct: the 2pm–5pm shift lands inside the right date. The audit is buildable.

Getting there needed one thing beyond the credentials, and it is the part that
will catch a future session out:

**Cloud sessions sit behind a network allowlist and Zoom is not on it by
default.** A session in a `Trusted` environment gets
`CONNECT tunnel failed, 403` for `zoom.us:443` — the request dies before any
credential is checked, so it looks exactly like a bad key. It needs a cloud
environment set to **Custom** network access listing `zoom.us` and
`api.zoom.us`. If Zoom calls fail, test reachability with curl before
suspecting the credentials. A session in the Custom environment reached
`zoom.us/oauth/token` (405, the expected GET-on-a-POST-endpoint) and
`api.zoom.us` (401, expected without a header) with no further setup.

**The allowlist is per environment; the credentials are not.** Confirmed 11
September from a session that had all three `ZOOM_*` variables set and still got
`403 Forbidden` on CONNECT to both `zoom.us:443` and `api.zoom.us:443` — it was
simply not the Custom environment. So having the credentials proves nothing
about reachability. Test it in one line before building anything on it:

    curl -sS -o /dev/null -w '%{http_code}\n' https://api.zoom.us/v2/users

`000` with a tunnel error means the wrong environment, not a bad key. Work that
needs the live API has to be started from the Custom one.

Two related traps: environment variables are copied in once at container
start, so the session that sets them can never see them; and the settings
gear does not appear on a running session's chip — use **Add cloud
environment** instead, whose creation form has the same fields.

**`ANSWERED` was wrong; it is fixed as of 11 September.** It read
`{"Connected", "Answered", "Call connected"}`. Against live data:

| `result` | n (11 days) | median | max | meaning |
|---|---:|---:|---:|---|
| `Auto Recorded` | 15,669 | 14s | 2,841s | **this is a human picking up** |
| `Call Cancel` | 11,457 | 0s | 0s | hung up before ring-out |
| `Call connected` | 5,579 | 3s | **7s** | dialler state, never a conversation |
| `Call failed` | 5 | 0s | 0s | — |

Two of the three names never appear at all and the third caps at 7 seconds, so
the module scored **0 completes for every caller on every day** — and scored it
silently. It is now `{"Auto Recorded", "Connected", "Answered"}`: `Auto Recorded`
added, `Call connected` dropped (counting it would invent 5,579 answered calls
nobody spoke on), the other two kept only for tenants on a different API
version. That gives 953 completes at the 150s threshold across the 11 days.

**Still to confirm with Brendon:** that `Auto Recorded` is what Zoom's own
reporting calls answered. Everything downstream of `Call.answered` —
`talk_seconds`, `completes`, `short_answers` — moves if it is not. The timing
work (`span`, `worked`, `idle_time`, `breaks`, `shortfall`) does not read
`answered` and is unaffected either way.

Also fixed: `calls_for_day` passed its default empty `token` straight to Zoom,
so the real fetcher sent `Bearer ` and got a 401 that reads like a bad
credential. It now mints one itself when no stub fetcher is supplied.

### Calibrated against Elaine's manual audit — 11 Sep 2026

Elaine's `Audit - PL.xlsx` (Drive `1XXdy0Ma3sG_z4MCkdzFxt3FzZGDUx50o`, owned by
`elainejoyabugan22@gmail.com`, shared with Brendon) already covers 10 September,
the same 22 callers. Comparing it to what this module produced:

- **Completes: 16 of 22 exact. 197 against her 204 — 96.6%.** The disagreements
  are 1–2 either way, never a caller-level miss.
- **The 150s threshold is Elaine's own.** She writes "1 completed survey was
  below 2 min and 30 seconds" — 2m30s *is* 150s. The parameter was not a guess
  that happened to work; it matches the manual process exactly. **This is the
  calibration the register kept asking for. It is done.**
- **Total calls: 21 of 22 exact** once counted her way — see below.

**Elaine counts every call log row by Zoom `owner.name`, both directions.** That
was tested, not assumed: grouping that way reproduces her "Total Number of Calls
in Call Logs" on 21 of 22 callers (the 22nd is off by one). `by_caller` currently
groups on `caller_name`, which is the agent on outbound calls and the member of
the public on inbound ones — so it undercounts against Elaine and invents a
caller named `Anonymous` out of withheld inbound numbers. **`owner.name` is the
right grouping key and is evidenced.** Not yet changed.

- **Cumulative off-phone time does NOT reconcile**, and no single gap floor
  makes it. Hers is consistently lower: Lovely Salva 15 min against 26 at a 60s
  floor and 9 at 120s; Gerard Siason 20 against 43 and 14; Eunilyn 18 against 81
  and 57. Florence Bularon is the one that matches (37 against 38). It is a
  human judgement, not a parameter. Brendon's 60s floor is his own decision and
  stands; do not tune it to chase Elaine's number, and do not present the two as
  the same measure.
- Individual break detection is sound: Elaine has Jean Carla Sumarago breaking
  at 2:18–2:22 and this module finds 2:17–2:22; she has Gerard Siason starting
  at 3:28 and so does this. Her breaks read shorter, consistent with her
  measuring start-to-start where this measures end-to-start.
- **Elaine's times are Manila**, and her sheet is one flat table, one tab,
  grouped by a date header row, running March 9 to September 10 2026.

Her column order, worth matching exactly when producing output:
name · completed surveys (WhatsApp) · completed surveys (call logs) · total
calls (WhatsApp) · total calls (call logs) · discrepancy Y/N · details.
The three WhatsApp/discrepancy columns come from what the caller declared and
**cannot be produced from call logs** — leave them blank rather than inventing a
rule. Her Y/N is a comparison of the two halves, not a call-log judgement.

Zoom display names do not match roster names, as expected. Of the 37 names,
19 match a call sheet folder exactly, 10 are near-misses needing a human
(`Jayzel Pureza`/`Jayzel Gabunada Pureza`, `Jahm Peralta`/`CJ Peralta`,
`Eunilyn Lisondra`/`Nilyn Lisondra` and similar), and 7 have no folder at all
(`Jane Wary Rose Espanueva`, `Florence Bularon`, `Leizel Boiser`,
`Lee Daniel Flores`, `Chary Jay Sanchez`, `Cha`, and `Tristan Philip
Bustamante`, whose folder is the shorter `Tristan Philip`). Per the standing
rule these are reported, never auto-merged. Note `Jane Wary Rose Espanueva` is
a **third** Jane spelling and is not yet known to be Jane Labora.

The one name resolved so far: Zoom's `Khars -` is the `Kharen Mae Pihana`
folder, confirmed by Brendon. The other 16 are still open.

There is still no CLI entry point.

## The declared half is moving to Slack

`#results-pacificlinkglobal` (`C0C0ZU714JG`). Checked live 11 Sep 2026.
Brendon's pinned format:

    Kharen — Sun 13 Sept — 12 completed, 3 ring backs, 41 refused

Name · date · completed · ring backs · refused, one message per shift, same
day. Corrections come as a new message starting `Correction:`, never a delete.
Two shifts in a day means two messages.

**This unblocks the audit's declared half** — it does not depend on the call
sheets, which are unreadable and unfiled. But three things are true and easy to
get wrong:

- **The channel is empty.** Zero results posted as of 11 September; it was set
  up the day before and holds only joins and the pinned instructions. The
  parser has never seen a real post. **Do not assume the format holds until
  real messages exist** — people will write `12 completed` and `12 Completed`
  and `completed: 12` and put the date in three formats.
- **There is no total-calls figure in it.** Elaine's sheet compares *two*
  declared numbers against the logs: completed surveys **and total number of
  calls**. Completed + ring backs + refused is not total calls — it omits no
  answers, cancels and failures, which on 10 September were the majority of
  every caller's rows. So the Slack format as written reproduces Elaine's
  completed-survey column and **cannot** reproduce her total-calls column. If
  that check matters, the format needs a fourth number; if it does not, drop
  that column rather than leaving it to be filled by guesswork.
- **Slack is a fourth spelling of every name**, after Zoom, the call sheet
  folders and Elaine's sheet: `boiserkaren21`, `Jane`, `Nilyn`, `Josephus`,
  `Goldy Kaye`, `Jasyl`, `MARY JOY VILLACURA`. **But Slack also exposes the
  email address**, and that is the first unambiguous join key this project has
  had — `janewareei919@gmail.com` ties the Slack `Jane` to the Jane Labora
  record above. Build the identity map on email, not on display names.

### Messaging callers about their own numbers — not yet

Brendon's intent (11 Sep) is to run the audit about an hour after the shift
ends and message a caller automatically about time off the phone. The timing
works: Zoom logs are complete immediately and results land at shift end.

**The blocker is the number itself.** Time off the phone is the one metric that
does *not* reconcile with Elaine's manual audit — this module reads up to four
times higher on the same caller and day (Eunilyn 81 minutes against her 18).
Completes agree 16 of 22; off-phone agrees on one caller in six. Sending
someone an automated message saying they were off the phone for 43 minutes,
when the existing manual method says 20, is an accusation built on the least
reliable figure in the system, delivered to an employee, with no person in the
loop. Get the off-phone measure reconciled first, then draft, then let Brendon
send. **Draft everything, send nothing still applies and has not been
relaxed.**

## How Brendon works

- **Draft everything, send nothing.** A standing setting. Compose messages,
  emails and posts; never send, post or share them without him asking. It is
  also doing real security work — untrusted text from ~100 group members can
  reach this agent, and nothing leaves without a person reading it. Do not
  relax it as a convenience.
- Tell him plainly when something cannot be done, and why, with the actual API
  behaviour. He makes better decisions with the real constraint than with a
  hedge. He has repeatedly been right when he pushed back — treat his objections
  as information.
- He runs this business alone. Anything that needs twenty manual repetitions
  will not happen, so prefer the shape that needs one action from him.

## Where things live

| What | Where |
|---|---|
| Call sheets | Moving to SharePoint `/sites/callsheets` (away from the site holding contracts and GST records) |
| Team comms | Moving to Slack; WhatsApp stays for problems and questions |
| Availability | Slack emoji reactions, one message per day |
| Apps Scripts | `agent/ops/*.gs` — run by hand in Brendon's own account |

## Things that are true and easy to get wrong

- `"USE FROM n"` means n is **still available**; `"USED TO n"` means n is
  **spent**. Opposite arithmetic, both written by hand by Curia.
- Excel drops the leading zero on NZ mobiles. `212507803` is a mangled
  `0212507803`. Restore it, but do not prepend a zero to a landline.
- A caller's block is never split across two number pools. A short block from
  two surveys is worse than a whole smaller one — the caller cannot tell where
  it changes.
- Duplicate names are reported, never auto-merged. A name that could be two
  people is matched to **neither**: tagging the wrong one puts the wrong person
  on a shift.
- Availability has three states, not two: available, unavailable, and
  **no answer**. Never collapse the last two. Leave is normal; silence is a
  caller drifting off, and they need different responses.
- Rates are per **active week**, so leave never reads as unreliability.

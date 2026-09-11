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

### The build register was trimmed on 12 September

Nine solved entries were removed from `build_register.html` and reduced to one
line each under **Closed**, on Brendon's instruction to strip anything that no
longer needs work. Three claims the register got wrong are kept **visible** in
their own Corrections entry — `ANSWERED`, the reading of `notSupported`, and
the Zoom allowlist being per environment. Do not delete those; a register that
hides its mistakes cannot be trusted on the rest.

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
in Call Logs" on 21 of 22 callers (the 22nd is off by one). **`by_caller` now
groups on `Call.agent`, which is `owner.name`** — applied 12 Sep 2026 on
Brendon's go. `caller_name` is the fallback only for an outbound row with no
owner; an inbound row with no owner belongs to nobody, so a withheld number can
no longer become a caller called `Anonymous`.

Counting inbound rows moved **completes to 19 of 22 exact (207 against her
204)**, up from 16 — Elaine counts an answered inbound call over 150s as a
completed survey, which is a ring-back coming good. It also exposed the next
trap:

**A missed inbound call is not presence.** The moment inbound rows counted
toward the agent, a missed call to Cherry Jean Raagas's extension at 7:53am
became a "488 min break" and zeroed her shift. So `Call.presence` is true for an
outbound call or an *answered* inbound one, and **every time measure —
`breaks`, `idle_time`, `span`, `worked`, `shortfall`, `started_at`,
`finished_at` — runs on `ShiftCalls.present`**: presence calls at or after the
1:30pm floor. Counts (`attempts`, `answered`, `completes`) still use every call.
A stray noon call still pins the clock to 1:30 and the wait is still charged.

- **Cumulative off-phone time now reconciles much better, and what is left is
  judgement.** With ring-backs counted as presence: Lovely Salva 14 min against
  Elaine's 15 (was 26); Florence Bularon 35 against 37; Mary Joy Villacura 9
  against her "4 min break" (was 33); Kharen 7 against none noted (was 37).
  Still apart: Nilyn 51 against 18 (was 81), Gerard Siason 42 against 20, Jean
  Carla Sumarago 23 against 9. Those remaining gaps are her measuring
  start-to-start and deciding what counts. Brendon's 60s floor stands; do not
  tune it to chase her number, and do not present the two as the same measure.
- **Someone whose only presence calls are before 1:30pm is not on shift.**
  `ShiftCalls.on_shift` is false, `started_at`/`finished_at` are `None`, and the
  report lists them without scoring them. Two people made one test call each at
  10:37 on 10 September; they are no longer three-hour no-shows. An extension
  that only *received* unanswered calls has `activity == 0` and is not a caller
  at all — counted in a footer, never named.
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

### The CLI, and the 6pm run

`python3 -m business_agent.audit_day [YYYY-MM-DD] [--xlsx PATH] [--json PATH]`
— run from `agent/`. No date means today in Manila. Prints the shift table,
the off-shift list, the names a person has to settle, and Elaine's Details
lines; writes her seven-column layout as xlsx and the same as JSON. The three
declared columns are left blank on purpose — they come from Slack, and the JSON
has `declared_completed`, `declared_calls`, `discrepancy` as `null` for the
merge step to fill. Tested offline through the same `fetch` stub as
`calls_for_day`; proven live on 10 September.

`business_agent/names.py` holds the roster as it stands (the 48 call sheet
folder names plus two people Elaine audits who have no folder) and every
Zoom/Elaine spelling Brendon has confirmed. Names only. `match()` returns
exact, settled, one candidate, ambiguous or unmatched — and **a shared first
name is ambiguous** (`Jean S` is `Jean` or `Jean Carla Sumarago`, so it is
neither). Extend `ALIASES` only on a decision from Brendon, never by inference.

**Shifts run Sunday to Thursday only** (Brendon, 12 Sep). Curia's own Drive
folder corroborates it: September has day folders for 1, 2, 3, 6, 7, 8, 9 and
10 — exactly Sun–Thu. Friday and Saturday have no shift.

**A Routine named "Shift audit — 6pm Manila (Sun–Thu)"
(`trig_01FBfhpRM9zCJp5ygLHrfzKN`) fires at 10:00 UTC, Sunday to Thursday** —
6pm Manila, 10pm NZ until the clocks change on 27 Sep 2026, 11pm after — into a
fresh session in the `Pacific Link` cloud environment
(`env_01Tbj77FEPUKBePCjAFhG2Jn`, the one with `zoom.us` allowlisted).
**That session has no connectors — no Slack.** This is certain, not a guess:
`create_trigger` refuses the `connectors` parameter for this organisation, and
the created Routine (`trig_01FBfhpRM9zCJp5ygLHrfzKN`) came back with the
warning that it "stores no MCP connectors, so the sessions it fires will run
without connector tools". The remedy the API names is for **Brendon to create
or edit the Routine in the claude.ai Routines UI**, where Slack can be attached
— a session cannot pass a connector it was not itself granted through that
path. Until he does, the 6pm run produces the **call-log half only**; the
prompt already tells it to say so and send that half alone. The declared half
stays a manual merge. It checks out this branch, curls Zoom before trusting it, runs
the CLI for today, reads `#results-pacificlinkglobal` for the declared half,
fills the three declared columns where it can, and sends Brendon the xlsx and
a short summary. It posts nothing anywhere, commits nothing, and does not edit
the modules. Brendon chose "report to me only" for its first runs; anything
addressed to a caller is a later decision, and off-phone time in particular is
not to be sent to a caller until it is settled against Elaine's judgement.
Manage it with `list_triggers` / `update_trigger`; the first real test is the
first shift that posts results.

### The second Routine — Curia's call log upload

**`trig_01JuNxDGwHQovzFDYuA2Dyna`, "Curia call log upload (Sun–Thu)"**, created
12 Sep 2026 on Brendon's instruction. Same schedule and environment as the
audit: `0 10 * * 0-4`, `env_01Tbj77FEPUKBePCjAFhG2Jn`. It runs
`calllog_export`, finds or creates the month and `D/M` day folder under the 2026
folder, and uploads one CSV per caller, verifying each returned `fileSize`
against the local byte count.

It was created from a session, so like the audit Routine it came back with **no
connectors** and needs **Google Drive ticked in the Routines UI**. The audit
Routine's Slack was attached that way on 12 Sep and `list_triggers` now shows it
— that is the confirmed working path.

**Brendon was told the cost and chose to run it anyway.** 22 files a night, every
byte through the session twice, roughly 45 minutes a run. The Apps Script remains
the better shape and he knows it; this is the interim.

## Curia's call sheet codes — what a caller writes against each number

From Brendon, 11 Sep 2026. These are the four marks callers put on a call sheet
row, and they are Curia's vocabulary, not ours.

| Code | Means | Call it again? |
|---|---|---|
| `NA` | The number does not ring at all — dead or invalid | No |
| `RB` | Ring back. It dialled and nobody picked up | **Yes**, later |
| `R` | Refusal. They were reached and declined the survey | **Never** |
| `C` | Completed. They took part and finished the survey | No |

`NA` and `RB` are easy to conflate and must not be: `NA` never rang, `RB` rang
and went unanswered. One is a bad number, the other is a person who was out.
Only `RB` goes back into the pool.

**This closes the total-calls gap.** A caller's total calls is
`C + RB + R + NA`. The Slack results format asks for completed, ring backs and
refused — three of the four — so adding `NA` makes the declared total
reproducible and restores Elaine's second check. Without it the declared total
cannot be computed at all, because `NA` was the largest category on 10
September.

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

## Curia's own auditor: raw call logs in Drive

Curia audit Pacific Link independently and need the raw phone records. They
live in Brendon's Drive at **`1ItFWjAuL_k9dpsZ4wR9Z6ixtcqUBvO-1`** — that ID is
the **2026** folder, not a year index — as `Month / D-M / <Caller>.csv`. The day
folder is named `10/9`, no leading zeros. A new year means a new year folder.
Elaine has been exporting these by hand from the Zoom console after every
shift, one caller at a time.

`business_agent/calllog_export.py` builds the same files from the API:

    python3 -m business_agent.calllog_export [YYYY-MM-DD] --out DIR [--everyone]

**This is not the audit.** Nothing in it judges anyone; it is the call log,
reproduced. `audit_day` is the module that scores a shift.

Verified against Elaine's real export of 10 September: **row counts match
exactly** (170 for Eunilyn Lisondra against her 170), and the phone-number
formatter matches on **36 of 36** number shapes taken from that file.
Sixteen of the eighteen columns are reproduced. Two caveats, both real:

- **`Device` cannot be reproduced.** The console names the softphone build
  (`Windows_Client(7.1.5.43453)`); the `call_logs` API returns it in no field.
  The column is written empty rather than guessed.
- **The API and the console spell two results differently** — `Call Cancel` for
  `Call Cancelled`, `Call connected` for `Call Connected`. `EXPORT_RESULT` maps
  them, so do not "fix" either vocabulary to match the other.

Times in these files are **New Zealand**, not Manila — that is what the console
exports and what Curia already hold. The shift audit is Manila. Do not
unify them.

Number grouping is libphonenumber's and cannot be restated as a rule. Only
`0210` and `0274` group as four digits; `0211`, `0212` and `0273` group as
three. Eleven-digit mobiles split by scheme: `020` goes 3-4-4
(`020 4005 3130`), everything else 3-3-5 (`027 365 36523`, `029 020 40106`).
A number the console cannot group at all it prints with a **leading space** and
no country — ` +6410091`. Every one of those was found by a rebuilt file
disagreeing with a real one, never by reasoning. **Do not add a prefix to
`_FOUR_DIGIT` on a hunch** — check it against a real exported file first, and
`check_formatting` measures a rebuild against one.

Both settled by Brendon 12 Sep:

- **22 files, not 28** — the people who worked the shift, as Elaine uploads it.
  `write_day(..., on_shift_only=True)` is the default; `--everyone` overrides.
- **Full names, hers where she has one.** `names.EXPORT_FILENAME` title-cases
  the two lowercase Zoom names (`katherine boiser` → `Katherine Boiser`) and
  maps `Khars -` → `Kharen Ybas`, which is what Curia already hold. The full
  name is written **inside** the file too, not just on it — Zoom's `Khars -`
  otherwise renders as `Khars - - Ext. 1030`, which an auditor should not have
  to decode.

**The `Kharen Ybas` / `Kharen Mae Pihana` surname clash is still unsettled.**
Elaine's spelling is used because Curia's folder already has it. Ask before
either reaches a contract or an invoice.

### Dummy run, 12 Sep — it works, and Curia can see it

`Eunilyn Lisondra.csv` was uploaded to a folder named
`TEST 10-9 (agent rebuild — safe to delete)` inside September
(`1Dz0TgR1m3uHpMzDjzMd8X2ex-LiWSAsg`). It landed as real `text/csv`, 26,448
bytes, 170 rows. **Delete that folder once checked.**

- **Sharing is inherited and reaches Curia.** The uploaded file's permissions
  list `curiaresearch@gmail.com` as writer, along with Elaine, Logan and three
  others. Nothing has to be shared by hand; a file dropped in the right folder
  is visible to the auditor immediately.
- **Size difference is expected and explained.** Elaine's file is 31,155 bytes
  against this 26,448. The 4.7KB gap is the `Device` column — 170 rows of
  `Windows_Client(7.1.5.43453)` that the API does not return. It is not
  truncation.
- **A real constraint on automating this.** File content has to pass through
  the session to reach Drive, and each caller's CSV is 30–70KB with ~22 a day.
  Reading one back through Bash is truncated above ~30KB and has to be read in
  halves. It works, but it is slow and expensive as a daily job. If that proves
  impractical the fallback is Brendon dragging the generated folder in himself,
  or an Apps Script inside his own account. **Flagged, not solved.**

`agent/ops/routine_prompts.md` holds both Routine prompts ready to paste into
the claude.ai Routines UI, with the settings and the connectors each needs.

**Uploading a full day through a session is the wrong shape and was stopped.**
On 12 Sep an attempt to upload all 22 files got one done and abandoned the
rest. The arithmetic: 880KB of CSV, and every byte has to pass through the
session twice — once read (Bash truncates above ~30KB, so a 45KB file needs
two or three reads) and once written into `create_file`. That is roughly 60
tool calls and 450K tokens for one day, every day, to produce something
Brendon can drag into Drive in thirty seconds. **The mechanism is proven and
the scale is not.** Do not grind it out again without asking; the routes worth
taking are a folder he drags in, or an Apps Script inside his own account with
no size cap, the same shape as `allocate_callsheet.gs`.

## Curia's results page — the sheet Curia read

`https://docs.google.com/spreadsheets/d/1H5xMVXnqBohxLDOcWHXNgPbeN0BoZ3BQWKzxZAlyRAQ`
— "PL FOR CURIA STAFF RESULTS RECORD". Read live 12 Sep 2026. This is the
**declared** half, formatted for Curia, and Brendon wants it automated.

Two banded column groups: **"1: PL to complete"** and **"2: Curia to complete"**.

| Column | Source |
|---|---|
| Staff Member | roster name, full |
| Date | `11/1` — **day/month, no leading zeros**, same convention as the Drive day folder |
| Phone | the caller's Zoom DID, e.g. `04 887 6326` — **this is in the call logs already** |
| Poll | survey name, e.g. `NZNP 1000`, `Corp 1000`, `ACT 500`, `Whanganui` |
| GNA · RB · R · C | declared by the caller — Curia's four codes |
| Total No. of calls made | `GNA + RB + R + C` |
| Shift Notes | free text, e.g. "Had breaks between 2:13 - 2:18" |
| Status | **Curia's**, not ours — "processed for audit 01/03/26". Never write it. |

Rows are grouped by date with a **Total row** per day summing GNA/RB/R/C and
total calls. Blank spacer row between days.

Three of these are already producible: **Phone** from the call log `From`
field, **Total** by arithmetic, and **Shift Notes** from the audit's own break
detection, which finds breaks in exactly that start–end shape. GNA/RB/R/C come
from Slack. Only **Poll** needs a source — Curia's survey email names it.

**Writing to it is blocked.** The Google Sheets connector returns:

    Access to this tool requires that your Google Cloud project (454021123290)
    be enrolled in the Google Workspace Developer Preview Program.

Confirmed live on both `get_values` and `get_spreadsheet`, 12 Sep 2026. Not a
permissions problem on the sheet and not fixable from a session.

**Reading it works** — `mcp__Google_Drive__read_file_content` on the sheet ID
returns the whole thing as markdown tables. So the connector can read the sheet
and cannot write it.

Do **not** try to write it with `Google_Drive__update_file`. That replaces file
content wholesale and would destroy the merged header bands, the per-day totals
and Curia's own Status column, on a live document Curia read. The routes are an
Apps Script in Brendon's own account, enrolling that Cloud project, or a
paste-ready block he pastes in himself.

## Curia's survey links arrive by email

From `curiaresearch@gmail.com`, forwarded from David Farrar
(`david@curia.co.nz`), subject lines like "Fwd: NZ tonight", "Fwd: Kapiti poll",
"Fwd: ACT link". Confirmed 12 Sep 2026. Each carries two links:

    Live: https://survey.cmix.com/<id>/<id>/en-US
    Test: https://test.cmix.com/#/?cmixPrj...

Brendon's idea is to read the survey and derive a per-survey expected length, so
the completes threshold stops being a flat 150s for every poll. Worth doing.

**Never open the Live link.** It is Curia's real data collection — fetching it
can register as a partial response and pollute the dataset they are paid to
produce. The **Test** link is the one built for this. Ask before opening either.

Note the 150s flat threshold is Elaine's own and currently agrees with her on 19
of 22 callers. A per-survey threshold has to be validated against real data
before it replaces that, not assumed to be better because it is more specific.

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

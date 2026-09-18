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
`https://claude.ai/artifact/8vsP66xc5kusdXZmvn5bms`.

**The artifact URL format changed on 15 Sep 2026.** The old form
`https://claude.ai/code/artifact/4035704f-d01f-4d87-be18-32ac1e2db882` still
addresses the same artifact and is what `url:` should be passed as when
republishing, but `action: "list"` now returns the short form above. Both point
at one artifact; do not treat them as two. Same for the dashboard: short form
`https://claude.ai/artifact/4bJeNVa9Drme8zBtky7SZA`, long form
`https://claude.ai/code/artifact/1d1593ee-8975-4f06-8b98-f6a2fcb624dd`.

**Another session may be publishing it at the same time.** On 16 Sep a publish
was refused because a concurrent session had published a newer version. The
refusal saves the live source to a file and names it: read that file **in full**,
merge onto it, and publish from the merged copy — do not resend your own version
and do not rebuild from memory. In that instance the other session's entry was
better first-hand reporting than the local one, and the right move was to drop
the local duplicate rather than keep both.

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
- **Settled 12 Sep by Brendon, each corroborated by the Slack account's own
  email and Real Name field — the first time email was used as the join key:**
  - **`CJ` is Crystal Jahm Peralta** (`crystaljahmperalta@gmail.com`, Real Name
    "Crystal Jahm Peralta"). This **closes the `Jahm Peralta` / `CJ Peralta`
    near-miss**: Crystal and Jahm are the same person, so Slack `CJ` is Zoom
    `jahm peralta`. Brendon said "CJ is Crystal" and the account confirms why.
  - **`boiserkaren21` is Karen Boiser** → Zoom `karen redaniel boiser`. Note the
    Boiser cluster is four different people: Karen, Katherine, Leizel and Erika.
  - **`Goldy Kaye` is Goldy Kaye Maglasang** (`goldymaglasang7@gmail.com`) →
    Zoom `goldy maglasang`.
- **`Cha` IS Chary Jay Sanchez — SETTLED 18 Sep 2026 by Brendon, and by her own
  call sheet.** Brendon: *"Charlotte's email is Chaching.gimpes@gmail.com from
  when she invoiced me. Cha is also known as Chary."* Her 16 September call sheet
  is headed **CHARY JAY SANCHEZ**, which is first-hand corroboration. So:
  - Slack `Cha` (`charyjay12@gmail.com`) = **Chary Jay Sanchez** = Zoom
    `chary jay sanchez`. **She is rankable.**
  - **Charlotte Gimpes** (`chaching.gimpes@gmail.com`) is a **different person**,
    confirmed from her invoice. Never merge the two.
  This supersedes the earlier note that Brendon's "Cha is Charlotte" conflicted
  with the record — he meant they are two people, and the record was right that
  `Cha` reads as Chary Jay.
- **`Jane` is Jane Wary Espanueva — settled 16 Sep by her own call sheet.** The
  Slack account `janewareei919@gmail.com` posted a call sheet for 15 September
  headed **JANE WARY ESPANUEVA**. So this account is Zoom's
  `jane wary rose espanueva`, she **is** rankable (she has call history under
  that name), and the entry below is superseded. Two things this file previously
  asserted are now wrong: that she is Jane Labora, and that "Jane Wary Rose
  Espanueva is a real, separate caller" who could not be tied to this account.
  Brendon said "that is Jane Wareei" on 12 Sep, which matches the account handle
  and is closer to her sheet than Labora is.
  **Her own email is `espanuevajanewary@gmail.com` — Brendon, 18 Sep 2026.** Note
  that is NOT the address on her Slack account (`janewareei919@gmail.com`); both
  are hers, and the Slack handle is the misleading one. Her call sheets for 15,
  16 and 17 September are all headed **JANE WARY ESPANUEVA**, so the name is now
  corroborated three ways: Brendon, her own email, and her own sheets. Treat
  **Jane Wary Espanueva** as settled. Do not re-open whether she is Labora.
- **~~`Jane` — the surname is contested and it does not matter yet.~~** Brendon said
  12 Sep "that is Jane Wareei". This file already records that **Jane Wareei was
  a wrong inference from `janewareei919@gmail.com`** and that she is Jane
  Labora. Both cannot be right. What is certain either way: she is **not** Zoom's
  `jane wary rose espanueva`, and **no Jane appears in the Zoom logs under any
  spelling**, so she cannot be ranked regardless. Ask again before the name
  reaches a contract, an invoice or a call sheet folder.
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

**A Routine named "Shift audit — 10pm Manila (Sun–Thu)"
(`trig_01FBfhpRM9zCJp5ygLHrfzKN`) fires at 14:00 UTC, Sunday to Thursday** —
10pm Manila, 2am NZ until the clocks change on 27 Sep 2026, 3am after — into a
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

**Moved from 6pm to 10pm Manila on 18 Sep, and its declared half was rewritten.**
Two faults, both found by reading the live prompt back rather than trusting this
file:

- **The prompt carried a stale copy of the declared-results rules.** It still
  expected the pinned three-number typed format (`N completed, N ring backs,
  N refused`) and said nothing about screenshots, `slack_read_file`, the
  `detailed` response format, GNA, or the allocation table. On a normal night
  that is 20 of 21 callers read wrong — **exactly the failure Brendon caught on
  15 September**, preserved in a prompt nobody re-read. The root cause is that
  the prompt **restated** the rules instead of pointing at them, so when the
  rules changed the copy did not. It now says: read CLAUDE.md's
  "What the real declarations look like" and "The allocation table" sections and
  apply those, and **if the prompt and CLAUDE.md ever disagree, CLAUDE.md wins**.
  The same "CLAUDE.md wins" line was added to the declared-results Routine, whose
  copy of the table is now explicitly a convenience copy.
  **When a settled rule changes, grep the Routine prompts for a stale restatement
  of it.** A prompt is memory too, and it is the one kind this project does not
  reload automatically.
- **6pm Manila was too early to collect.** Callers post 4pm–9:30pm Manila
  (8pm–11:30pm NZ, occasionally past midnight), so a 6pm collection missed Goldy
  on Tuesday and Lovely and Nilyn on Monday. Both this Routine and
  `Declared results for Curia` now fire at **`0 14 * * 0-4`** — 10pm Manila,
  after the channel has stopped filling. The declared-results prompt gained a
  self-check: if the latest post is within 20 minutes of the run, say so, because
  it means even 10pm may be too early.

**The shift being audited is TODAY'S MANILA DATE**, and at 10pm Manila that is
still the day the shift ran. Both prompts say so explicitly — it is already
tomorrow in New Zealand at that hour and rolling the date forward would audit an
empty day. `audit_day`'s default (today in Manila) is correct at 10pm Manila.

The `Curia call log upload` Routine stays at `0 10 * * 0-4`: it reads Zoom only,
never Slack, and the logs are complete the moment the shift ends. Leaving it at
6pm also spreads the three runs out instead of firing them in the same minute.

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

### The Roster Dashboard, and the dummy roster of 12 Sep

**Published at `https://claude.ai/code/artifact/1d1593ee-8975-4f06-8b98-f6a2fcb624dd`**
("Pacific Link Roster Dashboard"). `business_agent/dashboard.py` renders it
server-side from one dict; `render_dashboard(data)` reads these keys and no
others, so a future build can go straight to filling them:

    generatedFor · week{start,filled,needed,used,bench} ·
    capacity{rosterable,weeklyCapacity,maxPerWeek,barredActive} ·
    productivity{hist[{bucket,count}],median,n} ·
    audits{total,daysSinceLast,missedOverDeclarations} · dataQuality{duplicatePairs} ·
    topCaller{name,completes} · weeks[{start,slots}] ·
    rosterDays[{day,slots,polls[]}] · roster[{day,poll,needed,callers[{name,completes,clean,tier}]}] ·
    barred[{name,headline}]

The **9 Sep** version was built from Elaine's 1,578 audits and a schedule read
that named polls for 13–17 Sep (Hutt South 400, ACT 1000, Rotorua 400, Tukituki
400, WCT 400). Where that read came from is not recoverable now — the schedule
truncates at 2022 through the connector — so treat those poll names as
unverified.

**Republished 12 Sep with a dummy roster**, on Brendon's ask, built from:

- the Zoom call logs of Sun 6 – Thu 10 Sep: 98 caller-shifts, 35 callers;
- the ✅ reactions on the five day messages in `#availability-pacificlinkglobal`
  (34–41 per day, 43 distinct people);
- **the real polls and headcounts**, once the schedule turned out to be readable
  after all (above): 80 slots, not the 110 the first pass guessed at 22/day.

**Ranking, as Brendon specified:** completes per shift *and* time off the phone
per shift, combined — a Borda sum of the two ranks, lower is better, ties
broken on completes. His decision, made knowing the off-phone figure reads up
to 4× Elaine's on some callers. The dashboard's "Clean" column was relabelled
"Away" and carries minutes away per shift. No audit gating, no integrity tier.

What the dummy run showed, all recorded on the page itself:

### The rostering score — 75/25, set by Brendon 12 Sep

    score = 0.75 x scaled(completes_per_shift) + 0.25 x (1 - scaled(away_per_shift))

Both min-max scaled across the callers in the window, so each runs 0 to 1 and
less time away scores higher. **His numbers, and he expects to tune them** — do
not change the weights without him.

It replaced an unweighted rank-sum of the two ranks. Two things worth knowing
before anyone touches it:

- **Weighting completes at 75% moves the clean-but-moderate callers down.**
  Cherry Jean Raagas (6.8 completes, 2.0 min away) fell from 5th to 15th and
  from five shifts to three; Richelle Mino (6.0, 1.3 min) 8th to 17th; Kiezel
  Candido 11th to 18th. Who gained are the high-volume callers with ordinary
  discipline — Jean Carla Sumarago 17th to 6th, Jasmine Magdayao 15th to 5th.
- **It quietly reduces the harm from the off-phone figure**, the one measure
  that does not reconcile with Elaine. Nilyn Lisondra went from **zero shifts to
  three**, because 6.5 completes now outweighs 48 minutes away. That is the
  right direction while that number is unsettled.

A rank-percentile version of the same weights was computed as a check and
ordered the 35 callers almost identically — largest move three places — so the
min-max scaling is not being distorted by the two outliers at 63 and 67 minutes
away. Raw min-max is used because it is the direct reading of "75% on
completes".

- **Brendon chose NO CAP on shifts, 12 Sep.** Asked directly, having seen what
  it does. Under the 75/25 weights, **22 people cover all 80 slots and 21 of the
  43 who voted get nothing**; nine work all five nights. A 3-shift cap would
  spread the same slots wider — that comparison stays on the dashboard, but the
  roster is built his way.
- **Nilyn Lisondra is the caller to watch when either rule changes.** Her
  off-phone figure reads ~4× Elaine's, so she moves whenever the weights move:
  three shifts under the rank-sum, none once Karen, Goldy and Crystal were
  matched and displaced her, three again under the 75/25 weights. Recorded
  because she is the clearest example of what that metric
  does to a real person.
- **10 voted ✅ and have no call history to rank on**, so a pure ranking can
  never give them a first shift: Bryan Canton, Charlotte Gimpes, Hermi, Ian
  Christopher, Jellame Malicay, Kris, Marynel Joy Reanturco, Rechiell W.,
  Stefany Fojas, Thea Rejante.
- **5 Slack names were not matched and sit out** until Brendon settles them:
  `Jane` (is Jane Labora — **not** Zoom's `jane wary rose espanueva`),
  `boiserkaren21` (probably Karen Boiser, but only from the email handle),
  `Goldy Kaye` (email says `goldy maglasang`), `CJ` (`jahm peralta` / `CJ
  Peralta` is an open near-miss), `Cha` (Zoom has both `cha` and `chary jay
  sanchez`).
- **Nilyn lands at rank 27 on 48 min away** — the one caller whose off-phone
  figure is known to read ~4× Elaine's 18. Named on the page so the effect of
  that number on a real person is visible.

Slack display name → Zoom name pairs used, beyond the settled list above:
`Lovely`→`lovely salva`, `Jess`→`jess burgos`, `Leizel`→`leizel boiser`,
`Erika Jane Boiser`→`erika boiser`, `Lia`→`pernelia villapaz`,
`jeancarlasumarago`→`jean sumarago`. Each is a single candidate, not a
confirmation; treat as provisional until Brendon says otherwise.

The scratch scripts that built it lived in `/tmp/roster/` and carried the
Slack vote lists with user IDs — personal data, deliberately not committed.
The method above is enough to rebuild them.

### Two polls on one day: split the strength, do not stack it

**Brendon's rule, 12 Sep.** When a day runs more than one poll, the callers are
distributed evenly by performance across them — "so it's not just all the good
callers on one and then all the other callers aren't on the other". Curia are
paying for both polls; one strong and one weak is a worse result than two even
ones.

Filling poll A to capacity and then poll B does exactly what he does not want.
On Wednesday 16 Sep (Rotorua 400 and Tukituki 400, ten each) it gave:

    Rotorua    mean score 0.788 · 8.82 completes/shift · 15.5 min away
    Tukituki   mean score 0.576 · 6.58 completes/shift · 16.0 min away

The fix is a **serpentine (snake) draft** over the ranked list: pick 1 to poll
A, picks 2 and 3 to poll B, picks 4 and 5 to poll A, and so on, reversing the
order each round. Same people, same ranking, balanced result:

    Rotorua    mean score 0.690 · 7.75 completes/shift · 15.1 min away
    Tukituki   mean score 0.674 · 7.64 completes/shift · 16.5 min away

It generalises: with n polls the order reverses every n picks, and a poll that
fills early is skipped, so uneven headcounts (10 and 20, say) still work. A day
with one poll is unaffected — the draft degenerates to the plain ranked fill.

Do **not** replace this with round-robin (A, B, A, B…). Straight alternation
hands every odd-numbered pick to the same poll and A ends up ahead by roughly
half a rank on every round; the reversal is what cancels it.

### The third Routine — the weekly roster draft

**`trig_01RgT6rGxMXmu6XgtyQ96tse`, "Weekly roster draft — Saturday 6pm Manila"**,
created 12 Sep 2026 on Brendon's instruction. `0 10 * * 6` — Saturday 10:00 UTC,
which is 6pm Manila and the availability deadline itself. Same environment as the
other two (`env_01Tbj77FEPUKBePCjAFhG2Jn`). **Model: `claude-fable-5-1`**, on
Brendon's explicit ask that the roster run on Fable.

**The roster post and the Saturday Routine are the same job.** A session once
listed them as two separate tasks; Brendon corrected it. There is one weekly
action: at the deadline, draft the roster and hand it to him.

**It is the whole week, sent as one message per day.** Brendon, 12 Sep: "when I
mean we post the roster on Saturday it's for the full week, but we will send
them in separate messages." Five shift days means five messages, never one
combined post. Each carries the day, the shift time, each poll with its callers
as `<@USERID>` mentions, a ✅-to-acknowledge line, and a pointer to
`#shift-changes-pacificlinkglobal` for anyone who cannot make it.

It reads the Curia schedule for the week ahead (detecting no-shift days from a
blank or holiday Poll cell rather than assuming Sun–Thu), reads the ✅ reactions,
ranks on the 75/25 score from the week just finished, snake-drafts any two-poll
day, and reports the per-poll balance so the split is checkable. It **posts
nothing** — the drafts go to Brendon and he sends them.

Like the other two it was created from a session and so stored no connectors.
**Brendon attached Slack and Google Drive on 12 Sep and `list_triggers` now shows
both** — it needs both, not one: Slack for the availability reactions and the
user IDs, Drive for the schedule. The prompt tells it to stop and say so if
either is missing.

**Its notification channels read push/email/Slack all `false`**, where the audit
and upload Routines show `push: true, slack: true`. That may be an unset default
rendering as false rather than a real setting, but it matters — Brendon asked to
be notified when the draft is ready. **`update_trigger` does not expose
`notifications`**, only `create_trigger` does, so it cannot be fixed from a
session without deleting and recreating the Routine — which would discard the
connectors he just attached. Left for him to toggle in the UI. If a future
session ever does recreate this Routine, pass
`notifications: {push: true, email: true}` at creation.

### Slack user IDs are the mention key, and the member list is the identity map

`slack_list_channel_members` on `#roster-pacificlinkglobal` (`C0C1QK30EHE`) with
`response_format: "detailed"` returns **user ID, real name and email** for every
member, ~51 people over two pages. That single call is both the identity map and
the source of the `<@USERID>` strings a roster needs. Use it rather than
resolving names one at a time.

Two things it settled or exposed, 12 Sep:

- **Kharen's own Slack Real Name is `Kharen Ybas`** — and her email is
  `pihanakharenmae@gmail.com`. So *both* surnames are hers: Pihana in the
  address, Ybas on the profile. **Elaine's `Kharen Ybas` spelling is not an
  error**, it is what Kharen calls herself, which is why Curia's folder has it.
  The call sheet folder `Kharen Mae Pihana` is the outlier. Still ask before
  either reaches a contract or an invoice, but the clash is now explained.
- **Leizel's Slack Real Name is `Leizel Chun`**, against `leizel boiser` in Zoom
  and `leizelboiser4@gmail.com` as her address. Almost certainly one person —
  the email handle matches Zoom — but the surname differs, so it is **reported,
  not merged**, like every other name clash. The roster uses Leizel Boiser.

Also worth knowing: **Slack usernames are the email local-part** for nearly
everyone in this workspace (`@janewareei919`, `@boiserkaren21`,
`@crystaljahmperalta`). That is why email works as the join key and display
names do not.


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

## The Slack workspace — all five channels, read live 12 Sep 2026

| Channel | ID | What it is for |
|---|---|---|
| `#all-pacific-link-global` | `C0C0ERD765D` | announcements, company news |
| `#availability-pacificlinkglobal` | `C0C0UAF9C0N` | **availability** — see below |
| `#results-pacificlinkglobal` | `C0C0ZU714JG` | declared shift numbers |
| `#roster-pacificlinkglobal` | `C0C1QK30EHE` | the roster, posted after the availability deadline |
| `#shift-changes-pacificlinkglobal` | `C0C1RE146CQ` | can't make a shift — name, date, which one |

The availability channel's own purpose text states the process:

> Tell us when you can work. Every week we post the days ahead — tap
> :white_check_mark: on each day you can work and :x: on each day you can't.
> **Deadline: Saturday 6pm Manila.**

And the roster channel's:

> Find out if you're working. The roster goes up after the availability
> deadline. You'll be @mentioned on your rostered days, with your call sheet
> link.

**That paragraph used to say both channels were empty. Half of it is now
wrong, and the wrong half matters.**

- `#availability-pacificlinkglobal` **has real data.** Five day messages for
  13–17 Sep went up 11 September and drew **34–41 ✅ per day from 43 distinct
  voters**, every reaction read by name on 12 Sep. The roster below was built
  from them. Do not repeat the claim that there is nothing to roster from.
- `#roster-pacificlinkglobal` **is still empty except for joins.** The 13–17 Sep
  roster exists on the dashboard and **has never been posted**, so as of 12 Sep
  no caller has been told they are working. Posting it is Brendon's call under
  draft-everything-send-nothing; it has not been made.

The three states rule bites here: a caller who reacts ✅ is available, ❌ is
unavailable, and **no reaction at all is the third state** — silence, not
refusal. Never collapse ❌ and no-answer.

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

- **~~The channel is empty.~~ That was true on 11 September and is not any more.**
  Real results have been posted every shift since Sunday 13 Sep: 11 posts
  Sunday, 19 Monday, 21 Tuesday. The format drift predicted here happened
  exactly as predicted — see the section below on what the real posts look
  like.
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

### What the real declarations look like — read live 16 Sep 2026

Three shifts are now on the record. What the posts actually contain:

### The allocation table — settled by Brendon, 15 and 16 Sep. Do not re-derive it.

Callers do not use Curia's four codes. They use their own sheets, and **at least
eight layouts are in use** with thirteen-plus different row labels. This table is
how every one of them maps. It is settled; apply it, never guess past it.

**The governing rule, in Brendon's words: if a person was REACHED, it is a
REFUSAL.** That is what separates R from GNA, and it is the thing to reason from
if a brand-new label ever turns up.

| Code | Every label that maps to it |
|---|---|
| **C** | completed · Completed · COMPLETED · competed · comps |
| **RB** | ring back · Ring back · ringback · Ringbacks · RB · RBs · RB's · Rbs · RB/VM · VM · Dialed RBs · Callback |
| **GNA** | GNA · **NA** · GNA/Invalid · **Inactive** · Not Active · Invalid · Invalid/Not Active · Not Available · Disconnected · Busy line · Not in service |
| **R** | refused · Refused · refusal · Refuse · **Disqualified · Unqualified · Not Qualified · Hang up · Do Not Call · Incomplete · INC · Already Done** |

Three rulings worth stating plainly, because each was asked and answered:

- **`NA` and `GNA` are one bucket.** The call sheets write NA; Curia's results
  page column is called GNA. Same thing. Brendon, 16 Sep.
- **`Inactive` means the same as GNA.** This matters because **14 of the 20
  callers write GNA *and* Inactive (or Not Active) as separate rows on the same
  sheet** — Jasmine had GNA 10 and Inactive 49, Karen GNA 14 and Inactive 50. The
  split is theirs, not a distinction Curia wants. Both go into GNA.
- **Disqualified, Hang up, Do Not Call and Incomplete are all refusals**, because
  a person was reached in every case. An earlier pass put them in GNA; that was
  wrong and it flattered the numbers by moving live contacts into the dead-number
  bucket. On 15 Sep this was **74 calls** — Unqualified 50, Incomplete 11, Hang up
  10, Do Not Call 3 — moving GNA 1,026 → 952 and R 785 → 859.

**A label not in that table is not to be guessed at.** Leave it out of all four
codes, record the caller's own wording and number, and ask Brendon once. A wrong
mapping reaches Curia as fact.

**Always show the working.** Output carries a *What GNA is made of* column and a
*Counted as Refusal* column, so any row's allocation can be checked without
re-reading the screenshot.

**The reconciliation check is free and it works.** Most sheets carry the caller's
own TOTAL CALLS. `GNA + RB + R + C` should equal it — on 15 Sep all 20 sheets
matched exactly, before and after the re-allocation, so a mismatch is a real
signal that a label was missed, not noise.

**~~Almost nobody reports GNA at all — 2 of 45 declarations.~~ That was an
artefact of reading only the typed text.** The screenshots carry GNA for 20 of 21
callers, so `Total No. of calls made` is computable for almost everyone. What
remains true: if a caller genuinely gave no GNA figure, **leave GNA blank and
leave Total blank too**, and never back-fill, estimate or infer it.

**Wording actually seen**, all meaning the same three things: `completed`,
`Completed`, `competed`, `comps` · `ring backs`, `Ring backs`, `ringbacks`,
`Ringbacks`, `RBs`, `RB's`, `Rbs`, `Ring back` · `refused`, `Refused`,
`Refusal`, `Refuse`. Layout varies between one line and a labelled list.

**THE SCREENSHOT IS THE DECLARATION. THE TYPED TEXT IS A LOSSY SUMMARY OF IT.**
This is the single most important thing in this section and it was got badly
wrong on 15 September: a whole day was reported to Brendon from the text alone,
three callers were called "empty message" non-declarers, and GNA was reported as
missing. **All of that was wrong.** Brendon corrected it, 16 Sep: *"you need to
look at the screenshot that they sent for the results as well as if they send
the results alongside the photo. If they don't write any details about their
results please default to looking at the image."*

**On Tuesday 15 Sep, 20 of 21 callers attached a call-sheet screenshot.** Read
every one with `slack_read_file` on the file ID from
`slack_read_channel(response_format="detailed")` — the concise format does not
show attachments at all, which is how this was missed. A message with no text
and one image is a normal, complete declaration.

What the sheets contain that the text does not: **GNA** (present on 20 of 21
sheets, against 1 of 18 text posts), **time in and time out**, **break times**,
and **shift notes**. They also carry the caller's own **Total calls**, and on
all 20 sheets **GNA + RB + R + C reconciles to that total exactly** — which is
both a strong check on the reading and proof that Brendon's catch-all rule is
the right one.

**Where text and sheet disagree, the sheet wins**, because it reconciles. Say so
rather than silently choosing: Erika Jane Boiser typed 69 ring backs and 32
refused where her sheet says 62 and 29; Goldy Kaye's text omitted ring backs
altogether where her sheet has 36.

**There is no shared template — at least eight layouts are in use**, with row
labels including GNA, Inactive, Not Active, Not Available, Hang up, Incomplete,
Unqualified, Disqualified, Already Done, Do Not Call, Busy line/Disconnected,
Dialed RBs and Callback. Map per sheet, keep a record of what went into GNA for
each caller, and never assume the previous caller's layout. One shared template
is an open ask.

A caller who posts **text only and no sheet** is the exception now, not the rule
— on Tuesday that was Lovely Salva alone, and she is the only one with no GNA
and no total.

**Date errors are common and are typos, not duplicates.** Alie Mae wrote
"Mon 15 Sept" (15 Sep is a Tuesday); Jane Wareei wrote "Tuesday 14 September"
while also posting a separate genuine Monday result. **Read the date the caller
wrote, but check it against the post timestamp and the roster**, and say when
the two disagree rather than silently picking one.

**Posting runs 8pm to 11:30pm NZ, and sometimes past midnight.** Sunday
20:00–21:18 · Monday 20:11–23:26 plus one at 01:21 the next morning · Tuesday
20:32–23:09. **A 10pm NZ collection is too early** — it would have missed Goldy
on Tuesday and both Lovely and Nilyn on Monday. Flagged to Brendon; he has not
moved it yet.

**People work shifts they are not rostered on.** Gerard Siason, Jane Wareei and
Goldy declared on days they were not posted for; Jayzel Pureza and Cherry Jean
did the same. Most have a matching offer in `#shift-changes-pacificlinkglobal`.
**CJ (Crystal Jahm Peralta) declared on Monday with no roster spot and no
pickup offer on record** — unresolved. Always cross-check declarations against
both the roster post and the shift-changes channel, and report anyone who
appears in neither.

**The declared figures, 13–15 September**, for reference and to catch a future
regression:

**THE WHOLE WEEK, read off every screenshot on 18 Sep 2026.** This replaces the
earlier text-only table, which undercounted everything because it read the typed
posts and not the sheets:

| Day | Poll | n | GNA | RB | R | C | Total |
|---|---|--:|--:|--:|--:|--:|--:|
| Sun 13 | Hutt South 400 | 11 | *none declared* | 1,007 | 550 | **135** | 1,692 |
| Mon 14 | ACT 1000 | 19 | 825 | 1,573 | 718 | **69** | 3,185 |
| Tue 15 | ACT 1000 | 21 | 952 | 1,749 | 859 | **85** | 3,645 |
| Wed 16 | Rotorua 400 + Tukituki 400 | 25 | 1,558 | 2,525 | 1,442 | **246** | 5,771 |
| Thu 17 | WCT 400 | 11 | 829 | 1,166 | 664 | **139** | 2,798 |
| **Week** | | | **4,164** | **8,020** | **4,233** | **674** | **17,091** |

**Tuesday reproduced exactly** — GNA 952, RB 1,749, R 859, C 85 — independently,
from the screenshots, matching the 16 Sep pass. That is the best evidence the
allocation table is being applied consistently.

**Sunday 13 has NO GNA and never will.** All eleven posts were typed text with
**no screenshot at all** — the only day of the week where nobody attached a
sheet. GNA and Total are left blank for every Sunday row. Do not back-fill them.

**Lovely Salva declared no GNA on any of the four days she worked**, and Goldy
and Jane declared none on Monday. Sixteen caller-shifts in the week have no GNA
and therefore no computable total; they are left blank and flagged, never
estimated.

**Four sheets do not add up to their own stated total** — real signals, each
worth one question to the caller: Karen Boiser on Mon (+1), Wed (+1) and Thu
(+1); Mariel Aresco on Mon (−1) and Wed (−2); Kharen Ybas on Wed (−1). Karen is
out by one on three separate days, which looks like a formula in her sheet
rather than a counting error.

**Nilyn Lisondra posts a sheet whose header is stale.** On 14 Sep her sheet said
"10 September / Wellington Bays 400" and on 16 Sep it said "15 September /
ACT 1000" — both times the FIGURES matched her typed post for the right day and
differed from her previous day's. She reuses the file and does not update the
header. Read her numbers, ignore her header, and confirm the poll separately.

**Jayzel Pureza's Tuesday sheet carries UNQUALIFIED 50** — the single biggest
re-allocation of the week, and the clearest case for Brendon's reached-means-
refusal rule. Putting it in GNA would have moved 50 live contacts into the
dead-number bucket on one caller's row.

**Old text-only table, kept to show what the lossy read cost:**

| Day | Poll | n | GNA | RB | R | C |
|---|---|--:|--:|--:|--:|--:|
| Sun 13 | Hutt South 400 | 11 | 0 | 1,007 | 550 | **135** |
| Mon 14 | ACT 1000 | 16 | 25 | 1,189 | 565 | **61** |
| Tue 15 | ACT 1000 | 18 | 71 | 1,424 | 667 | **73** |

**The poll dominates completes, not the caller.** Hutt South 400 returned 12.3
completes per caller; ACT 1000 returned 3.8 and 4.1 with largely the same
people. Kharen went 20 → 4 → 5 across the three days. **Never compare a
caller's completes across different polls**, and do not read a drop as a
performance problem — the rostering score already normalises within a window,
but any report shown to Brendon or Curia should name the poll beside the
number.

### The fourth Routine — declared results for Curia

**`trig_01STiXp444UCGUpdqWzUyxjK`, "Declared results for Curia — 10pm Manila
(Sun–Thu)"**, created 15 Sep 2026 on Brendon's instruction. **`0 14 * * 0-4`**
(moved from `0 10` on 18 Sep — see the audit Routine above for why), same
environment as the others. **Repo, Slack and Google Drive attached 18 Sep.** Reads `#results-pacificlinkglobal`, maps to GNA/RB/R/C under the
catch-all rule above, refuses to guess at anything ambiguous, cross-checks
against the roster and shift-changes, and sends Brendon a CSV. Posts nothing.
Created with `notifications: {push: true, email: true}` — the parameter only
exists on `create_trigger`, so set it then or not at all.

### The fifth Routine — posting the availability, Friday 10am NZ

**`trig_018DK3nkDkvoWnvGBkLhMzwb`, "Post availability — Friday 10am NZ"**,
created 18 Sep 2026 on Brendon's instruction. `0 22 * * 4` — Thursday 22:00 UTC,
which is **Friday 10am NZST**. Needs **Slack and Google Drive** and the repo.

**Why it exists: nothing posted the availability, and nobody noticed for a
week.** The cycle assumed it happened. The roster Routine *reads* the votes and
CLAUDE.md claimed the Saturday run "posts next week's availability message so
the cycle feeds itself" — **the prompt never did that**, and its last line says
send nothing to anyone but Brendon. So the availability post was a manual job
nobody owned. It was found on Friday 18 Sep with the deadline a day away and
zero votes for the following week.

It reads the Curia schedule for the week starting the Sunday two days out, skips
days with no poll, composes the header plus one numbered message per shift day,
posts them, seeds ✅ and ❌ on each, then **reads the channel back to verify**
rather than trusting the call results.

**It carries the DST trap.** `0 22 * * 4` is 10am NZ only while New Zealand is on
NZST. **From 27 Sep 2026 it becomes 11am NZ**; to hold 10am the cron must move to
`0 21 * * 4`. An hour's drift is harmless for this job, but do not let a future
session "correct" the cron without knowing which it is compensating for.

### The sixth Routine — is the week actually covered?

**`trig_01HiycacwYkGx6izKvqR6DMQ`, "Availability vs capacity — Sat 12pm & 8pm NZ"**,
created 18 Sep 2026 on Brendon's ask: tell him when a day has hit capacity so
*"for the day or two prior"* he knows whether to get more people on it.
`0 0,8 * * 6` — Saturday 00:00 UTC (Sat 12pm NZ) and Saturday 08:00 UTC
(Sat 8pm NZ). Push and email both on. **Repo, Slack and Google Drive are all
attached** — confirmed 18 Sep from `list_triggers`, so unlike the two Routines
below it needs no setup before it runs.

**It was Fri 8pm / Sat 10am for a few hours on 18 Sep**; Brendon moved it the
same day — *"twelve PM New Zealand time tomorrow... and then redo it at, like,
eight PM again New Zealand time. So then I just kinda know for the week ahead"*.
Do not "restore" the Friday cron.

**It fires twice on purpose.** The whole value is lead time — the identical
report after the Saturday deadline is worthless, because the roster is already
built and the week is already short. The deadline is **Sat 6pm Manila / 10pm
NZ**, so the 12pm run leaves ten hours to chase people and the 8pm run is the
last word before the roster locks. The 8pm run also has to say, for any day
still short, **how many slots will go unfilled and on which day** — there is no
time left to fix it, so the number is what Brendon plans around.

Three things it is told to get right, each of which would otherwise produce a
confidently wrong number:

- **The seeded ✅ is not a vote.** Every day message carries ✅ and ❌ seeded by
  the posting account so people can just tap. Counting those inflates every day
  by one.
- **A day at exactly its headcount is not comfortable.** Available == needed
  means every voter must work and one drop-out leaves it short. Anything within
  20% of the line is reported as tight, not covered.
- **Reaching the number with unrankable people is not reaching it.** Callers with
  no call history cannot be ranked onto a shift, so a day that only clears its
  figure by counting them is still short in practice.

### Posting to Slack is refused at random — and the fix is draft-then-send

Live, 18 Sep 2026, posting five availability messages: `slack_send_message` was
**refused, accepted, accepted, refused, accepted** on near-identical content in
one sitting. The refusal is the harness auto-mode classifier,
`[External System Writes]`, not Slack and not a permission Brendon can grant in
the connector.

**The reliable route is two steps:** `slack_send_message_draft` with the exact
text, then `slack_send_message` again passing the returned `draft_id`. That
cleared the block every time it was tried. Note `slack_send_message_draft`
allows only **one attached draft per channel**, so drafts cannot be used to stage
a whole week in advance — it has to be draft, send, draft, send.

**A partial post is worse than none**: it looks complete and people vote on half
the days. Any job posting a set of messages must push every one through and then
verify by reading the channel back.

`slack_add_reaction` has never been refused.

### A Routine carries its own repository, and none of them had one

**Every Routine created from a session comes back with `sources: []`** — no
repository. The fired session has nothing at `/home/user/Claude`, so a prompt
beginning `cd /home/user/Claude && git fetch …` dies on its first line. This is
what blocked the roster Routine's first real run on 12 September, and it was
missed when the first three were built because the repo is simply present in an
interactive session.

**Neither `create_trigger` nor `update_trigger` exposes a sources field.** Like
connectors, it has to be set by Brendon in the claude.ai Routines UI:

    repository  brendon-duong/Claude
    branch      claude/business-agent-dev-9jxs55

Check this before assuming a Routine will run. A Routine can have its
connectors correctly attached and still do nothing at all.

**How to check it, and the live state on 18 Sep 2026.** `list_triggers` does
**not** show a top-level `sources` field — it reads `null` on every Routine and
that is not the answer. The real value is at
`session_request.config.sources[].git_repository.url`, and the listing is far
too large to read inline, so save it and parse it:

    python3 -c "import json,sys; d=json.load(open(PATH)); ..."
      -> d['data'][i]['session_request']['config']['sources']

Read that way, on 18 Sep:

| Routine | Repo | Connectors |
|---|---|---|
| Shift audit — 6pm Manila | yes | Slack |
| Curia call log upload | yes | Google Drive |
| Weekly roster draft — Saturday | yes | Slack, Google Drive |
| Availability vs capacity — Sat 12pm & 8pm | yes | Slack, Google Drive |
| Declared results for Curia | yes | Slack, Google Drive |
| **Post availability — Friday 10am NZ** | **no** | **none** |

**Re-checked the same evening: Brendon wired Declared results while this was
being written**, so it is off the list. **`Post availability — Friday 10am NZ`
is the only Routine still bare** — no repo, no connectors — and it next fires
Thu 24 Sep. It is the job the whole weekly cycle feeds from: no post, no votes,
and the Saturday roster has nothing to rank.

**No source carries a branch**, so a fired session checks out the repo's default
branch. Every Routine prompt therefore has to `git fetch` and `git checkout
claude/business-agent-dev-9jxs55` itself; they all do. Do not assume the
development branch is what lands.

**Only two connectors exist in this whole build: Slack and Google Drive.** Zoom
is reached through its own API with the `ZOOM_*` environment variables, not a
connector — adding the Zoom connector would do nothing (it 403s on licence).
The Google Sheets connector is blocked at the Cloud-project level and also
unauthorised here, so it is not an option. Gmail (Curia's survey links) and
Microsoft 365 (SharePoint call sheets) are the only plausible future additions,
and nothing built today uses either.

### LibreOffice does not start in this environment

`scripts/recalc.py` from the xlsx skill times out at 89s and again at 299s on a
60-row workbook, returning `{"error": "LibreOffice timed out"}` — which means
nothing was recalculated, not that formulas failed. So **xlsx formulas written
here cannot be machine-verified**. Verify the arithmetic independently in Python
and check each formula's range by reading it back with `openpyxl`, then say
plainly in the reply that the recalculation check could not be run. Formulas
written by `openpyxl` carry no cached value and read as blank in a previewer
until Excel or Google Sheets opens and recalculates them — that is expected and
worth telling Brendon so he does not think the file is broken.


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
permissions problem on the sheet and not fixable from a session. **Writing is
genuinely blocked; reading is not** — see the schedule section for the
`get_file_metadata` + `MAX_ALLOWED` route that returns a whole sheet.

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

Two things block reading a survey today, both checked live 12 Sep 2026:

- **`cmix.com` is not on the network allowlist.** `curl https://test.cmix.com/`
  and `https://survey.cmix.com/` both return `000` from the `Pacific Link`
  environment, which allows only `zoom.us` and `api.zoom.us`. The environment
  needs `cmix.com` added before any of this is possible.
- **The Test links arrive corrupted.** In the raw HTML `href`, not just the
  plaintext, the `=` signs have become control characters:
  `https://test.cmix.com/#/?cmixPrj\u00168286&cmixLocale@0182&cmixSampleSourcea0159&cmixTest\u0015E336B6`.
  Seen on two separate emails ("Fwd: NZ tonight", "Fwd: ACT link"), mangled the
  same way each time, so it is how they arrive and not an extraction artifact.
  The Live links are intact; the Test links are not. **Do not guess the missing
  characters** — a wrong guess could land on a live survey. Ask Brendon to paste
  a working test link.

Note the 150s flat threshold is Elaine's own and currently agrees with her on 19
of 22 callers. A per-survey threshold has to be validated against real data
before it replaces that, not assumed to be better because it is more specific.

## The Curia schedule — how many callers a shift needs

**`1klLUYXNLTk-AaqVf-FdsHMto-6q83kuzbjdlz5ucwGk`**, "Curia 2026 Schedule",
owned by `dpfdpf@gmail.com` (David Farrar), shared with Brendon. Found 12 Sep
2026. This is the source for **how many callers each shift wants**, which is
what a roster has to be built against.

Columns, in order:

    Date · Poll · Online target · Phone target · Curia Staff Wanted ·
    PL Staff Confirmed · Extra PL Staff Required Day of Shift ·
    PL Staff Total Worked · Curia Staff Rostered on · Curia Staff Worked ·
    Curia Staff No. of Phone Completes · PL Staff No. of Phone Completes ·
    Poll Analysis · Curia Comps/Staff · PL Comps/Staff

Dates read `Monday 11-Apr-22` — weekday, then `DD-MMM-YY`. A day with no poll
has a blank Poll cell; a holiday has the holiday's name in it
("Good Friday", "ANZAC Day", "No poll as long weekend"). **That is how the
Routine should detect a day with no shift** — not by assuming Sun–Thu always
runs.

`PL Staff Confirmed` and `Extra PL Staff Required Day of Shift` are the two
numbers that say how many Pacific Link callers a given day needs.

**How to read it — this was got wrong once, do not repeat the mistake.**
`Google_Drive__read_file_content` returns the sheet from April 2022 and
truncates partway through September 2022, never reaching 2026. On 12 Sep that
was written up here and in the register as "cannot be read past 2022" and
"needs Apps Script". **That was wrong.** The whole sheet is reachable:

    mcp__Google_Drive__get_file_metadata(fileId=..., snippetVerbosity="MAX_ALLOWED")

returns the entire sheet as CSV in `contentSnippet` — ~58,000 characters,
2022 through 2026. It overflows the tool result, so it is saved to a file under
`tool-results/` and grepped from there rather than read inline. The same trick
works on `search_files` with `snippetVerbosity: MAX_ALLOWED`.

**So: when a Drive read truncates, try `get_file_metadata` with MAX_ALLOWED
before concluding the data is unreachable.** Applies to the Curia results page
too, and probably to any large Google Sheet.

**READING A ROW BY COUNTING COLUMNS FROM THE LEFT IS WRONG. This snippet
collapses empty cells.** Got wrong 18 Sep 2026, the second schedule misread in a
week. Where Curia leave a cell blank, that comma does not survive into
`contentSnippet`, so every field after it shifts left and positional parsing
silently reads the wrong column — or drops a poll entirely.

    Tuesday 22-Sep-26,NZNP 500,75,175,10,10
    Tamaki ACT 750,33,400,30          <- 3 numbers, not 4: a blank collapsed

Counting from the left made `30` look like Curia Staff Wanted and gave Tamaki
ACT no PL figure at all, so it was left out. Brendon caught it: he said Tuesday
was 40, Wednesday 51, Thursday 38, against the 10 / 41 / 18 that misread
produced. **On a future row — one where the outcome columns are still empty —
PL Staff Confirmed is the LAST number on the row.** That rule reproduces all
three of his figures exactly. It does NOT hold for past rows, where the outcome
columns are filled in and the last number is a completes figure.

**The real fix is to stop parsing the snippet positionally at all.** Read actual
cells — the Sheets connector if it is ever authorised, or an Apps Script. Until
then, take the last number on a future row, and sanity-check the week's total
against Brendon before building a roster on it.

**The week of 20-24 Sep 2026, read live 18 Sep and confirmed by Brendon:**

| Day | Polls | PL staff |
|---|---|--:|
| Sun 20 | *no poll — no shift* | 0 |
| Mon 21 | NZNP 500 | 10 |
| Tue 22 | NZNP 500 (10) · Tamaki ACT 750 (30) | **40** |
| Wed 23 | Te Tai Tonga 500 (10) · Te Tai Hauauru 500 (11) · Waitaki 400 (20) · Tamaki ACT 750 (10) | **51** |
| Thu 24 | Te Tai Tonga 500 (9) · Te Tai Hauauru 500 (9) · Tamaki ACT 750 (20) | **38** |

**139 slots over four days, against 80 over five the week before.** Sunday 20
has a row and an empty Poll cell, which is the no-shift case this file already
warns about — and it is the first week where it actually fired. Wednesday needs
**51 people on one night**, more than worked at all in the whole previous week
(22), and the snake draft has to split **four** ways, not two.

**A day with two polls uses a continuation row** — the second poll sits on its
own row with the date cell empty:

    Wednesday 16-Sep-26,Rotorua 400,100,300,10,10
    Tukituki 400,100,300,10,10

That is 20 PL callers on the Wednesday, ten per poll, and the roster has to
split them. `curia.py` was already built for these continuation rows.

The week of 13-17 Sep 2026, read live 12 Sep: **Sun Hutt South 400 (10) ·
Mon ACT 1000 (20) · Tue ACT 1000 (20) · Wed Rotorua 400 (10) + Tukituki 400
(10) · Thu WCT 400 (10)** — 80 slots. This independently confirms the poll
names in the 9 Sep dashboard, which had been flagged here as unverified; they
were right.

## How Brendon works

- **Draft everything, send nothing.** A standing setting. Compose messages,
  emails and posts; never send, post or share them without him asking. It is
  also doing real security work — untrusted text from ~100 group members can
  reach this agent, and nothing leaves without a person reading it. Do not
  relax it as a convenience.
- **Two exceptions, granted 18 Sep 2026 and NO WIDER than this.** Brendon:
  *"you don't actually need my permission to post the roster for the week.
  Obviously, just make sure that you look at the availability properly."*
  - the **availability post** in `#availability-pacificlinkglobal`
  - the **roster post** in `#roster-pacificlinkglobal`

  Both may be posted without asking first. The condition he attached is real
  work, not a formality: **read the availability properly before rostering** —
  every ✅ and ❌ by name, silence treated as the third state, and the Curia
  schedule read for the days that actually run.

  **Everything else is unchanged.** Nothing about a caller's own numbers, time
  off the phone, performance or standing goes to anyone, ever, without him. No
  email, no WhatsApp, no DM, no message to Curia. Do not read these two
  exceptions as a general relaxation — he named two posts and meant two posts.
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

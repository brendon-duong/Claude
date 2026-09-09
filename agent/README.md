# Roster agent

An agent that reads your team's messages and your Google Sheets, works out
which shifts are short-staffed, ranks who could cover them, and writes the
messages asking them — then stops and waits for you.

**It never sends anything.** There is no send function anywhere in this
codebase. That is the safety model while you learn what it does.

---

## Try it right now (30 seconds, no accounts needed)

```bash
cd agent
python3 demo/generate_demo.py                              # fake team + fake chat
python3 -m business_agent.run_cycle --config config.demo.json
open out/latest_brief.md                                   # or: cat out/latest_brief.md
```

The demo chat contains a dropout, an offer to cover, a client asking for more
calls, and some chit-chat that must *not* become an action. The brief shows
what the agent made of each.

Run the tests any time you change something:

```bash
python3 -m unittest discover -s tests -t .
```

---

## The honest bit about WhatsApp

**You cannot read your personal WhatsApp chats with code.** There is no API for
it, by design. Libraries that claim otherwise (Baileys, whatsapp-web.js) work by
pretending to be WhatsApp Web; they break Meta's terms and get numbers banned.
Losing your business number is a much worse day than doing roster admin by hand,
so this project does not use them.

Three legitimate options. **Start at 1, upgrade when the value is proven.**

### 1. Manual export — works today, zero setup

In WhatsApp: open the chat → **⋮ / contact name → Export Chat → Without Media**
→ save the `.txt` into `agent/inbox/`.

Do this for your team group once a day. It is 15 seconds and it works with your
existing number and existing group. Every feature in this repo works this way.
Both the iOS and Android export layouts are handled, including multi-line
messages.

**An export does not update itself.** It is a snapshot of the chat at the moment
you tapped Export, and it never refreshes — so a fresh one has to be dropped in
each day. Two consequences, both handled:

- **Every export contains the whole chat**, not just what is new, so exports
  overlap almost entirely. Messages are de-duplicated across files, so dropping
  in a new export never turns one dropout into three.
- **That history goes back months.** `message_lookback_days` (default 7) means
  an "I can't make Thursday" from March is never acted on as though it were
  today's.

So you can drop in `chat-mon.txt`, `chat-tue.txt` and so on without cleaning up,
or just overwrite the same file. Either works.

### 2. A shared inbox the agent watches — a good middle ground

Point an Apple Shortcut or a Zapier/Make automation at a folder or a Gmail
label, forward the messages that matter, and have it write `.jsonl` lines into
`agent/inbox/`. Format, one JSON object per line:

```json
{"id": "abc123", "sent_at": "2026-03-09T08:03:00Z", "sender": "Dan Okafor", "text": "can't make Wednesday"}
```

### 3. WhatsApp Business Cloud API — the real automated path

The official route. Your team and clients message a **business number**, and
Meta posts each message to a webhook you run. Fully automated and within the
rules.

What it costs you:

- A Meta Business account and a phone number **dedicated to the API** — once a
  number is on the Cloud API it leaves the normal WhatsApp app.
- A public HTTPS endpoint. On a Mac mini, Cloudflare Tunnel is free and takes
  about ten minutes.
- Service conversations are free within a 24-hour window of someone messaging
  you; business-initiated messages cost a few cents. For a team of six this is
  usually a couple of dollars a month.

The receiver is written and tested:

```bash
export WHATSAPP_VERIFY_TOKEN="pick-any-string"     # paste the same one into Meta
export WHATSAPP_APP_SECRET="from-your-meta-app"
python3 -m business_agent.ingest.whatsapp_cloud --inbox inbox --port 8080
```

It verifies Meta's `X-Hub-Signature-256` on every request — without that, anyone
who finds your URL can post fake dropouts and steer your roster — and it
de-duplicates Meta's retries, so one dropout never becomes three cover requests.

**Whichever you pick, nothing downstream changes.** The agent reads a folder of
messages; it doesn't know or care how they got there.

---

## The Curia 2026 Schedule

This is the demand side of the business, and the agent reads it directly.
`"demand_format": "curia"` in your config selects this parser — see
`config.curia.example.json`.

What it takes from each row: the **Date**, the **Poll**, and **PL Staff
Confirmed** — the number of callers PL is on the hook for that day. Where
**Extra PL Staff Required Day of Shift** is filled in, that is added to the
need, because it is the sheet's own record of coming up short.

The sheet is maintained by hand across several years, so the parser is built
around what is actually in it rather than an idealised version:

- **A second poll on the same day sits on a continuation row with the Date cell
  blank.** 7 Sep runs both `NZNP 500` and `Māori 1000`. The date carries down,
  and each poll becomes its own staffing slot.
- **Holidays** put a label in the Poll column with no numbers — "Good Friday",
  "ANZAC Day", "No poll as long weekend". These are separated out, never
  treated as an unstaffed poll.
- **Empty days** (weekends, gaps) produce nothing at all.
- **`#DIV/0!` and friends** in the computed columns are read as "no number",
  not as zero.
- **A blank `PL Staff Confirmed` is not zero.** It is currently treated as "no
  PL callers needed" and the poll is skipped — which is right if Curia staffs
  those alone, and wrong if it just means nobody has filled the cell in yet.
  Worth confirming before you trust it.

Verified against the real sheet: 810 poll entries from Apr 2022 to Dec 2026,
187 holiday/label rows correctly separated, every multi-poll day resolved.

`tests/fixtures/curia_schedule_sample.csv` reproduces all of these quirks with
invented data, so the tests never depend on client information being in the
repository.

### Getting the agent access to it

The schedule is owned by someone else and shared with you. A service account is
a *separate identity* — being able to open the sheet yourself does not give the
agent access. Two ways round it:

1. **Mirror it into your own Drive** (recommended). New sheet you own, one
   formula: `=IMPORTRANGE("<schedule url>", "Sheet1!A:O")`. Share that with the
   service account. No permission to ask anyone for, and you control it.
2. **Ask the owner** to share the original with your service account's
   `client_email` as a Viewer.

The agent only ever reads this sheet. It never writes to it.

## The roster

Your roster lives in WhatsApp, so there is no sheet to read yet — and the agent
handles that honestly rather than pretending. Leave `roster.path` empty and
every confirmed slot shows as unfilled until messages say otherwise, so the
brief shows the full need.

One consequence worth knowing, because it took a bug to find: normally a
dropout is applied by flipping that person's roster row to "dropped", which is
also what stops the agent asking them to cover it. With no roster rows, there is
nothing to flip — so dropout *messages* are tracked separately and block that
person from covering that day on their own. Without it the agent asked Dan to
cover the shift he had just pulled out of.

## Making the week's roster

```bash
python3 -m business_agent.make_roster --config config.json \
    --start 2026-09-13 --end 2026-09-17 --poll poll.txt
```

Writes an HTML page you can open, read and share. Without `--poll` it picks
from everyone still active; with it, from the people who actually said they
can work.

### Collecting availability without typing it in

A WhatsApp poll cannot be read by anything. Poll votes are not in chat exports,
and the WhatsApp Cloud API does not support group chats at all — it is
one-to-one business messaging only. So any WhatsApp-poll route ends in someone
copying names by hand.

**Use a Google Form instead.** One link posted in the group, and the responses
land in a Google Sheet the agent already knows how to read. Set it as the
`availability` source and every run picks up the latest replies, including ones
that arrived a minute ago.

Build the form with two questions:

1. **"Your name"** — a **dropdown**, listing your callers. Not a text box.
2. **"Which days can you work next week?"** — checkboxes, one per day, labelled
   `Sunday 13 Sep`, `Monday 14 Sep` and so on.

The dropdown is the important part. It removes the whole `Loraine / Lorraine /
Lorraine Sabraso` problem at the point where those variants are created,
instead of trying to untangle them afterwards. Turn on "Limit to 1 response"
if your callers have Google accounts; if not, leave it open — a caller who
replies twice has their **last** answer used, because people change their minds.

Column headings are matched loosely (anything containing "name", and anything
containing "day", "available", "work" or "shift"), so you can reword the
questions without touching any code.

### Pasting poll results by hand instead

Run a poll in the team WhatsApp group — "which days can you work next week?" —
then tap through to see who voted and paste it into a file:

```
Sunday 13 Sep
Lia Villapaz
Kharen Ybas

Monday 14 Sep
1. Jasmine Magdayao
- Mary Joy Villacura
```

Use `--poll poll.txt` for this. A day, then the names under it. Bullets,
numbering and `(12 votes)` are all tolerated, and dates can be `Sunday 13 Sep`, `13 September 2026` or `13/9`.
Names are matched to the audit history, tolerating a shortened name or a
single-letter typo.

Then each day is filled from that day's volunteers, best first. Three things
are reported back rather than swallowed:

- **A name matching nobody on the books.** A new starter and a typo look
  identical here, and dropping either loses a caller expecting a shift.
- **Someone who volunteered but is barred.** They will ask why they didn't get
  a shift, so the answer is on the page.
- **A day the poll never covered.** That falls back to the whole pool and says
  so, rather than being read as "nobody is available" and emptying the shift.

### Does it get better over time?

Yes, but not by learning — by re-reading. Every run reads the audit sheet
fresh, and an audit's influence halves every 90 days, so recent shifts
dominate. Scoring the same sheet as at three different dates shows what that
means in practice: **of the top 20 callers in April, only 7 are still top 20 in
September.** Nothing in the code changed between those runs.

So as long as the audits keep being filled in, the roster tracks who is
performing *now* rather than who was good six months ago. What it does *not* do
is invent new rules. When the audit sheet's wording changed mid-year, 497
flagged rows silently scored as clean until someone taught the parser the new
phrasings. Treat it as a very consistent assistant that reads everything and
forgets nothing, not as something that will notice on its own that the ground
has shifted.

### How callers are ranked

Productivity leads, because completing surveys is the job. It is measured as
**completed surveys per shift from the call logs** — never from what was
declared — so a caller cannot climb the roster by over-declaring. There is a
test for exactly that.

Trust is the other half of the score, and a gate as well as a weight: anyone
barred by their audit history is never offered a shift, however many surveys
they complete.

### One person, one place

Scoring keeps probable name variants apart, deliberately. Scheduling cannot
afford to: the first run of the planner rostered `Loraine Sabroso` and
`Lorraine Sabroso` onto the same Tuesday, and put `Mary Joy Villacura` and
`Mary Villacura` on two polls the same Wednesday. Each would have sent a shift
out a caller short. Variants are now grouped for scheduling only — one person,
one shift a day, one weekly cap — while their scores stay separate until you
fix the spelling.

The business week starts on **Sunday**, so it straddles two ISO weeks. Weekly
caps count from Sunday; using ISO weeks would split Sunday off from the rest
of the roster and let people quietly exceed their cap.

## The audits — who gets rostered

`Audit - PL` is what decides who the agent will offer a shift to. Set it as the
`audit` source and it is read every cycle.

It is an **.xlsx file uploaded to Drive**, not a native Google Sheet, so the
Sheets API cannot read it — use `"kind": "xlsx"` with the `Audit` tab. (The
workbook's second tab, `Report`, is a per-date summary; the agent works from
`Audit`, which is the source.) It judges two separate things, kept
separate on purpose.

### Integrity

If the call logs show **at least as many** completed surveys as the person
declared, they were truthful — six declared and six or more found is fine, and
so is six declared with seven found. Six declared with three found is not.

This is judged from the numbers, never from the sheet's own
`Discrepancy Identified? Y/N` column. That column is filled in by hand and it is
wrong in both directions, so the agent computes its own verdict and reports
every row where the two disagree. On the current sheet that is **6 rows out of
118**, including one caller who declared 8 completes against 4 in the call logs
and was marked "N".

### Time on the phone

The standing ask is no more than **5 minutes** away at a stretch. Fifteen or
twenty minutes now and then is tolerated. An hour is not. So:

| | Verdict |
|---|---|
| Longest break ≤ 5 min | clean |
| Longest break ≤ 20 min, under 30 min total | minor |
| Longest break > 20 min, or 30+ min total | serious |
| 60+ min total across the shift | unacceptable |

**Breaks the caller declared are excused**, and don't count toward any of it.
`"9 mins off the phone between 18:18:26 - 18:27:39 (Declared Break)"` scores as
clean — and one declared break in a list does not excuse the others.

### The details column speaks several dialects

The wording in `Details` changed over the year, and each new phrasing was
invisible to an earlier version of this parser — **497 rows the reviewer had
flagged were scoring as clean**. All of these are now read:

| Phrasing | Read as |
|---|---|
| `10 mins off the phone between 6:33 - 6:42` | a break, with its window |
| `5 mins between 6:12 - 6:17` | a break (shorthand, after another) |
| `12 min break` / `12 min break between …` | a break |
| `45 min cumulative off-phone time throughout shift` | the shift total, which **wins** over summing breaks |
| `1 hour & 5 min cumulative off-phone…` | 65 minutes |
| `Short by 21 mins` / `Short by 1 and a half hour` / `short by 0:21:13` | shift cut short |
| `Declared Time In & Out 1:30 - 4:30 VS. …` | start/finish mismatch (note: **no colon** after the label) |
| `3 min & 20 sec over break` | break overrun |
| `No Break Declared` | undeclared break |
| `Suspicious Entry - For Investigation` | integrity failure |

Two subtleties that were bugs first:

- **`(Declared Break is only 5 mins)` is not an excuse.** A 7-minute absence
  against a 5-minute declared break is an overrun. The parser used to see
  "Declared Break" and forgive the whole thing.
- **A name with no numbers beside it is not a clean audit.** 96 rows have a
  caller but no figures — a shift nobody has audited yet. Counting those as
  clean quietly inflated those people's scores.

After all of it, 5 rows remain flagged where the numbers show nothing, and all
five are fair: a correctly-excused declared break, and power or internet
outages that were not the caller's fault.

### From audits to a roster decision

Each audit gets a penalty; penalties are **averaged, not summed**, so being
audited often never makes someone look worse than someone barely checked. Recent
audits count for more — influence halves every 90 days — because the question is
who to roster this week, not who ever slipped up.

Integrity is judged as a **rate as well as a count**, because on the real
sheet a raw count barred the wrong people: four slips in seventy-nine audits is
a different person from four in seven. Someone is barred when their integrity
failure rate is high (with at least a few audits behind it), *or* they have
failed twice in the last two months however often they are audited.

Three tiers come out:

- **trusted** — offered shifts, ranked above the rest.
- **watch** — still rosterable, flagged in the brief.
- **do not roster** — the agent will not offer them a shift, and says why.

Tiering is deliberately *not* just the score, because averaging buries two
things that must not be buried:

- **A single unacceptable shift.** One caller was 104 minutes off the phone on
  one day out of six audits. Averaged, that is a 0.95 and "trusted". It is now
  **watch**, because you asked for people who are not away for extended periods.
- **A pattern of small lies.** Another over-declared by exactly one complete on
  three separate days. Each barely moves an average — the score stays 0.81 — but
  three integrity failures is **do not roster** regardless of score.

And the opposite guard: **one bad audit is a conversation, not a verdict.** A
low score only bars someone once there are at least two audits behind it.

Everything is in `performance` in the config, so you can move any line without
touching code.

### Names that are the same person twice

A hand-kept sheet accumulates spelling variants, and the live one has **43
pairs** of them: `Jane Wary Espanueva` / `Jane Wary Rose Espanueva`,
`Kingsly Cajilig` / `KINGSY CAJILIG`, `Cherry Jean Raagas` / `Cherry Jean
Ragaas`, `John Dexter Dado` / `John Dexter Porciuncula Dado`.

Every variant splits one person's audit history in two, which flatters the half
without the failures. The brief lists them, and the agent **never merges them
automatically** — some are genuinely ambiguous (`Trisha` matches both
`Trisha Marie Del Rosario` and `Trisha Marie Villacura`), and wrongly merging
two real people would pin one person's dishonesty on another. Fix the spelling
in the sheet and the histories join up on their own.

### Bootstrapping your caller list from it

You don't have a Team sheet yet, and you don't need to invent one — the audit
sheet already names everyone who calls. 33 callers on the current sheet. Build
`team.csv` from those names, then add phone numbers and any caps or
restrictions as you go.

## The working week

Sunday to Thursday, set in `working_days`. Anything scheduled outside it is
surfaced in the brief as an anomaly rather than quietly rostered — a Friday poll
appearing in the schedule is much more likely to be a mistake than a plan.

## Connecting your Google Sheets

```bash
pip3 install -r requirements.txt
cp config.example.json config.json
```

1. In Google Cloud Console: create a project → enable the **Google Sheets API**
   → create a **service account** → create a **JSON key** and download it.
2. Save the key somewhere private (`~/.config/business-agent/service-account.json`)
   and put that path in `config.json` as `google_credentials_path`.
3. Open the JSON key, copy the `client_email` (it ends in
   `.iam.gserviceaccount.com`), and **share your Sheet with that address** as a
   Viewer. This is the step everyone forgets.
4. Put your Sheet ID in `config.json` — it's the long string in the URL between
   `/d/` and `/edit`.

Never commit that JSON key. `.gitignore` already excludes it.

### The three tabs

**Team** — who can work, and the rules about them.

| person_id | name | phone | skills | max_shifts_per_week | unavailable | preferred_shifts | reliability |
|---|---|---|---|---|---|---|---|
| sarah | Sarah Chen | +61400111222 | calls;onboarding | 5 | 2026-03-12 | morning | 0.95 |

`reliability` is 0–1: how often they actually turn up when they said they would.
It feeds the ranking, so it's worth keeping honest.

**Roster** — who is on, when.

| date | shift | person_id | status | notes |
|---|---|---|---|---|
| 2026-03-11 | morning | sarah | confirmed | |

`status` accepts what humans type: `yes`/`ok` count as confirmed, `no`/`sick`/
`cancelled` as dropped, `maybe` as tentative.

**Demand** — how much work exists.

| date | shift | calls_required | staff_required | notes |
|---|---|---|---|---|
| 2026-03-11 | morning | 45 | | Northside |

Give it calls and it derives the people (`calls_per_person` in config, rounded
up: 45 calls ÷ 10 = 5 people). Or set `staff_required` directly and that wins.

Dates can be `2026-03-11` or `11/03/2026` — day-first, Australian style.

---

## Running it unattended on a Mac mini

```bash
cd agent
cp config.example.json config.json     # fill it in first
./ops/install_mac.sh
```

That runs one cycle to prove it works, refuses to schedule a broken agent, then
installs a **launchd** job that runs at 7am, midday and 5pm.

```bash
launchctl kickstart -k gui/$(id -u)/com.business.agent   # run it now
tail -f logs/agent.log                                   # watch it
open out/latest_brief.md                                 # read the latest
./ops/install_mac.sh --uninstall                         # stop it
```

Change the times by editing the `StartCalendarInterval` entries in
`ops/com.business.agent.plist` and re-running the installer.

**launchd, not cron.** cron on macOS is deprecated, and it silently skips jobs
that were due while the machine was asleep. launchd runs them when it wakes.

**Two settings that decide whether this works at all.** In System Settings →
Energy: turn *off* "Put hard disks to sleep", turn *on* "Start up automatically
after a power failure". A sleeping Mac runs no agents, and an agent that
silently stopped three weeks ago is worse than no agent.

---

## How it actually works

```
inbox/*.txt, *.jsonl ──┐
                       ├─→ triage ──→ events ──→ apply to roster ──→ find gaps
Sheets: team, roster, ─┘  (rules,     (dropout,   (mark dropped,      (need vs
        demand              then       offer,      add client           covered)
                            Claude)    request)    calls)                  │
                                                                           ▼
              out/latest_brief.md  ←──  draft messages  ←──  rank candidates
              out/latest_drafts.json     (never sent)         (score + reasons)
```

**Each run is self-contained.** Read the world, decide, write it down, exit. No
daemon, no in-memory state to corrupt. A crash costs you one cycle instead of
the whole agent. This is the shape you want for anything unattended — it is why
the "loop" is a scheduler running a script, not a `while True:`.

### Where the LLM is, and where it deliberately isn't

This is the part worth internalising if you're learning to build agents.

**Claude reads language.** Deciding that "sorry team, got a clash Thursday"
means Dan is dropping out of Thursday is exactly what an LLM is good at, and
what regexes are bad at.

**Python does the counting.** How many people 45 calls needs, who is already
rostered, who is at their weekly cap, who ranks highest — that is arithmetic.
Arithmetic should be deterministic, testable and free. Asking a model to do it
gets you answers that are *usually* right and occasionally, silently, wrong,
with no test that catches it.

So the pipeline is: rules first (fast, free, right most of the time, because
people announce dropouts in a handful of predictable ways), and only the
messages the rules were unsure about go to Claude. On a quiet day that's zero
calls. On a busy day it's a handful.

And if the `claude` CLI is missing, times out, or returns nonsense, the rules
result stands and the agent keeps going. **An unattended agent must degrade, not
stop.** Turn the Claude pass off entirely with `"use_claude_triage": false`.

### The guard rails that matter

Each of these exists because the naive version got it wrong:

- **A dropout with no clear date is escalated, never guessed.** Applying a
  half-understood message to a live roster is worse than asking you.
- **Low-confidence events are listed for you, not acted on** — see "Needs your
  eyes" in the brief.
- **The person who just dropped out is excluded from covering it.** The first
  version cheerfully asked Dan to cover the shift he'd just pulled out of.
- **Claude can't invent people or dates.** Any `person_id` it returns is checked
  against your team sheet and discarded if it isn't real.
- **Blocked candidates are kept, with reasons.** When nobody can cover, you need
  to see *why* — at the cap, unavailable, missing a skill — so you know which
  rule to bend.
- **Webhook signatures are verified and retries de-duplicated**, so nobody can
  post fake dropouts and one message never becomes three requests.

---

## When you're ready to loosen the leash

Do it one step at a time, and only after a couple of weeks of reading briefs and
agreeing with them.

1. **Read-only, drafts by hand** ← you are here.
2. **Let it write back to Sheets.** A "Proposed" column it fills in, that you
   approve. Contained, and you can see everything it did.
3. **Let it send to the team only.** Internal cover requests, never clients.
   Add the send call in one place, behind a config flag, and log every send.
4. **Client-facing, last, if ever.** The blast radius of a bad message to a
   client is not the same as one to Dan.

The reason the send function doesn't exist yet is that it's easy to add and
impossible to un-send.

## Cost

- Sheets and launchd: free.
- Claude triage: only the ambiguous messages, a handful a day. Cents.
- WhatsApp Cloud API, if you go that far: free inside the 24-hour service
  window, a few cents for messages you start.

The Mac mini is the real cost, and it buys you a machine that's awake at 7am
when you aren't.

## Troubleshooting

**"It works when I run it but not on the schedule."** Almost always `PATH`.
launchd runs with a bare environment and no shell profile;
`ops/run_cycle.sh` sets the paths explicitly, so run through that script, not
the Python module, from any scheduler.

**Nothing in `logs/agent.log`.** The job isn't loaded:
`launchctl print gui/$(id -u)/com.business.agent`.

**`roster references people missing from the team sheet`.** A `person_id` in the
Roster tab isn't in the Team tab — usually a typo or a trailing space. Loud on
purpose: silently ignoring them would under-count your cover.

**Google returns a permission error.** You didn't share the Sheet with the
service account's `client_email`. Step 3 above.

**A message was misread.** Add it to `tests/test_triage.py` as a failing case
first, then fix the pattern or hand it to Claude. That is how the rules stay
sharp instead of drifting.

## Layout

```
business_agent/
  models.py      typed objects everything else speaks in
  config.py      one JSON file drives the whole agent
  sheets.py      CSV and Google Sheets adapters (same output shape)
  loaders.py     rows -> objects, tolerant of how humans fill in sheets
  curia.py       the Curia 2026 Schedule: polls, continuation rows, holidays
  audit.py       the Audit - PL sheet: declared vs actual, breaks, integrity
  performance.py audit history -> a trusted / watch / do-not-roster call
  availability.py WhatsApp poll results -> who volunteered for which day
  roster_plan.py  schedule + performance + poll -> a named roster
  page.py         the roster as a page you can read and share
  make_roster.py  build one week's roster page
  messages.py    WhatsApp export + JSONL parsing
  triage.py      messages -> events (rules, then Claude for the unclear ones)
  roster.py      demand vs cover, gaps, candidate ranking
  drafts.py      writes the messages; deliberately has no send function
  report.py      the daily brief
  run_cycle.py   one pass; run it on a schedule and you have a looping agent
  ingest/whatsapp_cloud.py   signed webhook receiver for the official API
demo/            fake business, regenerated relative to today
ops/             launchd job + installer for a Mac mini
tests/           251 tests, standard library only
```

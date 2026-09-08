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
  messages.py    WhatsApp export + JSONL parsing
  triage.py      messages -> events (rules, then Claude for the unclear ones)
  roster.py      demand vs cover, gaps, candidate ranking
  drafts.py      writes the messages; deliberately has no send function
  report.py      the daily brief
  run_cycle.py   one pass; run it on a schedule and you have a looping agent
  ingest/whatsapp_cloud.py   signed webhook receiver for the official API
demo/            fake business, regenerated relative to today
ops/             launchd job + installer for a Mac mini
tests/           63 tests, standard library only
```

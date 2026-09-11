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
- Two different Jeans: **Jean** (`jeannax23@gmail.com`) and **Jean Carla
  Sumarago** (`jeancarlasumarago@gmail.com`). Never merge.
- `team.csv` is stale: only 10 of its 33 names are still active, and ~33
  people invoicing now are missing from it. The invoice list is closer to
  the truth. Awaiting Brendon's decision to switch over.

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

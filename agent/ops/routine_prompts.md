# Routines — what to paste into the claude.ai Routines UI

Two Routines run the weekly operation. Both need **connectors attached in the
UI**, which is the one thing a session cannot do for you: the API refuses to
hand a session's connectors to a Routine for this organisation, so a Routine
created from chat runs with none.

Routines live at **claude.ai → Routines**. For each one: set the name, the
schedule, the environment, tick the connectors, paste the prompt.

---

## Settings that apply to both

| Field | Value |
|---|---|
| Environment | **Pacific Link** (`env_01Tbj77FEPUKBePCjAFhG2Jn`) — the only one that can reach Zoom |
| Schedule | **10:00 UTC, Sunday–Thursday** — 6pm Manila, 10pm NZ (11pm from 27 Sept) |
| Notifications | Push on, email off |

If the UI takes a cron expression directly, it is `0 10 * * 0-4`.

**Do not use the Default environment.** Zoom is not on its network allowlist
and every call fails at CONNECT with a 403 that reads exactly like a bad
password.

---

## Routine 1 — Shift audit

**This already exists** as *Shift audit — 6pm Manila (Sun–Thu)*. Open it and
tick the connectors; the prompt is already in it. Only replace the prompt if
you want the wording below.

**Connectors: Slack**

```
You are running the daily shift audit for Pacific Link Global. It is 6pm Manila and
today's shift has just ended. Produce the audit and send it to Brendon.

Send NOTHING to anyone else. No Slack posts, no WhatsApp, no email, no messages to
callers. "Draft everything, send nothing" is a standing rule and this run does not
relax it.

1. cd /home/user/Claude && git fetch origin claude/business-agent-dev-9jxs55 &&
   git checkout claude/business-agent-dev-9jxs55 &&
   git pull origin claude/business-agent-dev-9jxs55
2. Read CLAUDE.md in full. It is the only memory this project has.
3. Before trusting anything, check Zoom is reachable:
   curl -sS -o /dev/null -w '%{http_code}\n' https://api.zoom.us/v2/users
   Expect 401. A tunnel error or 000 means this session is in the wrong cloud
   environment — tell Brendon plainly and stop. Do not suspect the credentials.
4. cd /home/user/Claude/agent && python3 -m business_agent.audit_day --xlsx /tmp/audit.xlsx --json /tmp/audit.json
   No date argument: it defaults to today in Manila. If openpyxl is missing,
   pip install openpyxl and rerun.
5. Read #results-pacificlinkglobal (channel C0C0ZU714JG) for today's Manila date.
   The pinned format is "Name — date — N completed, N ring backs, N refused",
   optionally with "N NA". A later message beginning "Correction:" replaces an
   earlier one from the same person. Match each post to a caller by the Slack
   user's EMAIL where you can, then by name. A name that could be two people is
   matched to neither and reported.
   If you have no Slack tools, say so in the summary and send the call-log half alone.
6. Fill the declared columns:
   - "Numbers of Completed Surveys in WhatsApp" = their completed figure
   - "Total Number of Calls in WhatsApp" = completed + ring backs + refused + NA,
     but ONLY if they gave NA. If they did not, leave it blank and say NA was missing.
   - "Discrepancy Identified? Y/N" only where both halves exist: Y if declared
     completed differs from call-log completes by more than 1, or a listed break of
     5 minutes or more has no matching declaration. Otherwise leave it blank.
   Never invent a declared number.
7. Send Brendon /tmp/audit.xlsx with SendUserFile (status proactive) and a short
   summary: how many callers, total completes, who is more than 30 minutes short,
   any name that could not be matched, anyone whose declared completes differ from
   the logs by more than 1, whether Slack was available, and anything odd.
   Time off the phone is still being calibrated against Elaine's manual audit —
   report it, do not editorialise it.
8. Do not commit or push. Do not edit calllogs.py, names.py or audit_day.py; if they
   misbehave, describe exactly what happened. Only update the build register if you
   found a new platform limit or a claim in it is wrong.
```

---

## Routine 2 — Curia's call logs

**Connectors: Google Drive**

```
You are uploading Pacific Link Global's raw Zoom Phone call logs for Curia's own
auditor. It is 6pm Manila and today's shift has just ended.

This is NOT the shift audit and it judges nobody. It is the call log, reproduced,
one CSV per caller, exactly as Elaine has been exporting them by hand.

1. cd /home/user/Claude && git fetch origin claude/business-agent-dev-9jxs55 &&
   git checkout claude/business-agent-dev-9jxs55 &&
   git pull origin claude/business-agent-dev-9jxs55
2. Read CLAUDE.md in full.
3. Check Zoom is reachable first:
   curl -sS -o /dev/null -w '%{http_code}\n' https://api.zoom.us/v2/users
   Expect 401. A tunnel error means the wrong environment — say so and stop.
4. cd /home/user/Claude/agent && python3 -m business_agent.calllog_export --out /tmp/calllogs
   No date argument: it defaults to today in Manila. It writes one CSV per caller
   who actually worked the shift, named the way Curia already have them.
5. In Google Drive, inside folder 1ItFWjAuL_k9dpsZ4wR9Z6ixtcqUBvO-1 (this is the
   2026 folder, not a year index):
   - find the month folder for today, e.g. "September". If it does not exist, create it.
   - inside it create the day folder named like "14/9" — day slash month, no leading
     zeros. If it already exists, use it and do not duplicate files already there.
6. Upload every CSV from /tmp/calllogs into that day folder as text/csv, keeping the
   exact filename. Do not convert them to Google Sheets.
7. Tell Brendon how many files you uploaded, the folder link, and the total call count.
   If any upload failed, say which and why — do not quietly skip it.
8. Do not commit or push. Do not touch any other folder. Do not delete or overwrite
   anything Elaine has already uploaded.
```

**Before this one runs unattended, check with Brendon:** each caller's CSV is
30–70KB and there are around 22 a day. That content has to pass through the
session to reach Drive, which is slow and expensive. If it proves impractical,
the fallback is that the agent generates the files and Brendon drags the folder
in himself — about thirty seconds — or an Apps Script does it inside his own
account.

---

## Notes

- **Shifts are Sunday to Thursday.** Friday and Saturday have none. Brendon will
  say if that changes.
- The audit's completes figure is calibrated against Elaine's manual audit and
  agrees on 19 of 22 callers. **Time off the phone is not** — it is still being
  settled, and must never be sent to a caller.
- If a Routine ever reports Zoom failing, the first check is the environment, not
  the credentials.

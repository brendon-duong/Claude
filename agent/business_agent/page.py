"""Rendering a roster as a page you can read and share.

Static HTML on purpose: the roster is a record of a decision, so what it says
should not depend on scripts running. Everything is visible the moment it
loads.
"""

from __future__ import annotations

import html
from datetime import date

from .roster_plan import RosterPlan

_TIER_LABEL = {"trusted": "Clean record", "watch": "Watch", "do_not_roster": "Barred"}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _figure(value: object, label: str, note: str = "") -> str:
    note_html = f'<span class="figure-note">{_esc(note)}</span>' if note else ""
    return (
        '<div class="figure">'
        f'<span class="figure-value">{_esc(value)}</span>'
        f'<span class="figure-label">{_esc(label)}</span>{note_html}'
        "</div>"
    )


def _roster_table(shift) -> str:
    rows = []
    for index, assignment in enumerate(shift.assigned, 1):
        person = assignment.person
        tier_class = "watch" if person.tier == "watch" else "clean"
        chip = (
            f'<span class="chip chip-{tier_class}">{_esc(_TIER_LABEL[person.tier])}</span>'
            if person.tier == "watch"
            else ""
        )
        rows.append(
            "<tr>"
            f'<td class="num rank">{index}</td>'
            f'<td class="who">{_esc(assignment.name)}{chip}</td>'
            f'<td class="num">{person.avg_completes:.1f}</td>'
            f'<td class="num quiet">{person.clean_audits}/{person.audits}</td>'
            "</tr>"
        )

    if shift.shortfall:
        rows.append(
            '<tr class="short-row"><td class="num rank">—</td>'
            f'<td class="who" colspan="3">{shift.shortfall} slot(s) unfilled</td></tr>'
        )

    return (
        '<div class="table-wrap"><table>'
        "<thead><tr>"
        '<th class="num">#</th><th>Caller</th>'
        '<th class="num">Completes<br><span class="unit">per shift</span></th>'
        '<th class="num">Clean<br><span class="unit">audits</span></th>'
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _day_sections(plan: RosterPlan) -> str:
    by_day: dict[date, list] = {}
    for shift in plan.shifts:
        by_day.setdefault(shift.day, []).append(shift)

    sections = []
    for day, shifts in sorted(by_day.items()):
        needed = sum(s.needed for s in shifts)
        short = sum(s.shortfall for s in shifts)
        status = (
            f'<span class="day-status short">{short} short</span>'
            if short
            else '<span class="day-status ok">Fully staffed</span>'
        )
        polls = []
        for shift in shifts:
            volunteers = (
                f'<span class="poll-meta">{shift.volunteers} volunteered</span>'
                if shift.from_poll
                else ""
            )
            polls.append(
                '<section class="poll">'
                '<header class="poll-head">'
                f'<h3>{_esc(shift.poll)}</h3>'
                f'<span class="poll-count">{shift.filled} of {shift.needed} callers</span>'
                f"{volunteers}"
                "</header>"
                f"{_roster_table(shift)}"
                "</section>"
            )
        sections.append(
            '<article class="day">'
            '<header class="day-head">'
            f'<h2>{_esc(f"{day:%A}")} <span class="day-date">{day.day} {day:%b}</span></h2>'
            f'<span class="day-need">{needed} callers needed</span>{status}'
            "</header>"
            f"{''.join(polls)}"
            "</article>"
        )
    return "".join(sections)


def _barred_section(plan: RosterPlan) -> str:
    if not plan.excluded:
        return ""
    cards = []
    for person in sorted(plan.excluded, key=lambda p: -p.integrity_fails):
        concerns = "".join(
            f"<li>{_esc(concern)}</li>" for concern in person.concerns[:2]
        )
        cards.append(
            '<li class="barred-item">'
            f'<span class="barred-name">{_esc(person.name)}</span>'
            f'<span class="barred-head">{_esc(person.headline)}</span>'
            f'<ul class="barred-why">{concerns}</ul>'
            "</li>"
        )
    return (
        '<section class="panel panel-barred">'
        "<h2>Not offered a shift</h2>"
        "<p>Barred by their audit history. Completing surveys the call logs do not "
        "support is not completing surveys, so productivity never overrides this.</p>"
        f'<ul class="barred-list">{"".join(cards)}</ul>'
        "</section>"
    )


def _poll_section(plan: RosterPlan) -> str:
    polled = any(shift.from_poll for shift in plan.shifts)
    if polled:
        lead = (
            "This roster was picked from the people who put their hand up in the "
            "WhatsApp poll."
        )
    else:
        lead = (
            "No poll results yet, so this roster was picked from everyone still "
            "active. Run the poll and paste the results back, and each day is "
            "chosen from the people who said they can actually work it."
        )
    example = (
        "Sunday 13 Sep\n"
        "Lia Villapaz\n"
        "Kharen Ybas\n"
        "Tristan Bustamante\n"
        "\n"
        "Monday 14 Sep\n"
        "1. Jasmine Magdayao\n"
        "- Mary Joy Villacura\n"
    )
    return (
        '<section class="panel panel-poll">'
        "<h2>Feeding in the poll</h2>"
        f"<p>{_esc(lead)}</p>"
        "<p>Paste the results in this shape — a day, then the names under it. "
        "Bullets, numbering and vote counts are all fine.</p>"
        f"<pre>{_esc(example)}</pre>"
        "<p>Names that match nobody on the books, and anyone who volunteers but is "
        "barred, are both listed back rather than quietly dropped.</p>"
        "</section>"
    )


def _duplicates_section(pairs: list[tuple[str, str, str]], total: int) -> str:
    if not pairs:
        return ""
    items = "".join(
        f"<li><span>{_esc(a)}</span><span class='dup-join'>and</span>"
        f"<span>{_esc(b)}</span></li>"
        for a, b, _ in pairs
    )
    more = (
        f"<p class='dup-more'>…and {total - len(pairs)} more pairs.</p>"
        if total > len(pairs)
        else ""
    )
    return (
        '<section class="panel panel-warn">'
        f"<h2>{total} names look like the same person twice</h2>"
        "<p>Each spelling splits that caller's audit history in two, which flatters "
        "the half without the failures. Nothing is merged automatically — a wrong "
        "merge would pin one person's record on another. Fix the spelling in the "
        "audit sheet and the histories join up.</p>"
        f'<ul class="dup-list">{items}</ul>{more}'
        "</section>"
    )


def render_roster_page(
    plan: RosterPlan,
    *,
    business_name: str,
    audit_count: int,
    audit_from: date,
    audit_to: date,
    duplicates: list[tuple[str, str, str]] | None = None,
    duplicate_total: int = 0,
) -> str:
    """Render the whole roster as a standalone HTML page."""
    used = len(plan.shifts_per_person())
    fill_state = (
        f"{plan.total_shortfall} unfilled" if plan.total_shortfall else "Fully staffed"
    )
    fill_class = "short" if plan.total_shortfall else "ok"

    return f"""<title>{_esc(business_name)} Caller Roster</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --paper:#eef1f4; --surface:#ffffff; --surface-2:#f7f9fa;
  --ink:#151a21; --ink-soft:#3d4854; --muted:#67737f; --line:#d7dee4;
  --signal:#0f6b6b; --signal-soft:#e2efee;
  --ok:#2a6a48; --ok-soft:#e2efe7;
  --watch:#8a5a0b; --watch-soft:#f6eddc;
  --barred:#9a3227; --barred-soft:#f7e6e3;
  --display:'Archivo',system-ui,sans-serif;
  --body:'Public Sans',system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0e1217; --surface:#161b22; --surface-2:#1c222a;
    --ink:#e9edf2; --ink-soft:#c2cbd5; --muted:#8d99a6; --line:#2a323c;
    --signal:#57b3ac; --signal-soft:#16302f;
    --ok:#6fbf92; --ok-soft:#16301f;
    --watch:#d6a54e; --watch-soft:#33280f;
    --barred:#e0796c; --barred-soft:#341a17;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0e1217; --surface:#161b22; --surface-2:#1c222a;
  --ink:#e9edf2; --ink-soft:#c2cbd5; --muted:#8d99a6; --line:#2a323c;
  --signal:#57b3ac; --signal-soft:#16302f;
  --ok:#6fbf92; --ok-soft:#16301f;
  --watch:#d6a54e; --watch-soft:#33280f;
  --barred:#e0796c; --barred-soft:#341a17;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink);
  font-family:var(--body); font-size:16px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:53rem; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
h1,h2,h3 {{ font-family:var(--display); text-wrap:balance; margin:0; }}

.masthead {{ display:flex; flex-direction:column; gap:.6rem; padding-bottom:1.5rem;
  border-bottom:2px solid var(--ink); }}
.eyebrow {{ font-family:var(--mono); font-size:.72rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--signal); }}
.masthead h1 {{ font-size:clamp(1.9rem,4.5vw,2.7rem); font-weight:700; letter-spacing:-.02em; }}
.dates {{ font-size:1.05rem; color:var(--ink-soft); }}
.state {{ display:inline-flex; align-items:center; gap:.5rem; align-self:flex-start;
  font-family:var(--mono); font-size:.8rem; padding:.3rem .65rem; border-radius:2px; }}
.state.ok {{ background:var(--ok-soft); color:var(--ok); }}
.state.short {{ background:var(--barred-soft); color:var(--barred); }}

.figures {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));
  gap:1px; background:var(--line); border:1px solid var(--line); margin:1.75rem 0 2.5rem; }}
.figure {{ background:var(--surface); padding:1rem 1.1rem; display:flex;
  flex-direction:column; gap:.15rem; }}
.figure-value {{ font-family:var(--display); font-size:1.75rem; font-weight:700;
  line-height:1.1; font-variant-numeric:tabular-nums; }}
.figure-label {{ font-size:.82rem; color:var(--muted); }}
.figure-note {{ font-family:var(--mono); font-size:.7rem; color:var(--muted); }}

.day {{ margin-bottom:2.5rem; }}
.day-head {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.75rem;
  padding-bottom:.5rem; border-bottom:1px solid var(--ink); margin-bottom:1rem; }}
.day-head h2 {{ font-size:1.4rem; font-weight:600; letter-spacing:-.01em; }}
.day-date {{ color:var(--muted); font-weight:500; }}
.day-need {{ font-size:.85rem; color:var(--muted); margin-left:auto; }}
.day-status {{ font-family:var(--mono); font-size:.72rem; padding:.15rem .5rem; border-radius:2px; }}
.day-status.ok {{ background:var(--ok-soft); color:var(--ok); }}
.day-status.short {{ background:var(--barred-soft); color:var(--barred); }}

.poll {{ background:var(--surface); border:1px solid var(--line); margin-bottom:1rem; }}
.poll-head {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:.6rem;
  padding:.85rem 1rem; border-bottom:1px solid var(--line); background:var(--surface-2); }}
.poll-head h3 {{ font-size:1rem; font-weight:600; }}
.poll-count {{ font-family:var(--mono); font-size:.76rem; color:var(--signal); }}
.poll-meta {{ font-size:.76rem; color:var(--muted); margin-left:auto; }}

.table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
th {{ text-align:left; font-family:var(--mono); font-size:.68rem; font-weight:500;
  letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
  padding:.6rem 1rem; border-bottom:1px solid var(--line); vertical-align:bottom; }}
th .unit {{ letter-spacing:.04em; text-transform:none; }}
td {{ padding:.5rem 1rem; border-bottom:1px solid var(--line); }}
tbody tr:last-child td {{ border-bottom:none; }}
.num {{ text-align:right; font-family:var(--mono); font-variant-numeric:tabular-nums;
  white-space:nowrap; }}
.rank {{ color:var(--muted); width:2.5rem; }}
.quiet {{ color:var(--muted); }}
.who {{ font-weight:500; }}
.short-row td {{ color:var(--barred); font-family:var(--mono); font-size:.85rem; }}
.chip {{ font-family:var(--mono); font-size:.65rem; letter-spacing:.05em;
  padding:.1rem .4rem; margin-left:.5rem; border-radius:2px; vertical-align:.08em; }}
.chip-watch {{ background:var(--watch-soft); color:var(--watch); }}

.panel {{ background:var(--surface); border:1px solid var(--line);
  padding:1.4rem 1.5rem; margin-bottom:1.5rem; }}
.panel h2 {{ font-size:1.15rem; font-weight:600; margin-bottom:.5rem; }}
.panel p {{ margin:0 0 .75rem; color:var(--ink-soft); max-width:62ch; }}
.panel p:last-child {{ margin-bottom:0; }}
.panel-barred {{ border-left:3px solid var(--barred); }}
.panel-warn {{ border-left:3px solid var(--watch); }}
.panel-poll {{ border-left:3px solid var(--signal); }}

.barred-list {{ list-style:none; margin:1rem 0 0; padding:0; display:grid; gap:.9rem; }}
.barred-item {{ display:grid; gap:.15rem; padding-bottom:.9rem;
  border-bottom:1px solid var(--line); }}
.barred-item:last-child {{ border-bottom:none; padding-bottom:0; }}
.barred-name {{ font-weight:600; }}
.barred-head {{ font-size:.85rem; color:var(--barred); font-family:var(--mono); }}
.barred-why {{ margin:.3rem 0 0; padding-left:1.1rem; color:var(--muted); font-size:.85rem; }}

.dup-list {{ list-style:none; margin:1rem 0 0; padding:0; display:grid; gap:.4rem;
  font-size:.9rem; }}
.dup-list li {{ display:flex; flex-wrap:wrap; gap:.45rem; align-items:baseline; }}
.dup-join {{ color:var(--muted); font-size:.8rem; }}
.dup-more {{ margin-top:1rem; font-size:.85rem; color:var(--muted); }}

pre {{ background:var(--surface-2); border:1px solid var(--line); padding:.9rem 1rem;
  font-family:var(--mono); font-size:.82rem; line-height:1.6; overflow-x:auto;
  margin:0 0 .9rem; color:var(--ink); }}

footer {{ margin-top:2.5rem; padding-top:1.25rem; border-top:1px solid var(--line);
  font-size:.85rem; color:var(--muted); }}
footer strong {{ color:var(--ink); }}
</style>

<div class="wrap">
  <header class="masthead">
    <span class="eyebrow">Draft roster · nothing sent</span>
    <h1>{_esc(business_name)} caller roster</h1>
    <p class="dates">{_esc(f"{plan.start:%A %d %B}")} — {_esc(f"{plan.end:%A %d %B %Y}")}</p>
    <span class="state {fill_class}">{_esc(fill_state)}</span>
  </header>

  <div class="figures">
    {_figure(f"{plan.total_filled}/{plan.total_needed}", "Slots filled", f"{len(plan.shifts)} polls")}
    {_figure(used, "Callers rostered", f"{len(plan.bench)} on the bench")}
    {_figure(len(plan.excluded), "Barred by audits", "not offered a shift")}
    {_figure(f"{audit_count:,}", "Audits read", f"{audit_from:%b %Y} – {audit_to:%b %Y}")}
  </div>

  {_day_sections(plan)}

  {_barred_section(plan)}
  {_poll_section(plan)}
  {_duplicates_section(duplicates or [], duplicate_total)}

  <footer>
    <strong>Nothing here has been sent to anyone.</strong> Callers are ranked by
    completed surveys per shift, taken from the call logs rather than what was
    declared, so a caller cannot climb this list by over-declaring. Audit history
    gates the list: anyone barred is never offered a shift regardless of volume.
  </footer>
</div>
"""

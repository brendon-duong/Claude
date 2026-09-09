"""The weekly dashboard: who is working, and the numbers behind the decision.

Rendered server-side into static HTML so every figure is on the page the
moment it loads — a dashboard that needs scripts to run before it says
anything is no use on a phone with bad signal.

Charts are single-hue on purpose. Each one answers a magnitude question
("how many slots", "how many callers score this well"), and magnitude is one
hue; the status colours are reserved for good / watch / barred and always
ship beside a word, never as colour alone.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

# Validated against the light (#ffffff) and dark (#161b22) chart surfaces:
# chroma above the grey floor and contrast >= 3:1 in both.
CHART_HUE_LIGHT = "#0a8f86"
CHART_HUE_DARK = "#4fc3b8"

TIER_WORD = {"trusted": "clean", "watch": "watch", "do_not_roster": "barred"}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _bar_chart(
    rows: list[tuple[str, float]],
    *,
    reference: float | None = None,
    reference_label: str = "",
    value_suffix: str = "",
) -> str:
    """A horizontal bar chart. Rows are (label, value), highest value sets the scale."""
    if not rows:
        return ""
    top = max(max(value for _, value in rows), reference or 0) * 1.08 or 1
    bar_height, gap = 34, 12
    label_width, right_pad = 96, 54
    height = len(rows) * (bar_height + gap) - gap
    width = 640
    plot_width = width - label_width - right_pad

    parts = [
        f'<svg viewBox="0 0 {width} {height + 26}" role="img" '
        f'class="chart" preserveAspectRatio="xMinYMin meet">'
    ]

    if reference is not None:
        x = label_width + plot_width * (reference / top)
        parts.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" '
            f'class="ref-line" stroke-dasharray="4 4" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{height + 18}" class="ref-label" '
            f'text-anchor="middle">{_esc(reference_label)}</text>'
        )

    for index, (label, value) in enumerate(rows):
        y = index * (bar_height + gap)
        bar_width = max(2.0, plot_width * (value / top))
        parts.append(
            f'<text x="{label_width - 12}" y="{y + bar_height / 2 + 5}" '
            f'class="bar-label" text-anchor="end">{_esc(label)}</text>'
            f'<rect x="{label_width}" y="{y}" width="{bar_width:.1f}" '
            f'height="{bar_height}" rx="4" class="bar"><title>'
            f'{_esc(label)}: {_esc(value)}{_esc(value_suffix)}</title></rect>'
            f'<text x="{label_width + bar_width + 10:.1f}" y="{y + bar_height / 2 + 5}" '
            f'class="bar-value">{_esc(value)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _column_chart(rows: list[tuple[str, int]], *, marker_index: int | None, marker_label: str) -> str:
    """A distribution. Columns are (bucket label, count)."""
    if not rows:
        return ""
    top = max(count for _, count in rows) or 1
    width, height = 640, 200
    slot = width / len(rows)
    bar_width = slot * 0.62

    parts = [f'<svg viewBox="0 0 {width} {height + 46}" role="img" class="chart" preserveAspectRatio="xMinYMin meet">']
    for index, (label, count) in enumerate(rows):
        bar_height = (count / top) * height
        x = index * slot + (slot - bar_width) / 2
        y = height - bar_height
        if count:
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_height:.1f}" rx="4" class="bar"><title>'
                f'{_esc(count)} caller(s) at {_esc(label)} completes/shift</title></rect>'
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 7:.1f}" class="bar-value" '
                f'text-anchor="middle">{count}</text>'
            )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{height + 20}" class="bar-label" '
            f'text-anchor="middle">{_esc(label)}</text>'
        )
    if marker_index is not None:
        # Marked under the axis rather than as a line through the columns: a
        # vertical rule crossed the value label on the tallest bar it passed.
        x = marker_index * slot + slot / 2
        parts.append(
            f'<path d="M{x - 5:.1f} {height + 30} L{x:.1f} {height + 25} '
            f'L{x + 5:.1f} {height + 30}" class="ref-line" fill="none" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{height + 43}" class="ref-label" text-anchor="middle">'
            f"{_esc(marker_label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _figure(value: object, label: str, note: str = "", tone: str = "") -> str:
    tone_class = f" figure-{tone}" if tone else ""
    note_html = f'<span class="figure-note">{_esc(note)}</span>' if note else ""
    return (
        f'<div class="figure{tone_class}"><span class="figure-value">{_esc(value)}</span>'
        f'<span class="figure-label">{_esc(label)}</span>{note_html}</div>'
    )


def render_dashboard(data: dict, *, business_name: str = "Pacific Link Global") -> str:
    week = data["week"]
    cap = data["capacity"]
    tiers = data["tiers"]
    prod = data["productivity"]
    audits = data["audits"]
    quality = data["dataQuality"]

    weeks = data["weeks"]
    demand_rows = [(w["start"], w["slots"]) for w in weeks]
    peak = max(w["slots"] for w in weeks)
    over_capacity = peak > cap["weeklyCapacity"]

    hist_rows = [(h["bucket"], h["count"]) for h in prod["hist"]]
    median_bucket = int(prod["median"])

    # Roster, grouped by day.
    days: dict[str, list] = {}
    for shift in data["roster"]:
        days.setdefault(shift["day"], []).append(shift)
    roster_html = []
    for day, shifts in days.items():
        blocks = []
        for shift in shifts:
            names = "".join(
                f'<li><span class="caller">{_esc(c["name"])}</span>'
                f'<span class="metric">{c["completes"]:.1f}</span>'
                f'<span class="metric quiet">{_esc(c["clean"])}</span>'
                + (
                    f'<span class="pill pill-watch">watch</span>'
                    if c["tier"] == "watch"
                    else '<span class="pill-gap"></span>'
                )
                + "</li>"
                for c in shift["callers"]
            )
            blocks.append(
                f'<div class="poll"><h4>{_esc(shift["poll"])}'
                f'<span class="poll-need">{len(shift["callers"])} of {shift["needed"]}</span></h4>'
                f'<ul class="callers"><li class="head"><span>Caller</span>'
                f'<span class="metric">Comp<br>/shift</span>'
                f'<span class="metric">Clean<br>audits</span><span></span></li>{names}</ul></div>'
            )
        roster_html.append(
            f'<article class="day"><h3>{_esc(day)}</h3>{"".join(blocks)}</article>'
        )

    barred_html = "".join(
        f'<li><span class="barred-name">{_esc(b["name"])}</span>'
        f'<span class="barred-why">{_esc(b["headline"])}</span></li>'
        for b in data["barred"]
    )

    capacity_note = (
        f"Peak week needs {peak}; capacity is {cap['weeklyCapacity']}"
        if not over_capacity
        else f"Peak week needs {peak} — {peak - cap['weeklyCapacity']} beyond capacity"
    )

    return f"""<title>Pacific Link Roster Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --paper:#eef1f4; --surface:#fff; --surface-2:#f7f9fa;
  --ink:#151a21; --ink-soft:#3d4854; --muted:#67737f; --line:#d7dee4;
  --accent:{CHART_HUE_LIGHT};
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
    --accent:{CHART_HUE_DARK};
    --ok:#6fbf92; --ok-soft:#16301f;
    --watch:#d6a54e; --watch-soft:#33280f;
    --barred:#e0796c; --barred-soft:#341a17;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0e1217; --surface:#161b22; --surface-2:#1c222a;
  --ink:#e9edf2; --ink-soft:#c2cbd5; --muted:#8d99a6; --line:#2a323c;
  --accent:{CHART_HUE_DARK};
  --ok:#6fbf92; --ok-soft:#16301f;
  --watch:#d6a54e; --watch-soft:#33280f;
  --barred:#e0796c; --barred-soft:#341a17;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ background:var(--paper); color:var(--ink); font-family:var(--body);
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:60rem; margin:0 auto; padding:2.25rem 1.25rem 4rem; }}
h1,h2,h3,h4 {{ font-family:var(--display); margin:0; text-wrap:balance; }}

.masthead {{ display:flex; flex-direction:column; gap:.4rem;
  padding-bottom:1.25rem; border-bottom:2px solid var(--ink); }}
.eyebrow {{ font-family:var(--mono); font-size:.72rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--accent); }}
.masthead h1 {{ font-size:clamp(1.8rem,4.5vw,2.5rem); font-weight:700; letter-spacing:-.02em; }}
.masthead p {{ margin:0; color:var(--ink-soft); }}

.figures {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));
  gap:1px; background:var(--line); border:1px solid var(--line); margin:1.5rem 0 2.25rem; }}
.figure {{ background:var(--surface); padding:1rem 1.1rem; display:flex;
  flex-direction:column; gap:.1rem; }}
.figure-value {{ font-family:var(--display); font-size:1.8rem; font-weight:700;
  line-height:1.1; font-variant-numeric:tabular-nums; }}
.figure-label {{ font-size:.82rem; color:var(--muted); }}
.figure-note {{ font-family:var(--mono); font-size:.7rem; color:var(--muted); margin-top:.15rem; }}
.figure-warn .figure-value {{ color:var(--watch); }}
.figure-bad .figure-value {{ color:var(--barred); }}

section {{ margin-bottom:2.25rem; }}
section > h2 {{ font-size:1.25rem; font-weight:600; margin-bottom:.3rem; }}
.lede {{ color:var(--ink-soft); margin:0 0 1rem; max-width:62ch; }}

.panel {{ background:var(--surface); border:1px solid var(--line); padding:1.25rem 1.4rem; }}
.chart {{ width:100%; height:auto; display:block; overflow:visible; }}
.bar {{ fill:var(--accent); }}
.bar:hover {{ opacity:.82; }}
.bar-label {{ fill:var(--muted); font-family:var(--mono); font-size:12px; }}
.bar-value {{ fill:var(--ink); font-family:var(--mono); font-size:12px;
  font-variant-numeric:tabular-nums; }}
.ref-line {{ stroke:var(--muted); }}
.ref-label {{ fill:var(--muted); font-family:var(--mono); font-size:11px; }}

.day {{ background:var(--surface); border:1px solid var(--line); margin-bottom:1rem; }}
.day h3 {{ font-size:1.05rem; font-weight:600; padding:.8rem 1.1rem;
  border-bottom:1px solid var(--line); background:var(--surface-2); }}
.poll {{ padding:.9rem 1.1rem; border-bottom:1px solid var(--line); }}
.poll:last-child {{ border-bottom:none; }}
.poll h4 {{ font-size:.92rem; font-weight:600; display:flex; gap:.6rem;
  align-items:baseline; margin-bottom:.5rem; }}
.poll-need {{ font-family:var(--mono); font-size:.75rem; color:var(--accent); }}
.callers {{ list-style:none; margin:0; padding:0; }}
.callers li {{ display:grid; grid-template-columns:1fr 4.5rem 4.5rem 4rem;
  gap:.5rem; align-items:center; padding:.28rem 0; border-bottom:1px solid var(--line); }}
.callers li:last-child {{ border-bottom:none; }}
.callers li.head {{ font-family:var(--mono); font-size:.65rem; letter-spacing:.06em;
  text-transform:uppercase; color:var(--muted); padding-bottom:.4rem; }}
.caller {{ font-weight:500; font-size:.92rem; }}
.metric {{ font-family:var(--mono); font-size:.82rem; text-align:right;
  font-variant-numeric:tabular-nums; }}
.quiet {{ color:var(--muted); }}
.pill {{ font-family:var(--mono); font-size:.64rem; padding:.1rem .4rem;
  border-radius:2px; text-align:center; }}
.pill-watch {{ background:var(--watch-soft); color:var(--watch); }}

.risk {{ display:grid; gap:1px; background:var(--line); border:1px solid var(--line); }}
.risk-item {{ background:var(--surface); padding:.9rem 1.1rem; display:flex;
  flex-wrap:wrap; gap:.5rem; align-items:baseline; }}
.risk-item strong {{ font-family:var(--display); }}
.risk-tag {{ font-family:var(--mono); font-size:.65rem; padding:.12rem .45rem;
  border-radius:2px; text-transform:uppercase; letter-spacing:.05em; }}
.tag-watch {{ background:var(--watch-soft); color:var(--watch); }}
.tag-bad {{ background:var(--barred-soft); color:var(--barred); }}
.tag-ok {{ background:var(--ok-soft); color:var(--ok); }}
.risk-note {{ color:var(--ink-soft); font-size:.9rem; flex-basis:100%; margin:0; }}

.barred-list {{ list-style:none; margin:.75rem 0 0; padding:0; display:grid; gap:.55rem; }}
.barred-list li {{ display:grid; gap:.05rem; }}
.barred-name {{ font-weight:600; }}
.barred-why {{ font-family:var(--mono); font-size:.78rem; color:var(--barred); }}

footer {{ margin-top:2rem; padding-top:1.1rem; border-top:1px solid var(--line);
  font-size:.85rem; color:var(--muted); }}
</style>

<div class="wrap">
  <header class="masthead">
    <span class="eyebrow">Draft · nothing sent</span>
    <h1>{_esc(business_name)} roster dashboard</h1>
    <p>Week of {_esc(week["start"])} — built {_esc(data["generatedFor"])} from
       {audits["total"]:,} audits and the Curia schedule.</p>
  </header>

  <div class="figures">
    {_figure(f'{week["filled"]}/{week["needed"]}', "Slots filled next week", f'{week["polls"]} polls')}
    {_figure(week["used"], "Callers rostered", f'{week["bench"]} on the bench')}
    {_figure(cap["rosterable"], "Rosterable right now", f'{cap["barredActive"]} active but barred')}
    {_figure(prod["median"], "Median completes/shift", f'best {prod["max"]}')}
  </div>

  <section>
    <h2>Can you staff what's coming?</h2>
    <p class="lede">Caller-slots per business week (Sunday–Thursday), against what
      {cap["rosterable"]} rosterable callers can cover at {cap["maxPerWeek"]} shifts each.
      {_esc(capacity_note)}.</p>
    <div class="panel">
      {_bar_chart(demand_rows, reference=cap["weeklyCapacity"],
                  reference_label=f'capacity {cap["weeklyCapacity"]}', value_suffix=" slots")}
    </div>
  </section>

  <section>
    <h2>How the team is performing</h2>
    <p class="lede">Completed surveys per shift, from the call logs rather than what
      was declared. {prod["n"]} active callers.</p>
    <div class="panel">
      {_column_chart(hist_rows, marker_index=median_bucket, marker_label=f'median {prod["median"]}')}
    </div>
  </section>

  <section>
    <h2>Who's working</h2>
    <p class="lede">Ranked by completes per shift, with anyone barred by their audit
      history excluded before ranking.</p>
    {"".join(roster_html)}
  </section>

  <section>
    <h2>What needs a decision</h2>
    <div class="risk">
      <div class="risk-item">
        <span class="risk-tag tag-bad">integrity</span>
        <strong>{audits["missedOverDeclarations"]} over-declarations marked “N”</strong>
        <p class="risk-note">Rows where the caller declared more completed surveys than the
          call logs support, but the reviewer's Y/N column says no discrepancy. Worth asking
          whoever fills that column.</p>
      </div>
      <div class="risk-item">
        <span class="risk-tag tag-watch">data</span>
        <strong>{quality["duplicatePairs"]} names look like the same person twice</strong>
        <p class="risk-note">Each variant splits that caller's audit history, which flatters
          the half without the failures. Fixing the spellings is the single highest-value
          cleanup available.</p>
      </div>
      <div class="risk-item">
        <span class="risk-tag {"tag-ok" if audits["daysSinceLast"] <= 7 else "tag-watch"}">audits</span>
        <strong>Last audit {audits["daysSinceLast"]} day(s) ago</strong>
        <p class="risk-note">Rankings track recent performance — an audit's influence halves
          every 90 days. If auditing stops, the roster slowly reverts to who was good months ago.</p>
      </div>
      <div class="risk-item">
        <span class="risk-tag tag-watch">roster</span>
        <strong>{len(data["barred"])} active callers barred from shifts</strong>
        <ul class="barred-list">{barred_html}</ul>
      </div>
    </div>
  </section>

  <footer>
    Nothing here has been sent to anyone. Callers are ranked on completed surveys
    taken from the call logs, so nobody can climb this list by over-declaring, and
    audit history gates the list before productivity is considered.
  </footer>
</div>
"""


def build(data_path: str | Path, out_path: str | Path, *, business_name: str = "Pacific Link Global") -> Path:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    out = Path(out_path)
    out.write_text(render_dashboard(data, business_name=business_name), encoding="utf-8")
    return out

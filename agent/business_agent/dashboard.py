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

# Validated against the light (#ffffff) and dark (#131a22) chart surfaces:
# chroma above the grey floor and contrast >= 3:1 in both.
CHART_HUE_LIGHT = "#0a8f86"
CHART_HUE_DARK = "#4fc3b8"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _bar_chart(rows, *, reference=None, reference_label="", value_suffix=""):
    """Horizontal bars. Rows are (label, value); the largest sets the scale."""
    if not rows:
        return ""
    top = max(max(v for _, v in rows), reference or 0) * 1.06 or 1
    bar_h, gap, label_w, right_pad = 44, 14, 104, 62
    height = len(rows) * (bar_h + gap) - gap
    width = 700
    plot_w = width - label_w - right_pad
    parts = [
        f'<svg viewBox="0 0 {width} {height + 30}" role="img" class="chart" '
        f'preserveAspectRatio="xMinYMin meet">'
    ]
    if reference is not None:
        x = label_w + plot_w * (reference / top)
        parts.append(
            f'<line x1="{x:.1f}" y1="-4" x2="{x:.1f}" y2="{height + 2}" class="ref-line" '
            f'stroke-dasharray="3 5" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{height + 22}" class="ref-label" text-anchor="middle">'
            f"{_esc(reference_label)}</text>"
        )
    for i, (label, value) in enumerate(rows):
        y = i * (bar_h + gap)
        w = max(3.0, plot_w * (value / top))
        parts.append(
            f'<text x="{label_w - 14}" y="{y + bar_h / 2 + 5}" class="bar-label" '
            f'text-anchor="end">{_esc(label)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" '
            f'class="bar"><title>{_esc(label)}: {_esc(value)}{_esc(value_suffix)}</title></rect>'
            f'<text x="{label_w + w + 12:.1f}" y="{y + bar_h / 2 + 6}" class="bar-value">'
            f"{_esc(value)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _column_chart(rows, *, marker_index, marker_label):
    """A distribution. Columns are (bucket label, count)."""
    if not rows:
        return ""
    top = max(c for _, c in rows) or 1
    width, height = 700, 210
    slot = width / len(rows)
    bar_w = slot * 0.58
    parts = [
        f'<svg viewBox="0 0 {width} {height + 54}" role="img" class="chart" '
        f'preserveAspectRatio="xMinYMin meet">'
    ]
    for i, (label, count) in enumerate(rows):
        h = (count / top) * height
        x = i * slot + (slot - bar_w) / 2
        y = height - h
        if count:
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'rx="4" class="bar"><title>{_esc(count)} caller(s) at '
                f'{_esc(label)} completes/shift</title></rect>'
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" class="bar-value" '
                f'text-anchor="middle">{count}</text>'
            )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height + 20}" class="bar-label" '
            f'text-anchor="middle">{_esc(label)}</text>'
        )
    if marker_index is not None:
        # Marked under the axis rather than as a rule through the columns: a
        # vertical line crossed the value label on the tallest bar it passed.
        x = marker_index * slot + slot / 2
        parts.append(
            f'<path d="M{x - 6:.1f} {height + 36} L{x:.1f} {height + 30} '
            f'L{x + 6:.1f} {height + 36}" class="ref-line" fill="none" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{height + 50}" class="ref-label" text-anchor="middle">'
            f"{_esc(marker_label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _day_strip(days: list[dict]) -> str:
    """The week's shape, Sunday to Thursday — the rhythm this business runs on."""
    if not days:
        return ""
    top = max(d["slots"] for d in days) or 1
    cells = []
    for day in days:
        name, _, rest = day["day"].partition(" ")
        share = day["slots"] / top
        polls = "".join(f"<span>{_esc(p)}</span>" for p in day["polls"])
        cells.append(
            f'<div class="strip-cell">'
            f'<span class="strip-day">{_esc(name)}</span>'
            f'<span class="strip-date">{_esc(rest)}</span>'
            f'<div class="strip-track"><div class="strip-fill" '
            f'style="height:{share * 100:.0f}%"></div></div>'
            f'<span class="strip-slots">{day["slots"]}</span>'
            f'<div class="strip-polls">{polls}</div>'
            f"</div>"
        )
    return f'<div class="strip">{"".join(cells)}</div>'


def _figure(value, label, note=""):
    note_html = f'<span class="fig-note">{_esc(note)}</span>' if note else ""
    return (
        f'<div class="fig"><span class="fig-value">{_esc(value)}</span>'
        f'<span class="fig-label">{_esc(label)}</span>{note_html}</div>'
    )


def render_dashboard(data: dict, *, business_name: str = "Pacific Link Global") -> str:
    week, cap = data["week"], data["capacity"]
    prod, audits, quality = data["productivity"], data["audits"], data["dataQuality"]

    demand_rows = [(w["start"], w["slots"]) for w in data["weeks"]]
    peak = max(w["slots"] for w in data["weeks"])
    hist_rows = [(h["bucket"], h["count"]) for h in prod["hist"]]
    top_caller = data.get("topCaller", {})

    capacity_note = (
        f"Peak week needs {peak}; {cap['rosterable']} rosterable callers cover "
        f"{cap['weeklyCapacity']} at {cap['maxPerWeek']} shifts each."
        if peak <= cap["weeklyCapacity"]
        else f"Peak week needs {peak} — {peak - cap['weeklyCapacity']} beyond capacity."
    )

    days: dict[str, list] = {}
    for shift in data["roster"]:
        days.setdefault(shift["day"], []).append(shift)
    cards = []
    for day, shifts in days.items():
        name, _, rest = day.partition(" ")
        blocks = []
        for shift in shifts:
            rows = "".join(
                f'<li><span class="rank">{i}</span>'
                f'<span class="who">{_esc(c["name"])}</span>'
                f'<span class="num">{c["completes"]:.1f}</span>'
                f'<span class="num dim">{_esc(c["clean"])}</span>'
                + (
                    '<span class="tag tag-watch">watch</span>'
                    if c["tier"] == "watch"
                    else '<span class="tag-gap"></span>'
                )
                + "</li>"
                for i, c in enumerate(shift["callers"], 1)
            )
            blocks.append(
                f'<div class="poll"><h4>{_esc(shift["poll"])}'
                f'<span class="poll-count">{len(shift["callers"])}/{shift["needed"]}</span></h4>'
                f'<ul class="callers"><li class="head"><span></span><span>Caller</span>'
                f'<span class="num">Comp</span><span class="num">Clean</span>'
                f"<span></span></li>{rows}</ul></div>"
            )
        cards.append(
            f'<article class="day-card"><header><span class="day-name">{_esc(name)}</span>'
            f'<span class="day-date">{_esc(rest)}</span></header>{"".join(blocks)}</article>'
        )

    barred = "".join(
        f'<li><span class="b-name">{_esc(b["name"])}</span>'
        f'<span class="b-why">{_esc(b["headline"])}</span></li>'
        for b in data["barred"]
    )
    audit_tone = "ok" if audits["daysSinceLast"] <= 7 else "warn"

    return f"""<title>Pacific Link Roster Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --ground:#e9eef0; --panel:#fff; --panel-2:#f4f7f8; --band:#101820;
  --band-ink:#eef4f6; --band-muted:#93a6b3;
  --ink:#0e141a; --ink-2:#3a4652; --muted:#6b7986; --line:#d3dce1;
  --accent:{CHART_HUE_LIGHT}; --accent-soft:#dcefed;
  --ok:#2a6a48; --ok-soft:#e2efe7;
  --warn:#8a5a0b; --warn-soft:#f6eddc;
  --bad:#9a3227; --bad-soft:#f7e6e3;
  --display:'Bricolage Grotesque',system-ui,sans-serif;
  --body:'Public Sans',system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,monospace;
}}
@media (prefers-color-scheme:dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#0b0f14; --panel:#131a22; --panel-2:#182029; --band:#060a0e;
    --band-ink:#eef4f6; --band-muted:#7d8b99;
    --ink:#eaf0f6; --ink-2:#c0ccd6; --muted:#7d8b99; --line:#232e3a;
    --accent:{CHART_HUE_DARK}; --accent-soft:#12312e;
    --ok:#6fbf92; --ok-soft:#16301f;
    --warn:#d6a54e; --warn-soft:#33280f;
    --bad:#e8796b; --bad-soft:#341a17;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#0b0f14; --panel:#131a22; --panel-2:#182029; --band:#060a0e;
  --band-ink:#eef4f6; --band-muted:#7d8b99;
  --ink:#eaf0f6; --ink-2:#c0ccd6; --muted:#7d8b99; --line:#232e3a;
  --accent:{CHART_HUE_DARK}; --accent-soft:#12312e;
  --ok:#6fbf92; --ok-soft:#16301f;
  --warn:#d6a54e; --warn-soft:#33280f;
  --bad:#e8796b; --bad-soft:#341a17;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ background:var(--ground); color:var(--ink); font-family:var(--body);
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased; }}
h1,h2,h3,h4 {{ font-family:var(--display); margin:0; text-wrap:balance;
  letter-spacing:-.02em; }}
.wrap {{ max-width:62rem; margin:0 auto; padding:0 1.25rem 4rem; }}

/* ── Hero band ─────────────────────────────────────────── */
.band {{ background:var(--band); color:var(--band-ink); margin:0 0 2.5rem;
  padding:2.5rem 0 0; }}
.band-in {{ max-width:62rem; margin:0 auto; padding:0 1.25rem 2rem; }}
.eyebrow {{ font-family:var(--mono); font-size:.72rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--accent); display:block; margin-bottom:.6rem; }}
.band h1 {{ font-size:clamp(2rem,5.5vw,3.4rem); font-weight:800; line-height:1.02;
  margin-bottom:.5rem; }}
.band .dates {{ color:var(--band-muted); font-size:1.02rem; margin:0 0 1.75rem; }}
.headline {{ display:flex; flex-wrap:wrap; align-items:flex-end; gap:2.5rem;
  padding-bottom:1.75rem; border-bottom:1px solid rgba(255,255,255,.12); }}
.headline .big {{ font-family:var(--display); font-size:clamp(3rem,9vw,4.75rem);
  font-weight:800; line-height:.9; font-variant-numeric:tabular-nums; }}
.headline .big span {{ color:var(--accent); }}
.headline .big-label {{ display:block; font-family:var(--body); font-size:.85rem;
  font-weight:400; color:var(--band-muted); letter-spacing:0; margin-top:.5rem; }}
.trio {{ display:flex; gap:2.25rem; flex-wrap:wrap; }}
.trio div {{ display:flex; flex-direction:column; }}
.trio b {{ font-family:var(--display); font-size:1.6rem; font-weight:700;
  font-variant-numeric:tabular-nums; }}
.trio span {{ font-size:.8rem; color:var(--band-muted); }}

/* ── Day strip ─────────────────────────────────────────── */
.strip {{ display:grid; grid-template-columns:repeat(5,1fr); gap:1px;
  margin-top:1.75rem; }}
.strip-cell {{ display:flex; flex-direction:column; align-items:flex-start;
  gap:.3rem; padding-right:1rem; }}
.strip-day {{ font-family:var(--display); font-weight:700; font-size:1rem; }}
.strip-date {{ font-family:var(--mono); font-size:.7rem; color:var(--band-muted); }}
.strip-track {{ width:100%; height:52px; display:flex; align-items:flex-end;
  background:rgba(255,255,255,.05); border-radius:3px; margin:.35rem 0 .1rem; }}
.strip-fill {{ width:100%; background:var(--accent); border-radius:3px; min-height:4px; }}
.strip-slots {{ font-family:var(--mono); font-size:.95rem; font-weight:500; }}
.strip-polls {{ display:flex; flex-direction:column; gap:.05rem; }}
.strip-polls span {{ font-size:.68rem; color:var(--band-muted); line-height:1.35; }}

/* ── Sections ──────────────────────────────────────────── */
section {{ margin-bottom:3rem; }}
.sec-head {{ display:flex; align-items:baseline; gap:.75rem; margin-bottom:.35rem; }}
.sec-head h2 {{ font-size:1.5rem; font-weight:700; }}
.sec-num {{ font-family:var(--mono); font-size:.7rem; color:var(--accent);
  letter-spacing:.1em; }}
.lede {{ color:var(--ink-2); margin:0 0 1.25rem; max-width:60ch; }}
.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:2px;
  padding:1.5rem 1.6rem; }}
.chart {{ width:100%; height:auto; display:block; overflow:visible; }}
.bar {{ fill:var(--accent); }}
.bar:hover {{ opacity:.8; }}
.bar-label {{ fill:var(--muted); font-family:var(--mono); font-size:13px; }}
.bar-value {{ fill:var(--ink); font-family:var(--mono); font-size:13px;
  font-weight:500; font-variant-numeric:tabular-nums; }}
.ref-line {{ stroke:var(--muted); }}
.ref-label {{ fill:var(--muted); font-family:var(--mono); font-size:11px; }}

/* ── Roster ────────────────────────────────────────────── */
.days {{ display:grid; gap:1rem; align-items:start;
  grid-template-columns:repeat(auto-fit,minmax(25rem,1fr)); }}
.day-card {{ background:var(--panel); border:1px solid var(--line); border-radius:2px;
  overflow:hidden; }}
.day-card > header {{ display:flex; align-items:baseline; gap:.5rem;
  padding:.85rem 1.1rem; background:var(--panel-2); border-bottom:1px solid var(--line); }}
.day-name {{ font-family:var(--display); font-weight:700; font-size:1.05rem; }}
.day-date {{ font-family:var(--mono); font-size:.75rem; color:var(--muted); }}
.poll {{ padding:.85rem 1.1rem; border-bottom:1px solid var(--line); }}
.poll:last-child {{ border-bottom:none; }}
.poll h4 {{ font-size:.9rem; font-weight:700; display:flex; gap:.5rem;
  align-items:baseline; margin-bottom:.5rem; }}
.poll-count {{ font-family:var(--mono); font-size:.72rem; color:var(--accent);
  font-weight:400; letter-spacing:0; }}
.callers {{ list-style:none; margin:0; padding:0; }}
.callers li {{ display:grid; grid-template-columns:1.3rem minmax(0,1fr) 2.4rem 2.8rem auto;
  gap:.45rem; align-items:center; padding:.24rem 0; }}
.callers li + li {{ border-top:1px solid var(--line); }}
.callers li.head {{ font-family:var(--mono); font-size:.62rem; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted); border:none; padding-bottom:.35rem; }}
.rank {{ font-family:var(--mono); font-size:.7rem; color:var(--muted); }}
.who {{ font-size:.86rem; font-weight:500; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }}
.num {{ font-family:var(--mono); font-size:.78rem; text-align:right;
  font-variant-numeric:tabular-nums; }}
.dim {{ color:var(--muted); }}
.tag {{ font-family:var(--mono); font-size:.6rem; padding:.08rem .35rem;
  border-radius:2px; text-align:center; }}
.tag-watch {{ background:var(--warn-soft); color:var(--warn); }}

/* ── Decisions ─────────────────────────────────────────── */
.decisions {{ display:grid; gap:1px; background:var(--line);
  border:1px solid var(--line); border-radius:2px; }}
.dec {{ background:var(--panel); padding:1.15rem 1.4rem; }}
.dec-top {{ display:flex; flex-wrap:wrap; gap:.6rem; align-items:baseline; }}
.dec h3 {{ font-size:1.02rem; font-weight:700; }}
.dec p {{ margin:.4rem 0 0; color:var(--ink-2); font-size:.92rem; max-width:64ch; }}
.chip {{ font-family:var(--mono); font-size:.62rem; padding:.14rem .5rem;
  border-radius:2px; text-transform:uppercase; letter-spacing:.07em; }}
.chip-bad {{ background:var(--bad-soft); color:var(--bad); }}
.chip-warn {{ background:var(--warn-soft); color:var(--warn); }}
.chip-ok {{ background:var(--ok-soft); color:var(--ok); }}
.b-list {{ list-style:none; margin:.7rem 0 0; padding:0; display:grid; gap:.5rem; }}
.b-list li {{ display:grid; gap:.02rem; }}
.b-name {{ font-weight:600; font-size:.92rem; }}
.b-why {{ font-family:var(--mono); font-size:.74rem; color:var(--bad); }}

footer {{ margin-top:2.5rem; padding-top:1.2rem; border-top:1px solid var(--line);
  font-size:.85rem; color:var(--muted); max-width:66ch; }}
</style>

<div class="band">
  <div class="band-in">
    <span class="eyebrow">Draft roster · nothing sent</span>
    <h1>{_esc(business_name)}<br>roster dashboard</h1>
    <p class="dates">Week of {_esc(week["start"])} — built {_esc(data["generatedFor"])}
       from {audits["total"]:,} audits and the Curia schedule</p>

    <div class="headline">
      <div class="big"><span>{week["filled"]}</span>/{week["needed"]}
        <span class="big-label">caller-slots filled across {week["polls"]} polls</span></div>
      <div class="trio">
        <div><b>{week["used"]}</b><span>callers rostered</span></div>
        <div><b>{week["bench"]}</b><span>on the bench</span></div>
        <div><b>{cap["rosterable"]}</b><span>rosterable now</span></div>
        <div><b>{prod["median"]}</b><span>median completes/shift</span></div>
      </div>
    </div>

    {_day_strip(data.get("rosterDays", []))}
  </div>
</div>

<div class="wrap">
  <section>
    <div class="sec-head"><span class="sec-num">01</span>
      <h2>Can you staff what's coming?</h2></div>
    <p class="lede">Caller-slots per business week, Sunday to Thursday. {_esc(capacity_note)}</p>
    <div class="panel">
      {_bar_chart(demand_rows, reference=cap["weeklyCapacity"],
                  reference_label=f'capacity {cap["weeklyCapacity"]}', value_suffix=" slots")}
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="sec-num">02</span>
      <h2>How the team is performing</h2></div>
    <p class="lede">Completed surveys per shift across {prod["n"]} active callers, taken from
      the call logs rather than what was declared — so nobody can climb this by over-declaring.
      Best on the books is {_esc(top_caller.get("name", "—"))} at {top_caller.get("completes", 0):.1f}.</p>
    <div class="panel">
      {_column_chart(hist_rows, marker_index=int(prod["median"]),
                     marker_label=f'median {prod["median"]}')}
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="sec-num">03</span><h2>Who's working</h2></div>
    <p class="lede">Ranked by completes per shift, with anyone barred by their audit history
      excluded before ranking rather than after.</p>
    <div class="days">{"".join(cards)}</div>
  </section>

  <section>
    <div class="sec-head"><span class="sec-num">04</span><h2>What needs a decision</h2></div>
    <div class="decisions">
      <div class="dec"><div class="dec-top"><span class="chip chip-bad">integrity</span>
        <h3>{audits["missedOverDeclarations"]} over-declarations marked &ldquo;N&rdquo;</h3></div>
        <p>Rows where a caller declared more completed surveys than the call logs support,
        but the reviewer's Y/N column records no discrepancy. Worth raising with whoever
        fills that column.</p></div>
      <div class="dec"><div class="dec-top"><span class="chip chip-warn">data</span>
        <h3>{quality["duplicatePairs"]} names look like the same person twice</h3></div>
        <p>Each spelling splits that caller's audit history, which flatters the half without
        the failures. Fixing the spellings is the highest-value cleanup available.</p></div>
      <div class="dec"><div class="dec-top">
        <span class="chip chip-{audit_tone}">audits</span>
        <h3>Last audit {audits["daysSinceLast"]} day(s) ago</h3></div>
        <p>Rankings track recent performance — an audit's influence halves every 90 days.
        If auditing stops, the roster slowly reverts to who was good months ago.</p></div>
      <div class="dec"><div class="dec-top"><span class="chip chip-bad">roster</span>
        <h3>{len(data["barred"])} active callers barred from shifts</h3></div>
        <ul class="b-list">{barred}</ul></div>
    </div>
  </section>

  <footer>Nothing here has been sent to anyone. Callers are ranked on completed surveys
    taken from the call logs, and audit history gates the list before productivity is
    considered — so volume never buys a place.</footer>
</div>
"""


def build(data_path, out_path, *, business_name: str = "Pacific Link Global") -> Path:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    out = Path(out_path)
    out.write_text(render_dashboard(data, business_name=business_name), encoding="utf-8")
    return out

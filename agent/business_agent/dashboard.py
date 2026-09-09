"""The weekly dashboard: who is working, and the numbers behind the decision.

Rendered server-side into static HTML so every figure is on the page the
moment it loads — a dashboard that needs scripts to run before it says
anything is no use on a phone with bad signal. Day cards collapse using
<details>, which needs no script either, and ship open so the roster reads
at first paint.

Styled to the Pacific Link Global brand: the site's sky blue on deep navy,
its light gradient ground, and its geometric headline face.

Charts are single-hue on purpose. Each answers a magnitude question ("how
many slots", "how many callers score this well"), and magnitude is one hue;
the status colours are reserved for good / watch / barred and always ship
beside a word, never as colour alone.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

# The brand blue, checked against the light (#ffffff) and dark (#12202f)
# card surfaces: chroma above the grey floor and contrast >= 3:1 in both.
CHART_HUE_LIGHT = "#1b7fc9"
CHART_HUE_DARK = "#4fb6f0"


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
            f'style="width:{share * 100:.0f}%"></div></div>'
            f'<span class="strip-slots">{day["slots"]}<span>callers</span></span>'
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
        name, _, rest_of = day.partition(" ")
        total = sum(len(s["callers"]) for s in shifts)
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
                    else "<span></span>"
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
        polls = " · ".join(s["poll"] for s in shifts)
        cards.append(
            f'<details class="day-card" open><summary>'
            f'<span class="sum-left"><span class="day-name">{_esc(name)}</span>'
            f'<span class="day-date">{_esc(rest_of)}</span></span>'
            f'<span class="sum-mid">{_esc(polls)}</span>'
            f'<span class="sum-count">{total} callers</span>'
            f'<svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" '
            f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg></summary>'
            f'<div class="day-body">{"".join(blocks)}</div></details>'
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --sky:#3ba9ec; --brand:{CHART_HUE_LIGHT}; --navy:#0c1a2b;
  --grad-a:#eaf5fe; --grad-b:#f7fbff;
  --card:#fff; --card-2:#f4f9fd;
  --ink:#0c1a2b; --ink-2:#33506b; --muted:#5d7186; --line:#dceaf5;
  --ok:#16794f; --ok-soft:#e3f4ec;
  --warn:#a4700d; --warn-soft:#fbf1dd;
  --bad:#b33b2c; --bad-soft:#fbe8e5;
  --shadow:0 1px 2px rgba(12,26,43,.05), 0 8px 24px rgba(12,26,43,.06);
  --display:'Poppins',system-ui,sans-serif;
  --body:'DM Sans',system-ui,sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,monospace;
  --r:18px;
}}
@media (prefers-color-scheme:dark) {{
  :root:not([data-theme="light"]) {{
    --brand:{CHART_HUE_DARK}; --grad-a:#0a1725; --grad-b:#08111c;
    --card:#12202f; --card-2:#182b3d;
    --ink:#e8f1f8; --ink-2:#b6c9da; --muted:#86a0b6; --line:#1e3143;
    --ok:#5fd3a0; --ok-soft:#0f2c22;
    --warn:#e6b75c; --warn-soft:#31270f;
    --bad:#f08878; --bad-soft:#331915;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
  }}
}}
:root[data-theme="dark"] {{
  --brand:{CHART_HUE_DARK}; --grad-a:#0a1725; --grad-b:#08111c;
  --card:#12202f; --card-2:#182b3d;
  --ink:#e8f1f8; --ink-2:#b6c9da; --muted:#86a0b6; --line:#1e3143;
  --ok:#5fd3a0; --ok-soft:#0f2c22;
  --warn:#e6b75c; --warn-soft:#31270f;
  --bad:#f08878; --bad-soft:#331915;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ background:linear-gradient(180deg,var(--grad-a) 0%,var(--grad-b) 46%,var(--grad-b) 100%);
  background-attachment:fixed; color:var(--ink); font-family:var(--body);
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased; }}
h1,h2,h3,h4 {{ font-family:var(--display); margin:0; text-wrap:balance; letter-spacing:-.02em; }}
.wrap {{ max-width:62rem; margin:0 auto; padding:2.75rem 1.25rem 4rem; }}

/* ── Hero ──────────────────────────────────────────────── */
.eyebrow {{ display:inline-flex; align-items:center; gap:.5rem; font-size:.74rem;
  font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:var(--brand);
  margin-bottom:.9rem; }}
.eyebrow::before {{ content:""; width:7px; height:7px; border-radius:50%;
  background:var(--sky); }}
h1 {{ font-size:clamp(2rem,5vw,3rem); font-weight:700; line-height:1.06; }}
.sub {{ color:var(--ink-2); margin:.55rem 0 1.5rem; font-size:1.02rem; }}

.pills {{ display:flex; flex-wrap:wrap; gap:.6rem; margin-bottom:1.75rem; }}
.pill {{ display:inline-flex; align-items:center; gap:.5rem; background:var(--card);
  border:1px solid var(--line); border-radius:999px; padding:.5rem .95rem;
  box-shadow:var(--shadow); font-size:.88rem; font-weight:500; }}
.pill b {{ font-family:var(--display); font-weight:700; }}
.dot {{ width:8px; height:8px; border-radius:50%; }}
.dot-ok {{ background:var(--ok); }} .dot-brand {{ background:var(--sky); }}
.dot-bad {{ background:var(--bad); }} .dot-warn {{ background:var(--warn); }}

/* ── Week strip ────────────────────────────────────────── */
.strip {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr));
  gap:.75rem; margin-bottom:2.75rem; }}
.strip-cell {{ background:var(--card); border:1px solid var(--line);
  border-radius:var(--r); padding:1rem 1.05rem; box-shadow:var(--shadow);
  display:flex; flex-direction:column; gap:.15rem; }}
.strip-day {{ font-family:var(--display); font-weight:700; font-size:1.05rem; }}
.strip-date {{ font-family:var(--mono); font-size:.7rem; color:var(--muted); }}
.strip-track {{ height:6px; border-radius:999px; background:var(--card-2);
  margin:.7rem 0 .55rem; overflow:hidden; }}
.strip-fill {{ height:100%; border-radius:999px;
  background:linear-gradient(90deg,var(--sky),var(--brand)); }}
.strip-slots {{ font-family:var(--display); font-weight:700; font-size:1.35rem;
  font-variant-numeric:tabular-nums; }}
.strip-slots span {{ font-family:var(--body); font-weight:400; font-size:.76rem;
  color:var(--muted); margin-left:.25rem; }}
.strip-polls {{ display:flex; flex-direction:column; gap:.05rem; margin-top:.3rem; }}
.strip-polls span {{ font-size:.72rem; color:var(--muted); line-height:1.4; }}

/* ── Sections ──────────────────────────────────────────── */
section {{ margin-bottom:2.75rem; }}
.sec-head h2 {{ font-size:1.4rem; font-weight:600; }}
.lede {{ color:var(--ink-2); margin:.3rem 0 1.15rem; max-width:60ch; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
  padding:1.5rem 1.6rem; box-shadow:var(--shadow); }}
.chart {{ width:100%; height:auto; display:block; overflow:visible; }}
.bar {{ fill:var(--brand); }}
.bar:hover {{ opacity:.82; }}
.bar-label {{ fill:var(--muted); font-family:var(--mono); font-size:13px; }}
.bar-value {{ fill:var(--ink); font-family:var(--mono); font-size:13px; font-weight:500;
  font-variant-numeric:tabular-nums; }}
.ref-line {{ stroke:var(--muted); }}
.ref-label {{ fill:var(--muted); font-family:var(--mono); font-size:11px; }}

/* ── Day cards ─────────────────────────────────────────── */
.days {{ display:grid; gap:.85rem; }}
.day-card {{ background:var(--card); border:1px solid var(--line);
  border-radius:var(--r); box-shadow:var(--shadow); overflow:hidden; }}
.day-card summary {{ display:flex; align-items:center; gap:.9rem; cursor:pointer;
  padding:1.05rem 1.3rem; list-style:none; }}
.day-card summary::-webkit-details-marker {{ display:none; }}
.day-card summary:hover {{ background:var(--card-2); }}
.day-card summary:focus-visible {{ outline:2px solid var(--brand); outline-offset:-2px; }}
.sum-left {{ display:flex; align-items:baseline; gap:.5rem; min-width:7.5rem; }}
.day-name {{ font-family:var(--display); font-weight:700; font-size:1.05rem; }}
.day-date {{ font-family:var(--mono); font-size:.74rem; color:var(--muted); }}
.sum-mid {{ flex:1; color:var(--ink-2); font-size:.9rem; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; }}
.sum-count {{ font-family:var(--mono); font-size:.78rem; color:var(--brand);
  white-space:nowrap; }}
.chev {{ width:16px; height:16px; color:var(--muted); flex:none;
  transition:transform .18s ease; }}
.day-card[open] .chev {{ transform:rotate(180deg); }}
@media (prefers-reduced-motion:reduce) {{ .chev {{ transition:none; }} }}
.day-body {{ border-top:1px solid var(--line); }}
.poll {{ padding:1rem 1.3rem; }}
.poll + .poll {{ border-top:1px solid var(--line); }}
.poll h4 {{ font-size:.94rem; font-weight:600; display:flex; gap:.55rem;
  align-items:baseline; margin-bottom:.55rem; }}
.poll-count {{ font-family:var(--mono); font-size:.74rem; color:var(--brand);
  font-weight:400; letter-spacing:0; }}
.callers {{ list-style:none; margin:0; padding:0; columns:2; column-gap:2rem; }}
.callers li {{ display:grid; grid-template-columns:1.4rem minmax(0,1fr) 2.5rem 2.9rem auto;
  gap:.45rem; align-items:center; padding:.3rem 0; break-inside:avoid; }}
.callers li + li {{ border-top:1px solid var(--line); }}
.callers li.head {{ font-family:var(--mono); font-size:.62rem; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted); border:none; }}
.rank {{ font-family:var(--mono); font-size:.7rem; color:var(--muted); }}
.who {{ font-size:.88rem; font-weight:500; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; }}
.num {{ font-family:var(--mono); font-size:.78rem; text-align:right;
  font-variant-numeric:tabular-nums; }}
.dim {{ color:var(--muted); }}
.tag {{ font-family:var(--mono); font-size:.6rem; padding:.1rem .4rem; border-radius:999px; }}
.tag-watch {{ background:var(--warn-soft); color:var(--warn); }}

/* ── Decisions ─────────────────────────────────────────── */
.decisions {{ display:grid; gap:.85rem; grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));
  align-items:start; }}
.dec {{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
  padding:1.25rem 1.4rem; box-shadow:var(--shadow); }}
.dec-top {{ display:flex; flex-wrap:wrap; gap:.55rem; align-items:center;
  margin-bottom:.45rem; }}
.dec h3 {{ font-size:1rem; font-weight:600; flex-basis:100%; }}
.dec p {{ margin:0; color:var(--ink-2); font-size:.9rem; }}
.chip {{ display:inline-flex; align-items:center; gap:.4rem; font-family:var(--mono);
  font-size:.62rem; padding:.2rem .6rem; border-radius:999px; text-transform:uppercase;
  letter-spacing:.07em; }}
.chip-bad {{ background:var(--bad-soft); color:var(--bad); }}
.chip-warn {{ background:var(--warn-soft); color:var(--warn); }}
.chip-ok {{ background:var(--ok-soft); color:var(--ok); }}
.b-list {{ list-style:none; margin:.6rem 0 0; padding:0; display:grid; gap:.5rem; }}
.b-list li {{ display:grid; gap:.02rem; }}
.b-name {{ font-weight:500; font-size:.9rem; }}
.b-why {{ font-family:var(--mono); font-size:.72rem; color:var(--bad); }}

footer {{ margin-top:2.5rem; padding-top:1.2rem; border-top:1px solid var(--line);
  font-size:.85rem; color:var(--muted); max-width:66ch; }}
</style>

<div class="wrap">
  <span class="eyebrow">Draft roster · nothing sent</span>
  <h1>Week of {_esc(week["start"])}</h1>
  <p class="sub">{business_name} · built {_esc(data["generatedFor"])} from
    {audits["total"]:,} audits and the Curia schedule</p>

  <div class="pills">
    <span class="pill"><span class="dot dot-ok"></span><b>{week["filled"]}/{week["needed"]}</b>
      slots filled</span>
    <span class="pill"><span class="dot dot-brand"></span><b>{week["used"]}</b> callers rostered</span>
    <span class="pill"><span class="dot dot-brand"></span><b>{week["bench"]}</b> on the bench</span>
    <span class="pill"><span class="dot dot-warn"></span><b>{prod["median"]}</b>
      median completes/shift</span>
    <span class="pill"><span class="dot dot-bad"></span><b>{cap["barredActive"]}</b>
      barred by audits</span>
  </div>

  {_day_strip(data.get("rosterDays", []))}

  <section>
    <div class="sec-head"><h2>Can you staff what's coming?</h2></div>
    <p class="lede">Caller-slots per business week, Sunday to Thursday. {_esc(capacity_note)}</p>
    <div class="card">
      {_bar_chart(demand_rows, reference=cap["weeklyCapacity"],
                  reference_label=f'capacity {cap["weeklyCapacity"]}', value_suffix=" slots")}
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>How the team is performing</h2></div>
    <p class="lede">Completed surveys per shift across {prod["n"]} active callers, taken from
      the call logs rather than what was declared — so nobody can climb this by over-declaring.
      Best on the books is {_esc(top_caller.get("name", "—"))} at {top_caller.get("completes", 0):.1f}.</p>
    <div class="card">
      {_column_chart(hist_rows, marker_index=int(prod["median"]),
                     marker_label=f'median {prod["median"]}')}
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>Who's working</h2></div>
    <p class="lede">Ranked by completes per shift, with anyone barred by their audit history
      excluded before ranking rather than after. Tap a day to collapse it.</p>
    <div class="days">{"".join(cards)}</div>
  </section>

  <section>
    <div class="sec-head"><h2>What needs a decision</h2></div>
    <p class="lede">Four things the numbers are asking you to look at.</p>
    <div class="decisions">
      <div class="dec"><div class="dec-top"><span class="chip chip-bad">integrity</span>
        <h3>{audits["missedOverDeclarations"]} over-declarations marked &ldquo;N&rdquo;</h3></div>
        <p>Rows where a caller declared more completed surveys than the call logs support,
        but the reviewer's Y/N column records no discrepancy.</p></div>
      <div class="dec"><div class="dec-top"><span class="chip chip-warn">data</span>
        <h3>{quality["duplicatePairs"]} names look like the same person twice</h3></div>
        <p>Each spelling splits that caller's audit history, which flatters the half without
        the failures. The highest-value cleanup available.</p></div>
      <div class="dec"><div class="dec-top"><span class="chip chip-{audit_tone}">audits</span>
        <h3>Last audit {audits["daysSinceLast"]} day(s) ago</h3></div>
        <p>Rankings track recent performance — an audit's influence halves every 90 days.
        If auditing stops, the roster reverts to who was good months ago.</p></div>
      <div class="dec"><div class="dec-top"><span class="chip chip-bad">roster</span>
        <h3>{len(data["barred"])} active callers barred</h3></div>
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

"""Render results.json into a self-contained report.html — no libraries, no network.

Every arm present in results.json appears automatically, so adding a model never touches this
file. Charts are inline SVG so the page works offline and can be published as-is.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ["#8c6a3f", "#b08d57", "#5f7d6b", "#6a7fa0", "#8a6a8a", "#a06a5f",
           "#5f8a8a", "#9a8a4f", "#7a6aa0", "#6a9a6a"]


def bars(rows, lower_is_better=True, fmt="{:.3f}"):
    """Horizontal bars, one per arm. rows = [(label, value, colour, note, arm_id)]."""
    if not rows:
        return "<p class='muted'>no data</p>"
    vals = [r[1] for r in rows]
    hi = max(vals) or 1.0
    best = min(vals) if lower_is_better else max(vals)
    out = ["<div class='bars'>"]
    for label, v, colour, note, arm, prm in rows:
        pct = 0 if hi == 0 else max(1.5, v / hi * 100)
        win = " win" if v == best else ""
        tag = "<span class='tag'>" + note + "</span>" if note else ""
        out.append(
            "<div class='bar-row" + win + "' data-arm='" + arm + "' data-prompt='" + prm + "'>"
            "<div class='bar-label'>" + label + tag + "</div>"
            "<div class='bar-track'><div class='bar-fill' style='width:" + f"{pct:.1f}"
            + "%;background:" + colour + "'></div></div>"
            "<div class='bar-val'>" + fmt.format(v) + "</div></div>")
    out.append("</div>")
    return "".join(out)


def scatter(points, w=620, h=400, ylab="character error rate"):
    """Cost (x, log scale) against error (y). points = [(label, cost, err, colour)]."""
    pts = [p for p in points if p[1] and p[2] is not None]
    if not pts:
        return "<p class='muted'>no priced arms</p>"
    xs = [math.log10(p[1]) for p in pts]
    ys = [p[2] for p in pts]
    x0, x1 = min(xs), max(xs)
    lo, hi_ = min(ys), max(ys)
    pad_y = max((hi_ - lo) * 0.18, 0.02)
    y0, y1 = max(0.0, lo - pad_y), min(1.0, hi_ + pad_y) if hi_ <= 1 else hi_ + pad_y
    if x1 - x0 < 1e-9:
        x0, x1 = x0 - 0.5, x1 + 0.5
    pad = 58

    def px(x):
        return pad + (x - x0) / (x1 - x0) * (w - pad - 24)

    def py(y):
        return h - pad - (y - y0) / (y1 - y0) * (h - pad - 28)

    s = ["<svg viewBox='0 0 " + str(w) + " " + str(h) + "' class='chart' role='img'>"]
    s.append(f"<line x1='{pad}' y1='{h-pad}' x2='{w-16}' y2='{h-pad}' class='axis'/>")
    s.append(f"<line x1='{pad}' y1='16' x2='{pad}' y2='{h-pad}' class='axis'/>")
    for frac in (0, .25, .5, .75, 1):
        y = y0 + frac * (y1 - y0)
        s.append(f"<line x1='{pad}' y1='{py(y):.1f}' x2='{w-16}' y2='{py(y):.1f}' class='grid'/>")
        s.append(f"<text x='{pad-8}' y='{py(y)+4:.1f}' class='tick' text-anchor='end'>{y*100:.0f}%</text>")
    # X ticks at the 1-2-5 decade steps that bracket the data, labelled in real dollars. Without
    # these the horizontal axis carries no readable information at all — the points just sit
    # somewhere on an unlabelled log scale.
    def money(v):
        return f"${v:.5f}".rstrip("0").rstrip(".") if v < 0.01 else f"${v:.3f}"
    dec = math.floor(x0)
    ticks = []
    while dec <= math.ceil(x1):
        for m_ in (1, 2, 5):
            v = m_ * (10 ** dec)
            lx = math.log10(v)
            if x0 - 1e-9 <= lx <= x1 + 1e-9:
                ticks.append(v)
        dec += 1
    if len(ticks) < 2:
        ticks = [10 ** x0, 10 ** x1]
    for v in ticks:
        vx = px(math.log10(v))
        s.append(f"<line x1='{vx:.1f}' y1='16' x2='{vx:.1f}' y2='{h-pad}' class='grid'/>")
        s.append(f"<text x='{vx:.1f}' y='{h-pad+15}' class='tick' "
                 f"text-anchor='middle'>{money(v)}</text>")
    # Labels are placed INWARD: a point on the right half gets its label to its left, so nothing
    # can run past the plot edge. Then near-colliding labels are nudged apart vertically.
    placed = []
    mid = (pad + w - 16) / 2
    for label, cost, err, colour in sorted(pts, key=lambda t: t[2]):
        cx, cy = px(math.log10(cost)), py(err)
        ly = cy + 4
        while any(abs(ly - q) < 24 for q in placed):
            ly += 24
        if ly > h - pad - 4:                      # ran out of room below; go up instead
            ly = cy + 4
            while any(abs(ly - q) < 24 for q in placed):
                ly -= 24
        placed.append(ly)
        right = cx > mid
        tx = cx - 11 if right else cx + 11
        anchor = "end" if right else "start"
        tip = f"{label} — ${cost:.5f} per page — {err*100:.2f}%"
        s.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='7' fill='{colour}' opacity='.9'>"
                 f"<title>{tip}</title></circle>")
        # a generous invisible target so the tooltip is reachable without pixel-hunting
        s.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='15' fill='transparent'>"
                 f"<title>{tip}</title></circle>")
        if abs(ly - (cy + 4)) > 6:                # leader line when the label had to move
            s.append(f"<line x1='{cx:.1f}' y1='{cy:.1f}' x2='{tx:.1f}' y2='{ly-4:.1f}' "
                     f"class='grid'/>")
        s.append(f"<text x='{tx:.1f}' y='{ly:.1f}' class='pt' "
                 f"text-anchor='{anchor}'>{label}<title>{tip}</title></text>")
        s.append(f"<text x='{tx:.1f}' y='{ly+11:.1f}' class='tick' "
                 f"text-anchor='{anchor}'>${cost:.5f}</text>")
    s.append(f"<text x='{(w+pad)/2:.0f}' y='{h-14}' class='axlab' text-anchor='middle'>"
             "cost per page (USD, log scale)</text>")
    s.append(f"<text x='14' y='{h/2:.0f}' class='axlab' text-anchor='middle' "
             f"transform='rotate(-90 14 {h/2:.0f})'>{ylab}</text>")
    s.append("</svg>")
    return "".join(s)


def heatmap(arms, pages):
    """Per-page, per-arm structural accuracy — shows WHERE an arm fails, not just how much."""
    s = ["<table class='heat'><thead><tr><th>arm</th>"]
    s += ["<th>" + str(p) + "</th>" for p in pages]
    s.append("</tr></thead><tbody>")
    for arm_id, a in arms.items():
        by_pg = {x["page"]: x for x in a["pages"]}
        s.append("<tr data-arm='" + arm_id + "' data-prompt='" + a.get("prompt", "") +
                 "'><th class='rowlab'>" + a["label"] + "</th>")
        for p in pages:
            x = by_pg.get(p)
            if not x:
                s.append("<td class='na'>&middot;</td>")
                continue
            vals = [v for v in x["fields"].values() if v is not None]
            ok = sum(1 for v in vals if v)
            frac = ok / len(vals) if vals else 0
            cls = "g3" if frac == 1 else "g2" if frac >= .66 else "g1" if frac >= .34 else "g0"
            s.append("<td class='" + cls + "'>" + f"{ok}/{len(vals)}" + "</td>")
        s.append("</tr>")
    s.append("</tbody></table>")
    return "".join(s)


def headline(arms):
    """The two comparisons the page is built around, computed from results so they cannot drift."""
    def g(k, m):
        a = arms.get(k)
        return a["summary"][m] if a else None
    prod, flat, sch = "A_gemini25_P0", "B_gemini37_P0", "C_gemini37_P1"
    priced = [(k, a["summary"]["cost_per_page_usd"]) for k, a in arms.items()
              if a["summary"].get("field_accuracy") == 1.0]
    best = min(priced, key=lambda t: t[1]) if priced else (None, None)
    pc = g(prod, "cost_per_page_usd")
    return {
        "flat_fields": f"{(g(flat,'field_accuracy') or 0)*100:.0f}",
        "schema_fields": f"{(g(sch,'field_accuracy') or 0)*100:.0f}",
        "flat_fn": f"{(g(flat,'footnote_exact_rate') or 0)*100:.0f}",
        "schema_fn": f"{(g(sch,'footnote_exact_rate') or 0)*100:.0f}",
        "prod_cost": f"{pc:.5f}" if pc else "&mdash;",
        "best_cost": f"{best[1]:.5f}" if best[1] else "&mdash;",
        "best_label": arms[best[0]]["label"] if best[0] else "&mdash;",
        "cost_ratio": f"{pc/best[1]:.1f}" if (pc and best[1]) else "&mdash;",
    }


def num(v, fmt="{:.3f}"):
    """An unmeasured metric renders as an em dash. It must never render as zero."""
    return "&mdash;" if v is None else fmt.format(v)


def main():
    data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    arms = data["arms"]
    colours = {k: PALETTE[i % len(PALETTE)] for i, k in enumerate(arms)}
    pages = sorted({x["page"] for a in arms.values() for x in a["pages"]})

    def rows(metric, lower=True):
        r = [(a["label"], a["summary"][metric], colours[k],
              a["price_source"] if metric == "cost_per_page_usd" else "", k)
             for k, a in arms.items() if a["summary"].get(metric) is not None]
        return sorted(r, key=lambda t: t[1], reverse=not lower)

    tbl = ["<table class='summary'><thead><tr><th>arm</th><th>prompt</th>"
           "<th class='num'>CER</th><th class='num'>WER</th><th class='num'>fields</th>"
           "<th class='num'>footnotes</th><th class='num'>body purity</th>"
           "<th class='num'>$/page</th></tr></thead><tbody>"]
    for k, a in arms.items():
        s = a["summary"]
        tbl.append(
            "<tr data-arm='" + k + "'"
            + "".join(" data-" + m.replace("_", "-") + "='"
                      + ("" if s.get(m) is None else str(s[m])) + "'"
                      for m in ("field_accuracy", "footnote_exact_rate", "body_purity",
                                "cost_per_page_usd"))
            + "><td><span class='dot' style='background:" + colours[k] + "'></span>"
            + a["label"] + "<div class='muted small"
            + (" ctl" if a.get("control") else "") + "'>" + a["role"] + "</div></td>"
            "<td class='mono'>" + a["prompt"] + "</td>"
            + "<td class='num'>" + num(s['cer_norm']) + "</td>"
            + "<td class='num'>" + num(s['wer_norm']) + "</td>"
            + f"<td class='num'>{(s['field_accuracy'] or 0)*100:.0f}%</td>"
            + "<td class='num'>" + num(s['footnote_exact_rate'], "{:.0%}") + "</td>"
            + f"<td class='num'>{s['body_purity']*100:.0f}%</td>"
            + f"<td class='num'>${s['cost_per_page_usd']:.5f}"
            + "<span class='tag'>" + str(a["price_source"]) + "</span></td></tr>")
    tbl.append("</tbody></table>")

    html = TEMPLATE.format(
        summary_table="".join(tbl),
        cer_bars=(bars(rows("cer_norm")) if rows("cer_norm") else
                  "<p class='muted'>Not measured. CER and WER need a hand transcription of every "
                  "page; this run has gold text for the three hand-verified pages only. The "
                  "structural metrics below do not depend on it, and they are where 75% of the "
                  "observed damage lives. Building the gold set is the documented next step.</p>"),
        field_bars=bars(rows("field_accuracy", lower=False), lower_is_better=False, fmt="{:.0%}"),
        purity_bars=bars(rows("body_purity", lower=False), lower_is_better=False, fmt="{:.0%}"),
        cost_bars=bars(rows("cost_per_page_usd"), fmt="${:.5f}"),
        scatter=scatter([(a["label"].split(" · ")[0], a["summary"]["cost_per_page_usd"],
                          (1 - a["summary"]["field_accuracy"])
                          if a["summary"].get("field_accuracy") is not None else None,
                          colours[k]) for k, a in arms.items()]),
        heat=heatmap(arms, pages),
        controls="".join(
            ["<div class='controls'><span class='ctl-label'>Show arms</span>"]
            + ["<label class='chip'><input type='checkbox' checked data-toggle='" + k + "'>"
               "<span class='swatch' style='background:" + colours[k] + "'></span>"
               + a["label"] + "</label>" for k, a in arms.items()]
            + ["</div>"]),
        n_pages=len(pages), n_arms=len(arms), **headline(arms))
    (ROOT / "report.html").write_text(html, encoding="utf-8")
    print("report.html written - " + str(len(arms)) + " arms, " + str(len(pages)) + " pages")


TEMPLATE = """<meta charset="utf-8">
<title>Reading the Apparatus</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,500;0,700;1,300&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Noto+Naskh+Arabic:wght@400;600&display=swap">
<style>
:root{{
  --paper:#f0efe9; --card:#fbfaf6; --ink:#1a1815; --muted:#6a675e; --rule:#d9d6cc;
  --accent:#9e2b25; --good:#3d6b55; --warn:#a8762b; --shade:#e6e4dc;
  color-scheme:light;
}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  --paper:#141312; --card:#1d1b18; --ink:#e9e5db; --muted:#9b968a; --rule:#332f2a;
  --accent:#d4736a; --good:#7aa98e; --warn:#c99a52; --shade:#232019; color-scheme:dark;
}}}}
:root[data-theme="dark"]{{
  --paper:#141312; --card:#1d1b18; --ink:#e9e5db; --muted:#9b968a; --rule:#332f2a;
  --accent:#d4736a; --good:#7aa98e; --warn:#c99a52; --shade:#232019; color-scheme:dark;
}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);margin:0;
  font:400 16px/1.65 "IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.wrap{{max-width:940px;margin:0 auto;padding:64px 24px 96px;display:flex;flex-direction:column;gap:0}}
h1{{font:500 42px/1.12 Spectral,Georgia,serif;letter-spacing:-.015em;margin:0 0 14px;text-wrap:balance}}
h2{{font:500 23px/1.25 Spectral,Georgia,serif;margin:56px 0 4px;text-wrap:balance}}
h3{{font:600 13px/1.4 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.09em;
  color:var(--muted);margin:32px 0 10px}}
p{{margin:0 0 16px;max-width:66ch}}
.lede{{font:300 20px/1.55 Spectral,Georgia,serif;color:var(--muted);max-width:62ch;margin:0 0 8px}}
.eyebrow{{font:600 12px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.14em;
  color:var(--accent);margin:0 0 18px}}
.sub{{color:var(--muted);font-size:14.5px;margin:6px 0 0}}
hr{{border:0;border-top:1px solid var(--rule);margin:40px 0 0}}
.card{{background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:22px 24px;margin:18px 0}}
.mono,.num{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.ar{{font-family:"Noto Naskh Arabic",serif;direction:rtl;unicode-bidi:isolate;font-size:19px}}
.muted{{color:var(--muted)}} .small{{font-size:13px}}

/* the finding, stated once, with the pair that proves it */
.thesis{{border-left:3px solid var(--accent);padding:2px 0 2px 22px;margin:30px 0 8px}}
.thesis p{{font:300 21px/1.5 Spectral,Georgia,serif;margin:0;max-width:58ch}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--rule);
  border:1px solid var(--rule);border-radius:3px;margin:22px 0 4px;overflow:hidden}}
.pane{{background:var(--card);padding:20px 22px}}
.pane .who{{font:600 12px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.1em;
  color:var(--muted);margin-bottom:14px}}
.pane .big{{font-family:"IBM Plex Mono",monospace;font-size:33px;font-weight:500;line-height:1;
  font-variant-numeric:tabular-nums}}
.pane .cap{{font-size:13px;color:var(--muted);margin-top:7px}}
.pane.win .big{{color:var(--good)}} .pane.lose .big{{color:var(--accent)}}
.same{{text-align:center;font-size:13px;color:var(--muted);margin:12px 0 0}}

table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}}
thead th{{font:600 11.5px/1.3 "IBM Plex Sans",sans-serif;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--ink)}}
tbody tr:last-child td{{border-bottom:0}}
td.num,th.num{{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:1px}}
.tag{{display:inline-block;margin-left:6px;padding:1px 6px;border:1px solid var(--rule);
  border-radius:2px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
  font-family:"IBM Plex Sans",sans-serif}}
.ctl{{color:var(--muted);font-style:italic}}

.bars{{display:flex;flex-direction:column;gap:8px}}
.bar-row{{display:grid;grid-template-columns:250px 1fr 84px;align-items:center;gap:14px}}
.bar-label{{font-size:13.5px}}
.bar-track{{background:var(--shade);border-radius:2px;height:14px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:2px}}
.bar-val{{text-align:right;font-family:"IBM Plex Mono",monospace;font-size:13px;
  font-variant-numeric:tabular-nums}}
.bar-row.win .bar-val{{color:var(--accent);font-weight:500}}

.chart{{width:100%;height:auto}} .axis{{stroke:var(--muted);stroke-width:1}}
.grid{{stroke:var(--rule);stroke-width:1}}
.tick,.axlab{{fill:var(--muted);font-size:11px;font-family:"IBM Plex Mono",monospace}}
.pt{{fill:var(--ink);font-size:11.5px;font-family:"IBM Plex Mono",monospace}}

.heat td{{text-align:center;font-family:"IBM Plex Mono",monospace;font-size:11px;padding:5px 3px}}
.heat thead th{{font-size:10.5px;text-align:center;padding:5px 3px}}
.rowlab{{text-align:left;white-space:nowrap;font-size:12px;text-transform:none;letter-spacing:0;
  font-family:"IBM Plex Sans",sans-serif;font-weight:400;border-bottom:1px solid var(--rule)}}
.g3{{background:color-mix(in srgb,var(--good) 30%,transparent)}}
.g2{{background:color-mix(in srgb,var(--warn) 26%,transparent)}}
.g1{{background:color-mix(in srgb,var(--accent) 22%,transparent)}}
.g0{{background:color-mix(in srgb,var(--accent) 40%,transparent)}}
.na{{color:var(--muted)}}
.scroll{{overflow-x:auto}}
.note{{border-left:2px solid var(--rule);padding-left:18px;color:var(--muted);font-size:14.5px}}
.note strong{{color:var(--ink);font-weight:600}}
ul{{margin:0 0 16px;padding-left:20px;max-width:66ch}} li{{margin-bottom:7px}}
a{{color:var(--accent)}}
@media (max-width:700px){{
  .wrap{{padding:40px 18px 64px}} h1{{font-size:32px}}
  .pair{{grid-template-columns:1fr}} .bar-row{{grid-template-columns:1fr;gap:4px}}
  .bar-val{{text-align:left}}
}}
</style>
<div class="wrap">

<p class="eyebrow">Benchmark &middot; {n_arms} arms &middot; {n_pages} pages</p>
<h1>Reading the Apparatus</h1>
<p class="lede">A scanned page of an Arabic patristic edition carries a running head, a numbered
footnote apparatus, a printed page number and a printer&rsquo;s signature mark. A vision model can
read every character on it and still get the page wrong &mdash; by not being told those are
different things.</p>

<div class="thesis">
<p>Naming the parts is what repairs the apparatus. Every arm given a schema reads the footnote
structure perfectly; no arm given flat text does &mdash; and a newer, better model does not
close the gap.</p>
</div>

<div class="pair">
  <div class="pane lose">
    <div class="who">Flat prompt</div>
    <div class="big">{flat_fn}%</div>
    <div class="cap">of pages with the right footnote count. A single
      <span class="mono">[FOOTNOTE]</span> marker is one container, so an apparatus of twelve notes
      comes back as one.</div>
  </div>
  <div class="pane win">
    <div class="who">Schema prompt</div>
    <div class="big">{schema_fn}%</div>
    <div class="cap">of pages with the right footnote count, including pages whose notes are glued
      together with no space, and pages opening with a note continued from the previous leaf.</div>
  </div>
</div>
<p class="same">Same model. Same pages. Same images. Only the request changed.</p>

<p class="note" style="margin-top:26px"><strong>Where the schema does not help:</strong> separating
the running head and the printed page number. A flat-text parser recovers those from position
&mdash; first line, last line &mdash; and scores {flat_fields}% against the schema arms&rsquo;
{schema_fields}%. Positional heuristics are fine for things that sit in fixed positions. They have
nothing to say about an apparatus, which is where they break.</p>

<h2>The page that shows it</h2>
<p>Page 93 prints a citation of Psalm 109. The production pipeline stored a different, real-looking
one &mdash; the colon moved one place left, verse 1 vanished, and the digits changed Unicode block
from Arabic-Indic (U+0660) to Extended Arabic-Indic (U+06F0).</p>
<div class="card">
  <table>
    <tbody>
      <tr><td style="width:190px">On the page</td>
          <td class="ar">(&#x645;&#x632; &#x661;&#x660;&#x669;: &#x661; - &#x663;)</td>
          <td class="muted small">Psalm 109:1&ndash;3</td></tr>
      <tr><td>Production stored</td>
          <td class="ar" style="color:var(--accent)">(&#x645;&#x632; &#x6F1;&#x6F0;:&#x6F9; &ndash; &#x6F3;)</td>
          <td class="muted small">&ldquo;10:9&rdquo; &mdash; a citation that points somewhere else</td></tr>
      <tr><td>Schema prompt, cheaper model</td>
          <td class="ar" style="color:var(--good)">(&#x645;&#x632; &#x661;&#x660;&#x669;: &#x661; - &#x663;)</td>
          <td class="muted small">correct, and in the printed digit block</td></tr>
    </tbody>
  </table>
</div>
<p class="note">This is the failure mode worth fearing: not garbage, which is obvious, but a
plausible wrong answer that no downstream check will ever flag.</p>

<h2>Results</h2>
<div class="card scroll">{summary_table}</div>
<p class="note"><strong>Scoring is leave-one-out.</strong> Most ground truth is adjudicated from
agreement between arms, so each arm is scored against the agreement of the <em>others</em>; three
pages were read from the images by hand before any arm ran and are fixed for everyone. Fields where
the page is genuinely ambiguous are left unscored rather than settled by a coin-flip.</p>

<h2>Structural field accuracy</h2>
<p class="sub">Running header, page title, printed page number, printer mark &mdash; each in its own
place, not merged into the body.</p>
<div class="card">{field_bars}</div>

<h2>Cost per page</h2>
<p>The cost model is calibrated rather than assumed: production OCR of this book billed a measured
$0.001881 per page across 468 calls, which pins output at 1.97 characters per token for this
script. Every arm is priced from measured output characters through that one constant. Applied back
to production it predicts <span class="num">${prod_cost}</span> against the
<span class="num">$0.001881</span> actually billed.</p>
<div class="card">{cost_bars}</div>
<div class="thesis" style="border-color:var(--good)">
<p>The best-scoring arm is <strong>{cost_ratio}&times; cheaper</strong> than production, at
<span class="num">${best_cost}</span> per page &mdash; and gets the structure completely right.
Better and cheaper are the same choice here.</p>
</div>

<h2>Cost against error</h2>
<p class="sub">Log scale. Down and to the left is better. The most expensive model on the board is
not the most accurate one.</p>
<div class="card">{scatter}</div>

<h2>Character error rate</h2>
<div class="card">{cer_bars}</div>

<h2>Where each arm fails</h2>
<p class="sub">Structural fields correct, per page. Pages 3 and 36 are controls with no known
defects &mdash; an arm inventing structure there is as wrong as one missing it.</p>
<div class="card scroll">{heat}</div>

<h2>Method</h2>
<ul>
<li><strong>Same input everywhere.</strong> One 300&nbsp;DPI page image per call. No text layer, no
classical OCR &mdash; the production pipeline is already a vision model, so this compares
like with like.</li>
<li><strong>The baseline is scored through a parser.</strong> Flat-text arms are not treated as
having produced nothing; they run through the same heuristics production uses. That is the real
architecture: a model never asked what anything <em>is</em>, plus a parser guessing afterwards.</li>
<li><strong>Two arms use the flat prompt, and both are controls.</strong> A is production. B is the
same model as the schema arm, and exists only to show the prompt is the cause &mdash; without it,
the schema arms could be dismissed as merely newer. Neither is a fair test of its model.</li>
<li><strong>Difficulty is spread deliberately:</strong> ten hard pages, five medium, three light,
two clean controls.</li>
<li><strong>Price provenance travels with every price</strong> &mdash; measured, list, or proxy.</li>
</ul>

<h2>What this does not yet measure</h2>
<p>Character and word error rate need a gold transcription of all twenty pages; only three exist,
so those columns read as a dash rather than a zero. The structural findings do not depend on them,
and structure is where three quarters of the observed damage lives. Open-weight local models are
the other gap &mdash; they need a different cost axis entirely, GPU-seconds rather than tokens.</p>

<hr>
<p class="sub">Corpus: Justin Martyr, <em>&#x627;&#x644;&#x62F;&#x641;&#x627;&#x639;&#x627;&#x646;
&#x648;&#x627;&#x644;&#x62D;&#x648;&#x627;&#x631; &#x645;&#x639; &#x62A;&#x631;&#x64A;&#x641;&#x648;&#x646;</em>
&mdash; a 461-page Arabic scholarly edition. Adding a model is a block in the arm registry plus a
folder of outputs; every table and chart on this page regenerates from it.</p>

</div>
"""


if __name__ == "__main__":
    main()

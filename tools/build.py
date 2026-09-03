"""Build index.html — the whole benchmark as one page.

Three sections in one document:
  1. THE TASK      an annotated page, so a reader who has never seen the corpus understands what
                   is actually being asked of a model before seeing any score.
  2. RESULTS       the scoreboard, with a mode switch. "Pure model ability" hides the two flat-prompt
                   controls so the schema arms are compared on equal terms; "Everything" shows the
                   baseline too.
  3. SIDE BY SIDE  one page, two models, aligned field by field.

Regenerate after adding an arm:  python tools/score.py && python tools/build.py
"""
from __future__ import annotations

import base64
import json
import math
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
PALETTE = ["#8c6a3f", "#b08d57", "#5f7d6b", "#6a7fa0", "#8a6a8a", "#a06a5f",
           "#5f8a8a", "#9a8a4f", "#7a6aa0", "#6a9a6a"]


def num(v, fmt="{:.3f}"):
    """An unmeasured metric renders as an em dash. It must never render as zero."""
    return "&mdash;" if v is None else fmt.format(v)
import inspector as INS     # noqa: E402  — image embedding + per-page arm data

ROOT = Path(__file__).resolve().parent.parent

# The edition this corpus comes from; prices are quoted for the whole book.
# Source: README.md line 56, arms.yaml
BOOK_PAGES = 461

# Defect audit counts on 100 production pages.
# Source: README.md lines 6-7
DEFECTS_TOTAL = 365
DEFECTS_STRUCTURAL = 275
DEFECTS_MISREAD = 79
DEFECTS_OTHER = 11

# Thinking-tokens findings on Gemini 3.8 Flash.
# Source: measured_production/FINDINGS.md lines 36-37, 49
THINKING_ON_COST_PER_PAGE = 0.007184
THINKING_ON_ACCURACY = 0.9985
THINKING_OFF_COST_PER_PAGE = 0.002746
THINKING_OFF_ACCURACY = 0.9975
THINKING_ON_BOOK_COST = 3.31
THINKING_OFF_BOOK_COST = 1.27
THINKING_TOKENS_PCT = 74

# Colours for the ranked models, in task_score descending order.
# keep in sync with tools/chart.py line 28
CHART_COLOURS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b",
    "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#1a1815"
]

# Hand-placed annotation boxes for p093.webp (1513 x 2460 px).
# Source: BUILD_BRIEF_scrollytelling.md lines 75-82
STORY_BOXES = [
    {"label": "running head",             "colour": "#2f6f5e", "left": 9.58,  "top": 2.44,  "width": 10.58, "height": 2.11},
    {"label": "body paragraph",           "colour": "#3b5b8f", "left": 9.91,  "top": 6.71,  "width": 81.63, "height": 37.40},
    {"label": "chapter heading, in flow", "colour": "#a8452f", "left": 32.39, "top": 45.12, "width": 36.35, "height": 3.98},
    {"label": "body paragraph",           "colour": "#3b5b8f", "left": 9.91,  "top": 50.81, "width": 81.63, "height": 22.76},
    {"label": "footnote anchor ١٣٨",      "colour": "#b8860b", "left": 15.33, "top": 53.98, "width": 3.70,  "height": 2.11},
    {"label": "footnote anchor ١٣٩",      "colour": "#b8860b", "left": 72.57, "top": 66.99, "width": 4.23,  "height": 2.20},
    {"label": "footnote apparatus",       "colour": "#7a4a9a", "left": 11.24, "top": 78.86, "width": 81.30, "height": 13.62},
    {"label": "printed page number",      "colour": "#2f6f5e", "left": 45.94, "top": 95.93, "width": 4.96,  "height": 2.03}
]
# The annotated page. p8 is the right teaching example: its running head and its page title are the
# same word, its apparatus holds a nested list in three scripts, and its bottom mark is a page
# number in a separate front-matter series. Every hard thing about the corpus on one leaf.
TEACH_PAGE = 8
CALLOUTS = [
    (6, "Running head", "The section title, repeated on every leaf. Not body text — but it is the "
        "first line, so a flat-text parser calls it one."),
    (12, "Page title", "This page's own heading. On this page it is <em>the same word</em> as the "
         "running head, which is why position alone cannot separate them."),
    (34, "Body", "The prose. Everything else on the page is furniture, and any of it that lands "
         "here gets read aloud to the listener."),
    (69, "Apparatus", "Numbered notes below the rule. Here note 1 contains a nested list in Greek, "
         "Latin and Arabic with two different digit systems."),
    (95, "Page number", "Front matter carries its own series suffixed <span dir='rtl'>م</span>; "
         "the body restarts with plain numerals. Two series, both incrementing by one."),
]


GOLD_COLS = [
    ("body_accuracy", "body", "Character accuracy of the transcribed prose against gold."),
    ("heading_placement", "heading pos", "A heading counts only if it comes back at the same point "
     "in the block sequence — between the paragraphs it actually separates."),
    ("footnote_f1", "notes", "Is each printed note present, as its own object, with nothing "
     "invented? F1 over note identity."),
    ("footnote_text", "note text", "The text of the note, character by character. A note counted "
     "is not a note read."),
    ("anchor_f1", "anchors", "Do the inline anchors match the notes that are actually printed? "
     "Scored against gold, not against the model's own output."),
    ("anchor_placement", "anchor pos", "Is the anchor in the right block? Tap-to-open needs the "
     "link to start from the right paragraph, not merely to exist."),
    ("fields", "fields", "Running head, printed page number (digit-exact), printer mark, "
     "page title."),
    ("marker_exact", "markers", "The marker glyph as printed. `3` and `٣` are different "
     "characters; normalising them silently corrupts the apparatus."),
]


def fmt_pc(v):
    return "—" if v is None else f"{v*100:.1f}%"


def short_labels(arms: dict) -> dict:
    """A short display name per arm that is still UNIQUE.

    The model name alone is the readable label, but two arms can share it — the same model at two
    prompts, or an arm derived from another. Collapsing them produced a chart with two points both
    captioned "Gemini 3.5 Flash", which is worse than a long label.
    """
    first = {k: a["label"].split(" · ")[0] for k, a in arms.items()}
    seen = {}
    for k, v in first.items():
        seen.setdefault(v, []).append(k)
    out = {}
    for v, ks in seen.items():
        if len(ks) == 1:
            out[ks[0]] = v
        else:
            for k in ks:
                tail = arms[k]["label"].split(" · ")[-1]
                out[k] = f"{v} · {tail}"
    return out


def verdict(arms: dict, meta: dict) -> str:
    """The answer: which model performs the task, decided by a rule fixed before the scores.

    Only the arms sharing the recommended prompt are ranked. A gap between two arms that differ in
    BOTH model and prompt is unattributable, so mixing them into one ranking would answer nothing —
    which is exactly the objection that produced this section.
    """
    gp = meta.get("gold_pages") or []
    if not gp:
        return "<p class='note'>No gold pages yet — nothing here is accuracy.</p>"
    gates, band = meta["gates"], meta["noise_band"]

    ranked = []
    for k, a in arms.items():
        g = a.get("gold")
        # `derived_from` arms are excluded: their reading IS another arm's, so ranking them here
        # would enter the same transcription twice under two names.
        if not g or a["prompt"] != "P2" or a.get("derived_from"):
            continue
        ranked.append((k, a, g))
    ranked.sort(key=lambda t: (t[2].get("task_score") is None, -(t[2].get("task_score") or 0)))
    # Disambiguate against THIS table only. Every row here is already the same prompt, so appending
    # "· blocks" to all of them would add a column's worth of noise and distinguish nothing.
    names = short_labels({k: a for k, a, _ in ranked})

    passing = [r for r in ranked if not r[2]["gate_failures"]]
    head = []
    if not passing:
        head.append("<p class='vlede vfail'>No model clears every gate on the evaluation set. "
                    "The honest answer is that none of them does this task correctly end to end "
                    "yet — the table below says which part each one drops.</p>")
    else:
        import gold as GOLD
        top = passing[0]
        # Say only what the rule supports. "Not separated from the top arm" is NOT transitive, so
        # collecting those arms and calling them a group produced a statement that was false on its
        # own terms: an arm was admitted at 98.76 while a HIGHER one at 98.81 was excluded, and the
        # two were plainly not separated from each other. The honest claim is about the top arm and
        # the arms this evidence cannot distinguish from it — nothing about the shape of the set.
        tied = [r for r in passing[1:] if not GOLD.separated(top[2], r[2])]
        below = [r for r in passing[1:] if GOLD.separated(top[2], r[2])]
        short = [top] + tied
        name = names[top[0]]
        if tied:
            tied_names = ", ".join(names[r[0]] for r in tied)
            # Only claim a separation from the arms below if EVERY shortlist member has it. The
            # leader's lead is not the shortlist's lead, and saying otherwise is the transitivity
            # mistake in a new place.
            clean = [r for r in below
                     if all(GOLD.separated(s[2], r[2]) for s in short)]
            murky = [r for r in below if r not in clean]
            txt = (f"<p class='vlede'><b>{name}</b> has the highest score, and on {len(gp)} pages "
                   f"this evidence <b>cannot distinguish it from {tied_names}</b>. Any of those "
                   f"four performs the task; the ordering between them is not a result, so choose "
                   f"on cost and on the specific failure each one still has.</p>")
            if clean:
                txt += (f"<p class='note'>All four are separated from "
                        + ", ".join(names[r[0]] for r in clean) + " and everything below it.</p>")
            if murky:
                txt += (f"<p class='note'><b>And a limit worth stating.</b> "
                        + ", ".join(names[r[0]] for r in murky)
                        + f" score lower than all four, but the gap does not survive removing a "
                        f"single evaluation page for every member of the shortlist. On this "
                        f"evidence they are behind, not beaten.</p>")
            head.append(txt)
        else:
            head.append(f"<p class='vlede'><b>{name}</b> is the recommendation: the only "
                        f"gate-clearing arm whose lead over every other survives both the paired "
                        f"difference test and the removal of any single evaluation page.</p>")

    rows = ["<table class='verdict'><thead><tr><th>model</th><th class='num'>task score</th>"
            "<th class='num' title='90% interval from resampling the evaluation pages'>90% CI</th>"
            "<th class='num' title='list rate on measured output; Gemini excludes thinking tokens'>$/page</th>"
            + "".join(f"<th class='num' title='{d}'>{lab}</th>" for _, lab, d in GOLD_COLS)
            + "<th>gate</th></tr></thead><tbody>"]
    for k, a, g in ranked:
        s, fails = g["scores"], g["gate_failures"]
        cls = "" if not fails else " class='dim'"
        ts = g.get("task_score")
        cov = g.get("weight_covered") or 0
        cover = "" if cov > 0.98 else (f"<span class='cov' title='measured on "
                                       f"{cov*100:.0f}% of the weighted task'>"
                                       f"{cov*100:.0f}%</span>")
        cells = []
        for key, _, _ in GOLD_COLS:
            e = s.get(key) or {}
            v, n, of = e.get("v"), e.get("n"), e.get("of")
            title = f"scored {n} of {of}" if n is not None else "not measurable"
            cells.append(f"<td class='num' title='{title}'>{fmt_pc(v)}</td>")
        gate = ("<span class='ok'>clears</span>" if not fails
                else "<span class='bad'>" + "; ".join(fails) + "</span>")
        ci = g.get("ci")
        ci_txt = "—" if not ci else f"{ci[0]*100:.1f}–{ci[1]*100:.1f}"
        rows.append(f"<tr{cls}><td>{names[k]}</td>"
                    f"<td class='num'><b>{fmt_pc(ts)}</b> {cover}</td>"
                    f"<td class='num ci'>{ci_txt}</td>"
                    f"<td class='num'>${a['summary']['cost_per_page_usd']:.5f}</td>"
                    + "".join(cells) + f"<td class='gate'>{gate}</td></tr>")
    rows.append("</tbody></table>")

    gate_txt = ", ".join(f"{k.replace('_', ' ')} ≥ {v}" if isinstance(v, float)
                         else f"all {len(gp)} evaluation pages answered"
                         for k, v in gates.items())
    return ("".join(head) + "<div class='card scroll'>" + "".join(rows) + "</div>"
            + f"<p class='note'><b>How to read this.</b> Scored on {len(gp)} pages, each read twice "
            f"by a reader outside this field of arms, with every disagreement settled against the "
            f"image. An arm must clear every gate ({gate_txt}); among those that do, the score "
            f"weights the prose first, then note text, anchor placement, block order, heading "
            f"position, fields and markers. The band comes from resampling the {len(gp)} pages, and "
            f"differences under {band*100:.0f} point are not evidence. Hover a cell for its "
            f"denominator.</p>")


def build_chart_svg(rows: list, is_story: bool = True) -> str:
    vb_w, vb_h = 1000, 620
    plot_x0, plot_x1 = 70, 700
    plot_y0, plot_y1 = 40, 560
    plot_w = plot_x1 - plot_x0
    plot_h = plot_y1 - plot_y0

    x_min, x_max = 0.18, 11.5
    y_min, y_max = 0.10, 1.015
    log_x_min, log_x_max = math.log10(x_min), math.log10(x_max)

    def x_to_px(x):
        return plot_x0 + plot_w * (math.log10(x) - log_x_min) / (log_x_max - log_x_min)

    def y_to_px(y):
        return plot_y1 - plot_h * (y - y_min) / (y_max - y_min)

    passing = [r for r in rows if r["ok"]]
    px_x_min = min(x_to_px(r["x"]) for r in passing)
    px_x_max = max(x_to_px(r["x"]) for r in passing)
    px_y_min = min(y_to_px(r["hi"]) for r in passing)
    px_y_max = max(y_to_px(r["lo"]) for r in passing)

    zx0 = max(0.0, px_x_min - 30.0)
    zx1 = min(float(vb_w), px_x_max + 40.0)
    zy0 = max(0.0, px_y_min - 25.0)
    zy1 = min(float(plot_y1), px_y_max + 25.0)
    zoom_target_str = f"{zx0:.1f} {zy0:.1f} {zx1 - zx0:.1f} {zy1 - zy0:.1f}"

    svg_id = "id='storyChartSvg'" if is_story else "class='chart-svg static-chart'"
    data_attr = f" data-zoom-target='{zoom_target_str}'" if is_story else ""

    nudge = {"Gemini 3.7 Flash": (9, 7), "Gemini 3.5 Flash": (9, -9), "Claude Sonnet 5": (9, 8),
             "Qwen 3.8 Max": (-9, 8), "GPT 5.6 Terra": (-9, -8), "Kimi K3": (9, -8)}

    lines = [
        f"<svg {svg_id}{data_attr} viewBox='0 0 {vb_w} {vb_h}' preserveAspectRatio='xMidYMid meet' class='chart-svg'>",
        "<rect width='1000' height='620' fill='var(--card)' rx='3' ry='3' />",
        "<g class='chart-axes-grid'>"
    ]

    for yi in range(10, 101, 2):
        y_val = yi / 100.0
        py = y_to_px(y_val)
        if yi % 10 == 0:
            lines.append(f"<line x1='{plot_x0}' y1='{py:.1f}' x2='{plot_x1}' y2='{py:.1f}' stroke='var(--rule)' stroke-width='1' />")
            lines.append(f"<text x='{plot_x0 - 8}' y='{py + 4:.1f}' text-anchor='end' font-family='\"IBM Plex Mono\", monospace' font-size='11' fill='var(--muted)'>{yi}%</text>")
        else:
            lines.append(f"<line x1='{plot_x0}' y1='{py:.1f}' x2='{plot_x1}' y2='{py:.1f}' stroke='var(--rule)' stroke-width='0.5' stroke-opacity='0.4' />")

    lines.append(f"<line x1='{plot_x0}' y1='{plot_y1}' x2='{plot_x1}' y2='{plot_y1}' stroke='var(--rule)' stroke-width='1.2' />")

    xticks = [(0.2, "$0.20"), (0.5, "$0.50"), (1.0, "$1"), (2.0, "$2"), (5.0, "$5"), (10.0, "$10")]
    for x_val, x_lab in xticks:
        px = x_to_px(x_val)
        lines.append(f"<line x1='{px:.1f}' y1='{plot_y1}' x2='{px:.1f}' y2='{plot_y1 + 6}' stroke='var(--muted)' stroke-width='1' />")
        lines.append(f"<text x='{px:.1f}' y='{plot_y1 + 22}' text-anchor='middle' font-family='\"IBM Plex Mono\", monospace' font-size='11' fill='var(--muted)'>{x_lab}</text>")

    lines.append(f"<text x='22' y='{plot_y0 + plot_h/2:.1f}' text-anchor='middle' transform='rotate(-90 22 {plot_y0 + plot_h/2:.1f})' font-family='\"IBM Plex Sans\", sans-serif' font-size='11' fill='var(--muted)'>task score on gold</text>")
    lines.append(f"<text x='{plot_x0 + plot_w/2:.1f}' y='{vb_h - 12}' text-anchor='middle' font-family='\"IBM Plex Sans\", sans-serif' font-size='11' fill='var(--muted)'>price to read the whole {BOOK_PAGES}-page book, USD (log scale)</text>")
    lines.append("</g>")

    lines.append("<g class='chart-points'>")
    for i, r in enumerate(rows):
        px = x_to_px(r["x"])
        py = y_to_px(r["y"])
        py_lo = y_to_px(r["lo"])
        py_hi = y_to_px(r["hi"])
        c = r["c"]
        ok = r["ok"]
        name = r["name"]
        cls = "chart-point-group" + (" is-gate-passing" if ok else " is-gate-failing")
        lines.append(f"<g class='{cls}' data-idx='{i}' data-ok='{1 if ok else 0}' data-name='{name}' style='--pt-c:{c};'>")
        lines.append(f"<line class='point-whisker' x1='{px:.1f}' y1='{py_lo:.1f}' x2='{px:.1f}' y2='{py_hi:.1f}' stroke='{c}' stroke-width='1.6' stroke-linecap='round' />")
        lines.append(f"<line class='point-cap point-cap-lo' x1='{px - 3:.1f}' y1='{py_lo:.1f}' x2='{px + 3:.1f}' y2='{py_lo:.1f}' stroke='{c}' stroke-width='1.6' stroke-linecap='round' />")
        lines.append(f"<line class='point-cap point-cap-hi' x1='{px - 3:.1f}' y1='{py_hi:.1f}' x2='{px + 3:.1f}' y2='{py_hi:.1f}' stroke='{c}' stroke-width='1.6' stroke-linecap='round' />")
        if ok:
            lines.append(f"<circle class='point-dot' cx='{px:.1f}' cy='{py:.1f}' r='9' fill='{c}' stroke='{c}' stroke-width='1' />")
        else:
            lines.append(f"<circle class='point-dot' cx='{px:.1f}' cy='{py:.1f}' r='9' fill='var(--card)' stroke='{c}' stroke-width='3' />")
        if name in nudge:
            dx, dy = nudge[name]
            anchor = "start" if dx > 0 else "end"
            lines.append(f"<text class='point-name-label' x='{px + dx:.1f}' y='{py + dy:.1f}' text-anchor='{anchor}' font-family='\"IBM Plex Sans\", sans-serif' font-size='11' font-weight='600' fill='var(--ink)'>{name}</text>")
        lines.append("</g>")
    lines.append("</g>")

    lines.append("<g class='chart-legend-desktop' id='chartLegendDesktop'>")
    lines.append(f"<text x='730' y='55' font-family='\"IBM Plex Sans\", sans-serif' font-size='11' font-weight='600' fill='var(--muted)'>model · task score · $ for book</text>")
    for i, r in enumerate(rows):
        y_row = 85 + i * 44
        color = r["c"]
        dot_fill = color if r["ok"] else "var(--card)"
        dot_sw = 1 if r["ok"] else 2.5
        name = r["name"]
        score_pct = r["y"] * 100
        cost_val = r["x"]
        lines.append(f"<g class='chart-legend-row' data-idx='{i}'>")
        lines.append(f"<circle cx='738' cy='{y_row - 4}' r='5' fill='{dot_fill}' stroke='{color}' stroke-width='{dot_sw}' />")
        lines.append(f"<text x='752' y='{y_row}' font-family='\"IBM Plex Sans\", sans-serif' font-size='12' font-weight='500' fill='var(--ink)'>{name}</text>")
        lines.append(f"<text x='990' y='{y_row}' text-anchor='end' font-family='\"IBM Plex Mono\", monospace' font-size='12' fill='var(--ink)'><tspan>{score_pct:.1f}%</tspan> &nbsp; <tspan fill='var(--muted)'>${cost_val:.2f}</tspan></text>")
        lines.append("</g>")
    lines.append("</g>")

    lines.append("<g class='chart-legend-mobile' id='chartLegendMobile'>")
    lines.append("<text x='70' y='585' font-family='\"IBM Plex Sans\", sans-serif' font-size='10.5' font-weight='600' fill='var(--muted)'>model · task score · $ for book</text>")
    for i, r in enumerate(rows):
        col = 0 if i < 6 else 1
        row_in_col = i if col == 0 else i - 6
        cx = 70 if col == 0 else 390
        cright = 370 if col == 0 else 690
        ry = 605 + row_in_col * 24
        color = r["c"]
        dot_fill = color if r["ok"] else "var(--card)"
        dot_sw = 1 if r["ok"] else 2
        name = r["name"]
        score_pct = r["y"] * 100
        cost_val = r["x"]
        lines.append(f"<g class='chart-legend-row-mob' data-idx='{i}'>")
        lines.append(f"<circle cx='{cx + 5}' cy='{ry - 3}' r='4' fill='{dot_fill}' stroke='{color}' stroke-width='{dot_sw}' />")
        lines.append(f"<text x='{cx + 15}' y='{ry}' font-family='\"IBM Plex Sans\", sans-serif' font-size='10.5' font-weight='500' fill='var(--ink)'>{name}</text>")
        lines.append(f"<text x='{cright}' y='{ry}' text-anchor='end' font-family='\"IBM Plex Mono\", monospace' font-size='10' fill='var(--ink)'>{score_pct:.1f}% ${cost_val:.2f}</text>")
        lines.append("</g>")
    lines.append("</g>")

    lines.append("</svg>")
    return "\n".join(lines)


def main() -> None:
    data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    arms = data["arms"]
    cfg = yaml.safe_load((ROOT / "arms.yaml").read_text(encoding="utf-8"))
    colours = {k: PALETTE[i % len(PALETTE)] for i, k in enumerate(arms)}
    pages = sorted({x["page"] for a in arms.values() for x in a["pages"]})

    def rows(metric, lower=True):
        r = [(a["label"], a["summary"][metric], colours[k],
              a["price_source"] if metric == "cost_per_page_usd" else "", k, a["prompt"])
             for k, a in arms.items() if a["summary"].get(metric) is not None]
        return sorted(r, key=lambda t: t[1], reverse=not lower)

    # summary table
    tbl = ["<table><thead><tr><th>arm</th>"
           "<th class='num'>transcript</th><th class='num'>fields</th>"
           "<th class='num'>footnotes</th><th class='num'>anchors</th>"
           "<th class='num'>refs</th><th class='num'>failures</th>"
           "<th class='num'>$/page</th></tr></thead><tbody>"]
    for k, a in sorted(arms.items(),
                       key=lambda kv: -(kv[1]["summary"].get("transcript_accuracy") or 0)):
        s = a["summary"]
        tbl.append(
            f"<tr data-arm='{k}'>"
            f"<td><span class='dot' style='background:{colours[k]}'></span>{a['label']}"
            f"<div class='muted small'>{a['role']}</div></td>"
            f"<td class='num'>{num(s.get('transcript_accuracy'), '{:.2%}')}</td>"
            f"<td class='num'>{(s['field_accuracy'] or 0)*100:.0f}%</td>"
            f"<td class='num'>{num(s['footnote_exact_rate'], '{:.0%}')}</td>"
            f"<td class='num'>{num(s.get('anchor_consistency'), '{:.0%}')}</td>"
            f"<td class='num'>{s.get('references_total') if s.get('references_total') else '&mdash;'}</td>"
            f"<td class='num'>{('<b>' + str(s.get('output_failures')) + '</b>') if s.get('output_failures') else '0'}</td>"
            f"<td class='num'>${s['cost_per_page_usd']:.5f}"
            f"<span class='tag'>{a['price_source']}</span></td></tr>")
    tbl.append("</tbody></table>")

    # inspector payload, reusing the same builders
    insp_arms = [a for a in cfg["arms"] if (ROOT / "runs" / a["id"]).exists()]
    truth = {int(f.stem[1:]): json.loads(f.read_text(encoding="utf-8"))
             for f in sorted((ROOT / "truth").glob("p*.json"))}
    ipages, idata = [], {}
    for img in sorted((ROOT / "pages").glob("p*.webp")):
        pg = int(img.stem[1:])
        rowsd = {}
        for a in insp_arms:
            f = ROOT / "runs" / a["id"] / f"p{pg:03d}.json"
            if not f.exists():
                continue
            import metrics as M
            try:
                # ONE loader for every shape. Hand-rolling a second one here is how P2 arms ended up
                # in the inspector with an empty body and no blocks: this file knew about flat text
                # and the field-per-element schema, and silently produced nothing for a block record.
                rec = M.load_arm(f)
            except Exception:
                continue
            raw = f.read_text(encoding="utf-8")
            rowsd[a["id"]] = {
                "raw": raw if len(raw) <= 9000 else raw[:9000] + chr(10) + "... truncated ...",
                "prompt": a["prompt"],
                "runningHeader": rec.get("runningHeader"), "pageTitle": rec.get("pageTitle"),
                "printedPageNumber": rec.get("printedPageNumber"),
                "printerMark": rec.get("printerMark"),
                "body": [str(x) for x in (rec.get("body") or [])],
                "blocks": [{"type": b.get("type"), "text": str(b.get("text") or ""),
                            "noteRefs": [n for n in (b.get("noteRefs") or [])
                                         if isinstance(n, int)]}
                           for b in (rec.get("_blocks") or []) if isinstance(b, dict)],
                "anchors": rec.get("_anchors"),
                "references": rec.get("_references"),
                "footnotes": [{"marker": n.get("marker"), "text": n.get("text", "")}
                              for n in (rec.get("footnotes") or [])]}
        if not rowsd:
            continue
        ipages.append(pg)
        idata[pg] = {"img": INS.thumb(img), "arms": rowsd,
                     "truth": {k: truth.get(pg, {}).get(k) for k in
                               ("runningHeader", "pageTitle", "printedPageNumber",
                                "printerMark", "footnoteCount", "verifiedBy")}}
    from collections import Counter
    for pg in ipages:
        cons = {}
        for field in ("runningHeader", "pageTitle", "printedPageNumber", "printerMark"):
            c = Counter(json.dumps(r[field], ensure_ascii=False) for r in idata[pg]["arms"].values())
            top, n = c.most_common(1)[0]
            cons[field] = {"value": json.loads(top), "agree": n, "of": sum(c.values())}
        c = Counter(len(r["footnotes"]) for r in idata[pg]["arms"].values())
        cons["footnoteCount"] = {"value": c.most_common(1)[0][0],
                                 "agree": c.most_common(1)[0][1], "of": sum(c.values())}
        idata[pg]["consensus"] = cons

    meta = {"arms": [{"id": a["id"], "label": a["label"], "prompt": a["prompt"],
                      "colour": colours.get(a["id"], "#888"),
                      "control": bool(a.get("control"))} for a in insp_arms],
            "pages": ipages}

    summary = [{"id": k, "label": a["label"], "model": a["model"], "prompt": a["prompt"],
                "role": a["role"], "price_source": a.get("price_source"),
                "control": bool(a.get("control")), **{m: a["summary"].get(m) for m in (
                    "pages", "transcript_accuracy", "field_accuracy", "footnote_exact_rate",
                    "anchor_consistency", "body_purity", "output_failures",
                    "cost_per_page_usd", "references_total")},
                "byPage": {str(x["page"]): {
                    "fields": sum(1 for v in x["fields"].values() if v is True),
                    "fieldSlots": sum(1 for v in x["fields"].values() if v is not None),
                    "footnote_err": x.get("footnote_err"),
                    "body_cer": x.get("body_cer"),
                    "anchor": x.get("anchor_consistency"),
                    "failed": bool(x.get("output_failed")),
                } for x in a["pages"]}}
               for k, a in arms.items()]

    prompts = {"P2": (ROOT / "prompts" / "P2_blocks.txt").read_text(encoding="utf-8")}

    # --- Scrollytelling v2 story opening ---
    gold_pages = data.get("_meta", {}).get("gold_pages") or []

    chart_rows = []
    for k, a in arms.items():
        g = a.get("gold")
        if not g or a["prompt"] != "P2" or a.get("derived_from"):
            continue
        chart_rows.append(dict(id=k, name=a["label"].split(" · ")[0],
                               x=a["summary"]["cost_per_page_usd"] * BOOK_PAGES,
                               y=g["task_score"], lo=g["ci"][0], hi=g["ci"][1],
                               ok=not g["gate_failures"], gold=g))
    chart_rows.sort(key=lambda r: -r["y"])
    for i, r in enumerate(chart_rows):
        r["c"] = CHART_COLOURS[i % len(CHART_COLOURS)]

    ranked_arms = [(r["id"], arms[r["id"]], r["gold"]) for r in chart_rows]
    n_story_models = len(ranked_arms)

    story_chart_svg = build_chart_svg(chart_rows, is_story=True)
    scatter_chart_svg = build_chart_svg(chart_rows, is_story=False)

    deck_thumbs = {pg: INS.thumb(ROOT / "pages" / f"p{pg:03d}.webp", width=160) for pg in pages}
    p093_thumb = INS.thumb(ROOT / "pages" / "p093.webp", width=1100)

    deck_cards_html = "".join(
        f"<div class='deck-card{' is-gold' if pg in gold_pages else ''}' "
        f"data-idx='{i}' data-page='{pg}'"
        f"{f' data-gold-idx=\"{gold_pages.index(pg)}\"' if pg in gold_pages else ''}>"
        f"<img src='{deck_thumbs[pg]}' alt='p{pg:03d}'>"
        f"<span class='gold-check'>✓</span>"
        f"<span class='card-num'>p{pg:03d}</span>"
        f"</div>"
        for i, pg in enumerate(pages)
    )

    chips_html = "".join(
        f"<div class='story-chip' data-chip-idx='{i}' style='--chip-c:{r['c']};'>"
        f"<span class='dot' style='background:{r['c']}'></span>"
        f"<span class='chip-name'>{r['name']}</span></div>"
        for i, r in enumerate(chart_rows)
    )

    PAGE_W, PAGE_H = 1513, 2460
    box_svg_parts = []
    for i, b in enumerate(STORY_BOXES):
        bx = round(b["left"] * PAGE_W / 100, 1)
        by = round(b["top"] * PAGE_H / 100, 1)
        bw = round(b["width"] * PAGE_W / 100, 1)
        bh = round(b["height"] * PAGE_H / 100, 1)
        perim = round(2 * (bw + bh), 1)
        tab_w = max(190, len(b["label"]) * 30 + 40)
        col = b["colour"]
        lbl = b["label"]
        box_svg_parts.append(
            f"<g class='fig-box-g' data-idx='{i}' style='--box-c:{col};'>"
            f"<rect class='fig-box-rect' x='{bx}' y='{by}' width='{bw}' height='{bh}' rx='6' ry='6' "
            f"stroke='{col}' stroke-width='6' fill='{col}' fill-opacity='0.12' "
            f"stroke-dasharray='{perim}' stroke-dashoffset='{perim}' data-perim='{perim}' />"
            f"<g class='fig-box-tab' transform='translate({bx}, {by})'>"
            f"<rect class='fig-box-tab-bg' x='0' y='-78' width='{tab_w}' height='78' rx='8' ry='8' fill='{col}' />"
            f"<text class='fig-box-tab-text' x='20' y='-24' fill='#ffffff' font-family='\"IBM Plex Sans\", sans-serif' font-size='50' font-weight='500'>{lbl}</text>"
            f"</g></g>"
        )
    story_boxes_svg_html = "".join(box_svg_parts)

    import gold as GOLD
    passing = [r for r in ranked_arms if not r[2]["gate_failures"]]
    top = passing[0]
    tied = [r for r in passing[1:] if not GOLD.separated(top[2], r[2])]
    leader_name = top[1]["label"].split(" · ")[0]
    tied_names = ", ".join(r[1]["label"].split(" · ")[0] for r in tied)
    beat6_sub = f"{leader_name} scores highest. On {len(gold_pages)} pages the evidence cannot separate it from {tied_names}."

    shortlist = [top] + tied
    shortlist_costs = [r[1]["summary"]["cost_per_page_usd"] for r in shortlist]
    price_ratio_num = round(max(shortlist_costs) / min(shortlist_costs))
    price_ratio = f"{price_ratio_num}×"

    max_book_cost = max(r[1]["summary"]["cost_per_page_usd"] * BOOK_PAGES for r in passing)
    passing_bars_html = "".join(
        f"<div class='cost-bar-row' data-cost='{r[1]['summary']['cost_per_page_usd'] * BOOK_PAGES:.2f}'>"
        f"<span class='cost-bar-label'>{r[1]['label'].split(' · ')[0]}</span>"
        f"<div class='cost-bar-track'>"
        f"<div class='cost-bar-fill' style='width:{(r[1]['summary']['cost_per_page_usd'] * BOOK_PAGES / max_book_cost) * 100:.2f}%;"
        f"background:{CHART_COLOURS[next(idx for idx, ra in enumerate(ranked_arms) if ra[0] == r[0]) % len(CHART_COLOURS)]};'></div>"
        f"</div>"
        f"<span class='cost-bar-val'>${r[1]['summary']['cost_per_page_usd'] * BOOK_PAGES:.2f}</span>"
        f"</div>"
        for r in passing
    )

    story_rail_html = """<nav class="story-rail" id="storyRail" aria-label="Story navigation">
  <button class="rail-dot" data-beat="1" title="One leaf of a 461-page edition" aria-label="Beat 1"></button>
  <button class="rail-dot" data-beat="2" title="A model has to know what each thing is" aria-label="Beat 2"></button>
  <button class="rail-dot" data-beat="3" title="Get one of them wrong" aria-label="Beat 3"></button>
  <button class="rail-dot" data-beat="4" title="So we asked N models the same question" aria-label="Beat 4"></button>
  <button class="rail-dot" data-beat="5" title="Scored them on 8 pages read twice" aria-label="Beat 5"></button>
  <button class="rail-dot" data-beat="6" title="The answer" aria-label="Beat 6"></button>
  <button class="rail-dot" data-beat="7" title="Pick on cost" aria-label="Beat 7"></button>
  <button class="rail-dot" data-beat="8" title="Turn thinking off" aria-label="Beat 8"></button>
  <button class="rail-dot" data-beat="9" title="Everything below is the data" aria-label="Beat 9"></button>
</nav>"""

    story_html = f"""<section id="story">
  {story_rail_html}
  <div class="story-figure-col">
    <div class="story-figure-sticky">
      <div class="story-figure" id="storyFigure" data-beat="0">
        <!-- Page layer (Beats 0-3) -->
        <div class="fig-layer fig-page-layer">
          <div class="fig-page-frame" id="figPageFrame">
            <div class="fig-page-wrap">
              <img src="{p093_thumb}" class="fig-page-img" alt="Scanned leaf of Justin Martyr, p093">
              <svg viewBox="0 0 1513 2460" class="fig-boxes-svg" id="figBoxesSvg" preserveAspectRatio="none">
                {story_boxes_svg_html}
              </svg>
            </div>
            <p class="fig-page-caption">p093 &middot; 1 of {len(pages)} in this benchmark &middot; 1 of {BOOK_PAGES} in the book</p>
            <div class="fig-defects-strip" id="figDefects">
              <div class="defect-counter-row">
                <span class="defect-counter-num" id="defectCounter" data-target="{DEFECTS_TOTAL}">{DEFECTS_TOTAL}</span>
                <span class="defect-counter-label">defects on 100 production pages</span>
              </div>
              <div class="defect-track" id="defectTrack">
                <div class="defect-fill def-struct" style="width: {(DEFECTS_STRUCTURAL / DEFECTS_TOTAL) * 100:.2f}%;"></div>
                <div class="defect-fill def-mis" style="width: {(DEFECTS_MISREAD / DEFECTS_TOTAL) * 100:.2f}%;"></div>
                <div class="defect-fill def-oth" style="width: {(DEFECTS_OTHER / DEFECTS_TOTAL) * 100:.2f}%;"></div>
              </div>
              <div class="defect-legend">
                <span class="def-seg def-struct"><span class="def-dot" style="background:var(--accent)"></span>structural <b>{DEFECTS_STRUCTURAL}</b></span>
                &middot;
                <span class="def-seg def-mis"><span class="def-dot" style="background:var(--warn)"></span>misread <b>{DEFECTS_MISREAD}</b></span>
                &middot;
                <span class="def-seg def-oth"><span class="def-dot" style="background:var(--muted)"></span>other <b>{DEFECTS_OTHER}</b></span>
              </div>
            </div>
          </div>
        </div>

        <!-- Deck layer (Beats 4, 5) -->
        <div class="fig-layer fig-deck-layer" id="figDeckLayer">
          <div class="deck-stage">
            <div class="story-deck-fan" id="storyDeckFan">
              {deck_cards_html}
            </div>
            <div class="story-chips-arc" id="storyChipsArc">
              {chips_html}
            </div>
          </div>
        </div>

        <!-- Chart layer (Beats 6, 7) -->
        <div class="fig-layer fig-chart-layer" id="figChartLayer">
          <div class="fig-chart-frame">
            {story_chart_svg}
          </div>
          <div class="fig-cost-bars" id="figCostBars">
            {passing_bars_html}
          </div>
        </div>

        <!-- Thinking layer (Beat 8) -->
        <div class="fig-layer fig-thinking-layer" id="figThinking">
          <div class="fig-thinking-card">
            <div class="think-row">
              <div class="think-meta">
                <span class="think-title">thinking on</span>
                <span class="think-price" id="thinkOnPrice" data-target="{THINKING_ON_BOOK_COST:.2f}">${THINKING_ON_BOOK_COST:.2f}</span>
              </div>
              <div class="think-track">
                <div class="think-fill think-fill-on" id="thinkFillOn" style="width: 100%;">
                  <div class="think-seg-tokens" id="thinkSegTokens" style="width: {THINKING_TOKENS_PCT}%;">
                    <span class="think-seg-label">thinking tokens</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="think-row" style="margin-top: 18px;">
              <div class="think-meta">
                <span class="think-title">thinking off</span>
                <span class="think-price" id="thinkOffPrice" data-target="{THINKING_OFF_BOOK_COST:.2f}">${THINKING_OFF_BOOK_COST:.2f}</span>
              </div>
              <div class="think-track">
                <div class="think-fill think-fill-off" id="thinkFillOff" style="width: {(THINKING_OFF_BOOK_COST / THINKING_ON_BOOK_COST) * 100:.2f}%;"></div>
              </div>
            </div>
            <p class="fig-thinking-cap">same pages, same prompt &middot; accuracy {THINKING_ON_ACCURACY*100:.2f}% &rarr; {THINKING_OFF_ACCURACY*100:.2f}%</p>
          </div>
        </div>

        <!-- Outro layer (Beat 9) -->
        <div class="fig-layer fig-outro-layer" id="figOutro">
          <div class="fig-outro-wrap">
            <img src="{p093_thumb}" class="fig-outro-img" alt="Scanned leaf of Justin Martyr, p093">
            <p class="fig-outro-line">{len(pages)} pages &middot; {n_story_models} models &middot; {len(gold_pages)} read twice</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="story-steps-col" id="storySteps">
    <!-- Beat 0: Hero -->
    <article class="step step-hero" data-step="0">
      <div class="step-content">
        <p class="eyebrow">Benchmark &middot; {n_story_models} models &middot; {len(pages)} pages</p>
        <h1>Which model can read this page?</h1>
        <div class="scroll-hint">scroll <span class="scroll-arrow">&darr;</span></div>
      </div>
    </article>

    <!-- Beat 1 -->
    <article class="step" data-step="1">
      <div class="step-content">
        <h2>One leaf of a {BOOK_PAGES}-page Arabic scholarly edition.</h2>
        <p class="sub">Running head, body, a chapter heading, footnote anchors, the apparatus, a page number. Each is a different kind of thing.</p>
      </div>
    </article>

    <!-- Beat 2 -->
    <article class="step step-long" data-step="2">
      <div class="step-content">
        <h2>A model has to know what each thing is.</h2>
      </div>
    </article>

    <!-- Beat 3 -->
    <article class="step" data-step="3">
      <div class="step-content">
        <h2>Get one of them wrong and the app reads the running head aloud on every page.</h2>
        <p class="sub">An audit of 100 production pages found {DEFECTS_TOTAL} defects. {DEFECTS_STRUCTURAL} were structural: running head in the body, page number in the body, footnotes merged. {DEFECTS_MISREAD} were misreadings.</p>
      </div>
    </article>

    <!-- Beat 4 -->
    <article class="step" data-step="4">
      <div class="step-content">
        <h2>So we asked {n_story_models} models the same question.</h2>
        <p class="sub">The same {len(pages)} page images, the same instruction: give back the page as an ordered sequence of typed blocks, with the notes anchored where they belong.</p>
      </div>
    </article>

    <!-- Beat 5 -->
    <article class="step" data-step="5">
      <div class="step-content">
        <h2>&hellip;and scored them on {len(gold_pages)} pages that were read twice, independently.</h2>
        <p class="sub">The reader is a model outside the ranked set. Every disagreement between its two readings was settled against the page image. No model in the ranking helped write the reference.</p>
      </div>
    </article>

    <!-- Beat 6 -->
    <article class="step" data-step="6">
      <div class="step-content">
        <h2>The answer.</h2>
        <p class="sub">{beat6_sub}</p>
      </div>
    </article>

    <!-- Beat 7 -->
    <article class="step" data-step="7">
      <div class="step-content">
        <h2>They span <span id="storyPriceRatio" data-target="{price_ratio_num}">1&times;</span> in price. Pick on cost.</h2>
        <p class="sub">For the whole {BOOK_PAGES}-page book.</p>
      </div>
    </article>

    <!-- Beat 8 -->
    <article class="step" data-step="8">
      <div class="step-content">
        <h2>Turn thinking off.</h2>
        <p class="sub">On Gemini 3.8 Flash, thinking tokens were {THINKING_TOKENS_PCT}% of what was billed. Off, the book costs ${THINKING_OFF_BOOK_COST:.2f} instead of ${THINKING_ON_BOOK_COST:.2f} and accuracy holds at {THINKING_OFF_ACCURACY*100:.2f}%.</p>
      </div>
    </article>

    <!-- Beat 9: Outro -->
    <article class="step step-outro" data-step="9">
      <div class="step-content">
        <h2>Everything below is the data.</h2>
        <p class="sub">Every page, every reading, every number, and where each one came from.</p>
        <div class="outro-arrow">&darr;</div>
      </div>
    </article>
  </div>
</section>
"""

    teach = INS.thumb(ROOT / "pages" / f"p{TEACH_PAGE:03d}.webp", width=520)
    marks = "".join(
        f"<div class='mk' style='top:{y}%'><span class='mkn'>{i+1}</span></div>"
        for i, (y, _, _) in enumerate(CALLOUTS))
    legend = "".join(
        f"<li><span class='mkn'>{i+1}</span><div><b>{t}</b><p>{d}</p></div></li>"
        for i, (_, t, d) in enumerate(CALLOUTS))

    html = (TEMPLATE
            .replace("__TEACHIMG__", teach).replace("__MARKS__", marks).replace("__LEGEND__", legend)
            .replace("__STORY__", story_html)
            .replace("__TABLE__", "".join(tbl))
            .replace("__VERDICT__", verdict(arms, data.get("_meta", {})))

            .replace("__SCATTER__", scatter_chart_svg)
            .replace("__NGOLD__", str(len(data.get("_meta", {}).get("gold_pages") or [])))
            .replace("__NARMS__", str(len(arms))).replace("__NPAGES__", str(len(pages)))
            .replace("__DATA__", json.dumps(idata, ensure_ascii=False))
            .replace("__META__", json.dumps(meta, ensure_ascii=False))
            .replace("__PROMPTS__", json.dumps(prompts, ensure_ascii=False))
            .replace("__SUMMARY__", json.dumps(summary, ensure_ascii=False))
            .replace("__STORYJS__", (ROOT / "tools" / "story.js").read_text(encoding="utf-8"))
            .replace("__APPJS__", (ROOT / "tools" / "app.js").read_text(encoding="utf-8")))
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html written - {len(arms)} arms, {len(pages)} pages, "
          f"{(ROOT / 'index.html').stat().st_size // 1024} KB")


TEMPLATE = r"""<meta charset="utf-8">
<title>Reading the Apparatus</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,500;1,300&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Noto+Naskh+Arabic:wght@400;600&display=swap">
<style>
:root{--paper:#f0efe9;--card:#fbfaf6;--ink:#1a1815;--muted:#6a675e;--rule:#d9d6cc;
 --accent:#9e2b25;--good:#3d6b55;--warn:#a8762b;--shade:#e6e4dc;
 --red:rgba(158,43,37,.20);--yellow:rgba(168,118,43,.26);--diff:rgba(106,127,160,.13);
 color-scheme:light}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#141312;--card:#1d1b18;
 --ink:#e9e5db;--muted:#9b968a;--rule:#332f2a;--accent:#d4736a;--good:#7aa98e;--warn:#c99a52;
 --shade:#232019;--red:rgba(212,115,106,.24);--yellow:rgba(201,154,82,.26);
 --diff:rgba(140,160,196,.14);color-scheme:dark}}
:root[data-theme="dark"]{--paper:#141312;--card:#1d1b18;--ink:#e9e5db;--muted:#9b968a;
 --rule:#332f2a;--accent:#d4736a;--good:#7aa98e;--warn:#c99a52;--shade:#232019;
 --red:rgba(212,115,106,.24);--yellow:rgba(201,154,82,.26);--diff:rgba(140,160,196,.14);
 color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);margin:0;
 font:400 16px/1.65 "IBM Plex Sans",-apple-system,BlinkMacSystemFont,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:52px 24px 90px}
h1{font:500 40px/1.12 Spectral,Georgia,serif;letter-spacing:-.015em;margin:0 0 12px;text-wrap:balance}
h2{font:500 23px/1.25 Spectral,Georgia,serif;margin:0 0 4px;text-wrap:balance}
.eyebrow{font:600 12px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.14em;
 color:var(--accent);margin:0 0 16px}
.lede{font:300 20px/1.55 Spectral,Georgia,serif;color:var(--muted);max-width:64ch;margin:0 0 34px}
p{margin:0 0 15px;max-width:68ch}.sub{color:var(--muted);font-size:14.5px;margin:5px 0 0}
.muted{color:var(--muted)}.small{font-size:12.5px}
.mono,.num{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.card{background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:20px 22px;margin:16px 0}
section{margin:0 0 52px;scroll-margin-top:70px}
.nav{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--rule);
 display:flex;gap:4px;padding:9px 0;margin:0 0 34px;flex-wrap:wrap;align-items:center}
.nav a{font-size:13.5px;color:var(--muted);text-decoration:none;padding:6px 12px;border-radius:3px}
.nav a:hover{color:var(--ink);background:var(--shade)}
.modes{margin-left:auto;display:flex;gap:0;border:1px solid var(--rule);border-radius:3px;overflow:hidden}
.modes button{font:inherit;font-size:12.5px;padding:6px 13px;border:0;background:var(--card);
 color:var(--muted);cursor:pointer}
.modes button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.modes button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}

/* story */
#story{display:flex;flex-direction:row;width:100%;max-width:1280px;margin:0 auto;position:relative;box-sizing:border-box}
.story-figure-col{width:46%;flex:0 0 46%;position:sticky;top:0;height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;z-index:10}
.story-figure-sticky{width:100%;height:100%;display:flex;align-items:center;justify-content:center}
.story-figure{position:relative;width:100%;max-width:560px;height:82vh;max-height:740px;display:flex;align-items:center;justify-content:center}
.story-steps-col{width:54%;flex:0 0 54%;padding:0 32px 0 24px;box-sizing:border-box}
.step{min-height:85vh;display:flex;flex-direction:column;justify-content:center;padding:60px 0;box-sizing:border-box;opacity:.35;transition:opacity 300ms ease-out}
.step.active{opacity:1}
.step-hero{min-height:120vh}
.step-long{min-height:240vh}
.step-outro{min-height:75vh}
.step-content{max-width:40ch;margin:0 auto}
.step-content h1{font:500 38px/1.15 Spectral,Georgia,serif;letter-spacing:-.015em;margin:0 0 16px;text-wrap:balance;color:var(--ink)}
.step-content h2{font:500 27px/1.22 Spectral,Georgia,serif;letter-spacing:-.01em;margin:0 0 12px;text-wrap:balance;color:var(--ink)}
.step-content .eyebrow{font:600 12px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.14em;color:var(--accent);margin:0 0 16px}
.step-content .sub{font:400 15.5px/1.6 "IBM Plex Sans",sans-serif;color:var(--muted);margin:0}
.scroll-hint{margin-top:32px;font:500 12.5px/1 "IBM Plex Mono",monospace;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);display:inline-flex;align-items:center;gap:6px;opacity:1;transition:opacity 300ms ease-out}
.scroll-arrow{display:inline-block;animation:bob 1.6s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(5px)}}
.outro-arrow{margin-top:24px;font-size:24px;color:var(--accent);animation:bob 1.6s ease-in-out infinite}

/* Progress rail */
.story-rail{position:fixed;right:24px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:12px;z-index:40;opacity:1;transition:opacity 300ms ease-out;pointer-events:auto}
.story-rail.past-story{opacity:0;pointer-events:none}
.rail-dot{width:9px;height:9px;border-radius:50%;border:none;background:var(--rule);padding:0;cursor:pointer;transition:background 250ms ease-out,transform 250ms ease-out}
.rail-dot:hover{transform:scale(1.3)}
.rail-dot.active{background:var(--accent);transform:scale(1.25)}

/* Figure layers */
.fig-layer{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity 400ms ease-out}
.story-figure[data-beat="0"] .fig-page-layer,
.story-figure[data-beat="1"] .fig-page-layer,
.story-figure[data-beat="2"] .fig-page-layer,
.story-figure[data-beat="3"] .fig-page-layer{opacity:1;pointer-events:auto}
.story-figure[data-beat="4"] .fig-deck-layer,
.story-figure[data-beat="5"] .fig-deck-layer{opacity:1;pointer-events:auto}
.story-figure[data-beat="6"] .fig-chart-layer,
.story-figure[data-beat="7"] .fig-chart-layer{opacity:1;pointer-events:auto}
.story-figure[data-beat="8"] .fig-thinking-layer{opacity:1;pointer-events:auto}
.story-figure[data-beat="9"] .fig-outro-layer{opacity:1;pointer-events:auto}

/* Beat 0 & 1 Page frame */
.fig-page-frame{position:relative;display:inline-flex;flex-direction:column;align-items:center;max-width:100%;max-height:100%}
.fig-page-wrap{position:relative;display:inline-block;max-width:100%;max-height:100%}
.fig-page-img{display:block;max-height:70vh;max-width:100%;width:auto;height:auto;border:1px solid var(--rule);border-radius:3px;box-shadow:0 4px 20px rgba(0,0,0,.08)}
.fig-page-caption{font:400 12px/1.4 "IBM Plex Mono",monospace;color:var(--muted);margin-top:10px;text-align:center}

/* Beat 2 & 3 Boxes SVG */
.fig-boxes-svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.fig-box-rect{rx:6px;ry:6px;fill-opacity:.12;stroke-width:6px}
.fig-box-g{transition:opacity 150ms ease-out}
.fig-box-tab{transition:opacity 150ms ease-out}
@media(max-width:899px){.js .fig-box-g:not(.latest) .fig-box-tab{display:none !important}}

/* Beat 3 Defects strip */
.fig-defects-strip{width:100%;margin-top:10px}
.defect-counter-row{display:flex;align-items:baseline;gap:8px;margin-bottom:6px;justify-content:center}
.defect-counter-num{font:500 40px/1 Spectral,Georgia,serif;font-variant-numeric:tabular-nums;color:var(--accent)}
.defect-counter-label{font:400 13px/1.2 "IBM Plex Sans",sans-serif;color:var(--muted)}
.defect-track{display:flex;height:9px;border-radius:2px;overflow:hidden;background:var(--shade);gap:2px}
.defect-fill{height:100%}
.defect-fill.def-struct{background:var(--accent)}
.defect-fill.def-mis{background:var(--warn)}
.defect-fill.def-oth{background:var(--muted)}
.defect-legend{display:flex;gap:8px;justify-content:center;align-items:center;margin-top:6px;font-size:11.5px;color:var(--muted);font-family:"IBM Plex Sans",sans-serif}
.defect-legend b{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;color:var(--ink)}
.def-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px;vertical-align:0}

/* Beat 4 & 5 Deck & chips */
.fig-deck-layer{width:100%;height:100%}
.deck-stage{position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center}
.story-deck-fan{position:relative;width:80px;height:130px;display:flex;align-items:center;justify-content:center}
.deck-card{position:absolute;width:72px;aspect-ratio:1513/2460;background:var(--card);border:1px solid var(--rule);border-radius:2px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);transform-origin:center 120%;transition:box-shadow 250ms ease-out,opacity 250ms ease-out}
.deck-card img{width:100%;height:100%;object-fit:cover;display:block}
.deck-card .card-num{position:absolute;bottom:2px;left:3px;font:500 8.5px/1 "IBM Plex Mono",monospace;color:var(--ink);background:var(--card);padding:1px 2px;border-radius:2px}
.gold-check{position:absolute;top:3px;right:3px;width:16px;height:16px;border-radius:50%;background:var(--good);color:#fff;font:700 10px/16px "IBM Plex Sans",sans-serif;text-align:center;opacity:0;transition:opacity 200ms ease-out,transform 200ms ease-out}
.story-chips-arc{position:absolute;right:10px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:5px;z-index:20;transition:opacity 300ms ease-out}
.story-chip{display:inline-flex;align-items:center;background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:3px 8px;font-size:11.5px;font-weight:500;color:var(--ink);box-shadow:0 1px 4px rgba(0,0,0,.05)}

/* Beat 6 & 7 Chart layer */
.fig-chart-layer{width:100%;max-width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center}
.fig-chart-frame{width:100%;max-width:100%;background:var(--card);border:1px solid var(--rule);border-radius:3px;overflow:hidden}
.chart-svg{width:100%;height:auto;display:block}
.chart-point-group{transform-origin:center center}
.point-whisker{transform-origin:center center}
.chart-legend-mobile{display:none}
@media(max-width:899px){
  .chart-legend-desktop{display:none}
  .chart-legend-mobile{display:block}
}
.fig-cost-bars{width:100%;max-width:100%;margin-top:12px}
.cost-bar-row{display:grid;grid-template-columns:135px 1fr 50px;align-items:center;gap:8px;margin-bottom:5px;font-size:12px}
.cost-bar-label{font:500 12px/1 "IBM Plex Sans",sans-serif;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cost-bar-track{height:10px;background:var(--shade);border-radius:2px;overflow:hidden}
.cost-bar-fill{height:100%;border-radius:2px}
.cost-bar-val{text-align:right;font-family:"IBM Plex Mono",monospace;font-size:11.5px;font-variant-numeric:tabular-nums;color:var(--muted)}

/* Beat 8 Thinking */
.fig-thinking-card{width:100%;max-width:420px;background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:24px 20px;box-sizing:border-box}
.think-row{margin-bottom:16px}
.think-meta{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.think-title{font:500 14px/1 "IBM Plex Sans",sans-serif;color:var(--ink)}
.think-price{font:600 14px/1 "IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;color:var(--ink)}
.think-track{height:14px;background:var(--shade);border-radius:2px;overflow:hidden}
.think-fill-on{height:100%;background:var(--warn);border-radius:2px;display:flex}
.think-seg-tokens{height:100%;background:color-mix(in srgb,var(--warn) 70%,#000);border-radius:2px;display:flex;align-items:center;justify-content:center}
.think-seg-label{font:600 9px/1 "IBM Plex Sans",sans-serif;color:#fff;text-transform:uppercase;letter-spacing:.05em;padding:0 4px;white-space:nowrap;overflow:hidden}
.think-fill-off{height:100%;background:var(--good);border-radius:2px}
.fig-thinking-cap{font:italic 13px/1 "IBM Plex Sans",sans-serif;color:var(--muted);text-align:center;margin:12px 0 0}

/* Beat 9 Outro */
.fig-outro-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px}
.fig-outro-img{width:180px;height:auto;border:1px solid var(--rule);border-radius:3px;box-shadow:0 3px 12px rgba(0,0,0,.08)}
.fig-outro-line{font:500 13.5px/1.4 "IBM Plex Mono",monospace;color:var(--muted);text-align:center;margin:0}

/* Phone layout (<900px) */
@media(max-width:899px){
  #story{flex-direction:column}
  .story-figure-col{position:sticky;top:0;width:100%;height:46vh;flex:0 0 46vh;padding:8px 12px;background:var(--paper);border-bottom:1px solid var(--rule);z-index:25}
  .story-figure{height:100%;max-height:100%;max-width:100%}
  .fig-page-img{max-height:36vh}
  .story-steps-col{width:100%;flex:none;padding:0 20px}
  .step{min-height:85vh;padding:40px 0}
  .step-hero{min-height:54vh}
  .deck-card{width:44px}
  .story-chips-arc{right:4px;gap:3px}
  .story-chip{padding:2px 5px;font-size:10px}
  .fig-chart-frame{max-width:100%}
  .fig-cost-bars{margin-top:6px}
  .cost-bar-row{grid-template-columns:105px 1fr 44px;gap:6px;font-size:11px;margin-bottom:3px}
}

/* Fallbacks: no-JS and reduced motion */
html:not(.js) .fig-layer{position:static;opacity:1;pointer-events:auto;margin-bottom:24px}
html:not(.js) .story-figure{height:auto;max-height:none;display:block}
html:not(.js) .story-figure-col{position:static;height:auto}
html:not(.js) .fig-box-rect{stroke-dashoffset:0 !important}
html:not(.js) .fig-box-g{opacity:1 !important}
html:not(.js) .fig-box-tab{opacity:1 !important}
html:not(.js) .step{opacity:1 !important}
html:not(.js) .story-rail{display:none !important}
html:not(.js) .deck-card{transform:none !important;position:relative;display:inline-block;margin:4px}
html:not(.js) .story-deck-fan{width:100%;height:auto;display:flex;flex-wrap:wrap;gap:4px}
html:not(.js) .story-chips-arc{position:static;transform:none;display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
html:not(.js) .gold-check{opacity:1 !important}
html:not(.js) .chart-point-group{opacity:1 !important;transform:none !important}
html:not(.js) .point-whisker{transform:none !important}
html:not(.js) .point-cap{opacity:1 !important}
html:not(.js) .chart-legend-row{opacity:1 !important;transform:none !important}
html:not(.js) .cost-bar-fill{transform:none !important}
html:not(.js) .think-fill-on,.html:not(.js) .think-fill-off{transform:none !important}
html:not(.js) .defect-track{clip-path:none !important}

@media(prefers-reduced-motion:reduce){
  #story *,#story *::before,#story *::after{transition-duration:.001ms !important;animation-duration:.001ms !important}
  .step{opacity:1 !important;transition:none !important}
  .fig-box-rect{stroke-dashoffset:0 !important}
  .fig-box-g{opacity:1 !important}
  .fig-box-tab{opacity:1 !important}
  .deck-card{transform:none !important}
  .gold-check{opacity:1 !important;transform:none !important}
  .chart-point-group{opacity:1 !important;transform:none !important}
  .point-whisker{transform:none !important}
  .point-cap{opacity:1 !important}
  .chart-legend-row{opacity:1 !important;transform:none !important}
  .cost-bar-fill{transform:none !important}
  .think-fill-on,.think-fill-off{transform:none !important}
  .defect-track{clip-path:none !important}
}

/* story: visibility fixes after browser review */
.step-hero .step-content{position:relative;z-index:12}
@media(max-width:899px){#storyRail{display:none !important}}
@media(max-width:899px){
 .js .fig-box-g:not(.latest) .fig-box-tab{opacity:0 !important}
 .js .fig-box-g.latest .fig-box-tab-bg,.js .fig-box-g.latest .fig-box-tab-text{transform:scale(1.8);transform-box:fill-box;transform-origin:left bottom}
}
.js .fig-defects-strip{opacity:0;transition:opacity .4s ease-out}
.js .story-figure[data-beat="3"] .fig-defects-strip{opacity:1}
.js .fig-page-caption{opacity:0;transition:opacity .4s ease-out}
.js .story-figure[data-beat="1"] .fig-page-caption,.js .story-figure[data-beat="2"] .fig-page-caption,.js .story-figure[data-beat="3"] .fig-page-caption{opacity:1}
@media(prefers-reduced-motion:reduce){.js .fig-defects-strip,.js .fig-page-caption{opacity:1 !important}}
.js .fig-cost-bars{opacity:0;transition:opacity .4s ease-out}
.js .story-figure[data-beat="7"] .fig-cost-bars,.js .story-figure[data-beat="8"] .fig-cost-bars,.js .story-figure[data-beat="9"] .fig-cost-bars{opacity:1}
@media(prefers-reduced-motion:reduce){.js .fig-cost-bars{opacity:1 !important}}

/* the task */
.teach{display:grid;grid-template-columns:minmax(210px,300px) 1fr;gap:30px;align-items:start}
.teachimg{position:relative}
.teachimg img{width:100%;display:block;border:1px solid var(--rule);border-radius:3px}
.mk{position:absolute;left:-13px;transform:translateY(-50%)}
.mkn{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;
 border-radius:50%;background:var(--accent);color:#fff;font:600 12px/1 "IBM Plex Sans",sans-serif;
 flex:none}
.teach ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:17px}
.teach li{display:flex;gap:13px;align-items:flex-start}
.teach li b{font-weight:600;font-size:15px}
.teach li p{margin:2px 0 0;font-size:14.5px;color:var(--muted);max-width:58ch}
/* tables + bars */
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
thead th{font:600 11.5px/1.3 "IBM Plex Sans",sans-serif;text-transform:uppercase;
 letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--ink)}
tbody tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:1px}
.tag{display:inline-block;margin-left:6px;padding:1px 6px;border:1px solid var(--rule);
 border-radius:2px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.bars{display:flex;flex-direction:column;gap:8px}
.bar-row{display:grid;grid-template-columns:270px 1fr 84px;align-items:center;gap:14px}
.bar-label{font-size:13.5px}
.bar-track{background:var(--shade);border-radius:2px;height:14px;overflow:hidden}
.bar-fill{height:100%;border-radius:2px}
.bar-val{text-align:right;font-family:"IBM Plex Mono",monospace;font-size:13px;
 font-variant-numeric:tabular-nums}
.bar-row.win .bar-val{color:var(--accent);font-weight:500}
.chart{width:100%;height:auto}.axis{stroke:var(--muted);stroke-width:1}
.grid{stroke:var(--rule);stroke-width:1}
.tick,.axlab{fill:var(--muted);font-size:11px;font-family:"IBM Plex Mono",monospace}
.pt{fill:var(--ink);font-size:11.5px;font-family:"IBM Plex Mono",monospace}
.heat td{text-align:center;font-family:"IBM Plex Mono",monospace;font-size:11px;padding:5px 3px}
.heat thead th{font-size:10.5px;text-align:center;padding:5px 3px}
.rowlab{text-align:left;white-space:nowrap;font-size:12px;text-transform:none;letter-spacing:0;
 font-weight:400;border-bottom:1px solid var(--rule)}
.g3{background:color-mix(in srgb,var(--good) 30%,transparent)}
.g2{background:color-mix(in srgb,var(--warn) 26%,transparent)}
.g1{background:color-mix(in srgb,var(--accent) 22%,transparent)}
.g0{background:color-mix(in srgb,var(--accent) 40%,transparent)}
.na{color:var(--muted)}.scroll{overflow-x:auto}
.note{border-left:2px solid var(--rule);padding-left:18px;color:var(--muted);font-size:14.5px}
.note strong{color:var(--ink);font-weight:600}
/* The verdict block: the answer, before any of the workings. */
.vlede{font:300 20px/1.5 Spectral,Georgia,serif;color:var(--ink);margin:0 0 20px;
 border-left:3px solid var(--good);padding-left:20px}
.vlede.vfail{border-left-color:var(--accent)}
.vlede b{font-weight:500;color:var(--good)}.vlede.vfail b{color:var(--accent)}
table.verdict th[title]{cursor:help;border-bottom:1px dotted var(--rule)}
table.verdict td.num{font-variant-numeric:tabular-nums;cursor:help}
table.verdict tr.dim td{color:var(--muted)}
table.verdict tr.dim td:first-child{font-style:italic}
.cov{font-size:11px;color:var(--warn);margin-left:4px;font-variant-numeric:tabular-nums}
.gate{font-size:12px;max-width:230px}
.ok{color:var(--good);font-weight:600}
.bad{color:var(--accent)}
.hid{display:none !important}
/* side by side */
.bar2{display:flex;gap:13px;flex-wrap:wrap;align-items:end;padding:13px 0 14px;
 border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin-bottom:18px}
.fld{display:flex;flex-direction:column;gap:5px}
.fld span{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
select{font:inherit;font-size:14px;padding:6px 10px;background:var(--card);color:var(--ink);
 border:1px solid var(--rule);border-radius:3px;min-width:200px}
.btn{font:inherit;font-size:13px;padding:7px 13px;background:var(--card);color:var(--ink);
 border:1px solid var(--rule);border-radius:3px;cursor:pointer}
.btn:hover{border-color:var(--muted)}
.legend2{display:flex;gap:15px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);
 margin-left:auto;align-items:center}
.key{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:2px;border:1px solid var(--rule)}
.stage{display:grid;grid-template-columns:minmax(210px,300px) 1fr;gap:20px;align-items:start}
.pagecol{position:sticky;top:62px}
.pagecol img{width:100%;display:block;border:1px solid var(--rule);border-radius:3px}
.pagecap{font-size:12px;color:var(--muted);margin-top:7px;display:flex;justify-content:space-between;gap:8px}
.cmp{border:1px solid var(--rule);border-radius:3px;overflow:hidden;background:var(--card)}
.hdr,.row{display:grid;grid-template-columns:110px 1fr 1fr}
.hdr{border-bottom:1px solid var(--ink)}
.hdr div{padding:10px 12px;font:600 12.5px/1.3 "IBM Plex Sans",sans-serif;display:flex;
 align-items:center;gap:8px}
.hdr div+div,.rv{border-left:1px solid var(--rule)}
.row{border-bottom:1px solid var(--rule)}.row:last-child{border-bottom:0}
.row.differs{background:var(--diff)}
.rk{padding:9px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 color:var(--muted);white-space:nowrap}
.rv{padding:9px 12px;min-width:0;overflow-wrap:anywhere}
.swatch{width:9px;height:9px;border-radius:50%;flex:none}
.tagp{margin-left:auto;font:400 10px/1 sans-serif;text-transform:uppercase;letter-spacing:.06em;
 color:var(--muted);border:1px solid var(--rule);border-radius:2px;padding:3px 5px;white-space:nowrap}
.ar{font-family:"Noto Naskh Arabic",serif;direction:rtl;unicode-bidi:isolate;font-size:15.5px;line-height:1.95}
.bad{background:var(--red);border-radius:2px;padding:0 3px;box-shadow:inset 0 -2px 0 var(--accent)}
.mis{background:var(--yellow);border-radius:2px;padding:0 3px}
.tok-bad{background:var(--red);border-radius:2px;padding:0 2px;box-shadow:inset 0 -2px 0 var(--accent)}
.tok-gap{display:inline-block;background:var(--accent);color:#fff;border-radius:2px;
 font:600 10px/1.5 "IBM Plex Mono",monospace;padding:0 4px;vertical-align:2px;margin:0 2px}
.none{color:var(--muted);font-style:italic;font-size:12.5px}
.pickrow{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0 0}
.prompts td{font-size:13.5px;vertical-align:top}
.prompts tr.rec{background:color-mix(in srgb,var(--good) 12%,transparent)}
.rec-tag{border-color:var(--good);color:var(--good)}
.blk{margin:0 0 9px;padding-left:0}
.blk.head{border-left:3px solid var(--accent);padding-left:9px}
.btype{display:inline-block;font:600 9.5px/1.4 "IBM Plex Sans",sans-serif;text-transform:uppercase;
 letter-spacing:.07em;color:var(--accent);border:1px solid var(--accent);border-radius:2px;
 padding:0 4px;margin-right:6px;vertical-align:2px}
.anch{display:inline-block;font:600 9.5px/1.4 "IBM Plex Mono",monospace;color:var(--muted);
 border:1px solid var(--rule);border-radius:2px;padding:0 4px;margin-right:6px;vertical-align:2px}
.body p{margin:0 0 8px}.body p:last-child{margin:0}
.fn{margin:0 0 6px;font-size:14px}
.fnm{color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:11.5px;margin-left:6px}
.tally{font-size:12px;color:var(--muted);padding:9px 12px;border-top:1px solid var(--rule);
 display:flex;gap:17px;flex-wrap:wrap}
.tally b{color:var(--ink);font-weight:600;font-family:"IBM Plex Mono",monospace}
details{font-size:13px}
summary{cursor:pointer;color:var(--muted);font-size:12.5px;padding:2px 0}
summary:hover{color:var(--ink)}
pre.raw{font-family:"IBM Plex Mono",monospace;font-size:11.5px;line-height:1.55;
 background:var(--shade);border:1px solid var(--rule);border-radius:3px;padding:10px 11px;
 margin:8px 0 0;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;
 direction:ltr;text-align:left}
@media(max-width:900px){
 .teach,.stage{grid-template-columns:1fr}.pagecol{position:static;max-width:400px}
 .bar-row{grid-template-columns:1fr;gap:4px}.bar-val{text-align:left}
 h1{font-size:31px}.hdr,.row{grid-template-columns:86px 1fr 1fr}
 .mk{left:-11px}
}
</style>
__STORY__
<div class="wrap">

<h2>The data</h2>
<p class="sub">Everything the story summarised, in full.</p>

<div class="nav">
  <a href="#task">The task</a><a href="#verdict">The answer</a><a href="#results">Results</a><a href="#compare">Side by side</a><a href="#method">Method</a>
</div>

<section id="task">
<h2>The task</h2>
<p class="sub">One leaf, five different kinds of thing. A model can read every character correctly
and still return a page that is wrong, by putting them in the wrong bucket.</p>
<div class="card teach">
  <div class="teachimg"><img src="__TEACHIMG__" alt="an annotated page from the corpus">__MARKS__</div>
  <ol>__LEGEND__</ol>
</div>
<p class="note">The reason this matters downstream: whatever lands in <em>body</em> is what a
read-aloud reader speaks. A running head filed as body is read out on every page; a page number
filed as body is read out as a number in the middle of a sentence.</p>
</section>

<section id="verdict">
<h2>Which model reads this page correctly?</h2>
<p class="sub">Every model answering the same request, scored against a fixed reference that no
model in this table helped write.</p>
__VERDICT__
</section>

<section id="results">
<h2>Results</h2>
<div class="card scroll">__TABLE__</div>
<p class="note small"><strong>Prices.</strong> <span class="tag">measured</span> is real billing,
<span class="tag">list</span> the vendor&rsquo;s published rate, <span class="tag">proxy</span> a
comparable model&rsquo;s rate borrowed because none is published. Token counts are measured either
way. Gemini figures count candidate tokens only, not thinking tokens.</p>
<p class="note"><strong>This table is agreement, scored leave-one-out.</strong> Each arm is scored
against the agreement of the <em>others</em> over all 20 pages, so it finds outliers and cannot
rank a model. For that, see the answer at the top.</p>

<h3 style="margin-top:34px">Which model?</h3>
<p class="sub">Strictly these are model-plus-runner systems: the arms reached their answers by
different routes (direct API, agent CLI), so a few tenths of a point may be the runner. The
intervals at the top settle it.</p>
<div class="pickrow">
  <label class="fld"><span>Measure</span><select id="mcMetric"></select></label>
</div>
<div class="card" id="modelChart"></div>

<h3 style="margin-top:30px">Cost against task score</h3>
<p class="sub">Every model, priced per page, against its task score on gold. Subscription-routed
runs are priced at the vendor&rsquo;s published per-token rate on measured token volume; the six
that clear every gate are magnified in the inset.</p>
<div class="card">__SCATTER__</div>

<h3 style="margin-top:30px">Where each arm fails <span class="muted small">&mdash; per page</span></h3>
<p class="sub">Pick which kind of failure to look at. The four measures fail on <em>different</em>
pages, so any one of them alone is not &ldquo;where it fails&rdquo;.</p>
<div class="pickrow">
  <label class="fld"><span>Failure type</span><select id="heatMetric"></select></label>
</div>
<div class="card scroll" id="heatHost"></div>
</section>

<section id="compare">
<h2>Side by side</h2>
<p class="sub">One page, two readings, aligned field by field. <b>Red</b> disagrees with the verified
truth or stands alone against every other model. <b>Yellow</b> is text that is correct but filed in
the wrong place. A tinted row is one where the two models simply disagree.</p>
<div class="bar2">
  <label class="fld"><span>Page</span><select id="pg"></select></label>
  <label class="fld"><span>Left</span><select id="selA"></select></label>
  <label class="fld"><span>Right</span><select id="selB"></select></label>
  <label class="fld"><span>&nbsp;</span><button class="btn" id="swap" type="button">Swap</button></label>
  <div class="legend2">
    <span class="key"><span class="sw" style="background:var(--red)"></span>wrong</span>
    <span class="key"><span class="sw" style="background:var(--yellow)"></span>misplaced</span>
    <span class="key"><span class="sw" style="background:var(--diff)"></span>they disagree</span>
    <span class="key"><span class="tok-gap">3</span>words the others have, missing here</span>
  </div>
</div>
<div class="stage">
  <div class="pagecol"><img id="img" alt="the scanned page">
    <div class="pagecap"><span id="cap"></span><span id="vby"></span></div></div>
  <div class="cmp"><div class="hdr"><div>field</div><div id="ha"></div><div id="hb"></div></div>
    <div id="rows"></div><div class="tally" id="tally"></div></div>
</div>
</section>

<section id="method">
<h2>Method</h2>
<ul>
<li><strong>Same input everywhere.</strong> One 300&nbsp;DPI page image per call. There is no OCR
step and no text layer &mdash; the production pipeline is already a vision model, so this compares
like with like.</li>
<li><strong>One request.</strong> Every arm is asked for the same thing: one ordered sequence of
typed blocks with inline footnote anchors, plus the running head, page number and the notes with
their markers (<span class="mono">prompts/P2_blocks.txt</span>).</li>
<li><strong>Accuracy comes from gold, and only from gold.</strong> __NGOLD__ pages, picked on
printed features before any scoring, each read twice by a reader outside this field of arms, with
every disagreement settled against the image. Same reference for every arm; it does not move when
the field changes. Denominators are printed on every cell.</li>
<li><strong>Everything else is agreement, and says so.</strong> The 20-page figures compare an arm
to the other arms. They are good at finding an outlier and structurally incapable of ranking a
model, because the reference moves with the pool and a shared error passes unseen.</li>
<li><strong>The decision rule was written before the scores were read</strong> &mdash; gates, then a
weighted score over what the product depends on, then a bootstrap interval. Where two intervals
overlap, no winner is claimed.</li>
<li><strong>Cost is calibrated, not assumed.</strong> Production billed a measured $0.001881/page
over 468 calls. Characters-per-token differs by output shape &mdash; 1.97 for Arabic prose, 2.79
for JSON, the latter measured directly from the API's own token counts.</li>
<li><strong>Price provenance travels with every price:</strong> <span class="tag">measured</span>
is real billing, <span class="tag">list</span> the vendor&rsquo;s published rate,
<span class="tag">proxy</span> a rate borrowed from a comparable model because none is published.
Token volumes are measured for every arm either way; only the rate per token varies in how firmly
it is known, and a subscription-routed run is priced at list with that fact recorded.</li>
</ul>
<p class="note"><strong>What this still cannot tell you.</strong> Gold is a careful independent
reading, not a scholar's collation, so a misreading both readers shared would survive it. Each page
was read once per arm, so run-to-run variation inside a model is not in the band.</p>
</section>
</div>
<script id="d" type="application/json">__DATA__</script>
<script id="m" type="application/json">__META__</script>
<script id="pr" type="application/json">__PROMPTS__</script>
<script id="sm" type="application/json">__SUMMARY__</script>
<script>__STORYJS__</script>
<script>__APPJS__</script>
"""

if __name__ == "__main__":
    main()

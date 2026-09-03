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
            + f"<p class='note'><b>The rule, fixed before the scores were read.</b> An arm must "
            f"clear every gate ({gate_txt}) to be recommendable at all. Among those that do, the "
            f"ranking is a weighted score over what the product actually depends on — the prose "
            f"most, then note text and anchor placement, then order, heading position, furniture "
            f"and marker fidelity. Differences under {band*100:.0f} point are not evidence.</p>"
            f"<p class='note'><b>Measured on {len(gp)} pages ("
            + ", ".join(f"p{p}" for p in gp)
            + f"), against a reference that is not "
            f"another model's opinion.</b> Each page was read twice, independently, by a reader "
            f"outside this field of arms, and every disagreement was settled against the image. "
            f"Denominators are on every cell — hover it. This is the only part of this report that "
            f"is accuracy; everything below is agreement between arms, which describes how "
            f"conventional a reading is and cannot rank a model.</p>"
            + f"<p class='note'><b>What the band is, and what it is not.</b> It comes from resampling "
            f"these {len(gp)} pages, so it measures how much of a result depends on which pages "
            f"happen to be in the set. <b>It is not a confidence interval for the book.</b> The "
            f"pages were chosen on purpose, one per difficulty axis, so they are not a random "
            f"draw from anything and a bootstrap over them cannot be read as sampling the corpus. "
            f"Two further sources of uncertainty are missing entirely: each page was read once, "
            f"so run-to-run variation inside a model is absent, and the reference itself is a "
            f"careful reading rather than a collation. Separation claims use the <em>paired</em> "
            f"difference between two arms on the same pages, which cancels page difficulty; the "
            f"per-arm band is shown for stability, not for inference.</p>")


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

    teach = INS.thumb(ROOT / "pages" / f"p{TEACH_PAGE:03d}.webp", width=520)
    marks = "".join(
        f"<div class='mk' style='top:{y}%'><span class='mkn'>{i+1}</span></div>"
        for i, (y, _, _) in enumerate(CALLOUTS))
    legend = "".join(
        f"<li><span class='mkn'>{i+1}</span><div><b>{t}</b><p>{d}</p></div></li>"
        for i, (_, t, d) in enumerate(CALLOUTS))

    html = (TEMPLATE
            .replace("__TEACHIMG__", teach).replace("__MARKS__", marks).replace("__LEGEND__", legend)
            .replace("__TABLE__", "".join(tbl))
            .replace("__VERDICT__", verdict(arms, data.get("_meta", {})))

            .replace("__SCATTER__", "<img src='data:image/png;base64,"
                     + base64.b64encode((ROOT / "assets" / "accuracy-vs-cost.png").read_bytes()).decode()
                     + "' alt='task score against price per page, one point per model'"
                     " style='width:100%;height:auto;display:block'>")
            .replace("__NGOLD__", str(len(data.get("_meta", {}).get("gold_pages") or [])))
            .replace("__NARMS__", str(len(arms))).replace("__NPAGES__", str(len(pages)))
            .replace("__DATA__", json.dumps(idata, ensure_ascii=False))
            .replace("__META__", json.dumps(meta, ensure_ascii=False))
            .replace("__PROMPTS__", json.dumps(prompts, ensure_ascii=False))
            .replace("__SUMMARY__", json.dumps(summary, ensure_ascii=False))
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
<div class="wrap">

<p class="eyebrow">Benchmark &middot; __NARMS__ arms &middot; __NPAGES__ pages</p>
<h1>Reading the Apparatus</h1>
<p class="lede">Which vision model reads a scanned page of an Arabic scholarly book correctly,
and at what price? Every model here answered the same request and is scored against the same
fixed reference.</p>

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
<script>__APPJS__</script>
"""

if __name__ == "__main__":
    main()

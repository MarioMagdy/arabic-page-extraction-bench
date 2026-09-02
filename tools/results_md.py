"""Emit RESULTS.md from results.json — the written findings, generated so they cannot drift.

Every number in the document comes from the scored data. Re-run after adding an arm:

    python tools/score.py && python tools/results_md.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MIN_PAGES = 15          # below this an arm is reported as partial, never ranked


def pct(v, dp=1):
    return "—" if v is None else f"{v * 100:.{dp}f}%"


def main() -> None:
    data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    arms = data["arms"]
    cfg = yaml.safe_load((ROOT / "arms.yaml").read_text(encoding="utf-8"))
    declared = {a["id"]: a for a in cfg["arms"]}
    not_run = [a for a in cfg["arms"] if a["id"] not in arms]

    full = {k: a for k, a in arms.items() if a["summary"]["pages"] >= MIN_PAGES}
    partial = {k: a for k, a in arms.items() if a["summary"]["pages"] < MIN_PAGES}

    def by(metric, pool=None, best=max):
        pool = pool if pool is not None else full
        vals = [(k, a["summary"].get(metric)) for k, a in pool.items()
                if a["summary"].get(metric) is not None]
        return best(vals, key=lambda t: t[1]) if vals else (None, None)

    def row(k, a):
        s = a["summary"]
        cost = ("—" if declared.get(k, {}).get("pricing", {}).get("source") in ("plan", "local")
                else f"${s['cost_per_page_usd']:.5f}")
        return (f"| {a['label']} | {a['prompt']} | {s['pages']} | {pct(s.get('transcript_accuracy'), 2)} "
                f"| {pct(s.get('field_accuracy'), 0)} | {pct(s.get('footnote_exact_rate'), 0)} "
                f"| {pct(s.get('anchor_consistency'), 0)} | {s.get('output_failures', 0)} | {cost} |")

    L = []
    A = L.append
    A("# Results")
    A("")
    A(f"{len(arms)} arms scored across {len(data['_meta']['truth_pages'])} pages of a printed "
      "Arabic patristic edition. Generated from `results.json` — do not edit by hand.")
    A("")

    # ---- THE ANSWER --------------------------------------------------------
    # Accuracy against gold comes first and stands alone. Everything after it is agreement between
    # arms, which cannot rank a model and is labelled so throughout.
    meta = data.get("_meta", {})
    gpages = meta.get("gold_pages") or []
    if gpages:
        gates, band = meta["gates"], meta["noise_band"]
        # `derived_from` arms are excluded exactly as in the HTML report: the second-pass arm's
        # transcription IS arm K's, so listing it here would enter one reading twice.
        ranked = sorted(((k, a, a["gold"]) for k, a in arms.items()
                         if a.get("gold") and a["prompt"] == "P2" and not a.get("derived_from")),
                        key=lambda t: -(t[2].get("task_score") or 0))
        passing = [r for r in ranked if not r[2]["gate_failures"]]
        A("## The answer — which model performs the task")
        A("")
        A(f"Measured on **{len(gpages)} page{'s' if len(gpages)!=1 else ''}** "
          f"({', '.join('p%d' % p for p in gpages)}) against `truth/gold/`: a reading produced outside "
          "this field of arms, double-keyed and adjudicated against the page image. Same reference "
          "for every arm, and it does not move when the field changes. **This is the only section "
          "of this document that is accuracy.**")
        A("")
        if not passing:
            A("**No model clears every gate.** None of them performs this task correctly end to "
              "end on the evaluation set; the table says which part each one drops.")
        else:
            sys.path.insert(0, str(ROOT / "tools"))
            import gold as GOLD
            top = passing[0]
            tied = [r for r in passing[1:] if not GOLD.separated(top[2], r[2])]
            below = [r for r in passing[1:] if GOLD.separated(top[2], r[2])]
            short = [top] + tied
            nm = top[1]["label"].split(" · ")[0]
            if tied:
                names = ", ".join(r[1]["label"].split(" · ")[0] for r in tied)
                A(f"**{nm}** has the highest score, and on {len(gpages)} pages this evidence "
                  f"**cannot distinguish it from {names}**. Any of those performs the task; the "
                  "ordering between them is not a result, so choose on cost and on the specific "
                  "failure each one still has.")
                clean = [r for r in below
                         if all(GOLD.separated(s[2], r[2]) for s in short)]
                murky = [r for r in below if r not in clean]
                if clean:
                    A("")
                    A("All of them are separated from **"
                      + ", ".join(r[1]["label"].split(" · ")[0] for r in clean)
                      + "** and everything below.")
                if murky:
                    A("")
                    A("**A limit worth stating.** "
                      + ", ".join(r[1]["label"].split(" · ")[0] for r in murky)
                      + " score lower than all of them, but the gap does not survive removing a "
                        "single evaluation page for every member of the shortlist. On this evidence "
                        "they are behind, not beaten.")
            else:
                A(f"**{nm}** is the recommendation — the only gate-clearing arm whose lead "
                  "survives both the paired difference test and the removal of any single page.")
        A("")
        A("| model | task score | 90% CI | body | heading pos | notes | note text | anchors "
          "| anchor pos | fields | markers | gate |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for k, a, g in ranked:
            s = g["scores"]
            def gv(key):
                return pct(s.get(key, {}).get("v"), 1)
            cov = g.get("weight_covered") or 0
            ts = pct(g.get("task_score"), 1) + ("" if cov > 0.98 else f" _({cov*100:.0f}% cov)_")
            gate = "clears" if not g["gate_failures"] else "; ".join(g["gate_failures"])
            ci = g.get("ci")
            ts += " | " + ("—" if not ci else f"{ci[0]*100:.1f}–{ci[1]*100:.1f}")
            A(f"| {a['label'].split(' · ')[0]} | {ts} | {gv('body_accuracy')} "
              f"| {gv('heading_placement')} | {gv('footnote_f1')} | {gv('footnote_text')} "
              f"| {gv('anchor_f1')} | {gv('anchor_placement')} | {gv('fields')} "
              f"| {gv('marker_exact')} | {gate} |")
        A("")
        A("**The rule was fixed before the scores were read.** Gates: "
          + ", ".join(f"`{k}` ≥ {v}" if isinstance(v, float)
                      else f"all {len(gpages)} evaluation pages answered"
                      for k, v in gates.items())
          + ". Among arms that clear them, the ranking is a weighted score over what the product "
            "depends on — prose 35%, note text 15%, anchor placement 15%, block order 10%, heading "
            "position 10%, fields 10%, marker fidelity 5%.")
        A("")
        A("**What the gold scoring added that was missing.** Heading *position*, footnote *text*, "
          "marker *glyph* and anchor *linkage* were all previously unscored — a model could ace "
          "every published P2 metric while returning notes with the wrong text and anchors that "
          "link from the wrong paragraph. Anchor consistency, in particular, used to be "
          "self-consistency: a model that invented a note and an anchor for it scored 1.0. It is "
          "now scored against gold, where an invented anchor is a false positive.")
        A("")

    A("## Agreement between arms — not accuracy, and it cannot rank a model")
    A("")
    A("Everything below compares an arm to the *other arms*, over all 20 pages. It answers \"how "
      "conventional is this reading?\", which is useful for spotting an outlier and useless for "
      "picking a winner: the reference moves when the field changes, correlated arms can define "
      "it, and an error every model makes passes unseen. Read it as diagnosis, not as a score.")
    A("")
    A("| arm | prompt | pages | body agreement | fields | footnotes | anchor self-consistency "
      "| fails | $/page |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for k, a in sorted(full.items(), key=lambda kv: -(kv[1]["summary"].get("transcript_accuracy") or 0)):
        A(row(k, a))
    if partial:
        A("")
        A("**Partial runs** — reported, never ranked:")
        A("")
        A("| arm | prompt | pages | transcript | fields | footnotes | anchors | fails | $/page |")
        A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for k, a in sorted(partial.items(), key=lambda kv: -kv[1]["summary"]["pages"]):
            A(row(k, a))
    if not_run:
        A("")
        A("**Declared but not run:** " + ", ".join(a["label"] for a in not_run) +
          ". See `arms.yaml` for why each is empty — every one records its reason rather than "
          "being quietly deleted.")

    # ---- the prompt-family comparisons, computed rather than asserted ------------------------
    A("")
    A("## What each prompt bought")
    A("")
    fams = {}
    for k, a in full.items():
        fams.setdefault(a["prompt"], []).append((k, a))
    for p in sorted(fams):
        n = len(fams[p])
        t = [a["summary"]["transcript_accuracy"] for _, a in fams[p]
             if a["summary"].get("transcript_accuracy") is not None]
        f = [a["summary"]["footnote_exact_rate"] for _, a in fams[p]
             if a["summary"].get("footnote_exact_rate") is not None]
        A(f"- **{p}** — {n} arm(s). Mean transcript accuracy "
          f"{pct(sum(t)/len(t), 2) if t else '—'}, mean footnote-exact "
          f"{pct(sum(f)/len(f), 0) if f else '—'}.")

    # same model across prompts is the only clean read on what a prompt costs
    A("")
    A("### Same model, different prompt")
    A("")
    by_model = {}
    for k, a in arms.items():
        by_model.setdefault(a["model"], []).append((k, a))
    shown = False
    for model, entries in sorted(by_model.items()):
        prompts = {a["prompt"]: a for _, a in entries if a["summary"]["pages"] >= MIN_PAGES}
        if len(prompts) < 2:
            continue
        shown = True
        A(f"**{model}**")
        A("")
        A("| prompt | transcript | footnotes | anchors | pages |")
        A("|---|---:|---:|---:|---:|")
        for p in sorted(prompts):
            s = prompts[p]["summary"]
            A(f"| {p} | {pct(s.get('transcript_accuracy'), 2)} | {pct(s.get('footnote_exact_rate'), 0)} "
              f"| {pct(s.get('anchor_consistency'), 0)} | {s['pages']} |")
        A("")
    if not shown:
        A("_Not enough complete arms sharing a model to compare prompts directly yet._")
        A("")

    k, v = by("transcript_accuracy")
    if k:
        A(f"**Best transcript accuracy:** {arms[k]['label']} at {pct(v, 2)}.")
    priced = {k2: a for k2, a in full.items()
              if declared.get(k2, {}).get("pricing", {}).get("source") not in ("plan", "local")}
    k2, v2 = by("cost_per_page_usd", pool=priced, best=min)
    if k2:
        A(f"**Cheapest priced arm:** {arms[k2]['label']} at ${v2:.5f} per page.")
    A("")
    A("## How to read these numbers")
    A("")
    A("- **transcript** — the prose, scored against the medoid reading of the *other* arms. There is")
    A("  no gold transcription of this corpus, so this measures agreement, not truth: a mistake every")
    A("  model makes would pass unnoticed. **Pages with under 200 characters of reference body are")
    A("  not scored** — CER divides by the reference length, so on a half-title page a handful of")
    A("  characters produced rates above 6.0 and one page dominated every average. Mis-filing title")
    A("  text as body is a real error, but `fields` and `body purity` are the instruments for it.")
    A("- **fields** — running head, page title, section heading, printed page number, printer mark,")
    A("  each in its own place. Leave-one-out against the other arms; three hand-read pages are fixed.")
    A("- **footnotes** — share of pages with exactly the right number of notes. The flat prompt gives")
    A("  the model one `[FOOTNOTE]` container, so an apparatus of twelve notes comes back as one.")
    A("- **anchor self-consistency** — do the inline footnote references in the text account for the")
    A("  notes below the rule? This is self-consistency, not correctness: a model that invents a note")
    A("  and an anchor for it agrees with itself perfectly. Anchors are scored for real against gold")
    A("  in the section above; this column is a diagnostic only. Block-schema arms only.")
    A("- **fails** — pages where the model returned nothing usable. Counted, never averaged away.")
    A("- **$/page** — measured token counts where the API reported them, otherwise derived from")
    A("  measured output characters through a calibrated constant. Arms on a flat-rate plan show")
    A("  `—`: no per-page price exists to quote, which is not the same as free.")
    (ROOT / "RESULTS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"RESULTS.md written — {len(full)} ranked, {len(partial)} partial, {len(not_run)} not run")


if __name__ == "__main__":
    main()

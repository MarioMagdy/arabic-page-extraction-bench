"""Score every arm declared in arms.yaml and emit results.json.

Adding a model requires NO change to this file: add a block to arms.yaml and drop its outputs in
runs/<id>/pNNN.json. Arms with no run directory are skipped and reported as pending.

    python tools/score.py --adjudicate   # build the disagreement pack for truth/
    python tools/score.py                # score against truth/ -> results.json
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import metrics as M  # noqa: E402
import gold as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS, TRUTH = ROOT / "runs", ROOT / "truth"

# Minimum reference length for a transcript score. Below this the rate is dominated by its own
# denominator rather than by the reading. The corpus splits cleanly: real text pages carry
# 350-1400 characters of body, half-title pages carry none.
MIN_REF_CHARS = 200


def load_registry() -> tuple[dict, list[dict]]:
    cfg = yaml.safe_load((ROOT / "arms.yaml").read_text(encoding="utf-8"))
    return cfg["cost_model"], cfg["arms"]


_USAGE: dict[str, dict[int, dict]] = {}


def measured_usage(arm_id: str) -> dict[int, dict]:
    """Real token counts, when the arm was run through the API and the response reported them.

    A measured token count beats any characters-per-token estimate, so these are used in preference
    to the calibrated model and the arm is labelled accordingly in the report.
    """
    if arm_id not in _USAGE:
        f = RUNS / arm_id / "_usage.json"
        try:
            _USAGE[arm_id] = {u["page"]: u for u in json.loads(f.read_text(encoding="utf-8"))}
        except Exception:
            _USAGE[arm_id] = {}
    return _USAGE[arm_id]


def page_cost(arm: dict, cm: dict, out_chars: int, usage: dict | None = None) -> float:
    """USD per page. Tokens are derived from measured output characters via the calibrated
    ratio; the price row's `source` travels with the number so a proxy can never read as measured."""
    pr = arm["pricing"]
    if pr.get("source") in ("local", "plan"):
        return 0.0   # flat-rate or self-hosted: no per-page price exists to quote
    if usage and usage.get("prompt_tokens") and usage.get("output_tokens"):
        in_tok, out_tok = usage["prompt_tokens"], usage["output_tokens"]   # measured
    else:
        in_tok = cm["input_tokens"][arm["prompt"]]
        out_tok = out_chars / cm["chars_per_output_token"][arm["prompt"]]
    return (in_tok * pr["input"] + out_tok * pr["output"]) / 1e6


def load_all(arms: list[dict]) -> dict[str, dict[int, dict]]:
    out: dict[str, dict[int, dict]] = {}
    for a in arms:
        d = RUNS / a["id"]
        if not d.exists():
            continue
        recs = {}
        for f in sorted(d.glob("p*.json")):
            try:
                recs[int(f.stem[1:])] = M.load_arm(f)
            except Exception as e:  # a malformed output is a RESULT, not a crash
                recs[int(f.stem[1:])] = {"_error": f"{type(e).__name__}: {e}",
                                         "body": [], "footnotes": [], "_raw": ""}
        if recs:
            out[a["id"]] = recs
    return out


FIELDS = ("runningHeader", "pageTitle", "sectionHeading",
          "printedPageNumber", "printerMark")


def adjudicate(all_arms: dict) -> None:
    pages = sorted({p for a in all_arms.values() for p in a})
    pack, need = {}, 0
    for pg in pages:
        row = {}
        for field in FIELDS:
            answers = {arm: recs[pg].get(field) for arm, recs in all_arms.items() if pg in recs}
            norm = {M.normalize_ar(str(M._flat(v))) if v not in (None, [], "") else None
                    for v in answers.values()}
            row[field] = {"answers": answers, "unanimous": len(norm) == 1,
                          "consensus": next(iter(answers.values())) if len(norm) == 1 else None}
            need += 0 if len(norm) == 1 else 1
        counts = {arm: len(recs[pg].get("footnotes") or [])
                  for arm, recs in all_arms.items() if pg in recs}
        u = len(set(counts.values())) == 1
        row["footnoteCount"] = {"answers": counts, "unanimous": u,
                                "consensus": next(iter(counts.values())) if u else None}
        need += 0 if u else 1
        pack[pg] = row
    (ROOT / "adjudication.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    tot = sum(len(v) for v in pack.values())
    print(f"{len(pack)} pages · {tot} field-slots · {tot-need} unanimous · {need} need a human")


def summarise(pp: list[dict]) -> dict:
    def mean(k):
        vals = [x[k] for x in pp if x.get(k) is not None]
        return round(statistics.mean(vals), 4) if vals else None
    tp = sum(1 for x in pp for v in x["fields"].values() if v is True)
    tot = sum(1 for x in pp for v in x["fields"].values() if v is not None)
    return {
        "pages": len(pp),
        "cer_raw": mean("cer_raw"), "cer_norm": mean("cer_norm"), "wer_norm": mean("wer_norm"),
        "field_accuracy": round(tp / tot, 4) if tot else None,
        "field_slots_scored": tot,
        "footnote_err_mean": mean("footnote_err"),
        "footnote_exact_rate": (round(sum(1 for x in pp if x["footnote_err"] == 0)
                                      / len([x for x in pp if x["footnote_err"] is not None]), 4)
                                if any(x["footnote_err"] is not None for x in pp) else None),
        "footnote_pages_scored": len([x for x in pp if x["footnote_err"] is not None]),
        "body_purity": mean("body_purity"),
        "body_cer": mean("body_cer"),
        "body_wer": mean("body_wer"),
        "transcript_accuracy": (round(1 - mean("body_cer"), 4)
                                if mean("body_cer") is not None else None),
        "body_pages_scored": len([x for x in pp if x.get("body_cer") is not None]),
        "anchor_consistency": mean("anchor_consistency"),
        "anchor_pages_scored": len([x for x in pp if x.get("anchor_consistency") is not None]),
        "references_total": (sum(x["n_references"] for x in pp if x.get("n_references"))
                             if any(x.get("n_references") for x in pp) else None),
        "output_failures": sum(1 for x in pp if x.get("output_failed")),
        "cost_per_page_usd": round(statistics.mean(x["cost_usd"] for x in pp), 6),
    }


def arm_filter(argv) -> set[str] | None:
    """--arms A,B  restricts the run to those arm ids (prefix match is enough to type less)."""
    for i, a in enumerate(argv):
        if a == "--arms" and i + 1 < len(argv):
            return {x.strip() for x in argv[i + 1].split(",") if x.strip()}
        if a.startswith("--arms="):
            return {x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()}
    return None


def main() -> None:
    cm, arms = load_registry()
    want = arm_filter(sys.argv)
    # IMPORTANT: --arms narrows what is REPORTED, never what is used as evidence. Ground truth here
    # is adjudicated from agreement across the field, and the transcript reference is the medoid of
    # the other arms — so shrinking the pool would silently change every score. Load everything,
    # report a subset.
    all_arms = load_all(arms)
    if want:
        keep = {a["id"] for a in arms
                if a["id"] in want or any(a["id"].startswith(w) for w in want)}
        if not keep:
            sys.exit("--arms matched no arm in arms.yaml")
        arms = [a for a in arms if a["id"] in keep]
    else:
        keep = None
    by_id = {a["id"]: a for a in arms}
    for a in arms:
        n = len(all_arms.get(a["id"], {}))
        print(f"{a['id']:18s} {n:2d} pages   {a['label']}" + ("" if n else "   [pending]"))
    if "--adjudicate" in sys.argv:
        adjudicate(all_arms)
        return

    truth = {int(f.stem[1:]): json.loads(f.read_text(encoding="utf-8"))
             for f in sorted(TRUTH.glob("p*.json"))}
    if not truth:
        print("\nno truth/ yet — run with --adjudicate first")
        return

    # ---- LEAVE-ONE-OUT ------------------------------------------------------
    # Most of truth/ is ADJUDICATED FROM ARM AGREEMENT, so scoring an arm against a rubric it
    # helped write is circular — the arms in the majority score 100% by construction. For each
    # arm we therefore rebuild the adjudicated fields from the OTHER arms only. Pages marked
    # `verifiedBy: human-*` were established from the page images before any arm ran and are held
    # fixed for everyone.
    def truth_for(arm_id: str) -> dict:
        out = {}
        for pg, t in truth.items():
            if str(t.get("verifiedBy", "")).startswith("human"):
                out[pg] = t
                continue
            others = {a: r for a, r in all_arms.items() if a != arm_id and pg in r}
            if len(others) < 2:
                continue  # not enough independent voices to adjudicate this page
            t2 = {"page": pg, "verifiedBy": f"adjudicated-without-{arm_id}"}
            for f in FIELDS:
                vals = [r[pg].get(f) for r in others.values()]
                norm = {M.normalize_ar(str(M._flat(v))) if v not in (None, [], "") else None
                        for v in vals}
                if len(norm) == 1:
                    t2[f] = vals[0]           # unanimous among the others
            counts = [len(r[pg].get("footnotes") or []) for r in others.values()]
            if len(set(counts)) == 1:
                t2["footnoteCount"] = counts[0]
            out[pg] = t2
        return out

    results = {"_meta": {"cost_model": cm, "truth_pages": sorted(truth),
                         "gold_pages": G.eval_pages(),
                         "gates": G.GATES, "weights": G.WEIGHTS,
                         "noise_band": G.NOISE_BAND}, "arms": {}}
    for arm_id, recs in all_arms.items():
        if keep is not None and arm_id not in keep:
            continue
        a = by_id[arm_id]
        pp = []
        for pg, t in truth_for(arm_id).items():
            if pg not in recs:
                continue
            r = recs[pg]
            ref = t.get("referenceText") or ""
            hyp = M.flatten(r)
            body = "\n".join(str(x) for x in (r.get("body") or []))
            contaminants = [c for c in ([t.get("runningHeader"), t.get("printedPageNumber"),
                                         t.get("printerMark")] + (t.get("footnoteTexts") or []))
                            if c]
            fc = t.get("footnoteCount")
            # TRANSCRIPT ACCURACY. The reference is the medoid body among the OTHER arms — the
            # reading the rest of the field agrees with most — so an arm is never scored against
            # itself. Reported as agreement, not truth: it would flatter a mistake every model
            # makes, and that limit is stated in the report.
            others = [M.body_text(r2[pg]) for a2, r2 in all_arms.items()
                      if a2 != arm_id and pg in r2 and (r2[pg].get("body") or [])
                      and not r2[pg].get("_json_parse_failed")]
            mine_body = M.body_text(r)
            failed = bool(r.get("_json_parse_failed")) or bool(r.get("_error"))
            if failed:
                body_cer = body_wer = None
            elif len(others) >= 3 and mine_body.strip():
                ref_body = M.medoid(others)
                ref_n = M.normalize_ar(ref_body)
                # CER is edit distance OVER THE REFERENCE LENGTH, so a near-empty reference makes it
                # explode and unbounded: p23 and p36 are half-title pages with essentially no body,
                # and a handful of characters there produced CER 6.6 — one page dominating every
                # arm's mean. A rate computed over a few characters is not a measurement, so pages
                # with too little reference text are not scored at all.
                if len(ref_n) < MIN_REF_CHARS:
                    body_cer = body_wer = None
                else:
                    body_cer = M.cer(ref_n, M.normalize_ar(mine_body))
                    body_wer = M.wer(ref_n, M.normalize_ar(mine_body))
            else:
                body_cer = body_wer = None
            pp.append({
                "page": pg,
                # None, never 0.0: no truth file carries a gold transcription yet, and a 0.000
                # CER would read as PERFECT where it actually means NOT MEASURED. The report
                # prints "—" for these and says why.
                "cer_raw": M.cer(ref, hyp) if ref else None,
                "cer_norm": M.cer(M.normalize_ar(ref), M.normalize_ar(hyp)) if ref else None,
                "wer_norm": M.wer(M.normalize_ar(ref), M.normalize_ar(hyp)) if ref else None,
                # A field the truth file omits is genuinely ambiguous on that page and is NOT
                # scored — better an honest gap than a coin-flip baked into the result.
                "fields": {f: (M.field_match(r.get(f), t[f], f) if f in t else None) for f in FIELDS},
                "footnote_err": (abs(len(r.get("footnotes") or []) - fc) if fc is not None else None),
                "body_purity": M.body_purity(body, contaminants),
                "anchor_consistency": M.anchor_consistency(r, t.get("footnoteCount")),
                "n_references": (len(r.get("_references")) if "_references" in r else None),
                "body_cer": body_cer,
                "body_wer": body_wer,
                "output_failed": failed,
                "cost_usd": page_cost(a, cm, len(r.get("_raw") or hyp),
                                      measured_usage(arm_id).get(pg)),
                # pages whose truth came from the IMAGES, before any arm ran — the unbiased subset
                "_hand": str(t.get("verifiedBy", "")).startswith("human"),
            })
        hand = [x for x in pp if x.get("_hand")]
        # GOLD. Separate from everything above, and the only part of results.json that is accuracy:
        # a fixed reference, the same eight pages for every arm, denominators printed.
        gd = G.score_arm(recs) if G.eval_pages() else None
        if gd:
            gd["task_score"], gd["weight_covered"] = G.task_score(gd["scores"])
            gd["gate_failures"] = G.gate_failures(gd)
            gd["ci"] = G.bootstrap_ci(gd["per_page"])
        if pp:
            results["arms"][arm_id] = {"label": a["label"], "model": a["model"],
                                       "hand_verified": summarise(hand) if hand else None,
                                       "prompt": a["prompt"], "role": a["role"],
                                       "price_source": a["pricing"].get("source"),
                                       "tokens_measured": bool(measured_usage(arm_id)),
                                       "control": bool(a.get("control")),
                                       "derived_from": a.get("derived_from"),
                                       "gold": gd,
                                       "pages": pp, "summary": summarise(pp)}
            # An arm that makes MORE THAN ONE call per page cannot be priced from the output the
            # scorer can see — that output is only the last call. The addend carries the rest, or a
            # two-call pipeline is published at a one-call price and reads as free.
            add = a.get("cost_addend_usd")
            if add:
                s = results["arms"][arm_id]["summary"]
                s["cost_per_page_usd"] = round((s.get("cost_per_page_usd") or 0) + add, 6)
                s["cost_addend_usd"] = add
                s["cost_addend_source"] = a.get("cost_addend_source", "estimated")
    (ROOT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print()
    for k, v in results["arms"].items():
        print(f"{k:18s} {json.dumps(v['summary'])}")


if __name__ == "__main__":
    main()

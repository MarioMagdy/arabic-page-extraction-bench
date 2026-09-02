"""Measure the REAL structured OCR call: cost per page and accuracy vs gold.

Why this exists: the benchmark's cost column was computed from a rate table ~10x below
Google's published rates and never counted thinking tokens, so it cannot decide the model.
This runs the actual production call path (same prompt, same schema, same cost accounting)
on the eight adjudicated gold pages, for each candidate configuration, and reports MEASURED
tokens and dollars alongside accuracy against the gold reading.

Safety:
  * `src.config.CONFIG_PATH` is repointed at a local copy BEFORE any config load, so the
    repo's own config.yaml is never edited and the inventory backend is a local SQLite file.
    Production Turso is never opened, read or written.
  * Every call goes through the normal paid-call wrapper, so each one lands in the local
    llm_calls ledger and the totals below are the ledger's own numbers, not a re-derivation.

Usage:  python measure.py [--configs 2.5,3.8,3.8-nothink] [--pages 015,024,...]
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import time

RUN_DIR = pathlib.Path(__file__).resolve().parent
WT = RUN_DIR.parent.parent / "_wt" / "PAL-structured-m1"
BENCH = RUN_DIR.parent.parent.parent / "arabic-page-extraction-bench"
OUT = RUN_DIR / "measurement"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(WT))

# --- repoint config BEFORE anything loads it -------------------------------
import src.config as _cfgmod  # noqa: E402

_local_cfg = OUT / "measure_config.yaml"
if not _local_cfg.exists():
    text = (WT / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("inventory_db: turso", "inventory_db: local", 1)
    text = text.replace("inventory_db: data/inventory.db",
                        f"inventory_db: {(OUT / 'ledger.db').as_posix()}", 1)
    _local_cfg.write_text(text, encoding="utf-8")
_cfgmod.CONFIG_PATH = _local_cfg
if hasattr(_cfgmod.load_config, "cache_clear"):
    _cfgmod.load_config.cache_clear()

cfg = _cfgmod.load_config()
assert cfg.section("backends")["inventory_db"] == "local", "refusing to run against Turso"

from PIL import Image  # noqa: E402

from src.stage1_inventory.db import connect  # noqa: E402
from src.stage1_inventory.schema import SCHEMA_SQL  # noqa: E402
from src.stage3_ocr.engines.gemini import GeminiOcrEngine  # noqa: E402
from src.stage3_ocr.structured import PROMPT_VERSION  # noqa: E402

sys.path.insert(0, str(BENCH / "tools"))
from metrics import cer, normalize_ar  # noqa: E402

GOLD_PAGES = ["015", "024", "025", "030", "036", "039", "052", "093"]
CONFIGS = {
    "2.5":         ("gemini-2.5-flash", None),
    "3.8":         ("gemini-3.8-flash", None),
    "3.8-nothink": ("gemini-3.8-flash", "off"),
}


def png_bytes(page: str) -> bytes:
    with Image.open(BENCH / "pages" / f"p{page}.webp") as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        return buf.getvalue()


def gold(page: str) -> dict:
    return json.loads((BENCH / "truth" / "gold" / f"p{page}.json").read_text(encoding="utf-8"))


def body_of(blocks: list[dict]) -> str:
    return " ".join(b.get("text", "") for b in blocks)


def score(page: str, ex: dict) -> dict:
    g = gold(page)
    gb, ab = g.get("blocks") or [], ex.get("blocks") or []
    gn, an = g.get("footnotes") or [], ex.get("footnotes") or []
    body_cer = cer(normalize_ar(body_of(gb)), normalize_ar(body_of(ab)))
    gh = [b["text"] for b in gb if b.get("type") in ("heading", "pageTitle")]
    ah = [b["text"] for b in ab if b.get("type") in ("heading", "pageTitle")]
    return {
        "blocks_gold": len(gb), "blocks_got": len(ab),
        "notes_gold": len(gn), "notes_got": len(an),
        "body_accuracy": round(100 * (1 - body_cer), 2),
        "headings_gold": len(gh), "headings_got": len(ah),
        "header_ok": (ex.get("runningHeader") or None) == (g.get("runningHeader") or None),
        "pageno_ok": (ex.get("printedPageNumber") or None) == (g.get("printedPageNumber") or None),
    }


def ledger_total(since_id: int) -> tuple[int, float, int]:
    with connect() as c:
        r = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(cost_usd),0), COALESCE(SUM(output_tokens),0)"
            " FROM llm_calls WHERE id > ? AND stage='ocr'", (since_id,)).fetchone()
    return int(r[0]), float(r[1]), int(r[2])


def max_id() -> int:
    with connect() as c:
        try:
            r = c.execute("SELECT COALESCE(MAX(id),0) FROM llm_calls").fetchone()
            return int(r[0])
        except Exception:
            return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="2.5,3.8,3.8-nothink")
    ap.add_argument("--pages", default=",".join(GOLD_PAGES))
    args = ap.parse_args()

    with connect() as c:
        c.executescript(SCHEMA_SQL)
        c.commit()

    pages = [p.strip() for p in args.pages.split(",") if p.strip()]
    results: dict[str, dict] = {}

    for key in [k.strip() for k in args.configs.split(",") if k.strip()]:
        model, thinking = CONFIGS[key]
        engine = GeminiOcrEngine(model=model, thinking=thinking)
        start_id = max_id()
        rows, failures = [], []
        print(f"\n=== {key}  model={model} thinking={thinking or 'default'} "
              f"prompt={PROMPT_VERSION} ===", flush=True)
        for p in pages:
            t0 = time.monotonic()
            try:
                res = engine.ocr_page(png_bytes(p), page_num=int(p), note=f"measure p{p}")
                s = score(p, res.extraction)
                u = res.usage or {}
                rows.append({"page": p, **s, **{k: u.get(k) for k in
                            ("inputTokens", "outputTokens", "thoughtsTokens", "costUsd")},
                            "ms": int((time.monotonic() - t0) * 1000)})
                print(f"  p{p}: body={s['body_accuracy']:.2f}%  blocks={s['blocks_got']}/{s['blocks_gold']}"
                      f"  notes={s['notes_got']}/{s['notes_gold']}  in={u.get('inputTokens')}"
                      f"  out={u.get('outputTokens')}  think={u.get('thoughtsTokens')}"
                      f"  ${u.get('costUsd'):.6f}", flush=True)
                (OUT / f"{key}_p{p}.json").write_text(
                    json.dumps(res.extraction, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as e:  # a failure IS a result
                failures.append({"page": p, "error": f"{type(e).__name__}: {e}"[:200]})
                print(f"  p{p}: FAILED {type(e).__name__}: {str(e)[:120]}", flush=True)
        n, spend, out_tok = ledger_total(start_id)
        results[key] = {"model": model, "thinking": thinking, "rows": rows,
                        "failures": failures, "ledger_calls": n,
                        "ledger_cost_usd": round(spend, 6), "ledger_output_tokens": out_tok}

    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    print("\n" + "=" * 92)
    print(f"{'config':14s} {'pages':>5s} {'body%':>7s} {'blocks':>7s} {'notes':>7s} "
          f"{'in':>7s} {'out':>7s} {'think':>7s} {'$/page':>9s} {'461pp':>8s}")
    print("-" * 92)
    for key, r in results.items():
        rows = r["rows"]
        if not rows:
            print(f"{key:14s}  no successful pages ({len(r['failures'])} failures)")
            continue
        n = len(rows)
        avg = lambda f: sum(x[f] or 0 for x in rows) / n  # noqa: E731
        blocks_ok = sum(1 for x in rows if x["blocks_got"] == x["blocks_gold"])
        notes_ok = sum(1 for x in rows if x["notes_got"] == x["notes_gold"])
        per_page = r["ledger_cost_usd"] / n
        print(f"{key:14s} {n:5d} {avg('body_accuracy'):7.2f} {blocks_ok:4d}/{n:<2d} "
              f"{notes_ok:4d}/{n:<2d} {avg('inputTokens'):7.0f} {avg('outputTokens'):7.0f} "
              f"{avg('thoughtsTokens'):7.0f} {per_page:9.6f} {per_page*461:8.2f}")
    print("=" * 92)
    total = sum(r["ledger_cost_usd"] for r in results.values())
    calls = sum(r["ledger_calls"] for r in results.values())
    print(f"TOTAL SPENT (local ledger): ${total:.4f} across {calls} calls")
    print(f"Artifacts: {OUT}")
    print("\nNOTE: page images are the benchmark's 300 DPI renders, not Reli's 150 DPI ingest")
    print("render, so absolute input tokens run higher than production. The model-vs-model")
    print("comparison is apples-to-apples; treat $/page as an upper bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

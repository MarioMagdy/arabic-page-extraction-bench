"""Run one arm through the Google API directly.

Unlike the CLI-driven arms, this path returns `usageMetadata`, so the cost for arms run here is
MEASURED from real token counts rather than derived from the calibrated characters-per-token
constant. That also makes this the arm that validates the constant.

    python tools/run_gemini_api.py --model gemini-3.7-flash --prompt P2 --arm L_37flash_P2
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["003", "008", "009", "012", "015", "017", "023", "024", "025", "028",
         "030", "036", "039", "045", "048", "050", "052", "093", "095", "097"]


def get_key() -> str:
    """Resolve the Google API key. Never printed, never logged, never committed.

    Read from the environment first, so the benchmark carries no path to anyone's machine and no
    path to anyone's credential file. `GOOGLE_API_KEY` is enough to run every API arm here.

    The optional fallback exists because this benchmark grew inside a larger project whose key store
    it could borrow. That is a convenience for one machine, not part of the harness: both the code
    directory and the dotenv file are supplied by environment variables, so an absent variable
    simply means the fallback is unavailable rather than pointing at a location that only exists on
    the author's disk.
    """
    import os

    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key

    store = os.environ.get("BENCH_KEYSTORE_DIR")
    dotenv = os.environ.get("BENCH_DOTENV")
    if store:
        sys.path.insert(0, store)
        if dotenv:
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv)
            except ImportError:
                pass
        try:
            from src.lib.llm_keys import resolve_provider_key
            return resolve_provider_key("google")
        except Exception:
            pass

    raise SystemExit(
        "No Google API key. Set GOOGLE_API_KEY, or set BENCH_KEYSTORE_DIR "
        "(and optionally BENCH_DOTENV) to borrow an existing key store."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)   # any prompts/<NAME>_*.txt
    ap.add_argument("--arm", required=True)
    ap.add_argument("--limit", type=int, default=len(PAGES))
    # Default sends no thinking config at all, so every arm run before this flag existed keeps the
    # exact call it had. `off` is a deliberate second configuration of the same model, not a fix.
    ap.add_argument("--thinking", choices=["default", "off"], default="default")
    a = ap.parse_args()

    import requests

    key = get_key()
    matches = sorted((ROOT / "prompts").glob(a.prompt + "_*.txt"))
    if not matches:
        sys.exit(f"no prompt file matching prompts/{a.prompt}_*.txt")
    instruction = matches[0].read_text(encoding="utf-8")
    outdir = ROOT / "runs" / a.arm
    outdir.mkdir(parents=True, exist_ok=True)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{a.model}:generateContent")

    usage_log, failures = [], []
    for pg in PAGES[: a.limit]:
        dest = outdir / f"p{pg}.json"
        if dest.exists():
            continue
        img = base64.b64encode((ROOT / "pages" / f"p{pg}.webp").read_bytes()).decode()
        body = {
            "contents": [{"parts": [
                {"inline_data": {"mime_type": "image/webp", "data": img}},
                {"text": instruction},
            ]}],
            # Deliberately NOT using response_mime_type=application/json: the CLI-driven arms did
            # not get structured-output enforcement either, and the comparison must stay like-for-like.
            "generationConfig": {"temperature": 0},
        }
        if a.thinking == "off":
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        r = requests.post(url, params={"key": key}, json=body, timeout=180)
        if r.status_code != 200:
            failures.append((pg, r.status_code, r.text[:160]))
            continue
        data = r.json()
        try:
            # EVERY text part, not parts[0]. The API is free to split one answer across parts, and
            # reading only the first silently truncated the response mid-JSON while finishReason
            # still said STOP — an arm then scored as if the model had emitted broken JSON. The
            # tell is chars far below output_tokens * chars_per_token.
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p["text"] for p in parts if "text" in p)
            if not text:
                raise KeyError("no text part")
        except Exception:
            failures.append((pg, "no-text", json.dumps(data)[:160]))
            continue
        finish = (data.get("candidates") or [{}])[0].get("finishReason")
        um = data.get("usageMetadata", {})
        usage_log.append({"page": int(pg), "prompt_tokens": um.get("promptTokenCount"),
                          "output_tokens": um.get("candidatesTokenCount"),
                          # Recorded, never billed: the cost model counts candidate tokens only, as
                          # every other arm's does. Thinking is the gap between the two.
                          "thoughts_tokens": um.get("thoughtsTokenCount"), "finish": finish,
                          "total_tokens": um.get("totalTokenCount"), "chars": len(text)})
        t = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            rec = json.loads(t)
        except json.JSONDecodeError:
            # An arm that cannot return valid JSON when asked is a RESULT, not a crash — but only
            # when the model actually finished. Under load this API returns HTTP 200 with a body cut
            # off mid-token and a finishReason that is not STOP; persisting that scores an
            # infrastructure hiccup as a model failure. Re-running the same page then returns a
            # complete answer, which is how this was found. Unfinished responses are retried, not kept.
            if finish != "STOP":
                failures.append((pg, f"truncated ({finish})", f"{len(text)} chars"))
                continue
            rec = {"_json_parse_failed": True, "raw_text": text}
        rec["page"] = int(pg)
        dest.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"p{pg} ok  out_tokens={um.get('candidatesTokenCount')} chars={len(text)}")
        time.sleep(0.4)

    # Merge, never overwrite: a resumed run skips pages it already has, so writing only this
    # pass's rows would throw away the measured tokens of every earlier one.
    ulog = outdir / "_usage.json"
    if ulog.exists():
        prior = {u["page"]: u for u in json.loads(ulog.read_text(encoding="utf-8"))}
        prior.update({u["page"]: u for u in usage_log})
        usage_log = [prior[p] for p in sorted(prior)]
    ulog.write_text(json.dumps(usage_log, indent=1), encoding="utf-8")
    if usage_log:
        tot_out = sum(u["output_tokens"] or 0 for u in usage_log)
        tot_ch = sum(u["chars"] for u in usage_log)
        print(f"\npages={len(usage_log)}  mean prompt_tok="
              f"{sum(u['prompt_tokens'] or 0 for u in usage_log)/len(usage_log):.0f}"
              f"  mean out_tok={tot_out/len(usage_log):.0f}"
              f"  MEASURED chars/token={tot_ch/tot_out:.2f}")
    for f in failures:
        print("FAIL", f)


if __name__ == "__main__":
    main()

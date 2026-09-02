"""Second-pass reference extraction: read an EXISTING P2 transcription, not the page image.

The point of the experiment. Asking one call to transcribe and annotate cost 2.45 points of
transcript accuracy on this corpus (P2 99.48% -> P3 97.03%). If references are pulled from text that
is already transcribed, the reading is finished and fixed before anything is interpreted, so the
transcription cannot pay for the annotation. This measures whether that recovers the loss.

    python tools/run_second_pass.py --source K_35flash_P2 --arm V_secondpass --model gemini-3.5-flash
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def as_text(rec: dict) -> str:
    """Render a P2 record as the plain input the second pass reads — body flow, then apparatus,
    each labelled so `where` is answerable without the image."""
    lines = ["=== BODY ==="]
    for b in rec.get("blocks") or []:
        if isinstance(b, dict) and b.get("text"):
            lines.append(str(b["text"]))
    lines.append("=== FOOTNOTES ===")
    for n in rec.get("footnotes") or []:
        if isinstance(n, dict):
            lines.append(f"[{n.get('marker') or '-'}] {n.get('text', '')}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="arm id whose P2 transcriptions to read")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--model", default="gemini-3.5-flash")
    a = ap.parse_args()

    import requests

    key = get_key()
    instruction = (ROOT / "prompts" / "P4_refs_second_pass.txt").read_text(encoding="utf-8")
    src = ROOT / "runs" / a.source
    out = ROOT / "runs" / a.arm
    out.mkdir(parents=True, exist_ok=True)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{a.model}:generateContent"

    usage, failures, total_refs = [], [], 0
    for f in sorted(src.glob("p*.json")):
        dest = out / f.name
        # Resume, but only past a record that is actually complete. An early version of this script
        # wrote the references alone; the plain `exists()` skip then meant a fixed version never
        # repaired them, and the arm scored as if it had transcribed nothing at all.
        if dest.exists() and "blocks" in json.loads(dest.read_text(encoding="utf-8")):
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        payload = as_text(rec)
        if not payload.strip():
            continue
        body = {"contents": [{"parts": [{"text": instruction + "\n\n--- INPUT ---\n" + payload}]}],
                "generationConfig": {"temperature": 0}}
        r = requests.post(url, params={"key": key}, json=body, timeout=180)
        if r.status_code != 200:
            failures.append((f.name, r.status_code, r.text[:120]))
            continue
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            failures.append((f.name, "no-text", ""))
            continue
        t = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            refs = json.loads(t)
        except json.JSONDecodeError:
            refs = {"_json_parse_failed": True, "raw_text": text, "references": []}
        # The transcription is carried through UNCHANGED: this pass may add references and nothing
        # else, so the arm is directly comparable to its source on every reading metric.
        merged = dict(rec)
        merged["references"] = refs.get("references") or []
        total_refs += len(merged["references"])
        um = data.get("usageMetadata", {})
        usage.append({"page": rec.get("page"), "prompt_tokens": um.get("promptTokenCount"),
                      "output_tokens": um.get("candidatesTokenCount"), "chars": len(text)})
        dest.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{f.name}: {len(merged['references'])} refs")
        time.sleep(0.4)

    (out / "_usage.json").write_text(json.dumps(usage, indent=1), encoding="utf-8")
    print(f"\n{a.arm}: {len(usage)} pages, {total_refs} references total")
    for f in failures:
        print("FAIL", f)


if __name__ == "__main__":
    main()

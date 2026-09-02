"""Diff the two independent readings of each evaluation page, and report what must be adjudicated.

Double-keying is the standard way to build a transcription reference: two readers work from the
source without seeing each other, and only their disagreements get expensive human attention. What
they agree on is accepted; what they dispute is decided against the image.

    python tools/gold_merge.py            # show the diff, write nothing
    python tools/gold_merge.py --write    # write truth/gold/ for pages where the keys AGREE
    python tools/gold_merge.py --write --single   # ...and promote pages that only ever got ONE
                                                  #    reading, labelled as single-key

`--write` never invents a resolution. A page with any disagreement is left out of gold entirely
until it is adjudicated, so gold can never contain a coin-flip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import normalize_ar, cer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
K1, K2 = ROOT / "truth" / "_key1", ROOT / "truth" / "_key2"
GOLD = ROOT / "truth" / "gold"

# NO TOLERANCE on scored text. A 0.5% CER threshold sounded like "ignore spacing and hamza seats";
# what it actually did was wave through one-character disagreements on 1,000-character blocks — the
# exact class this reference exists to settle. On p015 it accepted `أثبتا` from key 1 over key 2's
# `أثبتنا`, where key 2 had counted the teeth (ث ب ت ن) to establish the نا. A difference of one
# letter in the body is a disagreement about what the page says, and the adjudicator decides it.
#
# Text is compared under `normalize_ar`, so the two readings still agree freely about alef seats,
# ya/alef-maqsura, ta-marbuta, harakat and tatweel — the things the scorer itself folds away and
# therefore never scores. Everything the scorer looks at is compared exactly.
SAME = 0.0


def blocks(rec):
    return [b for b in (rec.get("blocks") or []) if isinstance(b, dict)]


def diff_page(a: dict, b: dict) -> list[str]:
    out = []
    for f in ("runningHeader", "printedPageNumber", "printerMark"):
        x, y = a.get(f), b.get(f)
        if (x or None) != (y or None):
            out.append(f"{f}: key1={x!r}  key2={y!r}")
    ab, bb = blocks(a), blocks(b)
    if len(ab) != len(bb):
        out.append(f"block count: key1={len(ab)} key2={len(bb)}  "
                   f"types key1={[x.get('type') for x in ab]} key2={[x.get('type') for x in bb]}")
    else:
        for i, (x, y) in enumerate(zip(ab, bb)):
            if x.get("type") != y.get("type"):
                out.append(f"block {i} type: key1={x.get('type')} key2={y.get('type')}")
            tx, ty = normalize_ar(str(x.get("text") or "")), normalize_ar(str(y.get("text") or ""))
            d = cer(tx, ty) if tx else (0.0 if not ty else 1.0)
            if d > SAME:
                out.append(f"block {i} text differs by {d*100:.1f}% "
                           f"({len(tx)} vs {len(ty)} chars)")
            rx = [n for n in (x.get("noteRefs") or [])]
            ry = [n for n in (y.get("noteRefs") or [])]
            if rx != ry:
                out.append(f"block {i} noteRefs: key1={rx} key2={ry}")
    an, bn = a.get("footnotes") or [], b.get("footnotes") or []
    if len(an) != len(bn):
        out.append(f"footnote count: key1={len(an)} key2={len(bn)}")
    else:
        for i, (x, y) in enumerate(zip(an, bn)):
            if str(x.get("marker") or "") != str(y.get("marker") or ""):
                out.append(f"note {i} marker: key1={x.get('marker')!r} key2={y.get('marker')!r}")
            # `number` is what the scorer keys notes by, and `continuedFromPreviousPage` is what
            # tells the reader a note began on the previous leaf. Both are scored; neither was
            # compared, so two readings could disagree about them and still be called identical.
            if x.get("number") != y.get("number"):
                out.append(f"note {i} number: key1={x.get('number')} key2={y.get('number')}")
            if bool(x.get("continuedFromPreviousPage")) != bool(y.get("continuedFromPreviousPage")):
                out.append(f"note {i} continuedFromPreviousPage: "
                           f"key1={x.get('continuedFromPreviousPage')} "
                           f"key2={y.get('continuedFromPreviousPage')}")
            tx, ty = normalize_ar(str(x.get("text") or "")), normalize_ar(str(y.get("text") or ""))
            d = cer(tx, ty) if tx else (0.0 if not ty else 1.0)
            if d > SAME:
                out.append(f"note {i} text differs by {d*100:.2f}%")

    # foreignRuns is a scored field (gold.foreign_runs) and was never compared. On p030 the two
    # readings disagreed about whether the digits-only `4.1.8` is a Latin run, and the page was
    # still announced as AGREED.
    fa = [normalize_ar(str(r.get("text") or "")) for r in (a.get("foreignRuns") or [])
          if isinstance(r, dict)]
    fb = [normalize_ar(str(r.get("text") or "")) for r in (b.get("foreignRuns") or [])
          if isinstance(r, dict)]
    only_a = [x for x in fa if x not in fb]
    only_b = [x for x in fb if x not in fa]
    if only_a or only_b:
        out.append(f"foreignRuns: only in key1 {only_a}; only in key2 {only_b}")
    return out


def promote_single(names: set[str]) -> None:
    """Promote a lone reading to gold, labelled honestly as a lone reading.

    Used only for pages the second reader never reached inside the time cap. The label travels with
    the page so a reader of results.json can see exactly which pages carry the weaker guarantee —
    see truth/EVAL_SET.md. It is never applied to a page that HAS two readings.
    """
    GOLD.mkdir(parents=True, exist_ok=True)
    for name in sorted(names):
        src = K1 / name if (K1 / name).exists() else K2 / name
        d = json.loads(src.read_text(encoding="utf-8"))
        d["verifiedBy"] = "gold-single-key-image-checked"
        (GOLD / name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: promoted single key from {src.parent.name}")


def load_resolutions() -> dict:
    f = ROOT / "truth" / "_resolutions.json"
    if not f.exists():
        return {}
    return {k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


def main() -> None:
    write = "--write" in sys.argv
    resolutions = load_resolutions()
    GOLD.mkdir(parents=True, exist_ok=True)
    pages = sorted(set(p.name for p in K1.glob("p*.json")) & set(p.name for p in K2.glob("p*.json")))
    clean = 0
    for name in pages:
        a = json.loads((K1 / name).read_text(encoding="utf-8"))
        b = json.loads((K2 / name).read_text(encoding="utf-8"))
        d = diff_page(a, b)
        if not d:
            clean += 1
            print(f"{name}: AGREED  ({len(blocks(a))} blocks, {len(a.get('footnotes') or [])} notes)")
            if write:
                a["verifiedBy"] = "gold-double-keyed-agreed"
                (GOLD / name).write_text(json.dumps(a, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
        elif name in resolutions:
            # An adjudicated page: the decision is recorded in truth/_resolutions.json, names which
            # reading it adopts and why, and is repeated in the adjudication log. Gold carries the
            # decision with it, so nothing here is a silent choice.
            r = resolutions[name]
            src = a if r.get("base", "key1") == "key1" else b
            rec = json.loads(json.dumps(src))
            drop = {normalize_ar(x) for x in (r.get("drop_foreign_runs") or [])}
            if drop:
                rec["foreignRuns"] = [f for f in (rec.get("foreignRuns") or [])
                                      if normalize_ar(str(f.get("text") or "")) not in drop]
            print(f"\n{name}: {len(d)} disagreement(s) — ADJUDICATED "
                  f"(adopting {r.get('base', 'key1')}: {r.get('dispute', '')})")
            for line in d:
                print("   ", line)
            if write:
                rec["verifiedBy"] = "gold-double-keyed-adjudicated"
                rec["adjudication"] = r
                (GOLD / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
            clean += 0
        else:
            print(f"\n{name}: {len(d)} DISAGREEMENT(S) — UNRESOLVED, kept out of gold")
            for line in d:
                print("   ", line)
            print(f"    add an entry for {name} to truth/_resolutions.json to settle it")
            # A page promoted earlier on ONE key must not survive as gold once a second reading
            # arrives and contradicts it. Silently keeping the single-key file would mean gold
            # holds a reading we now know is disputed.
            existing = GOLD / name
            if write and existing.exists():
                if json.loads(existing.read_text(encoding="utf-8")).get("verifiedBy", "") \
                        == "gold-single-key-image-checked":
                    existing.unlink()
                    print("    (withdrew the single-key gold for this page — now disputed)")
    if "--single" in sys.argv:
        # Only pages that have exactly ONE reading. A page with two readings is never promoted this
        # way — if the two disagree it stays out of gold until it is adjudicated, which is the whole
        # point of the double key.
        lone = (set(p.name for p in K1.glob("p*.json")) ^ set(p.name for p in K2.glob("p*.json")))
        promote_single({n for n in lone if not (GOLD / n).exists()})
    only1 = sorted(set(p.name for p in K1.glob('p*.json')) - set(pages))
    only2 = sorted(set(p.name for p in K2.glob('p*.json')) - set(pages))
    print(f"\n{clean}/{len(pages)} pages agreed outright"
          + (f"; key1 only: {only1}" if only1 else "")
          + (f"; key2 only: {only2}" if only2 else ""))


if __name__ == "__main__":
    main()

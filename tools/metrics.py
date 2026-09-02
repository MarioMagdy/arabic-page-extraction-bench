"""Metrics for the Arabic page-extraction benchmark.

Three tiers, deliberately: the plain count anyone can check, the OCR-industry standard
(CER/WER), and the structural scores that measure whether the model told us WHAT each piece of
text is. Cost lives in score.py because it needs per-arm token accounting.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import Levenshtein

# ---------------------------------------------------------------- normalisation

_ALEF = {"\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627"}
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_INDIC = {chr(0x0660 + i): str(i) for i in range(10)}      # ٠١٢٣٤٥٦٧٨٩
_EXT_ARABIC_INDIC = {chr(0x06F0 + i): str(i) for i in range(10)}  # ۰۱۲۳۴۵۶۷۸۹
_WS = re.compile(r"\s+")


def fold_digits(s: str) -> str:
    """Collapse all three digit blocks onto ASCII.

    The two Arabic blocks render nearly identically and are different codepoints; a model that
    swaps them is wrong on the page but right on the number. Folding lets us measure that
    difference by comparing a folded score against an unfolded one.
    """
    out = []
    for ch in s:
        out.append(_ARABIC_INDIC.get(ch) or _EXT_ARABIC_INDIC.get(ch) or ch)
    return "".join(out)


def normalize_ar(s: str, *, digits: bool = True) -> str:
    """Standard Arabic text normalisation for scoring.

    Unifies the alef forms, ya/alef-maqsura, ta-marbuta/ha, strips harakat and tatweel, collapses
    whitespace. Optionally folds digit blocks. This is the usual pre-processing for Arabic CER —
    reporting BOTH raw and normalised is the point, so nothing here is applied silently.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(_ALEF.get(c, c) for c in s)
    s = s.replace("\u0649", "\u064A").replace("\u0629", "\u0647")
    s = _DIACRITICS.sub("", s)
    if digits:
        s = fold_digits(s)
    return _WS.sub(" ", s).strip()


# ---------------------------------------------------------------- text accuracy

def cer(ref: str, hyp: str) -> float:
    """Character Error Rate — the OCR standard. Levenshtein distance over reference length."""
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def wer(ref: str, hyp: str) -> float:
    """Word Error Rate — the same measure at whitespace-token level."""
    r, h = ref.split(), hyp.split()
    if not r:
        return 0.0 if not h else 1.0
    # Levenshtein over word sequences, via a private alphabet so we can reuse the C implementation.
    vocab: dict[str, str] = {}

    def enc(seq):
        return "".join(vocab.setdefault(w, chr(0xE000 + len(vocab))) for w in seq)

    return Levenshtein.distance(enc(r), enc(h)) / len(r)


# ---------------------------------------------------------------- structure

STRUCT_FIELDS = ("runningHeader", "pageTitle", "sectionHeading",
                 "printedPageNumber", "printerMark")


_TRAILING_MARKER = re.compile(r"[\s¹²³⁰-₟0-9٠-٩۰-۹]+$")


def strip_marker(s: str) -> str:
    """Drop a trailing footnote-reference glyph from a heading.

    A title printed as `تمهيد¹` is the title `تمهيد` plus a marker pointing at note 1. Scoring the
    marker as part of the title would punish an arm for reading the page correctly.
    """
    return _TRAILING_MARKER.sub("", s).strip()


def _flat(v):
    """A list field compares as its joined, ordered contents; a scalar compares as itself."""
    if isinstance(v, (list, tuple)):
        return " | ".join(str(x) for x in v)
    return v


def field_match(pred, truth, field: str | None = None) -> bool | None:
    """Compare one structural field.

    `strip_marker` may ONLY be applied to heading-like text, where a trailing glyph is a footnote
    reference rather than part of the title. Applied to a page number it deleted the entire value —
    every pure number reduced to '' and compared equal to every other, so `٧٢` passed against `٧٣`
    and `١١` against `٩٩`. Two of the four scored fields were awarding free passes.
    """
    if isinstance(pred, (list, tuple)) or isinstance(truth, (list, tuple)):
        pred = _flat(pred) or None
        truth = _flat(truth) or None
    if truth is None and pred is None:
        return True
    if truth is None:
        return pred is None
    if pred is None:
        return False
    a, b = normalize_ar(str(pred)), normalize_ar(str(truth))
    if a == b:
        return True
    # RTL order is a transcription artifact, not a reading error: the same printed mark comes back
    # as "م ١١" from one arm and "١١ م" from another. Token multiset only — never a value change.
    if sorted(a.split()) == sorted(b.split()) and a.split():
        return True
    # Heading-like fields only: a trailing footnote marker is not part of the title.
    if field in (None, "runningHeader", "pageTitle", "sectionHeading"):
        sa, sb = strip_marker(a), strip_marker(b)
        if sa and sb and sa == sb:
            return True
    return False


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def body_purity(body_text: str, contaminants: list[str]) -> float:
    """Share of body characters that are genuinely body.

    A contaminant is a string the page prints OUTSIDE the body — the running head, the printed page
    number, the printer mark, footnote text. Any of it appearing inside `body` is what makes the
    reader speak furniture aloud, so this is the metric that predicts the lived symptom.
    """
    body_n = normalize_ar(body_text)
    if not body_n:
        return 0.0
    leaked = 0
    for c in contaminants:
        cn = normalize_ar(c)
        if len(cn) >= 3 and cn in body_n:
            leaked += len(cn)
    return max(0.0, 1.0 - leaked / len(body_n))


# ---------------------------------------------------------------- P0 recovery

_FN_BLOCK = re.compile(r"\[FOOTNOTE\](.*?)\[/FOOTNOTE\]", re.S | re.I)
_TRAILING_NUM = re.compile(r"^\s*[\u0660-\u0669\u06F0-\u06F9\d\u0645\s]{1,6}\s*$")


def recover_structure_p0(raw: str) -> dict:
    """Reconstruct structure from flat P0 output the way the production parser must.

    This is what makes the comparison fair: production does not consume flat text directly, it runs
    a parser over it. Scoring P0 as if it produced nothing would flatter the schema arms; scoring it
    through the same heuristics production uses measures the real architecture — a model that was
    never asked what anything IS, plus a parser guessing afterwards.
    """
    notes = [{"marker": None, "number": None, "text": m.strip(),
              "continuedFromPreviousPage": False} for m in _FN_BLOCK.findall(raw)]
    body_src = _FN_BLOCK.sub("", raw)
    lines = [ln.strip() for ln in body_src.split("\n") if ln.strip()]
    header = lines[0] if lines else None          # the parser's only header signal: it is line 1
    rest = lines[1:] if lines else []
    page_no = None
    if rest and _TRAILING_NUM.match(rest[-1]):
        page_no = rest[-1]
        rest = rest[:-1]
    return {
        "runningHeader": header,
        "pageTitle": None,          # flat text carries no way to know
        "sectionHeading": [],
        "body": rest,
        "footnotes": notes,
        "printedPageNumber": page_no,
        "printerMark": None,
        "foreignRuns": [],
        "uncertain": re.findall(r"\[\?([^\]]+)\]", raw),
    }


def flatten(rec: dict) -> str:
    """Everything the arm believes is on the page, in reading order — the CER reference shape."""
    parts: list[str] = []
    for k in ("runningHeader", "pageTitle"):
        if rec.get(k):
            parts.append(str(rec[k]))
    parts += [str(x) for x in (rec.get("sectionHeading") or [])]
    parts += [str(x) for x in (rec.get("body") or [])]
    for n in rec.get("footnotes") or []:
        marker = n.get("marker") or ""
        parts.append(f"{marker} {n.get('text','')}".strip())
    for k in ("printedPageNumber", "printerMark"):
        if rec.get(k):
            parts.append(str(rec[k]))
    return "\n".join(p for p in parts if p)


def from_blocks(rec: dict) -> dict:
    """Map a block-sequence record (P2/P3) onto the common shape the metrics already use.

    The point of P2 is that `blocks` keeps ORDER, which parallel lists cannot. Flattening it here
    lets every existing metric keep working unchanged, while `_blocks`, `_anchors` and
    `_references` ride along so the order-aware and semantic metrics can use what the flattening
    throws away. Nothing is lost — the flattening is a view, not a replacement.
    """
    blocks = rec.get("blocks") or []
    body, headings, title = [], [], None
    anchors: list[int] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t, txt = b.get("type"), str(b.get("text") or "")
        for n in (b.get("noteRefs") or []):
            if isinstance(n, int):
                anchors.append(n)
        if t == "pageTitle" and title is None:
            title = txt
        elif t == "heading":
            headings.append(txt)
        else:
            body.append(txt)
    out = dict(rec)
    out.update({"pageTitle": title, "sectionHeading": headings, "body": body,
                "_blocks": blocks, "_anchors": anchors,
                "_references": rec.get("references") or []})
    return out


def anchor_consistency(rec: dict, truth_note_count: int | None = None) -> float | None:
    """Do the anchors in the text account for the notes below the rule, and vice versa?

    This is the one metric here that needs NO ground truth: the page checks itself. An anchor with
    no matching note, or a note nothing anchors, means one of the two readings is wrong. Jaccard
    over the two integer sets — 1.0 when they agree exactly. Returns None when the page has neither,
    so an empty page is not scored as perfect.
    """
    if "_anchors" not in rec:
        return None
    anchors = {n for n in rec.get("_anchors") or [] if isinstance(n, int)}
    notes = {n.get("number") for n in (rec.get("footnotes") or [])
             if isinstance(n, dict) and isinstance(n.get("number"), int)}
    # SELF-consistency alone is not correctness. A model that invents a note AND an anchor for it
    # agrees with itself perfectly: Luna emitted notes [2,3] and anchors [2,3] on a page whose truth
    # is ZERO notes and scored 1.0. Where the page's real note count is known, a mismatch caps the
    # score at zero — the model is consistent about something that is not there.
    if truth_note_count is not None and len(notes) != truth_note_count:
        return 0.0
    if not anchors and not notes:
        return None if truth_note_count in (None, 0) else 0.0
    union = anchors | notes
    return len(anchors & notes) / len(union) if union else None


def load_arm(rec_path: Path) -> dict:
    """Load one arm's page output, normalising P0 (raw_text) into the common shape."""
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    if "blocks" in rec and isinstance(rec.get("blocks"), list):
        return from_blocks(rec)
    if "raw_text" in rec and "body" not in rec:
        out = recover_structure_p0(rec["raw_text"])
        out["page"] = rec.get("page")
        out["_raw"] = rec["raw_text"]
        # A model that was asked for JSON and returned something unparseable has FAILED this page.
        # Carrying the flag through means it is reported, not silently smoothed into an average.
        out["_json_parse_failed"] = bool(rec.get("_json_parse_failed"))
        return out
    rec.setdefault("_raw", flatten(rec))
    return rec


# ---------------------------------------------------------------- transcript accuracy

def body_text(rec: dict) -> str:
    """The prose an arm believes is body, as one string."""
    return " ".join(str(x) for x in (rec.get("body") or []))


def medoid(texts: list[str]) -> str:
    """The most representative reading among several — the one with the lowest mean CER to the rest.

    There is no gold transcription of the prose in this corpus, so the reference has to come from
    the readings themselves. The medoid is the right choice rather than the longest or the first:
    it is the text the group agrees with most, and it is a REAL reading rather than a synthetic
    merge that no model actually produced.
    """
    if not texts:
        return ""
    if len(texts) == 1:
        return texts[0]
    best, best_score = texts[0], float("inf")
    for t in texts:
        others = [o for o in texts if o is not t]
        score = sum(_pair_cer(o, t) for o in others) / len(others)
        if score < best_score:
            best, best_score = t, score
    return best


@lru_cache(maxsize=200_000)
def _norm_cached(s: str) -> str:
    return normalize_ar(s)


@lru_cache(maxsize=400_000)
def _pair_cer(a: str, b: str) -> float:
    """Normalised CER between two readings, memoised.

    Leave-one-out means the medoid is rebuilt once per arm, over almost the same texts each time —
    the same pair of readings was being normalised and diffed twenty-odd times. Memoising turns the
    whole scoring pass from O(arms x pages x arms^2) into O(pages x arms^2).
    """
    return cer(_norm_cached(a), _norm_cached(b))

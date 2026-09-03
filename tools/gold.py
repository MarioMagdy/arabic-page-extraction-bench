"""Scoring against GOLD — the only measurements in this benchmark that are accuracy.

Everything in score.py compares an arm to the other arms. That answers "how conventional is this
reading?", never "how right is it?", and it cannot rank models: the reference moves when the pool
moves, correlated arms can define it, and a shared error passes unnoticed.

This module compares an arm to `truth/gold/pNNN.json` — a reading produced outside the arm pool,
double-keyed and adjudicated against the page image (see truth/EVAL_SET.md). The reference is the
same for every arm and does not move. That is what makes a ranking defensible.

It also scores the three things the benchmark previously claimed P2 delivered without ever checking:

    heading POSITION   a heading is only useful if it comes back between the right paragraphs
    footnote TEXT      a note counted is not a note read; the reader displays the text
    anchor LINKAGE     tapping note 3 must open note 3, so the anchor must be right AND in the
                       right block — not merely self-consistent with whatever the model invented

Every score is returned with its denominator. A metric that cannot be measured for an arm (a flat
prompt has no blocks) returns None and is reported as "not applicable", never as zero.
"""
from __future__ import annotations

import json
from pathlib import Path

import Levenshtein

from metrics import cer, normalize_ar

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "truth" / "gold"


def eval_pages() -> list[int]:
    """The frozen evaluation set — whatever gold exists for, and nothing else."""
    return sorted(int(p.stem[1:]) for p in GOLD.glob("p*.json"))


def acc(c: float) -> float:
    """CER -> accuracy, floored at 0. A reading can be no worse than entirely wrong."""
    return max(0.0, 1.0 - c)


# ------------------------------------------------------------------ block views

def _blocks(rec: dict) -> list[dict]:
    return [b for b in (rec.get("_blocks") or rec.get("blocks") or []) if isinstance(b, dict)]


def _body_of(rec: dict) -> str:
    return " ".join(str(x) for x in (rec.get("body") or []))


def _type_seq(blocks: list[dict]) -> str:
    """Block types as a string, so sequence distance is one Levenshtein call."""
    code = {"pageTitle": "T", "heading": "H", "paragraph": "P", "verse": "V"}
    return "".join(code.get(str(b.get("type")), "?") for b in blocks)


def _sim(a: str, b: str) -> float:
    a, b = normalize_ar(a), normalize_ar(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return acc(Levenshtein.distance(a, b) / max(len(a), len(b)))


# ------------------------------------------------------------------ the metrics

def body_accuracy(arm: dict, gold: dict) -> tuple[float | None, int]:
    """Character accuracy of the transcribed prose against gold prose.

    An arm that returns NO body for a page that has one has not scored well by staying silent — it
    has failed the page, and is scored 0. Silently omitting it (the old behaviour) let an arm
    improve its own average by skipping the hard pages.
    """
    g = normalize_ar(_body_of(gold))
    if not g:
        return None, 0
    a = normalize_ar(_body_of(arm))
    return acc(cer(g, a)), len(g)


def block_sequence(arm: dict, gold: dict) -> float | None:
    """Did the page come back as the right ORDERED sequence of block types?

    Normalised edit distance over the type sequence. A prompt that returns parallel lists has no
    sequence to score and returns None — which is the finding, not a penalty.
    """
    gb = _blocks(gold)
    if not gb:
        return None
    ab = _blocks(arm)
    if not ab:
        return None if "blocks" not in arm and "_blocks" not in arm else 0.0
    gs, as_ = _type_seq(gb), _type_seq(ab)
    return acc(Levenshtein.distance(gs, as_) / max(len(gs), len(as_)))


HEADING_TOL = 0.10


def _text_fraction_before(blocks: list[dict], idx: int) -> float:
    """How far down the page's text a block sits, as a share of all non-heading characters.

    Position has to be measured in TEXT, not in list index. Two readings can both put the heading
    between the same two printed paragraphs while disagreeing about how many blocks those
    paragraphs are: on p093 one arm split the psalm quotation from the commentary that follows it,
    which is defensible, and index equality would have marked that reading wrong for a judgement
    call rather than for misplacing anything. A character fraction is invariant to how the prose
    around the heading is divided, and still catches a heading hoisted to the top or dropped to the
    bottom — which is the failure that matters.
    """
    total = sum(len(str(b.get("text") or "")) for b in blocks if b.get("type") != "heading")
    if not total:
        return 0.0
    before = sum(len(str(b.get("text") or "")) for b in blocks[:idx] if b.get("type") != "heading")
    return before / total


def heading_placement(arm: dict, gold: dict) -> tuple[float | None, int]:
    """For each heading gold found INSIDE the flow: did the arm emit it in the right place?

    Right place means the same share of the page's prose runs above it, within a tolerance. This is
    the single printed feature P2 was introduced to capture, and until now nothing measured it at
    all: a heading hoisted to the top of the page scored exactly the same as one set between its own
    paragraphs.
    """
    gb = _blocks(gold)
    if not gb:
        return None, 0
    # A prompt that returns no block sequence cannot place a heading — it was never asked to, and
    # scoring it 0 misreports "could not be asked" as "asked and failed". That error also inflated
    # the published coverage figure for the flat and parallel-list prompts.
    if "_blocks" not in arm and "blocks" not in arm:
        return None, 0
    gold_heads = [(i, str(b.get("text") or "")) for i, b in enumerate(gb)
                  if b.get("type") == "heading"]
    if not gold_heads:
        return None, 0
    ab = _blocks(arm)
    arm_heads = [(i, str(b.get("text") or "")) for i, b in enumerate(ab)
                 if b.get("type") == "heading"]
    def prose_before(blocks, idx):
        return any(b.get("type") != "heading" and str(b.get("text") or "").strip()
                   for b in blocks[:idx])

    hits = 0
    for gi, gtext in gold_heads:
        gf = _text_fraction_before(gb, gi)
        for ai, atext in arm_heads:
            if _sim(gtext, atext) < 0.8:
                continue
            if abs(_text_fraction_before(ab, ai) - gf) > HEADING_TOL:
                continue
            # A tolerance alone is not enough. Where gold's heading follows a SHORT opening
            # paragraph its fraction is small, and a heading hoisted to the very top of the page
            # lands inside the tolerance and passes — the exact failure this metric exists to
            # catch. "Inside the flow" therefore also requires prose above it, as gold has.
            if prose_before(gb, gi) and not prose_before(ab, ai):
                continue
            hits += 1
            break
    return hits / len(gold_heads), len(gold_heads)


def align_notes(gn: list[dict], an: list[dict]) -> dict[int, int]:
    """Pair gold notes with arm notes by CONTENT and order, not by the number the arm assigned.

    Keying notes on `number` before comparing their text makes one misread digit cost four separate
    scores. On p093 an arm read both notes correctly and anchored both in the right paragraph, but
    read the raised `١٣٨`/`١٣٩` as 128/129; scored by number that page returned zero for note text,
    marker fidelity, anchor identity AND anchor placement. Positional text comparison of the same
    two notes is 99.3% accurate.

    The number error is a real error and still costs identity and marker fidelity. It must not also
    erase the measurement of the things it did not damage.
    """
    if not gn or not an:
        return {}
    # The apparatus is a short ordered list, so equal counts means the i-th note is the i-th note.
    if len(gn) == len(an):
        return {i: i for i in range(len(gn))}
    # Otherwise pair on text similarity, best first, each note used once.
    cand = []
    for i, g in enumerate(gn):
        for j, a in enumerate(an):
            s = _sim(str(g.get("text") or ""), str(a.get("text") or ""))
            if s >= 0.5:
                cand.append((-s, abs(i - j), i, j))
    cand.sort()
    out: dict[int, int] = {}
    used: set[int] = set()
    for _, _, i, j in cand:
        if i in out or j in used:
            continue
        out[i] = j
        used.add(j)
    return out


def footnotes(arm: dict, gold: dict) -> dict:
    """Notes matched by number, then their TEXT compared — plus marker fidelity as printed.

    Three separate questions that the old count-only score collapsed into one:
      identity  is note 3 present, and did the arm invent notes that are not there? (F1)
      text      is the note's text the text that is printed?  (character accuracy)
      marker    is the marker the GLYPH that is printed?  `3` and `٣` are different characters and
                a reader that normalises them silently corrupts the apparatus.
    """
    gn = [n for n in (gold.get("footnotes") or []) if isinstance(n, dict)]
    an = [n for n in (arm.get("footnotes") or []) if isinstance(n, dict)]
    if not gn and not an:
        return {"n": 0, "f1": None, "text_acc": None, "marker_exact": None}

    def key(n):
        v = n.get("number")
        return v if isinstance(v, int) else None

    gmap = {key(n): n for n in gn if key(n) is not None}
    amap = {key(n): n for n in an if key(n) is not None}
    # Unnumbered notes (a continuation from the previous leaf) match positionally at index 0.
    g_unnum = [n for n in gn if key(n) is None]
    a_unnum = [n for n in an if key(n) is None]

    tp = sorted(set(gmap) & set(amap))
    fn = len(set(gmap) - set(amap)) + max(0, len(g_unnum) - len(a_unnum))
    fp = len(set(amap) - set(gmap)) + max(0, len(a_unnum) - len(g_unnum))
    matched = len(tp) + min(len(g_unnum), len(a_unnum))
    p = matched / (matched + fp) if (matched + fp) else 0.0
    r = matched / (matched + fn) if (matched + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0

    # TEXT and MARKER are scored on the content alignment, not on the number. Identity (f1, above)
    # already carries the cost of a wrong number; charging it again here would make one misread
    # digit look like four independent failures.
    pair = align_notes(gn, an)
    scores, markers = [], []
    for i, g in enumerate(gn):
        j = pair.get(i)
        if j is None:
            scores.append(0.0)          # the arm produced nothing that matches this note
            markers.append(False)
            continue
        scores.append(acc(cer(normalize_ar(str(g.get("text") or "")),
                              normalize_ar(str(an[j].get("text") or "")))))
        # The marker is still compared as printed and still exact: reading `١٣٨` as `128` is a real
        # corruption of the apparatus and this is where it is charged.
        markers.append(str(g.get("marker") or "") == str(an[j].get("marker") or ""))
    return {"n": len(gn),
            "f1": round(f1, 4),
            "text_acc": round(sum(scores) / len(scores), 4) if scores else None,
            "marker_exact": round(sum(markers) / len(markers), 4) if markers else None}


def anchors(arm: dict, gold: dict) -> dict:
    """Anchor correctness against gold, and whether each anchor sits in the right block.

    Replaces the self-consistency score, which was never correctness: a model that invents a note
    AND an anchor for it agrees with itself perfectly. On a gold page with no notes at all, every
    anchor an arm emits is now a false positive, which is what it is.

    `block_acc` is the behaviour the product needs — tapping the marker in THIS paragraph must open
    THAT note. An anchor listed against the wrong block still links, but links from the wrong place.
    """
    gb, ab = _blocks(gold), _blocks(arm)
    if not gb:
        return {"n": 0, "f1": None, "block_acc": None}
    if "_blocks" not in arm and "blocks" not in arm:
        return {"n": 0, "f1": None, "block_acc": None}   # prompt cannot express an anchor

    def pairs(blocks):
        out = []
        for i, b in enumerate(blocks):
            for n in (b.get("noteRefs") or []):
                if isinstance(n, int):
                    out.append((i, n))
        return out

    gp, ap = pairs(gb), pairs(ab)
    gset, aset = {n for _, n in gp}, {n for _, n in ap}
    if not gset and not aset:
        return {"n": 0, "f1": None, "block_acc": None}
    tp = len(gset & aset)
    p = tp / len(aset) if aset else 0.0
    r = tp / len(gset) if gset else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0

    # Placement. Align the two block sequences ONE-TO-ONE first, then ask whether the arm anchored
    # note n in the block that corresponds to gold's block for n.
    #
    # The obvious implementation — "is there ANY arm block holding n that looks like gold's block
    # for n?" — silently passes the failure it exists to catch. Two adjacent paragraphs on a page
    # are textually similar, so anchors swapped between them each find a near-enough block and score
    # 1.0. Alignment is what makes the question mean "the right paragraph" rather than "a paragraph
    # like it".
    align = _align(gb, ab)
    # Translate gold note numbers into whatever the arm called the same notes, so PLACEMENT asks
    # only "is this note anchored in the right paragraph?" — the question it is named for. Whether
    # the arm numbered it correctly is already charged, once, against anchor identity above.
    gn = [n for n in (gold.get("footnotes") or []) if isinstance(n, dict)]
    an_ = [n for n in (arm.get("footnotes") or []) if isinstance(n, dict)]
    pair = align_notes(gn, an_)
    renum = {}
    for i, j in pair.items():
        gnum, anum = gn[i].get("number"), an_[j].get("number")
        if isinstance(gnum, int) and isinstance(anum, int):
            renum[gnum] = anum

    hits = 0
    for gi, n in gp:
        ai = align.get(gi)
        if ai is None:
            continue
        want = {n, renum.get(n, n)}
        got = {m for m in (ab[ai].get("noteRefs") or []) if isinstance(m, int)}
        hits += bool(want & got)
    return {"n": len(gp),
            "f1": round(f1, 4),
            "block_acc": round(hits / len(gp), 4) if gp else None}


def _align(gb: list[dict], ab: list[dict]) -> dict[int, int]:
    """Greedy 1:1 alignment of gold blocks to arm blocks by text similarity.

    Highest-similarity pair first, each block consumed once. Position breaks a tie between two
    equally similar candidates, which is what separates a swap from a match.
    """
    cand = []
    for gi, gbk in enumerate(gb):
        for ai, abk in enumerate(ab):
            s = _sim(str(gbk.get("text") or ""), str(abk.get("text") or ""))
            if s >= 0.5:
                cand.append((-s, abs(gi - ai), gi, ai))
    cand.sort()
    out: dict[int, int] = {}
    used: set[int] = set()
    for _, _, gi, ai in cand:
        if gi in out or ai in used:
            continue
        out[gi] = ai
        used.add(ai)
    return out


FIELDS = ("runningHeader", "printedPageNumber", "printerMark")


def fields(arm: dict, gold: dict) -> dict:
    """The page furniture, compared field by field, with the page number compared DIGIT-EXACT.

    Page numbers are not normalised: the printed digit block is part of the answer, so `٧٢` must
    not pass against `٧٣` and Arabic-Indic must not pass against Extended Arabic-Indic.
    """
    hit = miss = 0
    detail = {}
    for f in FIELDS:
        g, a = gold.get(f), arm.get(f)
        if f == "printedPageNumber":
            ok = (str(g).strip() if g else None) == (str(a).strip() if a else None)
        elif g is None and a is None:
            ok = True
        elif g is None or a is None:
            ok = False
        else:
            ok = normalize_ar(str(g)) == normalize_ar(str(a))
        detail[f] = ok
        hit += ok
        miss += not ok
    # pageTitle lives in the block sequence.
    gt = gold.get("pageTitle")
    at = arm.get("pageTitle")
    ok = (not gt and not at) or (bool(gt) and bool(at) and _sim(str(gt), str(at)) >= 0.85)
    detail["pageTitle"] = ok
    hit += ok
    miss += not ok
    return {"n": hit + miss, "acc": round(hit / (hit + miss), 4), "detail": detail}


def foreign_runs(arm: dict, gold: dict) -> tuple[float | None, int]:
    """Greek and Latin runs inside right-to-left prose — declared in the schema, never scored."""
    def texts(rec):
        out = []
        for r in (rec.get("foreignRuns") or []):
            if isinstance(r, dict) and r.get("text"):
                out.append(normalize_ar(str(r["text"])))
            elif isinstance(r, str) and r:
                out.append(normalize_ar(r))
        return out

    g, a = texts(gold), texts(arm)
    if not g:
        return None, 0
    hits = sum(any(_sim(x, y) >= 0.8 for y in a) for x in g)
    return hits / len(g), len(g)


# ------------------------------------------------------------------ per-arm roll-up

def score_arm(recs: dict[int, dict]) -> dict:
    """Score one arm on the evaluation pages. Every aggregate carries scored/eligible.

    `recs` is page number -> the arm's record, already normalised into the common shape by
    `metrics.load_arm`, so a flat-prompt arm arrives here through the same production parser it
    would meet in the pipeline.
    """
    pages = eval_pages()
    out = {"pages_eligible": len(pages), "pages_present": 0, "per_page": {}}
    body_s, body_w = [], []
    seq, head_hits, head_n = [], 0, 0
    fn_f1, fn_text, fn_marker = [], [], []
    an_f1, an_block = [], []
    fld_hit = fld_n = 0
    fr_hits, fr_n = 0, 0

    for pg in pages:
        gp = GOLD / f"p{pg:03d}.json"
        gold = json.loads(gp.read_text(encoding="utf-8"))
        if "blocks" in gold:
            from metrics import from_blocks
            gold = from_blocks(gold)
        if pg not in recs:
            # A page the arm never produced is a miss on EVERY measure that page was eligible for —
            # not just on the prose. Penalising only the body (the first version of this function)
            # is the same selective-omission bug the agreement layer was criticised for: an arm
            # could raise its heading, footnote and anchor scores by not answering the hard pages,
            # because those pages simply left the denominator. An empty record scores them all at
            # zero against the same gold, which is what "did not answer" means.
            blank: dict = {"body": [], "footnotes": [], "blocks": [], "_blocks": [],
                           "runningHeader": None, "printedPageNumber": None,
                           "printerMark": None, "pageTitle": None, "foreignRuns": []}
            # The per-page record for a missing page must carry the SAME zeroed values, under the
            # same keys and with the same body weight, that the aggregate uses — otherwise the
            # bootstrap resamples a different quantity from the one published, and an arm with
            # missing pages lands outside its own confidence interval.
            miss: dict = {"missing": True}
            out["per_page"][pg] = miss
            b, w = body_accuracy(blank, gold)
            if b is not None:
                body_s.append(0.0)
                body_w.append(w)
                miss["body"] = 0.0
                miss["body_w"] = w
            s = block_sequence(blank, gold)
            if s is not None:
                seq.append(0.0)
                miss["sequence"] = 0.0
            h, hn = heading_placement(blank, gold)
            if h is not None:
                head_n += hn
                miss["heading"] = 0.0
            f = footnotes(blank, gold)
            if f["f1"] is not None:
                fn_f1.append(0.0)
                miss["notes"] = {"f1": 0.0, "text_acc": None, "marker_exact": None}
                if f["text_acc"] is not None:
                    fn_text.append(0.0)
                    miss["notes"]["text_acc"] = 0.0
                # marker_exact was the one metric the missing-page path forgot, so an arm that
                # skipped a note page had that page vanish from its marker denominator — exactly
                # the selective omission this branch exists to prevent.
                if gold.get("footnotes"):
                    fn_marker.append(0.0)
                    miss["notes"]["marker_exact"] = 0.0
            a = anchors(blank, gold)
            if a["f1"] is not None:
                an_f1.append(0.0)
                an_block.append(0.0)
                miss["anchors"] = {"f1": 0.0, "block_acc": 0.0}
            miss["fields"] = {"acc": 0.0, "n": len(FIELDS) + 1}
            # Fields are zeroed outright rather than run through `fields()`. An empty record would
            # otherwise be CREDITED for the fields gold says are absent — null matching null — so an
            # arm that answered nothing would score 50% on furniture. Reporting nothing is not the
            # same as correctly reporting an absence.
            fld_n += len(FIELDS) + 1
            fr, frn = foreign_runs(blank, gold)
            if fr is not None:
                fr_n += frn
            continue
        out["pages_present"] += 1
        arm = recs[pg]

        rec = {}
        b, w = body_accuracy(arm, gold)
        if b is not None:
            body_s.append(b)
            body_w.append(w)
            rec["body"] = round(b, 4)
            # Carried so the bootstrap can weight body exactly as the point estimate does. Without
            # it the interval is computed on a DIFFERENT statistic — an unweighted mean — and on a
            # set with one near-empty page and one very dense one the published score can fall
            # outside its own confidence interval.
            rec["body_w"] = w
        s = block_sequence(arm, gold)
        if s is not None:
            seq.append(s)
            rec["sequence"] = round(s, 4)
        h, hn = heading_placement(arm, gold)
        if h is not None:
            head_hits += h * hn
            head_n += hn
            rec["heading"] = round(h, 4)
        f = footnotes(arm, gold)
        if f["f1"] is not None:
            fn_f1.append(f["f1"])
            # `text_acc` is None where gold has NO notes and the arm invented some: identity is
            # scored 0, but there is no gold text to compare against, so text has no denominator on
            # that page. Appending the None made the mean unsummable.
            if f["text_acc"] is not None:
                fn_text.append(f["text_acc"])
            if f["marker_exact"] is not None:
                fn_marker.append(f["marker_exact"])
            rec["notes"] = f
        a = anchors(arm, gold)
        if a["f1"] is not None:
            an_f1.append(a["f1"])
            if a["block_acc"] is not None:
                an_block.append(a["block_acc"])
            rec["anchors"] = a
        fl = fields(arm, gold)
        fld_hit += fl["acc"] * fl["n"]
        fld_n += fl["n"]
        rec["fields"] = fl
        fr, frn = foreign_runs(arm, gold)
        if fr is not None:
            fr_hits += fr * frn
            fr_n += frn
            rec["foreign"] = round(fr, 4)
        out["per_page"][pg] = rec

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    # Body accuracy is weighted by gold length: a long page is more of the book than a short one.
    body = round(sum(s * w for s, w in zip(body_s, body_w)) / sum(body_w), 4) if body_w else None
    out["scores"] = {
        "body_accuracy":      {"v": body,            "n": len(body_s), "of": len(pages)},
        "block_sequence":     {"v": mean(seq),       "n": len(seq),    "of": len(pages)},
        "heading_placement":  {"v": round(head_hits / head_n, 4) if head_n else None,
                              "n": head_n, "of": head_n},
        "footnote_f1":        {"v": mean(fn_f1),     "n": len(fn_f1),  "of": len(pages)},
        "footnote_text":      {"v": mean(fn_text),   "n": len(fn_text), "of": len(pages)},
        "marker_exact":       {"v": mean(fn_marker), "n": len(fn_marker), "of": len(pages)},
        "anchor_f1":          {"v": mean(an_f1),     "n": len(an_f1),  "of": len(pages)},
        "anchor_placement":   {"v": mean(an_block),  "n": len(an_block), "of": len(pages)},
        "fields":             {"v": round(fld_hit / fld_n, 4) if fld_n else None,
                              "n": int(fld_n), "of": len(pages) * 4},
        "foreign_runs":       {"v": round(fr_hits / fr_n, 4) if fr_n else None,
                              "n": fr_n, "of": fr_n},
    }
    return out


# ------------------------------------------------------------------ the verdict

# The recommendation rule, written down BEFORE the scores were looked at so it cannot be tuned to
# produce a favourite. An arm must clear every gate to be recommendable at all; among those that do,
# the ranking is the weighted task score, and cost breaks ties inside the noise band.
GATES = {
    # None = "every gold page there is", resolved at scoring time. It must NOT be a literal: the
    # evaluation set is whatever `truth/gold/` actually holds, and a hardcoded 8 against a gold set
    # of 7 would fail every arm on a gate about the harness rather than about the models — and the
    # report would announce that no model can do the task.
    "pages_present": None,     # it must actually answer every page
    "body_accuracy": 0.95,     # the prose has to be readable
    "footnote_f1": 0.80,       # the apparatus has to be separated correctly
    "anchor_f1": 0.80,         # the links have to point at real notes
}

WEIGHTS = {          # what the product actually depends on
    "body_accuracy": 0.35,     # the text is most of the value
    "footnote_text": 0.15,     # notes are displayed, not just counted
    "anchor_placement": 0.15,  # tap-to-open only works if the anchor is in the right block
    "block_sequence": 0.10,    # reconstruction order
    "heading_placement": 0.10, # the reason P2 exists
    "fields": 0.10,            # the furniture
    "marker_exact": 0.05,      # digit-script fidelity
}

# Differences below this are not evidence. One sample per page, 8 pages, no repeated runs: a gap
# of a few tenths of a point cannot be attributed to the model.
NOISE_BAND = 0.01


def task_score(scores: dict) -> tuple[float | None, float]:
    """Weighted composite over whatever the arm could be measured on, plus the weight it covered.

    Coverage is returned alongside the score and must be shown with it: an arm measured on 45% of
    the weight has not earned a comparable number, and a prompt that cannot express blocks or
    anchors is exactly that case.
    """
    total = got = 0.0
    for k, w in WEIGHTS.items():
        v = scores.get(k, {}).get("v")
        if v is None:
            continue
        total += w
        got += w * v
    if not total:
        return None, 0.0
    return round(got / total, 4), round(total, 4)


def bootstrap_ci(per_page: dict, iters: int = 2000, seed: int = 7) -> tuple[float, float] | None:
    """A 90% interval for the task score, by resampling the evaluation pages.

    Eight pages is a small sample and the report must not pretend otherwise. Resampling the pages
    with replacement says how much of a lead would survive a different eight pages drawn the same
    way. It does NOT capture model sampling noise — one run per page — so it is a floor on the
    uncertainty, not the whole of it, and the report says so where the interval appears.

    The seed is fixed so the published interval is reproducible.
    """
    import random

    rows = []
    for pg, rec in per_page.items():
        # A missing page is NOT special-cased here. score_arm writes its zeroed values into the same
        # keys a scored page uses, so the same code path reads both — which is what keeps the
        # interval attached to the statistic that was actually published.
        row = {"_w": float(rec.get("body_w") or 1.0)}
        if "body" in rec:
            row["body_accuracy"] = rec["body"]
        if "sequence" in rec:
            row["block_sequence"] = rec["sequence"]
        if "heading" in rec:
            row["heading_placement"] = rec["heading"]
        n = rec.get("notes") or {}
        if n.get("f1") is not None:
            row["footnote_text"] = n.get("text_acc")
            if n.get("marker_exact") is not None:
                row["marker_exact"] = n["marker_exact"]
        a = rec.get("anchors") or {}
        if a.get("block_acc") is not None:
            row["anchor_placement"] = a["block_acc"]
        f = rec.get("fields") or {}
        if f.get("acc") is not None:
            row["fields"] = f["acc"]
        rows.append({k: v for k, v in row.items() if v is not None})
    if len(rows) < 2:
        return None

    def composite(sample):
        tot = got = 0.0
        for k, w in WEIGHTS.items():
            pairs = [(r[k], r.get("_w", 1.0) if k == "body_accuracy" else 1.0)
                     for r in sample if k in r]
            if not pairs:
                continue
            wt = sum(p[1] for p in pairs)
            if not wt:
                continue
            tot += w
            # Body is length-weighted here for the same reason it is in the point estimate, so the
            # interval describes the statistic actually published rather than a nearby one.
            got += w * (sum(v * pw for v, pw in pairs) / wt)
        return got / tot if tot else None

    rng = random.Random(seed)
    out = []
    for _ in range(iters):
        s = [rows[rng.randrange(len(rows))] for _ in rows]
        c = composite(s)
        if c is not None:
            out.append(c)
    if not out:
        return None
    out.sort()
    return round(out[int(.05 * len(out))], 4), round(out[int(.95 * len(out)) - 1], 4)


def paired_diff(a: dict, b: dict, iters: int = 20000, seed: int = 11) -> tuple[float, float] | None:
    """90% interval for a MINUS b, resampling the pages once and scoring both arms on the draw.

    Comparing two marginal intervals for overlap is the wrong test here and it is the conservative
    kind of wrong: both arms are scored on the SAME eight pages, so most of the spread in each
    interval is page difficulty, which is common to both and cancels. Resampling the pages once and
    taking the difference removes it.

    It is also the only test that can produce a coherent statement. Non-overlap of marginal
    intervals is not transitive, so ranking by it produced a "tied group" that excluded an arm with
    a HIGHER score than one it included.
    """
    import random

    def rows(arm):
        out = {}
        for pg, rec in arm.get("per_page", {}).items():
            r = {"_w": float(rec.get("body_w") or 1.0)}
            if "body" in rec:
                r["body_accuracy"] = rec["body"]
            if "sequence" in rec:
                r["block_sequence"] = rec["sequence"]
            if "heading" in rec:
                r["heading_placement"] = rec["heading"]
            n = rec.get("notes") or {}
            if n.get("text_acc") is not None:
                r["footnote_text"] = n["text_acc"]
            if n.get("marker_exact") is not None:
                r["marker_exact"] = n["marker_exact"]
            an = rec.get("anchors") or {}
            if an.get("block_acc") is not None:
                r["anchor_placement"] = an["block_acc"]
            fl = rec.get("fields") or {}
            if fl.get("acc") is not None:
                r["fields"] = fl["acc"]
            out[str(pg)] = r
        return out

    ra, rb = rows(a), rows(b)
    keys = sorted(set(ra) & set(rb))
    if len(keys) < 2:
        return None

    def comp(sample, table):
        tot = got = 0.0
        for k, w in WEIGHTS.items():
            pairs = [(table[p][k], table[p].get("_w", 1.0) if k == "body_accuracy" else 1.0)
                     for p in sample if k in table[p]]
            if not pairs:
                continue
            wt = sum(x[1] for x in pairs)
            if not wt:
                continue
            tot += w
            got += w * (sum(v * pw for v, pw in pairs) / wt)
        return got / tot if tot else None

    rng = random.Random(seed)
    diffs = []
    for _ in range(iters):
        s = [keys[rng.randrange(len(keys))] for _ in keys]
        ca, cb = comp(s, ra), comp(s, rb)
        if ca is not None and cb is not None:
            diffs.append(ca - cb)
    if not diffs:
        return None
    diffs.sort()
    return round(diffs[int(.05 * len(diffs))], 4), round(diffs[int(.95 * len(diffs)) - 1], 4)


def lopo(a: dict, b: dict) -> dict | None:
    """Drop each evaluation page in turn: how much of `a`'s lead over `b` is one page?

    Eight pages chosen as extremes means any one of them can carry a result. A lead that evaporates
    when a single page is removed is a fact about that page, not about the model, and a reader
    deciding what to run is entitled to know which. Returns the worst and best remaining gap and
    names the page whose removal hurts `a` most.
    """
    pages = sorted(set(a.get("per_page", {})) & set(b.get("per_page", {})))
    if len(pages) < 3:
        return None
    out = []
    for drop in pages:
        keep = [p for p in pages if p != drop]
        sa = task_score(_scores_over(a, keep))[0]
        sb = task_score(_scores_over(b, keep))[0]
        if sa is not None and sb is not None:
            out.append((round(sa - sb, 4), drop))
    if not out:
        return None
    out.sort()
    return {"min": out[0][0], "min_page": out[0][1],
            "max": out[-1][0], "max_page": out[-1][1]}


def _scores_over(arm: dict, pages: list) -> dict:
    """Recompute an arm's aggregate over a SUBSET of pages, in the shape task_score expects."""
    acc_: dict[str, list] = {}
    wts: dict[str, list] = {}
    for pg in pages:
        rec = arm["per_page"].get(pg) or arm["per_page"].get(str(pg)) or {}
        def put(k, v, w=1.0):
            if v is None:
                return
            acc_.setdefault(k, []).append(v)
            wts.setdefault(k, []).append(w)
        put("body_accuracy", rec.get("body"), float(rec.get("body_w") or 1.0))
        put("block_sequence", rec.get("sequence"))
        put("heading_placement", rec.get("heading"))
        n = rec.get("notes") or {}
        put("footnote_text", n.get("text_acc"))
        put("marker_exact", n.get("marker_exact"))
        an = rec.get("anchors") or {}
        put("anchor_placement", an.get("block_acc"))
        fl = rec.get("fields") or {}
        put("fields", fl.get("acc"))
    return {k: {"v": (sum(v * w for v, w in zip(vals, wts[k])) / sum(wts[k]))
                if sum(wts[k]) else None}
            for k, vals in acc_.items()}


def separated(a: dict, b: dict) -> bool:
    """Does `a` beat `b` by more than this evidence can explain away?

    The PAIRED difference interval must exclude zero, and the point gap must clear the noise band.
    Both, because eight pages of one sample each will happily produce a hairline interval that
    excludes zero on a difference nobody should act on.
    """
    ta, tb = a.get("task_score"), b.get("task_score")
    if ta is None or tb is None or ta - tb < NOISE_BAND:
        return False
    d = paired_diff(a, b)
    if not d or d[0] <= 0:
        return False
    # THIRD CONDITION, and the one that does the work. Eight deliberately extreme pages means a
    # single page can carry a result: on this set the leader's paired interval excludes zero against
    # three arms, yet its lead over them falls to +0.15, +0.39 and +0.73 points — all inside the
    # noise band — when one page is dropped. A lead that one page can erase is a fact about that
    # page. It must survive the removal of ANY single page by more than the band, or it is not a
    # separation this benchmark will claim.
    lo = lopo(a, b)
    return bool(lo and lo["min"] >= NOISE_BAND)


def gate_failures(arm: dict) -> list[str]:
    out = []
    need = GATES["pages_present"] or len(eval_pages())
    if arm.get("pages_present", 0) < need:
        out.append(f"answered {arm.get('pages_present', 0)}/{need} pages")
    for k in ("body_accuracy", "footnote_f1", "anchor_f1"):
        v = arm["scores"].get(k, {}).get("v")
        if v is None:
            out.append(f"{k} not measurable")
        elif v < GATES[k]:
            out.append(f"{k} {v:.3f} < {GATES[k]}")
    return out

"""Self-check for the gold metrics: each assert is a way the old scoring was wrong.

    python tools/test_gold.py

These are not unit tests for their own sake. Every case below is a real failure this benchmark
published at some point — a hoisted heading scoring the same as a placed one, an invented note
scoring 1.0, `٧٢` passing against `٧٣`, an arm improving its average by returning nothing. If a
change makes one of these pass silently again, the score stops meaning what the report says.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gold as G  # noqa: E402
from metrics import from_blocks  # noqa: E402

A = "المقدمة في الكتاب"  # المقدمة في الكتاب
B = "الفصل السادس"                          # الفصل السادس
C = "وقال القديس يوستينوس"  # وقال القديس يوستينوس
NOTE = "انظر المرجع السابق"          # انظر المرجع السابق


def gold_page(**over):
    rec = {
        "page": 99,
        "runningHeader": A,
        "printedPageNumber": "٧٣",          # ٧٣
        "printerMark": None,
        "blocks": [
            {"type": "paragraph", "text": C * 6, "noteRefs": [1]},
            {"type": "heading", "text": B, "noteRefs": []},
            {"type": "paragraph", "text": C * 6, "noteRefs": [2]},
        ],
        "footnotes": [
            {"marker": "١", "number": 1, "text": NOTE, "continuedFromPreviousPage": False},
            {"marker": "2", "number": 2, "text": NOTE + " 2", "continuedFromPreviousPage": False},
        ],
        "foreignRuns": [],
        "uncertain": [],
    }
    rec.update(over)
    return from_blocks(rec)


def close(a, b, eps=1e-6):
    return a is not None and abs(a - b) < eps


def main() -> None:
    g = gold_page()

    # 1. A perfect reading scores perfectly on every measure. If this fails, nothing below means
    #    anything.
    same = gold_page()
    assert close(G.body_accuracy(same, g)[0], 1.0)
    assert close(G.block_sequence(same, g), 1.0)
    assert close(G.heading_placement(same, g)[0], 1.0)
    f = G.footnotes(same, g)
    assert close(f["f1"], 1.0) and close(f["text_acc"], 1.0) and close(f["marker_exact"], 1.0)
    a = G.anchors(same, g)
    assert close(a["f1"], 1.0) and close(a["block_acc"], 1.0)
    assert close(G.fields(same, g)["acc"], 1.0)

    # 2. THE HOISTED HEADING. Same three blocks, same text, heading moved to the top of the page —
    #    which is precisely the failure P2 was introduced to make visible, and which every previous
    #    version of this scorer graded identically to a correct reading.
    hoisted = gold_page(blocks=[
        {"type": "heading", "text": B, "noteRefs": []},
        {"type": "paragraph", "text": C * 6, "noteRefs": [1]},
        {"type": "paragraph", "text": C * 6, "noteRefs": [2]},
    ])
    assert close(G.heading_placement(hoisted, g)[0], 0.0), "a hoisted heading must not score"
    assert close(G.body_accuracy(hoisted, g)[0], 1.0), "...and its prose is still correct"

    # 2b. THE SPLIT PARAGRAPH. Same heading, same place on the page, but the paragraph above it is
    #     returned as two blocks instead of one — a judgement call about the printed layout, not a
    #     misplacement. Measuring position by block INDEX failed this: an arm that split the psalm
    #     quotation off from the commentary on p093 was marked wrong for a defensible reading.
    split = gold_page(blocks=[
        {"type": "paragraph", "text": C * 3, "noteRefs": [1]},
        {"type": "paragraph", "text": C * 3, "noteRefs": []},
        {"type": "heading", "text": B, "noteRefs": []},
        {"type": "paragraph", "text": C * 6, "noteRefs": [2]},
    ])
    assert close(G.heading_placement(split, g)[0], 1.0), \
        "splitting a paragraph must not count as misplacing the heading"

    # 2c. THE SHORT OPENING PARAGRAPH. When gold's heading sits after only a little prose, its
    #     text-fraction is small — and a heading hoisted to the very top of the page then lands
    #     INSIDE the tolerance and passes on the arithmetic alone. Position must also mean "has
    #     prose above it", as gold does.
    short_gold = gold_page(blocks=[
        {"type": "paragraph", "text": C, "noteRefs": []},
        {"type": "heading", "text": B, "noteRefs": []},
        {"type": "paragraph", "text": C * 20, "noteRefs": []},
    ])
    hoisted_short = gold_page(blocks=[
        {"type": "heading", "text": B, "noteRefs": []},
        {"type": "paragraph", "text": C, "noteRefs": []},
        {"type": "paragraph", "text": C * 20, "noteRefs": []},
    ])
    assert close(G.heading_placement(hoisted_short, short_gold)[0], 0.0), \
        "a heading hoisted above all prose must fail even when the fraction is close"

    # 3. THE INVENTED APPARATUS. A model that hallucinates a note AND an anchor for it is perfectly
    #    self-consistent. Against gold it is simply wrong.
    empty_gold = gold_page(blocks=[{"type": "paragraph", "text": C * 6, "noteRefs": []}],
                           footnotes=[])
    invented = gold_page(blocks=[{"type": "paragraph", "text": C * 6, "noteRefs": [2, 3]}],
                         footnotes=[{"marker": "2", "number": 2, "text": NOTE,
                                     "continuedFromPreviousPage": False},
                                    {"marker": "3", "number": 3, "text": NOTE,
                                     "continuedFromPreviousPage": False}])
    assert close(G.anchors(invented, empty_gold)["f1"], 0.0), "invented anchors must score 0"
    assert close(G.footnotes(invented, empty_gold)["f1"], 0.0), "invented notes must score 0"

    # 4. THE PAGE NUMBER. ٧٢ is not ٧٣, and Arabic-Indic ٧٣ is not Extended Arabic-Indic ۷۳.
    assert G.fields(gold_page(printedPageNumber="٧٢"), g)["detail"]["printedPageNumber"] is False
    assert G.fields(gold_page(printedPageNumber="۷۳"), g)["detail"]["printedPageNumber"] is False
    assert G.fields(gold_page(printedPageNumber="٧٣"), g)["detail"]["printedPageNumber"] is True

    # 5. SILENCE IS NOT SAFETY. Returning no body for a page that has one is a failure, not an
    #    omission — the old scorer dropped it from the denominator, so skipping hard pages RAISED
    #    an arm's average.
    assert close(G.body_accuracy(gold_page(blocks=[]), g)[0], 0.0)

    # 6. A NOTE COUNTED IS NOT A NOTE READ. Right count, right numbers, wrong text.
    wrong_text = gold_page(footnotes=[
        {"marker": "١", "number": 1, "text": "لا شيء",
         "continuedFromPreviousPage": False},
        {"marker": "2", "number": 2, "text": "لا شيء",
         "continuedFromPreviousPage": False}])
    fw = G.footnotes(wrong_text, g)
    assert close(fw["f1"], 1.0), "identity is still perfect"
    assert fw["text_acc"] < 0.5, "but the text is not"

    # 7. THE MARKER GLYPH. Note 2 is printed as a Western `2` among Arabic-Indic markers; an arm
    #    that regularises it to ٢ has corrupted the apparatus while reading the number correctly.
    regularised = gold_page(footnotes=[
        {"marker": "١", "number": 1, "text": NOTE, "continuedFromPreviousPage": False},
        {"marker": "٢", "number": 2, "text": NOTE + " 2", "continuedFromPreviousPage": False}])
    fr = G.footnotes(regularised, g)
    assert close(fr["f1"], 1.0) and close(fr["text_acc"], 1.0)
    assert close(fr["marker_exact"], 0.5), "one of two markers is the wrong glyph"

    # 8. THE ANCHOR IN THE WRONG BLOCK. Both anchors present, both pointing at real notes, but
    #    swapped between paragraphs — the links exist and start from the wrong place. Identity
    #    cannot see this; placement must.
    swapped = gold_page(blocks=[
        {"type": "paragraph", "text": C * 6 + " x", "noteRefs": [2]},
        {"type": "heading", "text": B, "noteRefs": []},
        {"type": "paragraph", "text": "y " + C * 6, "noteRefs": [1]},
    ])
    asw = G.anchors(swapped, g)
    assert close(asw["f1"], 1.0), "both anchors point at real notes"
    assert close(asw["block_acc"], 0.0), "but both start from the wrong paragraph"

    # 9. COVERAGE IS REPORTED, NOT ASSUMED. A prompt with no blocks cannot be scored on sequence or
    #    anchors, and must return None — never 0, which would read as "tried and failed".
    flat = {"body": [C * 6], "footnotes": [], "runningHeader": A,
            "printedPageNumber": "٧٣", "printerMark": None}
    assert G.block_sequence(flat, g) is None
    assert G.anchors(flat, g)["f1"] is None
    score, covered = G.task_score({"body_accuracy": {"v": 1.0}, "fields": {"v": 1.0}})
    assert covered < 0.5, "an arm measured on less weight must say so"

    # 9b. ONE MISREAD DIGIT IS ONE ERROR, NOT FOUR. An arm reads both notes correctly and anchors
    #     both in the right paragraph, but reads the raised markers ١٣٨/١٣٩ as 128/129. Keying note
    #     text on `number` charged that single mistake against note text, marker fidelity, anchor
    #     identity AND anchor placement — four zeros for one error, which moved a real arm's
    #     composite by roughly five points.
    renumbered = gold_page(
        blocks=[
            {"type": "paragraph", "text": C * 6, "noteRefs": [11]},
            {"type": "heading", "text": B, "noteRefs": []},
            {"type": "paragraph", "text": C * 6, "noteRefs": [12]},
        ],
        footnotes=[
            {"marker": "١١", "number": 11, "text": NOTE, "continuedFromPreviousPage": False},
            {"marker": "١٢", "number": 12, "text": NOTE + " 2", "continuedFromPreviousPage": False},
        ])
    fr2 = G.footnotes(renumbered, g)
    assert close(fr2["f1"], 0.0), "wrong numbers must still fail note IDENTITY"
    assert close(fr2["marker_exact"], 0.0), "...and must still fail MARKER fidelity"
    assert close(fr2["text_acc"], 1.0), "but the note TEXT was read correctly and must score so"
    ar2 = G.anchors(renumbered, g)
    assert close(ar2["f1"], 0.0), "anchor identity is wrong, and is charged"
    assert close(ar2["block_acc"], 1.0), "but each anchor IS in the right paragraph"

    # 10. NOT ANSWERING A PAGE IS THE WORST SCORE, NOT NO SCORE. An arm that skips the hard page
    #     must not thereby remove it from its own denominator — that is how the agreement layer
    #     flattered the majority, and the first version of score_arm reproduced it exactly, docking
    #     only the body while heading, footnote and anchor scores were computed over what was left.
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "p099.json").write_text(json.dumps(gold_page()), encoding="utf-8")
        real_gold, G.GOLD = G.GOLD, tmp
        answered = G.score_arm({99: gold_page()})
        skipped = G.score_arm({})
        G.GOLD = real_gold
    except Exception:
        G.GOLD = real_gold
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for key in ("body_accuracy", "block_sequence", "heading_placement",
                "footnote_f1", "footnote_text", "marker_exact", "anchor_f1", "fields"):
        a, s = answered["scores"][key], skipped["scores"][key]
        assert close(a["v"], 1.0), f"{key}: a correct answer should score 1.0, got {a['v']}"
        assert s["v"] is not None, f"{key}: skipping the page must not erase the metric"
        assert close(s["v"], 0.0), f"{key}: skipping the page must score 0, got {s['v']}"
        assert s["n"] == a["n"], f"{key}: denominator changed when the arm skipped the page"

    # 11. THE POINT ESTIMATE MUST LIE INSIDE ITS OWN INTERVAL. The aggregate weights body accuracy
    #     by gold page length; if the bootstrap does not, the two are different statistics and a
    #     published score can sit outside the confidence interval attached to it — which a reader is
    #     entitled to treat as proof the numbers are unrelated.
    per_page = {
        1: {"body": 0.99, "body_w": 2000, "fields": {"acc": 1.0}},
        2: {"body": 0.60, "body_w": 40, "fields": {"acc": 1.0}},
        3: {"body": 0.98, "body_w": 1800, "fields": {"acc": 0.75}},
        4: {"body": 0.97, "body_w": 1500, "fields": {"acc": 1.0}},
    }
    scores = {
        "body_accuracy": {"v": round(sum(p["body"] * p["body_w"] for p in per_page.values())
                                     / sum(p["body_w"] for p in per_page.values()), 4)},
        "fields": {"v": round(sum(p["fields"]["acc"] for p in per_page.values())
                              / len(per_page), 4)},
    }
    ts, _ = G.task_score(scores)
    lo, hi = G.bootstrap_ci(per_page, iters=3000)
    assert lo <= ts <= hi, f"task score {ts} outside its own interval {lo}-{hi}"

    print("all gold metric checks passed")


if __name__ == "__main__":
    main()

# Results

11 arms scored across 20 pages of a printed Arabic patristic edition. Generated from `results.json` — do not edit by hand.

## The answer — which model performs the task

Measured on **8 pages** (p15, p24, p25, p30, p36, p39, p52, p93) against `truth/gold/`: a reading produced outside this field of arms, double-keyed and adjudicated against the page image. Same reference for every arm, and it does not move when the field changes. **This is the only section of this document that is accuracy.**

**Gemini 3.7 Flash** has the highest score, and on 8 pages this evidence **cannot distinguish it from Gemini 3.5 Flash, Claude Sonnet 5, Qwen 3.8 Max**. Any of those performs the task; the ordering between them is not a result, so choose on cost and on the specific failure each one still has.

**A limit worth stating.** GPT 5.6 Terra, Kimi K3 score lower than all of them, but the gap does not survive removing a single evaluation page for every member of the shortlist. On this evidence they are behind, not beaten.

| model | task score | 90% CI | body | heading pos | notes | note text | anchors | anchor pos | fields | markers | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Gemini 3.7 Flash | 99.9% | 99.8–100.0 | 99.8% | 100.0% | 100.0% | 99.7% | 100.0% | 100.0% | 100.0% | 100.0% | clears |
| Gemini 3.5 Flash | 98.8% | 97.7–99.6 | 99.8% | 100.0% | 100.0% | 99.5% | 100.0% | 100.0% | 96.9% | 91.7% | clears |
| Claude Sonnet 5 | 98.8% | 96.9–99.8 | 98.8% | 100.0% | 100.0% | 98.8% | 100.0% | 100.0% | 100.0% | 100.0% | clears |
| Qwen 3.8 Max | 98.7% | 97.3–99.9 | 99.7% | 100.0% | 83.3% | 99.7% | 83.3% | 100.0% | 100.0% | 83.3% | clears |
| GPT 5.6 Terra | 96.7% | 94.9–98.0 | 98.7% | 100.0% | 88.9% | 99.5% | 85.0% | 94.4% | 93.8% | 83.3% | clears |
| Kimi K3 | 96.2% | 93.8–97.9 | 97.8% | 100.0% | 88.9% | 99.9% | 83.3% | 100.0% | 84.4% | 88.9% | clears |
| DeepSeek V4 Flash Vision | 86.4% | 73.5–95.0 | 91.3% | 100.0% | 50.0% | 80.5% | 50.0% | 89.3% | 75.0% | 50.8% | body_accuracy 0.913 < 0.95; footnote_f1 0.500 < 0.8; anchor_f1 0.500 < 0.8 |
| GLM 5.3 Flash | 84.9% | 72.0–93.9 | 76.1% | 100.0% | 66.7% | 91.6% | 48.5% | 80.6% | 90.6% | 66.7% | body_accuracy 0.761 < 0.95; footnote_f1 0.667 < 0.8; anchor_f1 0.485 < 0.8 |
| Claude Haiku 4.5 | 78.0% | 70.0–84.0 | 88.1% | 100.0% | 77.8% | 95.5% | 16.7% | 13.9% | 87.5% | 77.8% | body_accuracy 0.881 < 0.95; footnote_f1 0.778 < 0.8; anchor_f1 0.167 < 0.8 |
| GPT 5.6 Luna | 70.9% | 49.7–85.9 | 75.8% | 100.0% | 54.3% | 51.8% | 47.6% | 50.0% | 93.8% | 43.6% | body_accuracy 0.758 < 0.95; footnote_f1 0.543 < 0.8; anchor_f1 0.476 < 0.8 |
| MiMo v2.5 | 44.4% | 12.9–66.8 | 40.4% | 100.0% | 46.7% | 40.4% | 44.5% | 33.3% | 37.5% | 16.7% | answered 4/8 pages; body_accuracy 0.404 < 0.95; footnote_f1 0.467 < 0.8; anchor_f1 0.445 < 0.8 |

**The rule was fixed before the scores were read.** Gates: all 8 evaluation pages answered, `body_accuracy` ≥ 0.95, `footnote_f1` ≥ 0.8, `anchor_f1` ≥ 0.8. Among arms that clear them, the ranking is a weighted score over what the product depends on — prose 35%, note text 15%, anchor placement 15%, block order 10%, heading position 10%, fields 10%, marker fidelity 5%.

**What the gold scoring added that was missing.** Heading *position*, footnote *text*, marker *glyph* and anchor *linkage* were all previously unscored — a model could ace every published P2 metric while returning notes with the wrong text and anchors that link from the wrong paragraph. Anchor consistency, in particular, used to be self-consistency: a model that invented a note and an anchor for it scored 1.0. It is now scored against gold, where an invented anchor is a false positive.

## Agreement between arms — not accuracy, and it cannot rank a model

Everything below compares an arm to the *other arms*, over all 20 pages. It answers "how conventional is this reading?", which is useful for spotting an outlier and useless for picking a winner: the reference moves when the field changes, correlated arms can define it, and an error every model makes passes unseen. Read it as diagnosis, not as a score.

| arm | pages | body agreement | fields | footnotes | anchor self-consistency | fails | $/page |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen 3.8 Max · blocks | 20 | 99.09% | 100% | 100% | 92% | 0 | $0.00826 |
| Gemini 3.5 Flash · blocks | 20 | 99.05% | 97% | 100% | 92% | 0 | $0.00069 |
| Claude Sonnet 5 · blocks | 20 | 98.98% | 100% | 100% | 92% | 0 | $0.01517 |
| Gemini 3.7 Flash · blocks | 20 | 98.87% | 100% | 100% | 92% | 0 | $0.00070 |
| Kimi K3 · blocks | 20 | 98.28% | 92% | 94% | 85% | 0 | $0.01542 |
| GPT 5.6 Luna · blocks | 20 | 97.97% | 97% | 76% | 43% | 0 | $0.00096 |
| GPT 5.6 Terra · blocks | 20 | 95.51% | 97% | 94% | 87% | 0 | $0.01100 |
| DeepSeek V4 Flash Vision · blocks | 20 | 93.75% | 88% | 88% | 86% | 0 | $0.00051 |
| Claude Haiku 4.5 · blocks | 20 | 91.55% | 86% | 94% | 17% | 0 | $0.00507 |
| GLM 5.3 Flash · blocks | 20 | 89.89% | 94% | 81% | 70% | 1 | $0.00062 |

**Partial runs** — reported, never ranked:

| arm | pages | transcript | fields | footnotes | anchors | fails | $/page |
|---|---:|---:|---:|---:|---:|---:|---:|
| MiMo v2.5 · blocks | 14 | 79.01% | 81% | 79% | 36% | 0 | $0.00049 |
**Best transcript accuracy:** Qwen 3.8 Max · blocks at 99.09%.
**Cheapest priced arm:** DeepSeek V4 Flash Vision · blocks at $0.00051 per page.

## How to read these numbers

- **transcript** — the prose, scored against the medoid reading of the *other* arms. There is
  no gold transcription of this corpus, so this measures agreement, not truth: a mistake every
  model makes would pass unnoticed. **Pages with under 200 characters of reference body are
  not scored** — CER divides by the reference length, so on a half-title page a handful of
  characters produced rates above 6.0 and one page dominated every average. Mis-filing title
  text as body is a real error, but `fields` and `body purity` are the instruments for it.
- **fields** — running head, page title, section heading, printed page number, printer mark,
  each in its own place. Leave-one-out against the other arms; three hand-read pages are fixed.
- **footnotes** — share of pages with exactly the right number of notes.
- **anchor self-consistency** — do the inline footnote references in the text account for the
  notes below the rule? This is self-consistency, not correctness: a model that invents a note
  and an anchor for it agrees with itself perfectly. Anchors are scored for real against gold
  in the section above; this column is a diagnostic only.
- **fails** — pages where the model returned nothing usable. Counted, never averaged away.
- **$/page** — measured token counts where the API reported them, otherwise derived from
  measured output characters through a calibrated constant. Subscription-routed arms are
  priced at the vendor's published rate on measured volume. Gemini figures exclude thinking tokens.

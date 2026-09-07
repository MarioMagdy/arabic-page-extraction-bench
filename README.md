# Arabic page-extraction benchmark

**Which vision model should read a scanned Arabic scholarly book, and at what price?**

I build a reading app over digitised Arabic patristic texts. Its OCR stage is a vision model
reading page images, and an audit of 100 production pages found 365 defects, 75% of them
structural: running heads and page numbers in the body, footnotes merged. So the request was
rewritten to ask for the structure explicitly, and this repo is how the model behind it was chosen.
14 arms across 13 models, one request, 20 pages, the same images for every arm.

![Task score against price per page, one point per model](assets/accuracy-vs-cost.png)

## The answer

Scored on 8 pages against an independent reference. Full tables in [RESULTS.md](RESULTS.md), every
page and every reading in the [interactive report](https://mariomagdy.github.io/arabic-page-extraction-bench/).

| model | task score | 90% band | $/page | 461-page book |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash | 99.9% | 99.8–100.0 | $0.00070 | $0.32 |
| Gemini 3.8 Flash | 99.6% | 98.9–99.9 | $0.00507 | $2.34 |
| Gemini 3.5 Flash | 98.8% | 97.7–99.6 | $0.00069 | $0.32 |
| Claude Sonnet 5 | 98.8% | 96.9–99.8 | $0.01517 | $6.99 |
| Qwen 3.8 Max | 98.7% | 97.3–99.9 | $0.00826 | $3.81 |
| Gemini 3.8 Flash, thinking off | 98.2% | 97.2–99.0 | $0.00501 | $2.31 |
| GPT 5.6 Terra | 96.7% | 94.9–98.0 | $0.01100 | $5.07 |
| Kimi K3 | 96.2% | 93.8–97.9 | $0.01542 | $7.11 |

Gemini 2.5 Flash, DeepSeek V4 Flash Vision, GLM 5.3 Flash, Claude Haiku 4.5, GPT 5.6 Luna and
MiMo v2.5 fail one or more gates and are reported but not ranked.

- **The top five cannot be separated on 8 pages, and they span 22× in price.** Pick on cost.
- **This benchmark cannot price Gemini 3.8 Flash against 3.7 Flash, and does not claim to.** The
  two are indistinguishable on accuracy (99.6% and 99.9%, overlapping bands, both in the tied
  group), and they emit the same volume: every Gemini arm here returns 3.1-3.2 KB per page. So the
  gap in the cost column is not a measurement, it is the ratio of two assumptions — 3.7 is priced
  by *proxy* at Gemini 3.5 Flash's published rate, 3.8 by a rate *derived* from metered billing.
  Neither is a published price for the model it is attached to. Until Google's rate card for both
  is quotable, read the Gemini rows as accuracy results with an indicative price, not as a price
  comparison. The one Gemini cost comparison that does hold is 3.8 against itself, below, where the
  rate cancels.
- **Turn thinking off — and here is what it actually costs.** Every Gemini price in the table
  excludes thinking tokens, so the table cannot show this and the two 3.8 arms misleadingly read
  as the same price. Measured on this benchmark's own run, same prompt and same images: Gemini 3.8
  Flash bills **$6.82** a book with thinking on and **$2.31** with it off, a 3× cut. This is the
  one Gemini price comparison the evidence supports on its own: same model, same rate, so the
  rate assumption cancels and what remains is measured token volume. Thinking is
  75% of its output. The accuracy it buys is small but not nothing — 99.6% → 98.2%, still clearing
  every gate. Body accuracy barely moves (99.8% → 99.7%); what degrades is marker fidelity
  (100% → 80.6%) and fields (96.9% → 93.8%). The production run in
  [measured_production/FINDINGS.md](measured_production/FINDINGS.md) reported thinking-off as free,
  but it scored body accuracy alone, which is exactly the measure that does not move.
- **The model production already shipped on is the wrong one.** Gemini 2.5 Flash places every
  gold anchor correctly but misreads the prose: 87.5%, failing the body-accuracy gate at 0.879.
  It also costs 3.7× Gemini 3.5 Flash, which scores 98.8% — and unlike the 3.7-vs-3.8 comparison
  above, both sides of that one are published list rates, so the ratio is real. Older and cheaper
  are not the same thing.

## How it is scored

Every arm answers the same instruction, `prompts/P2_blocks.txt`: an ordered sequence of typed
blocks with footnote anchors, plus running head, page number, and the notes with their markers.

The 8 evaluation pages were chosen on printed features before any scoring. Each was transcribed
twice, independently, by a model outside the ranked set (Claude Opus 5), and every disagreement
was settled against the page image (`truth/ADJUDICATION_LOG.md`). Gates and weights were fixed
before the scores were read: all 8 pages answered, body accuracy ≥ 0.95, footnote F1 ≥ 0.8,
anchor F1 ≥ 0.8, then a weighted score over prose, note text, anchor placement, block order,
heading position, fields and marker fidelity. The other 12 pages are scored as agreement between
arms, leave-one-out, and never rank a model.

Costs are list rates on measured output; the constant behind them was calibrated against real
billing. Subscription-routed runs say so in `arms.yaml`.

## The corpus

20 pages of a 461-page Arabic edition of Justin Martyr, *الدفاعان والحوار مع تريفون*: running
heads, a dense footnote apparatus, Arabic-Indic page numbers, Greek and Latin inside right-to-left
prose. The ancient text is public domain; the edition's translation and apparatus are modern work,
included here (4% of the book) for the non-commercial purpose of evaluating extraction tools.
Credits from its own page 3: translation Amal Fouad; review Irini Thabet George, Mariam Saad Mina,
Girgis Gamal Fayez, Wagdi Rizk Ghali, Emad Maurice Iskandar; introduction and final review Joseph
Maurice Faltas. Rights holders who want the pages removed: open an issue.

## Run it

```
pip install -r requirements.txt
python tools/score.py && python tools/results_md.py && python tools/chart.py && python tools/build.py
python tools/hero.py && python tools/social.py
python tools/test_gold.py
```

To add a model: add a block to `arms.yaml`, write its outputs to `runs/<id>/pNNN.json` in the
prompt's schema, run the line above.

Not done: gold on the other 12 pages (the only thing that could separate the top five), repeated
runs, open-weight models.

## License

Code under [MIT](LICENSE). The page images and transcriptions are the edition's; see above.

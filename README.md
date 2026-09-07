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
| Gemini 3.7 Flash | 99.9% | 99.8–100.0 | $0.00383 | $1.77 |
| Gemini 3.8 Flash | 99.6% | 98.9–99.9 | $0.00507 | $2.34 |
| Gemini 3.5 Flash | 98.8% | 97.7–99.6 | $0.00828 | $3.82 |
| Claude Sonnet 5 | 98.8% | 96.9–99.8 | $0.01517 | $6.99 |
| Qwen 3.8 Max | 98.7% | 97.3–99.9 | $0.00826 | $3.81 |
| Gemini 3.8 Flash, thinking off | 98.2% | 97.2–99.0 | $0.00501 | $2.31 |
| GPT 5.6 Terra | 96.7% | 94.9–98.0 | $0.01100 | $5.07 |
| Kimi K3 | 96.2% | 93.8–97.9 | $0.01542 | $7.11 |

Gemini 2.5 Flash, DeepSeek V4 Flash Vision, GLM 5.3 Flash, Claude Haiku 4.5, GPT 5.6 Luna and
MiMo v2.5 fail one or more gates and are reported but not ranked.

**Every Gemini price in this table changed on 2026-09-07.** Three of the four Gemini rates were
wrong, and the newest model looked expensive only because it was the one priced correctly. See
[Costs](#costs) for what was wrong and what the numbers are now.

- **The top five cannot be separated on 8 pages, and they span 4× in price.** Pick on cost.
- **Gemini 3.7 Flash wins on both axes.** Highest score in the field and the cheapest of the five
  that cannot be separated from it, at $1.77 a book. It is the recommendation.
- **3.7 and 3.8 Flash are on the same rate card**, $0.75/$3.75 per million, so the difference
  between their rows is token volume rather than price: 3.8 spends slightly more to reach a score
  the evidence cannot distinguish from 3.7's. Nothing here argues for moving to the newer model,
  and nothing here says it is worse either.
- **Turn thinking off.** Every price above counts candidate tokens only, so the table cannot show
  this: Gemini 3.8 Flash bills **$6.82** a book with thinking on and **$2.31** with it off, a 3×
  cut, measured on this benchmark's own run with the same prompt and images. Thinking is 75% of its
  output. The accuracy it buys is small but not nothing — 99.6% → 98.2%, still clearing every gate.
  Body accuracy barely moves (99.8% → 99.7%); what degrades is marker fidelity (100% → 80.6%) and
  fields (96.9% → 93.8%). The production run in
  [measured_production/FINDINGS.md](measured_production/FINDINGS.md) reported thinking-off as free,
  but it scored body accuracy alone, which is exactly the measure that does not move.
- **The model production already shipped on is the cheapest Gemini here, and still the wrong one.**
  Gemini 2.5 Flash reads the book for $0.59, a third of 3.7 Flash's price. It also places every
  gold anchor correctly. Then it misreads the prose: 87.5%, failing the body-accuracy gate at
  0.879, with marker fidelity at 33%. Cheap is not the constraint that binds here; being right is.
  It also retires on 2026-10-16.

## Costs

Every price is the vendor's published rate applied to this benchmark's own measured output. Token
counts are measured where the API reported them and otherwise derived from output characters
through a constant calibrated against real billing (2.75 characters per token, confirmed at 2.71
to 2.82 on the arms that report both).

**The Gemini rates were wrong until 2026-09-07,** and the error mattered more than any single
result in this repo. Three of the four were restated:

| model | this repo used | published rate | effect |
|---|---|---|---|
| Gemini 3.5 Flash | $0.15 / $0.60 | $1.50 / $9.00 | understated 10× and 15× |
| Gemini 3.7 Flash | $0.15 / $0.60, by proxy | $0.75 / $3.75 | understated 5× and 6× |
| Gemini 2.5 Flash | $0.30 / $2.50 | $0.15 / $1.25 | overstated 2× |
| Gemini 3.8 Flash | $0.75 / $3.75 | $0.75 / $3.75 | correct |

The 3.7 rate was a proxy borrowed from 3.5, and the 3.5 rate was itself wrong, so the error
compounded across two rows. It made Gemini 3.8 Flash — the only Gemini priced correctly — look
five to six times more expensive than its siblings for no reason a reader could see, and it put a
headline of "$0.32 a book" and "22× in price" on a benchmark whose real figures are $1.77 and 4×.

Gemini 3.7 and 3.8 Flash are quoted at Google's **introductory** rate, which runs to 2026-12-31.
From 2027-01-01 both become $1.50 / $7.50, doubling every Gemini 3.x figure in this repo.

Rates checked 2026-09-07 against
[Google Cloud](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing),
[BenchLM](https://benchlm.ai/google/api-pricing) and
[pricepertoken](https://pricepertoken.com/pricing-page/model/google-gemini-3.8-flash).
Non-Gemini arms carry the vendor's published rate; several were run through a flat-rate
subscription, which `arms.yaml` says per arm.

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

Costs are published rates on measured output; see [Costs](#costs) above, including the rate
correction of 2026-09-07 and the introductory pricing that expires at the end of 2026.

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

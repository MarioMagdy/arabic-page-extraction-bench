# Arabic page-extraction benchmark

**Which vision model should read a scanned Arabic scholarly book, and at what price?**

I build a reading app over digitised Arabic patristic texts. Its OCR stage is a vision model
reading page images, and an audit of 100 production pages found 365 defects, 75% of them
structural: running heads and page numbers in the body, footnotes merged. So the request was
rewritten to ask for the structure explicitly, and this repo is how the model behind it was chosen.
11 models, one request, 20 pages, the same images for every arm.

![Task score against price per page, one point per model](assets/accuracy-vs-cost.png)

## The answer

Scored on 8 pages against an independent reference. Full tables in [RESULTS.md](RESULTS.md), every
page and every reading in the [interactive report](https://mariomagdy.github.io/arabic-page-extraction-bench/).

| model | task score | 90% band | $/page | 461-page book |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash | 99.9% | 99.8–100.0 | $0.00070 | $0.32 |
| Gemini 3.5 Flash | 98.8% | 97.7–99.6 | $0.00069 | $0.32 |
| Claude Sonnet 5 | 98.8% | 96.9–99.8 | $0.01517 | $6.99 |
| Qwen 3.8 Max | 98.7% | 97.3–99.9 | $0.00826 | $3.81 |
| GPT 5.6 Terra | 96.7% | 94.9–98.0 | $0.01100 | $5.07 |
| Kimi K3 | 96.2% | 93.8–97.9 | $0.01542 | $7.11 |

DeepSeek V4 Flash Vision, GLM 5.3 Flash, Claude Haiku 4.5, GPT 5.6 Luna and MiMo v2.5 fail one or
more gates and are reported but not ranked.

- **The top four cannot be separated on 8 pages, and they span 22× in price.** Pick on cost.
- **Turn thinking off.** These Gemini prices exclude thinking tokens. A measured run of the real
  production call ([measured_production/FINDINGS.md](measured_production/FINDINGS.md)) found
  thinking was 74% of Gemini 3.8 Flash's billed output; switching it off kept 99.75% body accuracy
  and cut the price 2.6×, to $0.0027 per page.
- **The old production model cannot use the structured request.** Gemini 2.5 Flash scores 76.5%
  on it, with the wrong block count on 4 of 7 pages.

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
python tools/test_gold.py
```

To add a model: add a block to `arms.yaml`, write its outputs to `runs/<id>/pNNN.json` in the
prompt's schema, run the line above.

Not done: gold on the other 12 pages (the only thing that could separate the top four), repeated
runs, open-weight models.

## License

Code under [MIT](LICENSE). The page images and transcriptions are the edition's; see above.

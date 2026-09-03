# Arabic page-extraction benchmark

**Which vision model should read a scanned Arabic scholarly book, and at what price?**

I needed an answer for a real pipeline: a reading app over digitised Arabic patristic texts, with
tap-to-open footnotes and read-aloud narration. Its OCR stage was a vision model reading page
images, and a 100-page audit of its output found 365 defects, **75% of them structural**: running
head in the body, page number in the body, footnotes merged, footnote text in the body. Not
misreadings. So the request was rewritten to ask for the structure explicitly, and this repo is how
the model behind it was chosen. 11 models, one request, 20 pages, the same images for every arm.

![Task score against price per page, one point per model](assets/accuracy-vs-cost.png)

## The answer

Measured on **8 pages** against `truth/gold/`, a reference produced outside the ranked set (see
[How accuracy is measured](#how-accuracy-is-measured)). Full tables and every arm's failure detail
are in [RESULTS.md](RESULTS.md); the interactive report with every page and every reading is
[here](https://mariomagdy.github.io/arabic-page-extraction-bench/).

| model | task score | 90% band | $/page | 461-page book |
|---|---:|---:|---:|---:|
| Gemini 3.7 Flash | 99.9% | 99.8–100.0 | $0.00070 | $0.32 |
| Gemini 3.5 Flash | 98.8% | 97.7–99.6 | $0.00069 | $0.32 |
| Claude Sonnet 5 | 98.8% | 96.9–99.8 | $0.01517 | $6.99 |
| Qwen 3.8 Max | 98.7% | 97.3–99.9 | $0.00826 | $3.81 |
| GPT 5.6 Terra | 96.7% | 94.9–98.0 | $0.01100 | $5.07 |
| Kimi K3 | 96.2% | 93.8–97.9 | $0.01542 | $7.11 |

Five more models (DeepSeek V4 Flash Vision, GLM 5.3 Flash, Claude Haiku 4.5, GPT 5.6 Luna,
MiMo v2.5) fail one or more gates and are reported but not ranked. Gemini prices count candidate
tokens only, not thinking tokens; see the third bullet.

- **The top four cannot be separated on this evidence, and they span 22× in price.** The leader's
  margin over Sonnet falls to +0.15 points if a single evaluation page is dropped. The decision the
  data supports is: pick on cost, not on rank.
- **The rule was fixed before the scores were read.** Gates: all 8 evaluation pages answered, body
  accuracy ≥ 0.95, footnote F1 ≥ 0.8, anchor F1 ≥ 0.8. Among arms that clear them the ranking is a
  weighted score over what the product depends on: prose 35%, note text 15%, anchor placement 15%,
  block order 10%, heading position 10%, fields 10%, marker fidelity 5%.
- **Turn thinking off.** The benchmark's runners never saw thinking tokens, so its Gemini prices
  are a floor. A later measured run of the real production call against the same gold pages
  ([measured_production/FINDINGS.md](measured_production/FINDINGS.md)) found that on Gemini 3.8
  Flash thinking was 74% of billed output, and switching it off moved body accuracy from 99.85% to
  99.75% while cutting the price 2.6×, from $0.007184 to $0.002746 per page. On this task the
  thinking budget buys nothing measurable.
- **The old production model cannot use the structured request.** The same measured run put
  Gemini 2.5 Flash at 76.50% body accuracy on it, with the wrong block count on 4 of 7 pages and one
  page where it emitted far more text than the leaf carries. The fix in production was both the
  request and the model.

## How accuracy is measured

Two layers of truth, and only one of them is accuracy.

- **`truth/gold/`, 8 pages, the only ranking evidence.** Each page was transcribed twice,
  independently, by a model that is not an arm here (Claude Opus 5; the ranked Claude arms are
  Sonnet 5 and Haiku 4.5), from the page image and the instruction alone. The two readings were
  diffed on every scored field and each disagreement settled against the image, recorded in
  `truth/ADJUDICATION_LOG.md`. Five pages agreed outright, three needed adjudication, and page 93
  was also checked by hand. It is independent of the arm pool, which is what makes ranking
  possible. It is not a scholar's collation: a misreading shared by both readings would survive.
- **`truth/pNNN.json`, 20 pages, agreement only.** Structural facts adjudicated from where the
  arms agree, scored leave-one-out so an arm never votes on its own rubric. It finds outliers and
  never ranks a model.

The 8 pages were chosen on printed features alone, one per axis that makes this corpus hard,
before any arm was scored. `truth/EVAL_SET.md` records the rule and where its rationale turned out
to be wrong.

## The corpus

20 pages of a 461-page Arabic scholarly edition of Justin Martyr, *الدفاعان والحوار مع تريفون*
(the two Apologies and the Dialogue with Trypho): running heads, a dense numbered footnote
apparatus, printed page numbers in Arabic-Indic digits, printer marks, Greek and Latin quotations
inside right-to-left prose. Ten pages carry known production defects, five are medium, three light,
and two are clean controls where an arm that reports problems is inventing structure.

**Rights.** The ancient text is public domain; this edition's translation, apparatus and
typesetting are modern work. The 20 page images and their transcriptions, 4% of the book, are
included for the non-commercial purpose of evaluating extraction tools, with credit to the people
who made the edition: translation from the English by Amal Fouad; review against the English by
Dr. Irini Thabet George and Mariam Saad Mina; review against the Greek by Dr. Girgis Gamal Fayez;
Arabic language review by Dr. Wagdi Rizk Ghali; general review and subject index by Dr. Emad
Maurice Iskandar; introduction, final and theological review by Dr. Joseph Maurice Faltas. If you
hold rights in this edition and want the pages removed, open an issue and they will be.

## The request

Every arm gets the same instruction, `prompts/P2_blocks.txt`: return one ordered sequence of typed
blocks (paragraph, heading, page title, verse) with the footnote numbers anchored in each block,
plus the running head, the printed page number, the printer mark, and the notes below the rule with
their markers and text. Order is asked for because 6 of the 20 pages carry a heading between
paragraphs, and a reader that gets the heading in a separate list cannot put it back.

Two defects the gold readers found in that prompt are left in it on purpose, because every arm ran
against this exact text: its worked example about page 24 cites numerals that are not what it says
they are, and it has no way to mark a paragraph that continues across the page break. Both are fixed
in the production prompt, `measured_production/structured_v1.txt`.

## Repo map

```
arms.yaml            the arm registry: the only file you edit to add a model
prompts/             the instruction every arm answers
pages/               the 20 page images
runs/<arm>/          one JSON per page, per arm
truth/gold/          the reference: 8 pages, read twice outside the arm pool, adjudicated
truth/EVAL_SET.md    which 8 pages, chosen before any scoring, and why
truth/pNNN.json      structural truth over all 20 pages (agreement layer)
measured_production/ a later measured run of the real production call: thinking tokens counted,
                     corrected prompt, raw rows and outputs, FINDINGS.md
tools/score.py       -> results.json   (gold accuracy + leave-one-out agreement)
tools/results_md.py  -> RESULTS.md
tools/build.py       -> index.html     (the report, one self-contained page)
tools/chart.py       -> assets/accuracy-vs-cost.png
tools/test_gold.py   12 invariants, each one a bug this scoring once shipped
tools/run_gemini_api.py, run_opencode.ps1, run_codex.ps1   how the arms were run
```

```
pip install -r requirements.txt
python tools/score.py && python tools/results_md.py && python tools/build.py && python tools/chart.py
python tools/test_gold.py
```

**Adding a model:** add a block to `arms.yaml`, write its outputs to `runs/<id>/pNNN.json` in the
schema the prompt specifies, run the line above. It appears in every table and chart.

## Cost

Calibrated, not assumed. Production's `gemini-2.5-flash` OCR of this book cost a measured
$0.001881/page over 468 billed calls, which fixes characters-per-token for this script; JSON output
tokenises differently and was measured from the API's own usage metadata. Every arm's cost is
derived from measured output characters through those constants, or from real token counts where
the API reported them. Subscription-routed runs are priced at the vendor's published per-token rate
and say so in `arms.yaml`. Gemini 3.x figures exclude thinking tokens and are therefore a floor;
`measured_production/` counted them.

## Not yet done

- Gold on the other 12 pages. Three have both readings finished and can be merged with
  `tools/gold_merge.py`. This is the only thing that could separate the top four.
- Repeated runs. One sample per page, so the band is a floor on the uncertainty.
- Open-weight vision models, on a GPU-seconds cost axis.

## The report

`index.html` is self-contained and begins with `<meta charset="utf-8">`. That line is load-bearing:
a server that sends no charset leaves the browser to guess Windows-1252, and every Arabic character
becomes mojibake. It only ever happens locally.

## License

Code and scoring under [MIT](LICENSE). The page images and transcriptions are the edition's; see
[Rights](#the-corpus).

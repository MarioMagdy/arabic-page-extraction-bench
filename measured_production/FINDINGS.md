# Measured Production Findings: Thinking Tokens, Enforced Schema, and Gemini 2.5 vs 3.8

This benchmark evaluated 22 arms of Arabic page extraction across 20 pages of a printed patristic edition and delivered an initial recommendation. Two of its conclusions have since been overturned by a **measured run of the shipping production call** against this repository's own gold evaluation pages (`truth/gold/`).

Because this repository is where the comparative record for this task lives, the corrections are recorded here rather than left solely in the consuming pipeline.

The raw evidence is preserved in this directory:
- `results.json` — per-page measured rows for each tested configuration (token counts, thinking tokens, latency, cost, and accuracy against gold).
- `extractions/` — raw model output for every completed page and configuration, stored as `{config}_p{page}.json`.
- `structured_v1.txt` — the prompt used for this run (the benchmark's `prompts/P2_blocks.txt` with four targeted corrections).
- `measure.py` — the execution harness, allowing the run to be reproduced directly.

---

## How this run differed from the benchmark's arms

1. **It used the real production call, not the benchmark's call.** The benchmark deliberately omitted `response_mime_type="application/json"` and `response_schema` (see the architectural note in `tools/run_gemini_api.py`) so that direct API arms and CLI-wrapped arms remained strictly comparable. This run uses the shipping pipeline's call: strict JSON mime type with a schema derived from the application's typed Pydantic models at temperature 0. Crucially, the schema constrains `block.type` to an enum (`pageTitle`, `heading`, `paragraph`, `verse`), eliminating arbitrary or hallucinated block types.
2. **It counted thinking tokens.** The benchmark's cost model recorded `candidatesTokenCount` only. On the Gemini 3.x line, Google bills thinking tokens at the full output rate. Every 3.x dollar figure in the original `results.json` was therefore an underestimate. This run captures `thoughtsTokenCount` from the API's `usageMetadata` and folds it into billed output.
3. **It used the corrected prompt (`structured_v1.txt`).** Four targeted adjustments were made to `prompts/P2_blocks.txt`:
   - *Anchor worked example:* Replaced the earlier fictitious numbers with the leaf's actual facts (a year range `بين أعوام ١٠٠ - ١١٠م` in the body text, and `فصل ١٢٠` inside footnote 4).
   - *Missed anchor guidance:* Added an explicit instruction stating that the more common failure mode is a *missed* anchor, prompting the model to verify that notes below the rule are accounted for by anchor refs in the body blocks.
   - *Sentence boundary state:* Added two per-block booleans, `opensMidSentence` and `closesMidSentence`, allowing the model to capture sentence flow across page boundaries without inventing terminal punctuation.
   - *Definition of `uncertain`:* Defined the format (text snippet — em dash — explanation) for the `uncertain` list, which `P2_blocks.txt` declared in its JSON template but never explained (causing all benchmark arms to return it empty).
4. **Image resolution:** Renders are this benchmark's 300 DPI images (`pages/pNNN.webp`), not the consuming application's 150 DPI ingest renders. Absolute input token volume is higher (~2,057–2,891 tokens per page), but the cross-model comparison is apples-to-apples. Reported dollar figures should be treated as an upper bound.
5. **No variance estimates:** Each configuration was run once per page (with retry on transient service errors). There are no repeated trials, so none of these figures carry confidence intervals.

---

## The Measured Numbers

The table below averages the seven gold pages that completed across all three tested configurations (`p015`, `p024`, `p030`, `p036`, `p039`, `p052`, `p093`):

| configuration | body accuracy | worst page | blocks exact | notes exact | avg output tok | avg thinking tok | $/page | 461-pp book | worst page $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-2.5-flash | 76.50% | −51.82% | 3/7 | 5/7 | 3306 | 2386 | $0.004441 | $2.05 | $0.007082 |
| gemini-3.8-flash | 99.85% | 99.43% | 7/7 | 7/7 | 3253 | 2409 | $0.007184 | $3.31 | $0.012347 |
| gemini-3.8-flash, thinking off | 99.75% | 99.34% | 7/7 | 7/7 | 887 | 0 | $0.002746 | $1.27 | $0.003578 |

- **Body accuracy** is $100 \times (1 - \text{CER})$ after normalisation with `tools/metrics.py` (`normalize_ar`). A negative score indicates that the model generated substantially more text than exists on the leaf (runaway repetition / hallucination).
- **blocks exact** and **notes exact** count pages where the count of returned blocks and footnotes matches the gold count exactly.
- **Run economics & failures:** Total measured expenditure was **$0.1077 across 27 API calls** (24 calls in the initial pass, 3 refills). Three calls failed with HTTP 503 "The model is overloaded" (high demand): `gemini-3.8-flash` on `p015` and `p025`, and thinking-off on `p030`. Retries succeeded for `p015` and `p030`; `p025` failed twice on thinking-on and remains the only missing cell. These were transient infrastructure capacity limits, not model capability failures.

---

## The Three Findings

### 1. Thinking tokens dominate cost, and turning thinking OFF costs nothing in accuracy

On thinking-enabled Gemini 3.8 Flash runs, thinking tokens accounted for roughly **74% of billed output** (an average of 2,409 thinking tokens out of 3,253 total output tokens).

Disabling thinking reduced average output from 3,253 to 887 tokens — an immediate **2.6× reduction in per-page cost** ($0.007184 down to $0.002746). Meanwhile:
- Body accuracy moved by just 0.10 percentage points (99.85% to 99.75%).
- Structural integrity was completely unaffected: block counts (7/7) and footnote counts (7/7) remained exact across all evaluated pages.

For this transcription and block-structuring task, deliberation buys no measurable performance. The initial benchmark could not discover this because it never requested a thinking configuration and never billed thinking tokens.

### 2. Thinking makes cost unpredictable, which is a separate problem from being higher

Beyond inflating average cost, thinking introduces massive page-to-page cost volatility. Because the model chooses how long to deliberate, the cost of processing a leaf becomes impossible to forecast:

- **Thinking enabled:** The most expensive page (`p015`) cost **$0.012347** against a $0.007184 average — **1.7× the mean**, and **4.5× the thinking-off mean**. Output reached 6,007 tokens (5,346 thinking tokens) on a single leaf.
- **Thinking disabled:** Costs were tightly bounded. The most expensive page (`p030`) was **$0.003578** against a $0.002746 mean.

For budgeting book-scale ingests (such as this 461-page edition), thinking-off yields a dependable, quotable figure ($1.27/book). Thinking-on leaves budgets exposed to arbitrary model deliberation swings ($3.31/book on average, with single pages spiking 4× higher).

### 3. The never-tested cell is now filled, and it reverses a caution this repo issued

The original `arms.yaml` never tested `gemini-2.5-flash` on the `P2` ordered-blocks prompt. The consuming project's earlier findings document cautioned that the benchmark's evidence did not justify calling 2.5 Flash a worse reader: the only isolated model comparison holding the prompt fixed was on the flat `P0` prompt, where 2.5 Flash was slightly ahead of 3.7 Flash (72.2% vs 70.0% agreement).

That caution was entirely valid as an assessment of missing evidence. Now that the cell is filled, the empirical results directly overturn it:
- On the structured ordered-blocks prompt, Gemini 2.5 Flash collapses to an average of **76.50% body accuracy**.
- It failed block count on **4 of 7 pages** (recovering exact counts on only 3/7), and failed footnote count on **2 of 7 pages** (5/7).
- On `p052`, it suffered an uncontrolled generative runaway, scoring **−51.82%** (5,419 output tokens of looping text on a leaf that Gemini 3.8 Flash transcribed cleanly in 1,165 tokens at 100.0% accuracy).

The earlier caution was not wrong; it was simply empty because the experiment had not been run. The evidence now exists: Gemini 2.5 Flash cannot reliably handle structured block extraction with schema enforcement.

---

## Per-Page Measurement Data

Individual page results taken directly from `measured_production/results.json`:

### Gemini 2.5 Flash (`gemini-2.5-flash`, thinking default)
| page | body acc | blocks (got/gold) | notes (got/gold) | input tok | output tok | think tok | cost | latency |
|---|---:|:---:|:---:|---:|---:|---:|---:|---:|
| p015 | 99.53% | 3 / 3 | 0 / 0 | 2057 | 2569 | 1906 | $0.003520 | 23.3s |
| p024 | 98.96% | 4 / 3 | 6 / 6 | 2057 | 3304 | 2082 | $0.004439 | 18.3s |
| p025* | 93.84% | 3 / 2 | 2 / 3 | 2057 | 3005 | 1999 | $0.004065 | 16.5s |
| p030 | 99.77% | 4 / 3 | 7 / 7 | 2057 | 4206 | 2809 | $0.005566 | 22.6s |
| p036 | 100.00% | 1 / 1 | 0 / 0 | 2057 | 250 | 169 | $0.000621 | 5.4s |
| p039 | 89.70% | 7 / 5 | 1 / 2 | 2057 | 4718 | 3744 | $0.006206 | 24.7s |
| p052 | −51.82% | 3 / 1 | 1 / 3 | 2057 | 5419 | 4173 | $0.007082 | 28.3s |
| p093 | 99.34% | 3 / 3 | 2 / 2 | 2057 | 2676 | 1817 | $0.003654 | 17.0s |

*\*Note: p025 is excluded from the summary comparison table because 3.8 thinking-on could not complete it.*

### Gemini 3.8 Flash (`gemini-3.8-flash`, thinking default)
| page | body acc | blocks (got/gold) | notes (got/gold) | input tok | output tok | think tok | cost | latency |
|---|---:|:---:|:---:|---:|---:|---:|---:|---:|
| p015 | 99.92% | 3 / 3 | 0 / 0 | 2891 | 6007 | 5346 | $0.012347 | 95.7s |
| p024 | 100.00% | 3 / 3 | 6 / 6 | 2891 | 3196 | 2322 | $0.007077 | 40.1s |
| p025 | *503 error* | — | — | — | — | — | — | — |
| p030 | 100.00% | 3 / 3 | 7 / 7 | 2891 | 2795 | 1465 | $0.006325 | 43.5s |
| p036 | 100.00% | 1 / 1 | 0 / 0 | 2891 | 250 | 144 | $0.001553 | 6.8s |
| p039 | 99.58% | 5 / 5 | 2 / 2 | 2891 | 2261 | 1346 | $0.005324 | 39.6s |
| p052 | 100.00% | 1 / 1 | 3 / 3 | 2891 | 2953 | 1790 | $0.006621 | 23.0s |
| p093 | 99.43% | 3 / 3 | 2 / 2 | 2891 | 5309 | 4449 | $0.011039 | 49.5s |

### Gemini 3.8 Flash, Thinking Off (`gemini-3.8-flash`, thinking="off")
| page | body acc | blocks (got/gold) | notes (got/gold) | input tok | output tok | think tok | cost | latency |
|---|---:|:---:|:---:|---:|---:|---:|---:|---:|
| p015 | 99.53% | 3 / 3 | 0 / 0 | 2891 | 660 | 0 | $0.002322 | 29.6s |
| p024 | 99.91% | 3 / 3 | 6 / 6 | 2891 | 1177 | 0 | $0.003291 | 21.0s |
| p025* | 100.00% | 2 / 2 | 3 / 3 | 2874 | 1024 | 0 | $0.002998 | 6.8s |
| p030 | 100.00% | 3 / 3 | 7 / 7 | 2891 | 1330 | 0 | $0.003578 | 11.7s |
| p036 | 100.00% | 1 / 1 | 0 / 0 | 2891 | 106 | 0 | $0.001283 | 5.4s |
| p039 | 99.50% | 5 / 5 | 2 / 2 | 2891 | 912 | 0 | $0.002794 | 30.7s |
| p052 | 100.00% | 1 / 1 | 3 / 3 | 2891 | 1165 | 0 | $0.003269 | 83.3s |
| p093 | 99.34% | 3 / 3 | 2 / 2 | 2891 | 856 | 0 | $0.002689 | 17.3s |

# The evaluation set — 8 pages, frozen before scoring

Every number the report presents as **accuracy** is measured on these eight pages and no others.
They were chosen on **printed features alone**, before any arm was scored against them, so no arm
can have been favoured by the selection. The remaining twelve pages stay in the corpus as
*diagnostic* material — parse failures, output volume, self-consistency — but never as accuracy.

## Why a subset at all

Accuracy needs a reference that does not come from the models being ranked. The other twenty pages
have only *adjudicated* truth: a structural field survives into `truth/` when the arms agree about
it, which measures conformity to this particular pool of arms, not fidelity to the page. A page can
only leave that regime by being read independently, block by block, and that is expensive. Eight
pages read properly answer the question; twenty pages of arm consensus do not answer it at all.

## The selection rule

One page per axis that makes this corpus hard, taking the most extreme page on each axis:

| page | axis it covers |
|------|----------------|
| p093 | a **chapter heading between paragraphs** — the one printed feature ordered blocks exist to capture |
| p030 | **heaviest apparatus** — 7 notes, the largest footnote block in the corpus |
| p024 | **dense citation apparatus** — 6 notes carrying names, works and publication data |
| p052 | **densest page** — the largest image in the set (268 KB at fixed DPI) |
| p015 | **long body, zero notes** — separates reading load from apparatus load |
| p036 | **sparse page** — 15 KB; almost no text, where invention is the failure mode |
| p039 | **the typical page** — median image size, 2 notes, no unusual furniture |
| p025 | **mixed digit scripts** in the apparatus; also the earliest hand-read page, as a control |

### Corrections to the rationale, after the pages were actually read

The eight pages are unchanged — this records where the *reason given* for one of them turned out to
be wrong, rather than quietly rewriting it.

- **p025 was selected for "mixed digit scripts" and does not have them.** Its markers are `٧` and
  `٨`, both Arabic-Indic. The mixed-script page in the corpus is p024, whose notes run
  `١، ٢، 3، ٤، ٥، ٦` — and p025 opens with the *tail* of note 6, which is how the two came to be
  confused. The axis is still covered, twice over and by accident: p039 prints a Western `9` below
  the rule among Arabic-Indic markers, and p030 prints Arabic-Indic markers for its Arabic notes and
  Western ones for its Latin notes on the same leaf.
- **What p025 actually contributes** is the apparatus opening with a note continued from the
  previous leaf, carrying no marker at all — a case the production prompt merges into the note that
  follows it. p052 turns out to carry the same feature.

## The time cap, and what it costs

Each independent reading took **around two hours** — the p039 reader made 134 tool calls, zooming
to the glyph to decide whether a stroke was a hyphen or a tatweel, and caught two of its own image
crops returning text that was not on the page. That thoroughness is why the reference is worth
scoring against, and it is also why sixteen of them do not fit in one sitting.

So the protocol degrades gracefully instead of waiting indefinitely, and each page records which
level it actually got in its own `verifiedBy` field:

| `verifiedBy` | what it means |
|---|---|
| `gold-double-keyed-agreed` | two independent readings, identical on every scored element |
| `gold-double-keyed-adjudicated` | two independent readings, disagreements settled against the image |
| `gold-single-key-image-checked` | one independent reading, checked against the page image by the adjudicator |
| `gold-adjudicator-read` | read by the adjudicator alone |

The first two are the strong form. The last two are weaker in a specific, statable way: a slip
shared by reader and checker survives, because there is no second opinion to contradict it. They
are still independent **of the arm pool**, which is the property that makes ranking possible at all
— but a result that turns on a page carrying one of the weaker labels should be treated as
provisional, and the per-page detail in `results.json` shows which pages those are.

## If a page does not make it

Written down **before** knowing which pages would land, so the set cannot be quietly trimmed to
whatever flattered the result. The authoritative evaluation set is the contents of `truth/gold/` —
the scorer globs it, the gate derives from its size, and both reports print the page numbers next
to every aggregate. Nothing in this file overrides that.

If a page is missing when the benchmark is finalised, the row above is struck rather than
substituted, and the axis it covered is reported as **unmeasured** — a nearby page is not a
replacement, because the axes are what the selection was for. One consequence deserves naming in
advance: **p093 is the only page in the corpus carrying a heading inside the flow.** Without it,
`heading_placement` is unmeasurable and the strongest argument for ordered blocks loses its direct evidence,
which the report must say in place of the number rather than falling back on the other seven pages.

## How gold was made

Each page was read **twice, independently**, by a model that is not an arm in this benchmark
(Claude Opus 5 — the arms are Sonnet 5 and Haiku 4.5). Each reader saw only the page image and the
extraction instruction, never another arm's output and never the other reader's. The two readings were then
diffed **exactly, on every scored field**, and each disagreement was settled by the adjudicator and
recorded in `truth/_resolutions.json` and `truth/ADJUDICATION_LOG.md`. The result is in
`truth/gold/pNNN.json`, in exactly the schema the arms return, so gold and arm output are directly comparable
element for element.

As it stands: **5 pages agreed outright and
3 needed adjudication.** An earlier draft claimed all
eight agreed; that was an artifact of a comparison that ignored `footnote.number`,
`continuedFromPreviousPage` and `foreignRuns` entirely and treated a ≤0.5% character difference as
identity. The disagreements it hid were small — one letter, two spaces, one classification — but
"agreed outright" was not true, and a reference is exactly the wrong place to round that off.

**The limitation, stated plainly.** This is an independent reading, not a scholar's collation of the
printed book. It is independent *of the arm pool*, which is the property the adjudicated truth
lacks, and that is what makes ranking possible. It is not infallible, and a systematic misreading
shared by both keys would survive — two runs of the same model family are correlated, so the errors
double-keying is *least* able to catch are exactly the ones that come from a shared prior about what
an Arabic patristic page says.

**`uncertain` is recorded but NOT excluded from scoring.** An earlier version of this file claimed
those elements were held out for every arm equally. They are not: each reader writes an `uncertain`
list — a shadda it could not separate from a fatha, a stroke that is a tatweel or a low hyphen — and
the scorer never reads it. What that costs is small and known: the entries are almost entirely
diacritics and dash codepoints, and `normalize_ar` folds harakat and tatweel away before anything is
compared, so most of them cannot affect a score even in principle. But a few (a dash rendered as
U+0640 rather than `-`) are scored as if certain, and calling that "excluded" was wrong. Making the
lists machine-readable and masking them is the honest next step.

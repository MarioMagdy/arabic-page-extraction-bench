# Adjudication log

What the adjudicator actually checked, per page, against the page image. Recorded so that
"image-checked" is an auditable claim rather than an assurance — a reader can take any line here
back to the leaf and confirm or refute it.

The adjudicator is the orchestrating model. It is outside the arm pool (the arms are Sonnet 5 and
Haiku 4.5), which is the property that lets gold rank them; it is not a second *independent* reading
where a page carries only one key, and `verifiedBy` on each gold page says which case applies.

## Why every check below reads the original image, never a crop

While the reference was being built, three readers independently reported that a zoomed crop had
come back showing *a different page's* text. One produced a fluent running header that is absent from
its own leaf but genuine on p015, p025 and p052 of the same book. The cause was mundane: crops written
under shared filenames were overwritten by another reader's crop before being read back. All three
caught it by checking the crop's dimensions against what had just been written.

It is recorded because of what it shows about references: the failure produced a **confident,
plausible, wrong** reading, and nothing downstream could have flagged it, because gold is by
definition what everything else is measured against. **This is the single most dangerous failure
mode in building a reference this way**, and it is invisible to every check except comparison with
the source. So the adjudicator's pass reads `pages/pNNN.webp` directly at full size, and every
CONFIRMED below is a check against that file.

## The three real disagreements, and how they were settled

An earlier version of this file, and of the report, said all eight pages "agreed outright on every
scored element". **That was wrong, and it was wrong because the comparison was too loose**, in two
ways found in review:

- It treated a normalised character difference of ≤0.5% as agreement. On a 632-character block that
  waves through a one-letter disagreement — exactly the class this reference exists to settle.
- It never compared `footnote.number`, `continuedFromPreviousPage`, or `foreignRuns` at all, though
  all three are scored.

With the comparison tightened to exact on every scored field, **five of eight pages agree outright
and three carry a real disagreement**. Each is settled below and in `truth/_resolutions.json`; the
decision travels inside the gold file itself, under `adjudication`.

| page | the dispute | adopted | on what basis |
|---|---|---|---|
| p015 | block 1: `أثبتا` (key 1) vs `أثبتنا` (key 2) — one letter | **key 2** | key 2 counted the letterforms — four teeth carrying ث ب ت ن — and said it had corrected the reading deliberately; key 1 never discussed the token. Grammar agrees: `أثبتنا` takes `مَن` as its object, while `أثبتا` is a dual verb with no dual antecedent. **The adjudicator could not resolve the tooth count independently at the resolution available**, so this rests on key 2's stated count plus grammatical agreement. |
| p024 | note 0: a space before the colon in `انظر :` | **key 1** | key 1 measured it and named the basis — the line is short and unjustified, so the gap cannot be justification stretch. key 2 was silent on the question. A reading backed by a measurement beats one that is not. |
| p030 | note 2: `و التي` separated (key 1) vs `والتي` joined (key 2); and whether `4.1.8` is a Latin run | **key 1** for the space, **key 2** for the run | key 1 verified the space with a column ink-profile. On the foreign run, `4.1.8` is note 34's entire text and is digits only; the schema asks for an embedded Latin or Greek *script* run, and a bare dotted numeral is not one. Adopting key 2 changes no score — `foreignRuns` carries no weight — but the reference should be right. |

Everything else that looked like a difference between the two readings was harakat, tanween or a
shadda/fatha ordering — all folded away by the scorer's own normalisation, and therefore never
scored on either side.

---

## p039 — DOUBLE-KEYED, both keys agreed · and independently CONFIRMED against the image

Checked against `pages/p039.webp`:

| element | gold says | image |
|---|---|---|
| runningHeader | `الدفاع الأول` | confirmed |
| printedPageNumber | `١٩` | confirmed, foot of the leaf |
| printerMark | null | none present |
| blocks | 5 × paragraph, no heading, no pageTitle | confirmed |
| block 1 | continues from the previous leaf | confirmed — opens mid-sentence, no indent |
| anchors | `٨` in the *وختامًا* paragraph, `٩` in the *ويبدو* paragraph | confirmed |
| NOT anchors | `٢١ ـ ٦٠`, `٦١ ـ ٦٨`, `فصل ٦٩/٧٠/٧١`, `١٢٨م`, `١٥٦م` | confirmed in-sentence numerals |
| footnotes | 2 | confirmed |
| **note markers** | note 8 = Arabic-Indic `٨`, note 9 = **Western `9`** | **confirmed — the scripts genuinely differ on this leaf** |
| foreignRuns | `Cf. the detailed analysis in W. Smith and H Wace, loc. cit. 3, 563` | confirmed, including `H Wace` with no period |

The mixed marker script is the point worth recording: it is a real printed feature of this page, so
`marker_exact` is measuring something the leaf actually does, not an artifact of the schema.

## p025 — DOUBLE-KEYED, both keys agreed · CONFIRMED

Checked against `pages/p025.webp`. Header `كتابات القديس يوستينوس الفيلسوف والشهيد`, printed page
`٤`, no mark. Two blocks: a short paragraph continuing from the previous leaf, then a long one
carrying anchors `٧` and `٨`. **Three footnotes, and the first carries no marker at all** — it opens
mid-citation (`الثالثة - باريس ١٩٣٨) فصل ١١٠ …`), which is the continued-from-previous-page case
this page was selected for. Latin runs `B. Altaner`, `Patrologia`, `Smith and Wace, Dict. of
Christ. Bio.` all present and correctly placed inside right-to-left prose.

## p030 — DOUBLE-KEYED, both keys agreed · CONFIRMED, and it settles a question about markers

Checked against `pages/p030.webp`. Header `تمهيد`, printed page `٩`, no mark. Three paragraph
blocks anchoring `[31,32,33]`, `[34,35]`, `[36,37]`. Seven notes — the heaviest apparatus in the
corpus — and the marker scripts are **not uniform**:

| note | marker as printed | note language |
|---|---|---|
| 31 | `٣١` Arabic-Indic | Arabic |
| 32 | `32` **Western** | Latin (`Adversus haereses 4.6.2.`) |
| 33 | `٣٣` Arabic-Indic | Arabic |
| 34, 35, 36, 37 | **Western** | Latin |

Meanwhile every anchor in the body is Arabic-Indic. So the marker script tracks the *note's*
language, not the page's — and a model that regularises markers to one script is wrong seven times
on this leaf while reading every number correctly. This is the page that makes `marker_exact` worth
scoring separately from note identity.

## p052 — one key at the cutoff · CONFIRMED against the image by the adjudicator

Checked against `pages/p052.webp`, the densest leaf in the set. Header
`كتابات القديس يوستينوس الفيلسوف والشهيد`, printed page `٣٢`, no mark. **One** block: the leaf opens
mid-sentence and closes mid-sentence, so the whole page is a single continuing paragraph, anchoring
`٤٢` and `٤٣`. Three notes, the first again unmarked and continued from the previous leaf; note 42
runs to 819 characters and carries a five-item Latin bibliography (`Th. Deman, Socrate et Jesus,
Paris, 1944; A. Harnack, …`). Nothing truncated.

## p024 — read by the adjudicator; both keys were still queued at the cutoff

Checked against `pages/p024.webp`. Header `تمهيد`, printed page `٣`, no mark. Three paragraph
blocks: anchor `١` in the first, none in the second, and `٢ ٣ ٤ ٥ ٦` in the third. Six notes.

**This is the page that carries the mixed digit scripts** — the feature p025 was wrongly selected
for. Its markers print `١`, `٢`, **`3`**, `٤`, `٥`, `٦`: one Western digit among Arabic-Indic ones,
and it is precisely the note whose text is Latin (`Cf. Adversus Haereses 46.`). The same rule holds
on p030. The p025 reader deduced this page must be the source of the mixed-script feature without
ever seeing it, from the fact that p025 opens with the tail of note 6; reading the leaf confirms it.

Also on the leaf: Latin runs `Acta. SS. Justini et Sociorum`, `Flavia Neapolis`, `K. Bihlmeyer, Die
Apostolischen Väter (Tübingen, 1924) VIIf.`, `F. Cayré`, `Patrologie et Histoire de Théologie` —
several with diacritics (`Väter`, `Cayré`, `Théologie`) that a normalising reader would flatten.
In-sentence numerals not to be mistaken for anchors: `١٠٠- ١١٠م`, `فصل ١`, `فصل ١٢٠`, `فصل ٢٧`.

Recorded even though the page may not reach gold, because it documents the axis and the reason the
selection rationale was corrected.

## p093 — read by the adjudicator before either key landed

Checked against `pages/p093.webp`, as the page the whole P2 argument rests on:

- Running header `الدفاع الأول`; printed page number **`٧٣`** at the foot.
- **A centred chapter heading — `الفصل السادس والأربعون` — sits BETWEEN two paragraphs**, roughly
  mid-leaf. This is the only in-flow heading in the evaluation set and the direct evidence for P2.
- Two footnotes below the rule, markers `١٣٨` and `١٣٩`, anchored in the second paragraph.
- The numerals `١٠٩: ١ - ٣` (a psalm citation), `١٤٧`, `١٤٨`, `١٥٤`, `٢٩` are in-sentence, not
  anchors — and `١٣٨`/`١٣٩` are three-digit anchors, which is what makes this page hard.
- A Latin run `Logos` inside the right-to-left prose.

Consequences confirmed directly from the arm outputs for this page:
`MiMo v2.5` printed `٧٢` where the leaf prints `٧٣`; `GLM 5.3 Flash` anchored `148, 149` against
notes `138, 139`; `Claude Haiku 4.5` found both notes and anchored neither; every P1 arm returned
the heading in a parallel list, losing its position; both P0 arms returned it as undifferentiated
body text.

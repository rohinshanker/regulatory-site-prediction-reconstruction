# mRNA stability inference source boundary

- Purpose: define the published sequence featurization and frozen inference prerequisites under #8.
- Last verified: 2026-10-21.
- Decision: **no complete sequence-to-stability runtime admitted**. The checked public
  sources supply training code and feature tables, but not the complete featurizer,
  six fitted models or their frozen categorical contract.
- Pins and machine-readable counts: [source manifest](../../benchmarks/stability/inference-source-manifest.json).

## Checked sources and limits

[Cetnar et al. 2024](https://doi.org/10.1038/s41467-024-54059-7), especially the
predictive-model Results, Methods, and code/data availability sections, identifies
the public [SalisLabCode repository](https://github.com/hsalis/SalisLabCode/tree/46da9132740bce30bccd107f02808adf2215e2f0/mRNA_Stability_Calculator).
Its sole public branch still points to `46da9132740bce30bccd107f02808adf2215e2f0`.
The complete cached recursive tree has 363 entries. The stability directory has
seven files: a training script, README, Dockerfile, MIT licence, an outcome
workbook and two precomputed-feature archives. No fitted stability-model files
or separate featurizer appear in that directory.

The public branches, tags and releases lists each terminated on their first
100-item page. The sole tag/release, `r2022`, predates this directory; its exact
tag contents lookup returned 404. Four path-history commits add the initial
five files, README, a README edit and licence. Their changed-file metadata shows
no removed stability featurizer or fitted models. This is a bounded observation
of the named public surfaces, not proof that no author-held implementation exists.
Other calculators' coefficients and prediction pickles are not stability weights.

The official [Supplementary Information](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-024-54059-7/MediaObjects/41467_2024_54059_MOESM1_ESM.pdf)
has six pages. Table 2 on page 1 supplies training hyperparameters;
Supplementary Code 1 on page 6 fits decay rates from experimental read counts.
It neither computes sequence features nor loads frozen prediction models. Both
pages were inspected as rendered pages. The [supplement description](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-024-54059-7/MediaObjects/41467_2024_54059_MOESM2_ESM.pdf)
describes Data 1 as sequences/measurements and Data 2 as featurization,
calculations and predictions. These are tables, not a recovered callable bundle.
The Data 2 workbook was not downloaded or parsed; its publisher HEAD response
did not provide a length. No claim of its exact schema or embedded contents is
made here. Existing cached CSV-header evidence is used instead.

The primary article's reference 1 leads to the already admitted
[Promoter source](promoter-source-and-benchmarks.md); the referenced 2022 paper
names the `r2022` code release. Reference 2 identifies the Model Test System.
Its pinned `TranslationRateModels.py:26-27` explicitly imports private `DNAc`,
and lines 129-133 use `RBS_Calculator_v2_1`. These leads do not recover the
stability-specific sequence pipeline. Reference 55 is a ViennaRNA methods
reference; it does not supply that pipeline or the six trained models.

## What the public code actually specifies

`ModelTrainingTesting.py:22-50` loads the two precomputed tables and casts
named fields to pandas categories independently in each table. Lines 65-84
define a column-name selector; this function does not accept a sequence.
Lines 117-119 and 246-248 select columns by membership while preserving each
table's existing order. A caller must not use selector-list order as model order.

The main block trains models for `T0`, `T2`, `T4`, `T8`, `T16`, then a decay
model. The expected output filenames are `model_T0_saved.txt`,
`model_T2_saved.txt`, `model_T4_saved.txt`, `model_T8_saved.txt`,
`model_T16_saved.txt`, and `decay_rate_saved.txt`. These are names constructed
by the script, not located artifacts. The first five targets are natural-log
RNA/DNA ratios; their predictions feed the sixth model alongside sequence
features. The decay target is the measured fitted rate, in inverse minutes.
No training, module import, model loading or prediction was run for this check.

## Count and ordering contract

| Count | Exact meaning |
| --- | --- |
| 460 | Five isoforms, each with 80 positional nucleotide fields and 12 other selected fields. |
| 465 | The 460 fields plus five predicted timepoint levels for decay inference. |
| 420 | Fields cast to category: 400 nucleotide positions plus `rppH`, `GQUAD`, `iMOTIF`, `CsrA` for each of five isoforms. |
| 40 | Remaining selected timepoint fields: eight per isoform, not cast to category by this script. |
| 513 | Each cached CSV header: all 460 selected fields plus 53 excluded fields. |
| 496 | Feature count stated in the paper's predictive-model Results; not the selector's width. |

The 53 excluded fields consist of 30 additional isoform fields (five each of
`fold_lengths`, `TSS`, `final_fold`, `start_codon_position`, `initial_fold`,
`Ribo`) and 23 global fields. The latter comprise 12 identity/sequence/design/
measurement fields, six prediction fields, four global motif/ribosome flags
and `id`. The decay selector includes five of those predictions, leaving 48
excluded table columns. The two cached headers differ only by a UTF-8 BOM on
the first, unselected test-table field; both selected orders are identical.

Numerically, 490 isoform table fields plus six prediction fields equal 496.
That arithmetic is **not** an established explanation of the paper's claimed
minimal feature set: it includes fields excluded by the public selector and a
decay prediction. No frozen-model feature roster or source mapping establishes
which 496 fields the paper means. Preserve the discrepancy; do not pad the
selector, silently drop columns or label 513 table fields as model inputs.
The manifest records independently derived order digests and exact partitions.

## Separate source and dependency admission

| Component | Evidence and disposition |
| --- | --- |
| Training code | Pinned script and directory MIT notice, copyright 2023-2024 Cetnar, Hossain and Salis. Reuse requires the notice. This is not a sequence-inference implementation. |
| Six fitted models | Not recovered on checked surfaces; no weight bytes, model metadata or artifact-specific terms admitted. Hyperparameters cannot substitute for fitted trees. |
| Input contract | Precomputed table columns recoverable; sequence coordinates, isoform tie handling, truncation/padding and missing-value rules for the original featurizer remain unrecovered. |
| Categories/order | Selected CSV order recoverable. The script infers categories from each table; frozen vocabulary, codes, unknown-category handling and model-stored category metadata remain unrecovered. |
| Primary article/supplements | Article CC-BY-4.0 notice retains the third-party-material exception. This does not establish terms for absent model artifacts or every dependency. No large table redistributed. |
| Dependencies | Paper names Promoter v1.0, RBS v2.1, ViennaRNA 2.4.11 and LightGBM 3.3.2. Docker instead downloads ViennaRNA 2.5.0 and leaves Python dependencies and BLAMM unpinned. No exact inference lock or all-open dependency bundle recovered. |

NumPy, pandas, matplotlib, LightGBM and scikit-learn are imported by the training
script, with an Excel reader needed for its outcome workbook. The broader
README/Docker install lists are not evidence that every package is necessary
for inference. Preserve the existing [open-backend decision](rbs-source-decision.md):
ViennaRNA/Kinfold are not newly admitted required dependencies. Substituting
RNAstructure or another model does not establish historical feature equivalence.

## Smallest supported next step

The complete recoverable component is **schema projection**: the 460/465 name
sets, 420 category-designated fields, and selected order for these exact cached
headers. Its input is column-name metadata; its output is selected names and
category flags, never a biological prediction. The existing isolated selector
[smoke receipt](../../benchmarks/other-calculators/stability-feature-smoke.json)
already covers that operation; this task adds no duplicate runtime.

For a new independent sequence-feature implementation, the smallest plausible
subset is literal positional bases from a caller-supplied transcript, reflected
by `nt_0` through `nt_79`. A must first choose an explicit coordinate, alphabet,
length and missing-value contract. This would be a new feature definition:
the source does not establish the original encoding or edge behavior. No exact
sequence-feature fixture is admitted from names alone. Automatic selection of
five isoforms, transcription/translation rates, structural summaries and motif
features remain outside this source admission.

A complete historical inference admission needs the featurizer source and
parameters, all six immutable model artifacts, exact feature/category contracts,
compatible component terms, and a reproducible dependency boundary. An author
supplied bundle meeting those requirements is the direct missing dependency;
retraining or constructing substitute weights would be a different project.

## Rechecking this boundary

Validate each manifest source against its byte count and SHA-256, keeping
previous cache pins immutable. Read only existing header JSON for table counts;
derive the 92-name family roster from inspected selector syntax and expand over
isoforms 0 through 4. Filter headers by membership, then hash each selected name
plus a newline as UTF-8. Check train/test order equality, the 53/48 complements,
and the 420/40 category partition. Never import the training module for this
metadata check. Recheck public refs before any future source admission; absence
claims remain limited to the recorded observation date and surfaces.

Acquisition used external caches and a 50 MiB budget. The source worker fetched
69,487 bytes of API bodies; its request hashes are observations (raw bodies were
not retained). Coordinator source bodies are retained with hashes. The publisher
HTML request followed redirects whose body sizes were not separately logged, so
the recorded body sum is not a complete transport-byte measurement. No bulk
archive or workbook was acquired. This accounting limitation must not be reported
as an exact all-response byte audit.

Exposure is limited to already public article/supplement narrative, aggregate
figures/tables and source/schema metadata. No new per-case outcome table was
opened, and no private outcomes, fitting, inference, native execution or model
accuracy approval is part of this contract. Parent #8 remains open.

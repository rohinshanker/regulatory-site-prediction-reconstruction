# Independent Promoter and transcript-context evaluation

- Purpose: Keep numerical parity, native localization, input sensitivity and measured strength separate.
- Scope: Session B, Wave 5 tickets #34/#35; no model fitting or hosted jobs.
- Last verified: 2026-10-18
- Planning baseline: `d37ebd7d8eb2422389d003e3fc2ebab2aa5c6466`.
- State: Phase 1 protocol; final collection requires reviewed tools, immutable input/settings hashes and A's candidate/gate receipt.

## Authority and independence

Use the unchanged [Tan source contract](rbs-native-validation.md) and
[native evidence envelope](rbs-native-input-contract.md). The 4,808 publisher
Table S1 rows have absolute transcription-start coordinates, source categories,
condition metadata and explicit historical/current CDS alternatives. They are
not translation-strength measurements, promoter boundaries or a labelled negative
universe. Neither raw read counts nor their sums are transcript-mixture weights.

The [consumer policy receipt](../../benchmarks/promoter/native-policy-reuse.json)
pins 15 inspected files at cyano commit
`086111949f5039782d1ed8f2fa4a4a647c0fc956`. Each matches its committed bytes.
Unrelated dirty documentation is recorded and is not adopted as authority.
The visualizer already retains published absolute TSS positions, paper-era start
distances and current-start disagreement. Reuse that policy; do not resolve
aliases, reannotate genes or copy the application's display placement into truth.
The portable pipeline does not require a sibling checkout.

The consumer's protein-coding join and reconstruction's GFF-preserving join have
different denominators. The former has 2,432 gTSS rows at 1,789 current loci;
the latter preserves every source row, pseudogene and compound-model exception.
The existing 236 start disagreements and 15 internal current-CDS gTSSs are not
newly discovered discrepancies. The consumer's older answer-centered localization
pilot supplies coordinate cautions, not this wave's candidate-window definition.
Its exposed existence also prevents describing Tan as a newly discovered study.

Final outcomes and per-case metrics stay with B. Public source TSS coordinates
remain public, but window membership, tolerances and grouping must be committed
before model scoring. A receives input-only examples and reviewed aggregates.
No prior Cambray/PCC 6803 final cohort is reused for fitting or model selection.

## Four distinct outputs

### 1. Source-equation and coordinate parity

Reuse the immutable [212-state executed reference](promoter-executed-reference.md)
and its 11 synthetic cases. Compare every admitted finite state, term sum,
selected state, relative score/log-score and forward/reverse interval using the
declared 1e-12 absolute/relative numerical tolerance. Preserve source bugs as
named historical behavior: reverse dictionary `L-t` is not a base coordinate,
the arbitrary scanner omits a gap, and sigma settings do not affect inference.
The reconstructed API's corrected coordinates are checked against independent
algebra, not against those legacy keys. Failure is a software discrepancy; it
cannot be repaired using native outcomes and called an untouched rerun.

### 2. Positive-TSS localization

Define genomic tiles `[1000*k, min(1000*(k+1), L))` independently on each pinned
replicon. On each strand select at most 128 tiles by deterministic SHA256 order
under seed `wave5-tan-grid-v1`; small replicons retain all their tiles. Record the
complete grid and sampled/not-selected denominators. Every genomic base in a
selected tile is a candidate TSS, irrespective of any source TSS or CDS.
Extract 67 upstream and 19 downstream bases beyond the candidate range, in
transcription orientation. Circular padding requires explicit topology and may
not traverse the replicon twice. Linear clipping and insufficient full-state
context remain explicit. Each retained position ordinarily admits all 30 states.

Use the explicit E. coli calibration and label UTEX 2973 as extrapolated target
metadata. Rank positions by the raw learned score, lower first; do not interpret
it as a physical free energy or calibrated native rate. Freeze the runtime's
selected-state contract before converting results. No data-dependent score
threshold, local-max suppression or candidate filtering is allowed.
Query DNA is already in transcript orientation on each genomic strand. Native
collection requests only the runtime's forward strand on that DNA, then maps
its local TSS points through the query's declared segments. It must not scan
both runtime strands and count the opposite orientation as the same query.
The separate source-parity stage tests the runtime's own reverse-strand contract.

Report all 4,808 source rows, unique point/strand positives, selected-window
positives, out-of-window positives, full/partial-state support, positions
requested/scored and every status. Report exact recovery at top 1, 5 and 10 per
tile; ±3 nt is a separate sensitivity result. Use one-to-one maximum-cardinality
matching within each tolerance so one predicted position cannot recover two
positives. All-positive recall and in-window conditional recall have distinct
denominators. Incomplete queries contribute no successful top-k recovery to the
all-case endpoint; successful-position-only summaries are explicitly secondary.

Exact score ties use genomic point then stable ID for deterministic top-k output.
Also report best/worst tied ranks and midrank for each positive, with all-tied
controls demonstrating the distinction. A constant-score control is an explicitly
uninformative ranking baseline, not another biological predictor. No precision,
PR-AUC, specificity or false-discovery claim is admissible from unlabelled sites.
Separate gTSS, aTSS, iTSS and nTSS aggregates without treating source categories
as independently validated full promoter classes.
Also report replicons separately: the fixed cap samples chromosome tiles while
retaining all small-replicon tiles. The in-window aggregate therefore has a
different replicon mix from the complete source population. It is conditional
sample performance, not an unweighted estimate of whole-genome sensitivity.
Replicons or categories without positives have an undefined recovery denominator;
their unlabelled queries do not supply negative controls. Subgroup summaries are
descriptive; the predeclared cluster intervals apply to the overall endpoints.

Repeated conditions share one positional label; alternate TSSs remain separate.
Freeze uncertainty groups before scoring as connected components of the following
input-only graph (including out-of-window positives):

- All labels competing in one selected query share a group. Selected queries
  whose padded genomic intervals overlap or touch on the same replicon share a
  group across strands; circular-origin segments use actual genomic intervals.
- Labels sharing an exact nonempty source locus tag on the same replicon share a
  group. Labels within 86 nt of one another on the same replicon also share a
  group, across strands, using the minimum circular distance where applicable.
- For every label, extract its 87-base oriented context (67 bases upstream,
  the TSS base and 19 downstream), with explicit circular topology. Canonicalize
  each distinct 15-mer against its reverse complement. Connect labels when the
  Jaccard similarity of their nonempty 15-mer sets is at least 0.5. This is a
  fixed near-duplicate screen, not exhaustive homology detection. Linear clips
  remain explicit; absent or shorter-than-15 contexts have an unavailable screen.

Use the lexicographically smallest constituent label ID as the stable component
ID. Publish edge counts by rule, group counts/sizes and missing screens before
scores; never weaken grouping to obtain narrower intervals. Unlabelled-only
queries have coverage counts but no positive-recovery denominator. Use 10,000 cluster
resamples, seed 20261018, percentile 95% intervals when at least 20 groups are
available; otherwise retain descriptive counts and an explicit insufficient-group
status. Resample complete groups with replacement and recompute the ratio of
summed recovered positives to summed eligible positives, retaining zero-recovery
and out-of-window groups. Report all-positive and in-window intervals separately;
if a resample has a zero denominator, report its count and omit only that undefined
ratio. Intervals condition on this source's ascertainment and do
not propagate raw-read mapping or biological replicate uncertainty.

### 3. Unchanged-RBS transcript-context sensitivity

Prepare an input-only bounded diagnostic panel from Tan associations before
scoring. Consider exact nonempty source locus tags on gTSS rows only; do not turn
an antisense/intragenic association into an inferred upstream transcript. Preserve
all selected loci's gTSS alternatives. Assign each locus to the first applicable
stratum, using any of its source rows: internal current leader (<0), leaderless
(0), short leader (1–20), historical/current start disagreement (nonzero declared
delta), ordinary current context (>20), or unresolved current start. Choose at
most four loci in each stratum by ascending SHA256 of compact UTF-8 JSON
`["wave5-tan-context-v1", genome_id, source_locus_tag]`, with locus ID as tie-break.
No response, read count, codon or model score affects selection; empty strata are
reported without replacement. The six-stratum source/locus counts stay visible.
Commit the precise selected IDs and resulting job count before execution.
Historical/current starts are separate scenarios, never silently substituted.

Compare measured-TSS-clipped leaders against the explicit 100-nt genomic-flank
assumption, with 100 nt from the supplied start into the CDS. Keep explicit
annotated-tail aSD `ACCUCCUUU`, declared temperature and unchanged `historical`
and `context2017` profiles. The diagnostic temperature is explicitly 37°C for
every job, isolating context changes; it is not an estimate for all four source
conditions. Each retained source row has current and historical anchor scenarios,
each with measured-TSS and unmeasured-flank input, under both profiles. Missing
anchor scenarios remain explicit unsupported rows rather than being dropped.
Identical contexts are identified in the receipt; all source associations remain
represented. Source conditions do not create calibrated alternate
host models. Report leader lengths, input hashes, all failures/unsupported cases,
paired raw-term and log-score changes, and within-panel rank changes. These are
input-sensitivity results, never demonstrated translation improvements. No TSS
read count is joined as a strength label; leaderless/internal cases stay in
coverage even when a profile cannot score them.

Summarize each profile and anchor scenario separately. A paired comparison needs
successful measured-TSS and flank results for the same source association.
Report every other status in coverage, and never substitute a missing score with
zero. Define changes as measured-TSS minus flank for each raw term and emitted
log-score. Report paired count, minimum, quartiles, median, maximum and the count
with absolute change greater than 1e-12; retain all finite pairs without outlier
removal. Within each fixed paired subset, rank higher log-scores first using
midranks for exact ties and report paired rank changes. Do not compare physical
units or fitted scales across profiles. Repeated loci are descriptive scenarios,
not independent samples; no translation-accuracy significance test is made.

The standard-library input builder is
[`benchmarks/rbs/context_panel.py`](../../benchmarks/rbs/context_panel.py).
It emits one `native-rbs-evidence-1` envelope for use under each of the two
profiles, with four named coordinate/context scenarios per selected source row.
Condition identities are retained; replicate counts and source quality fields
are omitted from runtime inputs. Missing anchors stay null. Outputs are created
exclusively with mode 0600; a selection exceeding 1,024 source alternatives fails
without truncation, and an empty selection cannot produce a runtime envelope.
Source metadata and fixed anti-SD/provenance agreement are validated. Each
scenario derives its own circular crossing declaration from its explicit signed
leader and actual 100-nt flank/downstream bounds; the source crossing flag remains
separate provenance. Internal TSSs never become origin-spanning leaders.
Reproduce from the pinned external Tan envelope:

```sh
python -m benchmarks.rbs.context_panel ENVELOPE PANEL.json \
  --source-sha256 c442baf07480ddece0956a9ac10aefd5884472ec63ed0c62166e2ad7ef8a03d5
python -m pytest tests/benchmarks/test_context_panel.py
```

This prepares inputs only. Collection still requires the candidate/settings
receipt and folding-slot agreement below.
After collection, use the [paired-context metric tool](rbs-context-metrics.md)
with explicit panel, collection, candidate and model identities. It verifies
core-request/profile consistency and retains unsuccessful scenarios; failure
text and reason hashes remain private rather than entering aggregate reports.

### 4. Measured Promoter strength

Reassess only the existing reserved GSE144621 lead and its
[admission record](../../benchmarks/promoter/gse144621-admission-update.json).
Require rights, exact per-row reporter construct/orientation, condition,
measurement identity, denominator reconciliation and locus/family/training
exposure before admitting a final challenge. Public access alone supplies none
of those missing grants. If these checks fail, record the exact blocker and
complete the other three outputs. No exposed published-column audit is relabelled
as prospective validation, and no new study search or outcome-guided calibration
is introduced to replace a failed admission.

## Execution and review gates

Test preparation, status accounting, matching, ties and uncertainty on synthetic
labels. B independently reviews Claude's exact tool patch. Freeze protocol,
source/annotation policies, queries/labels/groups, tool hashes, candidate commit,
parameters and full backend/runtime settings before the first real prediction.
Record any owner-approved release-gate exception; elapsed time is not approval.
The reviewed public interface is `docs/validation/promoter-runtime.md` at
`5b890a3c307d366a828d95812f22a2b9975e6cfe`. Interface preparation and synthetic
adapter tests may proceed while the gate is pending. They do not authorize a
runtime implementation, a real input collection or a label/outcome join.

The final receipt must bind these separately checkable items before collection:

- The recorded release dependency or owner exception, immutable candidate commit,
  wheel hash, implementation version, complete emitted model object, six-key
  `identity_model`, model/parameter/source hashes and the exact reviewed public
  interface. A version string alone is insufficient.
- The unchanged input manifest and query/label/group/context-panel hashes,
  adapter/evaluator hashes and explicit metric settings. Query construction does
  not read labels; no labels enter runtime requests.
- Calibration and target-host metadata, deterministic request order and batch
  membership, exact serialized request hashes, the complete twenty-key effective
  runtime limits, separate evaluator packing limits, float record/batch deadlines
  and explicit CLI defaults. All settings come from the candidate's synthetic
  feasibility receipt, within this protocol's whole-stage ceilings.
- Every requested batch and case, with an explicit completed, failed or not-run
  receipt. Missing, extra, duplicate or mismatched results fail validation.
  A setup failure has no invented prediction; it still retains the complete
  planned candidate roster with null scores in the evaluation representation.
- Any completed sites in a failed record remain failed-record observations.
  They may enter the separately named successful-position diagnostics but never
  an all-case endpoint. Coordinate-eligible partial state sets are distinct from
  missing candidate scores: the runtime may score 1–29 valid states at an edge,
  and the report preserves that context limitation.
- Private output storage and hashes, exact CLI invocations, collection stop
  conditions and the independent reviewer for final arithmetic/public claims.
  Exceeding the total deadline leaves all unstarted work explicit; there is no
  automatic retry, batch shrinking or settings change after outcomes.

The [runtime/evaluator adapter](promoter-runtime-adapter.md) never invokes
inference. Its synthetic feasibility checks establish serialization, identity and denominator behavior only. CPU,
wall-time and memory capacity require A's actual synthetic runtime measurements;
packing a valid request is not evidence that it will finish within a deadline.

Choose finite per-record and whole-stage deadlines using synthetic feasibility
only. Initial ceilings are 3,600 seconds for native Promoter scanning and 7,200
seconds for bounded RBS context diagnostics, with at most two expensive folding
processes total on the shared machine. Agree slot ownership with A before folding.
Candidate-specific caps and actual panel sizes must be in the final receipt;
exhaustion retains every unstarted item as not run. Hash-addressed cached outputs
must match complete input/model/backend/settings identity, not just a filename.
No retry or model repair against final outcomes is an independent evaluation.

An independent reviewer recomputes final arithmetic and checks public claims
against the saved collection. Publish only reviewed aggregates and reproducible
artifact identities. Keep raw outcomes and per-case residuals private, with
exclusive file creation and restrictive permissions. A integrates reviewed
commits and owns runtime, CI and publication. B does not merge main, tag,
publish packages, access browsers/credentials or spend coins in this wave.

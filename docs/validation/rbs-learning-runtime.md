# Experimental learned RBS models

- Purpose: Define reproducible development fitting and explicit learned inference.
- Scope: Frozen sequence/energy features, ridge artifacts and local CLI.
- Last verified: 2026-10-17

These models predict an assay's log2 response, not thermodynamic energy, a
probability, or an absolute initiation rate. Fluorescence and ribosome-profiling
TE are imperfect translation proxies with different confounders. Keep models
trained on different assays separate. No experimental model is promoted merely
because its development loss is lower.

## Frozen features and fitting

`sequence-v1` contains 19 features in a fixed order: leader/downstream lengths
clipped at 100 nt; A/C/G fractions in upstream 35, upstream 100, first 13 coding,
and coding positions 14–35; GUG/UUG/CUG indicators (AUG reference); longest exact
complementary aSD run in the upstream 35 nt and its gap before the start. Matching
runs tie-break by proximity to gap 5, then smaller gap. No matching nucleotide
gives length 0/gap 36. Empty regions give zero fractions, with context length
retained. These are sequence statistics, never biological binding boundaries.

`context-energy-sequence-v1` appends five unchanged energy values from a matching
successful `context2017` prediction: total, unbound mRNA, spacing, signed standby
and isolated post-footprint energy. The signed standby term retains its sign.
The extractor verifies sequence/hash, strand, aSD, temperature, explicit start,
model identity and finite terms. Missing energy is unsupported, never zero-filled.
The sequence feature module was frozen before fitting any assay outcomes.

Ridge minimizes summed squared log2 residuals plus lambda times squared weights.
Training population means/scales standardize each feature; the intercept is
unpenalized. Constant training columns have zero weights and remain inactive at
inference. The fixed per-observation penalty grid is 0.01, 0.1, 1, 10; the solver
receives that value times the training-row count. Overflow, invalid inputs and
severely small relative Cholesky pivots fail explicitly. The pivot guard is a
heuristic, not a general coefficient-accuracy guarantee.

The 2014 development recipe leaves each source family out in turn, fitting all
scaling and coefficients inside the training fold. Selection minimizes mean
family MAE; row RMSE and then stronger penalty break exact ties. Selection
diagnostics are not unbiased test accuracy. Each selected 2014 artifact then fits
all development rows. Native train/validation/final partitions follow B's separate
frozen protocol; neither the 2017 nor native final outcomes enter this recipe.

## Reproduce the public development experiment

Use the exact source/feature code commit recorded in each artifact. The pinned
public [2014 data](../../benchmarks/rbs/standby2014.json) are CC-BY-3.0, attributed
to Espah Borujeni et al., DOI 10.1093/nar/gkt1139. All 136 rows are retained; source
predicted energies, apparent energies and measured counts are never features.
After installing the [runtime](rbs-runtime.md):

```sh
RBS_CODE_COMMIT=$(git rev-parse HEAD)
.venv/bin/python -m experiments.rbs.collect benchmarks/rbs/standby2014.json \
  "$REGSITE_RNASTRUCTURE" .cache/context2017-development.json \
  --code-commit "$RBS_CODE_COMMIT"
.venv/bin/python -m experiments.rbs.standby benchmarks/rbs/standby2014.json \
  .cache/context2017-development.json .cache/standby-models \
  --code-commit "$RBS_CODE_COMMIT"
.venv/bin/regsite-learned .cache/standby-models/sequence-v1.json examples/rbs-learned.json
.venv/bin/regsite-learned .cache/standby-models/context-energy-sequence-v1.json examples/rbs-learned.json
```

The collector is local, bounded to 30 minutes by default (one hour maximum), and
retains failed records. It never downloads data or silently truncates a set.
Training requires exact source bytes and complete matching cached predictions;
it writes no models until both configurations have fit successfully. No final
evaluation is performed by these training commands. Recollection on another
backend build may change provenance and numerical outputs; retain source/data,
binary/table, cache, model and code identities rather than assuming equivalence.

## Inference and artifacts

`regsite-learned MODEL.json REQUEST.json` accepts one or up to 100 standard RBS
requests. Each must select exactly one start. Sequence-only models need no folding
backend. Energy models require separately installed RNAstructure 6.6. Output
[schema v1](../../schemas/rbs-learned-result-1.schema.json) includes the frozen
artifact hash, target units, feature values, start anchor, domain warnings and
explicit failure status. Energy models embed their independent mechanistic
reference; no learned coefficient is presented as an energy contribution.

Artifacts use the strict `ridge-log2-v1` JSON format: feature names, training
means/scales, coefficients, intercept, penalty, training-input SHA256 and provenance,
plus a content checksum. The checksum detects accidental changes, not authenticity.
JSON is the portability boundary; pickle/deepcopy/hashability are unsupported.
The inference adapter also requires feature kind, assay target/units and explicit
training host/aSD/temperature domains. Out-of-domain predictions are warned, never
silently called calibrated. Host text matching is exact, not a synonym inference.

Setup/artifact errors exit 2; any unsuccessful prediction makes the CLI exit 1.
Missing scores remain null. Scores are log2 assay responses; conversion to a
positive scale for a separately specified evaluator must retain units, finite
range checks and development-only calibration. Candidate selection and scientific
promotion remain governed by the [evaluation contract](rbs-evaluation-protocol.md).

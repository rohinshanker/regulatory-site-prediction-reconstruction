# Executable upstream RBS comparators

- Purpose: Run identifiable upstream predictors without replacing their algorithms or conflating their output scales.
- Scope: Optional research environments and independent experimental comparisons; no required runtime dependencies.
- Last verified: 2026-10-17
- Owner: Session B.

## Admitted inference artifacts

Machine-readable pins and synthetic outputs are in
`benchmarks/rbs/comparator-artifacts.json`. The adapter checks upstream source,
configuration and weight hashes before inference. Ordinary offline tests use
small independent boundary fixtures; actual upstream smokes are recorded separately.

**OSTIR 1.1.3**, tag commit `9a1a5744bd70f28313a342ba9bf7946c8cd12bd2`, executes
its unchanged library with ViennaRNA Python bindings 2.7.2 and NumPy 2.4.2 in an
isolated Python 3.14.7 environment. All 12 packaged source/parameter files match
the tag's Git blobs. Code is GPLv3 (distribution classifier GPLv3-or-later).
ViennaRNA's fee-bearing redistribution limits and NAVIEW's noncommercial notice
remain; OSTIR's licence does not override them. Keep this stack outside the
required open runtime. The smoke did not invoke plotting.

The adapter requires an explicit nine-base aSD; missing aSD is rejected, never
filled with an E. coli default. It preserves `temperature_celsius` and
`temperature_c` aliases and rejects conflicts. The released library API fixes
temperature at **37°C**. Native PCC 6803 assay
metadata says 30°C; the adapter reports the mismatch and does not monkey-patch
upstream constants. It supplies the exact declared aSD, sequence and one-based
start to upstream, converting zero-based input only at this boundary. The library
smoke returned expression 3325.07148797 for the manifest's synthetic sequence,
start 33 one-based; a repeated call was identical and the off-by-one control
returned no candidate. The upstream CLI fails because the Python wheel does not
supply genuine `RNAfold`, `RNAsubopt`, `RNAeval` binaries. Library execution uses
real `RNA.fold_compound` calculations; no fake executables were installed.
Upstream environment.yml specifies ViennaRNA 2.6.4, so numerical parity with that
original environment is unverified. Scores are native relative expression units.

**rebeca scalar exp67_true**, author [Zenodo record 11081336](https://zenodo.org/records/11081336),
checkpoint `best_model_124605_seed_3.pth`, SHA-256
`5b17912c6a177db87dfc5008ecebb6c13c2095747748eface1fc72fa46b43b9b`, is a genuine
one-output CONVBILSTM model. Bounded ZIP64 HTTP-range recovery retrieved 6.8 MB
from a 12.5 GB archive, verifying each selected member's CRC32, length and hash.
The whole archive checksum was not verified. Embedded MIT source and the deposit's
CC BY 4.0 weight declaration are separate from unverified original-training-data
rights. No checkpoint or upstream source is bundled here. A historical eight-bin
rebeca classifier also ran, but is a different model and is excluded from scalar
strength comparisons. Solaris has no recovered pretrained universal estimator;
its local GP fitting/design task is not substituted for this checkpoint.

The pinned upstream architecture and `UTRMeanFluoDataset` run unchanged using
Python 3.9, torch 1.13.1, NumPy 1.24.4, pandas 1.5.3, PyYAML 6.0.1,
torch-geometric 2.4.0, SciPy 1.10.1 and scikit-learn 1.3.2. `pip check` passes.
Weights load with `weights_only=True` and strict state matching on CPU, one thread.
The synthetic 30-nt input in the manifest yields 6.047040939331055, shape (1,1),
with identical repeated calls. This smoke verifies execution, not native accuracy.

Preprocessing uses the last 30 UTR bases **excluding the start codon and CDS**,
DNA T→U and A/C/G/U channels. Short UTRs are right-padded with zero-encoded Z;
N is unsupported. The native scalar is a mean natural-log fluorescence parameter.
The deposited exp67 analysis notebook explicitly applies `np.exp`; under its
lognormal interpretation that is median/geometric-mean fluorescence, not the
arithmetic mean (which would require the unpredicted variance). Preserve both
native output and the declared positive scale. Neither is absolute TIR.

Config identifies Kuo fepB `data_4`, MSE and scratch/fluorescence-diversity sampling.
Exact training rows, pretraining overlap and mapping to the paper's final reported
predictor remain unverified. The embedded Git reference does not establish that
all archived working files match it; exact file hashes are authoritative. An
archived active training loop's size limit conflicts with the checkpoint's
124605 filename, and the documented `mu_mle`→`log_mu_f` column handoff is incomplete.
No training invocation or target-host transfer claim follows from this recovery.

## Experimental comparison boundary

All competitors receive the same supplied genomic context/start; each adapter
uses its documented input features. Native output scales are preserved, then
one intercept is fitted on the frozen primary HC training partition only.
No final refit, outlier trimming or assay mixing is allowed. Native evaluation
uses `benchmarks.rbs.strength`; it rejects booleans, distinguishes missing/zero
assays and counts every eligible prediction failure. Final paired comparisons
resample full frozen homology groups with 97.5% intervals for two prespecified
contrasts. Complete coverage, rank and subgroup gates remain required.

Development-validation (479 primary HC genes) after train-only calibration:

| Upstream identity | Successful | MAE log2 | Spearman |
| --- | ---: | ---: | ---: |
| OSTIR 1.1.3 / ViennaRNA 2.7.2 / fixed 37°C | 479 | 2.917893 | 0.210213 |
| rebeca exp67_true checkpoint above | 479 | 3.566328 | 0.075965 |

These are development selection results, not final performance. OSTIR is the
provisional strongest eligible upstream comparator for the prespecified final
contrast. Entire-source inference retained all 2,530 rows: OSTIR scored 2,499,
rebeca 2,503; unresolved input rows remain unsupported. The primary admission
set and every failure are assessed separately from this full-source denominator.

## Reproduction

Use isolated environments satisfying the exact versions and component terms;
never modify shared packaging for an optional comparator. The rebeca root is the
extracted `rebeca/rebeca` directory from the author archive. Recover just the
manifest's selected members using a range-capable ZIP reader, or download the
whole archive separately after checking its size; neither is an ordinary CI step.
Per-file hash checks reject drift before loading. Source notebooks supporting
units are identified in the external evidence dossier and the author deposit;
no experimental outcomes from notebook cells are used.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "$OSTIR_PYTHON" -m benchmarks.rbs.comparators ostir "$INPUTS" "$PRIVATE/ostir-predictions.json"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "$REBECA_PYTHON" -m benchmarks.rbs.comparators rebeca "$INPUTS" "$PRIVATE/rebeca-predictions.json" --rebeca-root "$REBECA_ROOT"
python -m unittest discover -s tests/benchmarks -p 'test_comparators.py'
python -m unittest discover -s tests/benchmarks -p 'test_strength.py'
```

Inputs are an object with `records`: id, sequence, zero-based `start` or
`start_position`, aSD and temperature metadata. Output records preserve native
output, transformed score, failure status, input hash and model artifact pins.
The strength API's `fit_intercept`, `evaluate`, `paired_comparison` and
`subgroup_gates` accept explicit records; they never import reconstruction scoring.
Measurement eligibility and the immutable split must be supplied by the source
pipeline, not inferred from model success. Timing is recorded separately and is
not part of numerical prediction identity.

## Hash-locked aggregate evaluation

`benchmarks.rbs.native_evaluation` reads a manifest containing byte hashes for a
private case table and every normalized prediction table. `native_cases` admits
the frozen primary chromosome cohort from both source conditions, checking the
original input hash, complete HC/LC measurement identities and split metadata.
It assigns input-only codon, strand and source/current protein-length strata.
No prediction-dependent source filtering is permitted.

The report fits median log2 residuals on development-train only, then evaluates
the requested validation or final partition. It never selects a model. The final
manifest must explicitly freeze champion, selected simple-control baseline,
selected upstream reference, original historical/upstream and constant identities
before use. Two champion contrasts use 97.5% paired-group
bootstrap intervals, a 0.20 log2 worthwhile MAE gain, no lost baseline-valid
predictions, at least 95% coverage, Spearman deterioration at most 0.05, and
at most 0.50 log2 MAE deterioration in predeclared strata with at least 30 common
successful cases. Small strata are descriptive; an absence of applicable strata
cannot silently pass the subgroup gate. Assay-missing/zero cases remain counted
separately and are excluded only from logarithmic errors.

```sh
python -m benchmarks.rbs.native_evaluation "$PRIVATE/frozen-evaluation.json" "$PRIVATE/final-aggregate.json" --stage final
python -m unittest discover -s tests/benchmarks -p 'test_native_evaluation.py'
```

The manifest's paths resolve relative to the manifest, and files with mismatched
hashes fail before evaluation. This is a reproducibility boundary, not an
adversarial access-control mechanism: the independent owner retains final labels,
records the agreed roster freeze and does not rerun selection after final results.
Native TE scale calibration does not convert a proxy into an absolute rate.

Before final outcomes, A/B agreed on two additional fixed affine controls and six
learning-curve fits, bringing the total budget to **24 fits/seven named model or
calibration families**. Historical and OSTIR affine controls fit an OLS log2 slope
on training only and center the training residual by its median. `fit_affine` and
`apply_affine` preserve failures and raw scores; numerical range failures are
explicit. This is a named native assay-scale adaptation with two fitted parameters,
not a changed upstream algorithm or absolute-rate conversion. All models retain
the common median-residual intercept convention in the aggregate report.

Select the simple reference on validation from training-median constant,
historical intercept-only and historical affine. Select upstream from OSTIR
intercept-only, rebeca intercept-only and OSTIR affine. A lower conditional MAE
cannot win by dropping original-historical-valid cases; report all and common-case
denominators. Freeze these choices before final evaluation. Original historical
and OSTIR intercept-only contrasts remain descriptive if not selected; they do
not create extra confirmatory claims. The fixed 25/50/75% training-family learning
curves use already selected penalties, never choose finalists and are not
uncertainty estimates.

A constant has undefined Spearman, not zero. If it is selected as the simple
reference, its rank comparison is not applicable. The no-more-than-0.05 rank-loss
gate still applies against original historical and the strongest nonconstant
eligible upstream. Every original-historical-valid primary case must remain
scored, independently of the chosen reference's coverage. Subgroups are fixed
input-only start codon (ATG/GTG/TTG/other), genomic strand and source/current
protein-length agreement/discrepancy. No threshold or cohort changes use final
outcomes. Protocol agreement is recorded in issue #16 comments
[6228890626](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/16#issuecomment-6228890626)
and [6228902938](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/16#issuecomment-6228902938).

## Public 2014 development audit

`benchmarks.rbs.oof` independently checks submitted OOF case/family identities,
every configuration's family-mean MAE and row RMSE, and the declared selection
rule (family MAE, then RMSE, then stronger penalty). It reads public predictions
and measurements, not training internals or weights. All eight configurations
reproduced within 1e-12: selected sequence lambda 1 family MAE 0.9346512883,
row RMSE 1.4277071995; selected hybrid lambda 1 family MAE 0.9147545857, row RMSE
1.3378574978. There are four configurations per family, eight total. The two
aggregate `standby2014-*-oof-audit.json` artifacts pin their inputs.

```sh
python -m benchmarks.rbs.oof benchmarks/rbs/standby2014.json "$MODEL_ROOT/sequence-v1-selection.json" "$AUDIT/sequence.json"
python -m benchmarks.rbs.oof benchmarks/rbs/standby2014.json "$MODEL_ROOT/context-energy-sequence-v1-selection.json" "$AUDIT/hybrid.json"
```

This recomputes reported prediction metrics; it is not an independent retraining
or proof of fold isolation. Selection itself uses these 22 source families, and
near-identical constructs can cross source-family boundaries. Treat the result as
development evidence, never native-host or wholly independent study performance.

# Frozen RBS experimental evaluation protocol

- Purpose: Keep experimental accuracy separate from implementation and hosted agreement.
- Scope: Wave 1 RBS scoring at supplied starts; no site-discovery or native-cyano validation.
- Last verified: 2026-10-17

Wave 2 native and secondary final results are recorded in the
[frozen evaluation](rbs-wave2-results.md). Its primary native protocol is distinct
from this historical/reporting-study scope; the 2017 panel remains secondary.

## Partitions and evaluator boundary

The primary development set is the 136 constructs in the 2014 standby-site
supplement (DOI 10.1093/nar/gkt1139). The 2009 author-curated supplement copy is
an audit-only source. The **entire 2017 coding-footprint study's 27 newly
measured constructs** (DOI 10.1093/nar/gkx061) is reserved for final evaluation.
Its repeated FP=0…35 tabs are predictions on the same measurements, not separate
experiments. Its additional 495-mRNA compilation is audit-only and contains
earlier studies; it must not be counted as an independent held-out set.

This is a study holdout from reconstruction tuning, not an assertion that the
published models never used those measurements. In fact, the 2017 paper selected
its footprint using 17 of these constructs. The evidence owner may inspect source
measurements for extraction and audit; Session A receives no held-out outcomes or
per-case error feedback for tuning. Only input identities and aggregate structural
overlap diagnostics are public before the final evaluation. Raw restricted
supplements and held-out outcomes remain outside Git. Two source rows were visible
to the evaluator during spreadsheet schema inspection; no reconstruction scoring
internals or predictions were examined.

Freeze exact record IDs, source rows, normalized sequence hashes, regulatory-window
hashes and partition labels in `benchmarks/rbs/experimental-split.json` before any
new model tuning. All conditions/replicates of a construct stay together. Keep
each study whole; no random row split. Audit cross-study exact sequences and
normalized edit similarity of the regulatory region (last 35 UTR bases plus first
70 CDS bases), at a predeclared 0.85 threshold. Quarantine any development family
connected to the held-out set, including other members of the source's labelled
design family, before exposing development outcomes. Report shared reporters and
templates even when no pair crosses that threshold. These thresholds are a
conservative audit rule, not proof that remaining examples are biologically
independent.

## Outcomes and normalization

- 2014: mean autofluorescence-subtracted mRFP1 flow-cytometry signal, E. coli DH10B,
  pFTV1/ColE1, J23100, LB + 50 µg/ml chloramphenicol, 37°C; three samples during
  exponential growth. These are not three independent biological days. Fluorescence
  is an expression proxy, not an absolute initiation-rate measurement.
- 2009: preserve original figure groups, means, SDs and replicate counts. Do not
  mix spacing-parameter fitting, existing RBSs and designed RBSs into a single
  untouched accuracy claim. Source row headers specify n=5 or n=6.
- 2017: use reported fluorescence divided by measured mRNA abundance (column P,
  zero-based 15) as the main relative translation outcome; report fluorescence
  separately. Only 18/27 have this measured translation outcome; nine explicit
  `N/A` rows are measurement-ineligible, not prediction failures. All 27 have
  fluorescence, with four samples across two days; mRNA replicate counts vary.
  Preserve both replicate counts and reported SDs. AEB-1 is the
  predeclared no-hairpin reference for normalization, not a fitted test-set scale.

For new reconstruction/live comparison with 2014, use the unstructured
`5'UTR_136` reference to report relative rates; for 2017 use AEB-1. Reference
normalization is declared in advance and reported as one shared reference
measurement, with induced dependence. Do not fit test-set slope/intercept or
choose the reference after seeing prediction errors. Include a constant-relative-
rate baseline of 1. Do not interpret unnormalized arbitrary-unit TIR as measured
fluorescence. Preserve absolute energy/rate comparison for reconstruction-versus-
live, where both outputs have matching declared scales.

## Metrics and promotion rule

For every comparison report submitted/eligible/successful/failed counts and
explicit exclusions. Invalid, unsupported and missing predictions are failures of
coverage; never turn them into 0 rates or drop them silently. Report all-case and
successful-pair twofold/fivefold fractions, Wilson intervals (descriptive only
when observations are dependent), log2 RMSE, median absolute log2 error, log2 bias,
Pearson correlation of logs, and actual tie-aware Spearman rho. Squared Pearson
correlation is not predictive R² or percentage accuracy. State undefined metrics
for constant vectors rather than inventing 0 or 1.

Report family-level resampling uncertainty, not an iid bootstrap across close
variants. The 2017 panel is one shared-template family: its family bootstrap is
undefined, and promotion needs additional independent families/studies. Analyze
all cases first, then prespecified sensitivities for source-flagged anomalies,
low signal and high measurement CV. Never tune an exclusion using prediction
residuals on the final set. Raw replicate-level measurements are unavailable for
several sources; SD/mean and n cannot establish a full noise model.

For ticket 13, freeze the exact baseline/improved commits, parameters and runtime
limits before submitting either to the evaluator. A candidate must reduce paired
family-bootstrap log2 absolute error with a 95% interval excluding no improvement,
without lower prediction coverage or a greater than 0.25 log2-unit increase in
mean absolute error in either short- or long-hairpin subgroup. If this small
panel cannot distinguish the models, report inconclusive evidence and use a new
independent study before promotion. No automatic parameter search on the holdout.

## Three separate comparisons

1. Reconstruction versus experiments: above biological outcomes and controls.
2. Hosted reference versus experiments: same constructs/settings and the same
   normalization/coverage rules; returned server identity must be recorded.
3. Reconstruction versus hosted reference: matching starts and per-term energies,
   raw log-rate differences, structure/coordinate agreement and status coverage.

Never substitute one comparison for another. Live acquisition is optional to
offline execution; no account, paid backend or restricted measurement file is
required for public fixture tests.

## Recorded 2017 exposure boundary

The original 2017 partition and its private outcomes remain fixed. During Wave 2
mechanism retrieval, Session A incidentally saw the published no-hairpin and +4
construct fluorescence values; no private table or final prediction errors were
opened or used for fitting. The paper itself selected its 13-nt footprint using
these constructs. Therefore the full panel is not wholly unseen, and a refined
profile has original-model exposure. Report it as a secondary external check,
not independent evidence for promoting the model. Native final outcomes remain
blinded under the frozen family partitions.

# A_12-benchmark-quality-and-ground-truth__20261016 — Active

- Scope: Audit and reproduce the actual benchmark quality of all four calculators, with RBS first.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-18
- Current State: Promoter published-column correlations, active parameters and 212 executed reference states independently reproduced. The single frozen Wave 4 evaluation completed all 6,556 jobs across Cambray335 and Kuo261; independent arithmetic/publication review confirms no joint-selection advancement (paired gain -0.0001661354, interval crossing zero). Cambray's selected panel is consumed; Kuo remains exposed secondary. Broader suite and native benchmark admission remain active.
- Verification: The benchmark suite passes 235 tests with 100% statement/branch coverage. DEM-516 independently matched all 464 floating and 659 exact aggregate fields and accepted both reporting corrections. Exact results, hashes, limitations and future-cycle hypotheses are in rbs-wave4-results.md; Promoter execution/review is in promoter-executed-reference.md. Original frozen artifacts and earlier results remain unchanged.
- Cleanup: Owning session records final checks and unresolved findings, distills reusable benchmark guidance, updates indexes and GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/12
- Priority: P0
- Owner: Session B (`9677689a-1792176763`), Wave 4 evidence; branch `wave4/b-independent-evaluation`, baseline `73521a6ae3251678073dce76181ee5909b34fe8b`.
- Dependencies: Start now from the source map; coordinate data pins/splits with 01, 05 and 06–09.

The owner reports that older calculators were not close enough to ground truth
and asks how good the current benchmarks are and whether prediction can improve.
Read [the initial assessment](../../validation/benchmark-quality.md).

## Work

- Trace every reported accuracy to a model version, dataset, organism, assay,
  sample count, split, fitted normalization, excluded observations and metric.
  Reconcile paper versions with the observed production server; unknown stays unknown.
- Fetch and pin permitted raw sequences/measurements, supplements and model-test
  harnesses. Reproduce the original metrics before comparing new methods. Explain
  differences in denominator or database size, including the 2020 abstract versus
  older SynBioMTS README, rather than merging their numbers.
- Assess leakage, designed versus native sequences, noise, dynamic range,
  selection biases, family/context redundancy and outlier handling. Distinguish
  prediction at known sites from genome-scale site detection.
- Define frozen grouped splits and all-case metrics with uncertainty. Include
  external study/host tests and cyano-specific evidence where available; no
  organism-specific accuracy claim without an adequate independent set.
- Pair coin-funded live predictions with these measured sequences where useful.
  Report live-versus-experiment, reconstruction-versus-experiment and
  reconstruction-versus-live as three distinct comparisons.
- Quantify evidence gaps and propose the highest-value additional data. If a
  larger live panel is preferable, give ticket 05 a sample-size rationale and coin
  budget for lab funding. New experimental ground truth needs a separate lab plan.

## Acceptance criteria

- Each calculator has a reproducible benchmark-quality card with reported and
  recomputed metrics, limitations, exact model/data versions and uncertainty.
- The current-live-version status is explicit; historical results are not
  mislabeled current. Operon end-to-end quality is not inferred from submodels.
- Frozen experimental and live-reference panels and appropriate simple baselines
  are ready for tickets 06–09/13, with no training/tuning leakage.
- A prioritized improvement hypothesis list identifies evidence, expected benefit,
  required data, cost and the held-out test that could falsify each hypothesis.

## Verification to record

Raw-data hashes/licences, metric reproduction commands, split-overlap audits,
denominators/outlier sensitivity, confidence intervals, and an independent check
of high-impact accuracy claims. A literature summary alone does not complete this ticket.

# O_12-benchmark-quality-and-ground-truth__20261016 — Open

- Scope: Audit and reproduce the actual benchmark quality of all four calculators, with RBS first.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Initial primary-source assessment exists in benchmark-quality.md; raw-data reproduction and current-live-version evaluation have not run.
- Verification: Initial numerical statements and located passages checked against primary papers; implementation benchmarks remain unexecuted.
- Cleanup: Owning session records final checks and unresolved findings, distills reusable benchmark guidance, updates indexes and GitHub issue, then removes the resolved ticket.
- Priority: P0
- Owner: Unclaimed.
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

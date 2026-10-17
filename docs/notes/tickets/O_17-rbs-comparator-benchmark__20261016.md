# O_17-rbs-comparator-benchmark__20261016 — Open

- Scope: Establish runnable, task-matched mechanistic and ML comparator benchmarks with complete provenance.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Primary-source shortlist prepared; no newly audited comparator has been executed. Planned Wave 2 owner is Session B.
- Verification: Paper/repository metadata and selected licence files inspected; full artifact adoption and runtime verification pending.
- Cleanup: Preserve comparator/source contracts and reproducible reports, update indexes and GitHub issue, then remove the resolved ticket after acceptance.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/17
- Priority: P0
- Owner: Unclaimed; reserved for Session B when Wave 2 is started by the user.
- Dependencies: 01 code/weight/data review, 12/16 frozen evaluation; informs 04/13/18 and release 06.

Read [comparator landscape](../../validation/rbs-comparator-landscape.md) and
[Wave 2 program](../../validation/rbs-wave2-program.md).

## Work

- Refresh the primary-source search for strong applicable methods. Start with
  OSTIR, rebeca, SAPIENs, EMOPEC and Solaris; inspect GARDN–SANDSTORM and RBSeval
  as restricted research comparators only where permitted. For localization,
  consider Prodigal/GeneLM separately from rate predictors. Avoid an unbounded
  catalogue or claiming that public download implies open reuse.
- Audit exact code, weights, energy tables, datasets and training exposure;
  communicate an early recommended model/installation path to A. A paper's CC
  licence does not automatically license its code, data or weights.
- Implement isolated optional benchmark runners under benchmarks/, retaining
  native input/output semantics, inference resource limits and failures. Do not
  add heavy/restrictive dependencies to the required runtime or ordinary CI.
- Demonstrate actual predictions from at least one eligible learned comparator
  and one distinct mechanistic/empirical comparator, or record bounded failures
  and leave the unmet comparison explicit. Verify any environment port numerically
  before retaining the upstream identity.
- Compare on frozen common cases and full-domain coverage; retain separate
  zero-shot, development-calibrated and fine-tuned results. Fix calibration and
  compute budgets without final outcomes. A single headline correlation is not
  adequate; report errors, ranking, uncertainty, subgroups and runtime.
- Extend independent metric tests, including rejecting booleans/nonfinite scores
  as measurements and preserving assay-defined zero/missing distinctions.

## Acceptance criteria

- Dated comparator matrix with pins, applicable domain, source/weight/data terms,
  runtime status, exclusions, input context and known training overlap.
- Reproducible real comparator predictions, fair task-specific reports and
  integration-ready manifests/runners/tests. Restricted artifacts remain outside
  the open release; freely runnable released profiles have no paid dependency.
- A named strongest eligible comparator and an evidence-based recommendation for
  simple calibration, mechanistic improvements, hybrid learning or transfer
  learning; lack of adequate data is a valid conclusion, not a fabricated winner.

## Verification

Fresh isolated comparator smoke tests, source/weight checksums, numerical parity
fixtures for ports, all owned benchmark branches covered, frozen evaluation
commands, and exact model/data/parameter identities in every report.

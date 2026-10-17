# A_06-rbs-validation-and-first-release__20261016 — Active

- Scope: Validate and release the first fully usable open RBS calculator.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-17
- Current State: Release candidate 0.2.0rc1 on wave2/rbs-models, stacked draft PR20. Real mechanistic/refined/native/learned scoring, development recipes and independent frozen comparisons are implemented. Native sequence fails the promotion rule; reporter generalization and backend coverage remain limited. Reviewed B evaluator commits through 9bb479f and the final report package 4b2f582 are integrated (d062b95). The independent arithmetic audit reports 9,759 checks and no numerical mismatches; its private-review transcript handling exception is disclosed in the result provenance. A public tag/package and main merge are separate, unauthorized release actions.
- Verification: Integrated a3b46fa passes 1,383 real-backend tests at 100% statement/branch coverage (4,185/1,742), plus Ruff/mypy. Cached inference review accepted immutable 7547778 including independent arithmetic checks. Fresh wheel single/batch/native/GFF3/learned and real Tan subset checks pass; four Linux/macOS Python 3.11/3.14 jobs pass at 62981a6, including the shipped real two-strand native example. Final report hashes and exact freeze copy verify; the final source-package and CI status are linked from draft PR20.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/6
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), Wave 2 implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: 02–04; 05 for hosted claims; 12/16/17 independent evidence and comparisons; 18 for native-context exports. Scope claims to completed gates.

Deliver the first installable, documented RBS prediction release. This is the milestone before implementation of the other calculators; source discovery for those tools may continue independently.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.
- Apply [native task-specific gates](../../validation/rbs-native-validation.md):
  TSS context integrity, experimental TIS localization and translation-strength
  accuracy are separate. Include eligible ML/mechanistic contenders from 17,
  native TE/context challenges from 16 and full prediction coverage. Unsupported
  leaderless/native cases remain explicit; they cannot silently disappear from
  denominators. B owns final metrics and outcomes; A owns release integration.

- Assemble licensed experimental/reference datasets with exact sequences, host, construct context, measured quantity, conditions and model settings. Split by study/sequence family to prevent near-duplicate leakage.
- Evaluate equation correctness, hosted agreement and experimental predictive accuracy separately under the shared contract. Report site matching/coverage, per-term energy differences, log-rate errors, ranks, failures and uncertainty by domain.
- Predeclare acceptance tolerances and numerical regression criteria before held-out evaluation. Compare against the historical baseline, simple appropriate baselines and Jaymin's scorer where executable.
- Package a stable library/CLI, single/batch prediction, JSON/CSV and verified annotated export, examples, supported input limits, dependency pins and full source/parameter notices.
- Publish model identity, known deviations and applicability. Native cyanobacterial accuracy is not established by an E. coli fit or a host dropdown. The UTEX synthetic-RBS reporter paper has narrower scope than genome-wide calibration.

## Acceptance criteria

- A clean machine installs the release and runs complete offline examples with no account, private DNAc, required restrictive dependency or unavailable binary.
- All specified prediction paths and exports pass unit/integration/coordinate tests; every added branch is exercised. Runtime/memory limits and batch failure behavior are measured.
- Reproducible benchmark reports distinguish implementation correctness, production-reference agreement and biological accuracy, with complete denominators and unresolved gaps.
- Hosted testing can be pending for a clearly labeled provisional release, but claims of production equivalence and completion of the hosted-comparison work remain open until measured. Never fabricate reference fixtures.
- The release/tag, compatibility notes and consumer-ready schema are available; ticket 10 can integrate this first calculator independently of the others.

## Verification to record

Full CI/coverage, fresh-install and offline smoke tests, frozen benchmark rerun, licence/dependency inventory and an independent review of the exact release candidate. RBS design is completed under ticket 11 and must not be advertised before it works.

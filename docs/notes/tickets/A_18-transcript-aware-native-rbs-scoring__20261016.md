# A_18-transcript-aware-native-rbs-scoring__20261016 — Active

- Scope: Implement portable transcript-aware native RBS scoring and coordinate export in the reconstruction repository.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-17
- Current State: Native JSON/GFF3 adapter and source integration are implemented. All 4,808 Tan rows are retained; 2,417 contexts prepare and 2,212 score successfully. All 2,503 mapped PCC contexts match independent 200-nt sequences/start 100 at 30°C; 27 unresolved rows remain unsupported. Three full PCC profile runs are underway.
- Verification: Independent coordinate review accepted the core adapter after exhaustive checks; final temperature-alias/unresolved-source delta is in review. Latest 106 source/native/collector tests pass with 100% statement/branch coverage and the real backend. Fresh-wheel eight-case Tan example gives five scores and three explicit leaderless cases. Final integrated gates remain.
- Cleanup: Distill the final input/coordinate/runtime contract, update indexes and GitHub issue, then remove the resolved ticket after acceptance.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/18
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), Wave 2 implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: Existing runtime 02/03; 16 supplies admitted manifests and mappings; refinements 04 as available. Consumer UI/admission remains ticket 10.

Read [native validation](../../validation/rbs-native-validation.md) and
[Wave 2 program](../../validation/rbs-wave2-program.md).

## Work

- Agree an explicit manifest/record contract with B, then implement source-agnostic
  extraction and scoring for pinned genomes, transcript contexts and starts.
  B owns source-specific parsing/association evidence; A owns the runtime adapter.
- Preserve alternate transcript contexts, source associations and unmapped cases;
  clip leaders to verified transcript starts. Never treat a TSS as a TIS or choose
  a context using its agreement with an experimental translation outcome.
- Define supplied-start scoring versus conditional candidate scanning, start
  universe, tie policy, strand orientation and genome projection. Add a distinct
  versioned result contract if existing semantics would change.
- Test reverse strand, circular origin where supported, short/no leader, internal
  operon starts, overlapping starts, annotation disagreements, mismatched assembly,
  missing context and failed engines. Unsupported cases remain explicit.
- Keep strain/aSD/temperature parameters explicit and uncalibrated unless evidence
  supports a named calibration. Learned models must not fabricate energy terms or
  SD intervals. Score equal input context for fair comparisons.
- Deliver a local CLI/library batch example and machine-readable annotated output,
  with bounded resources and portable inputs. No browser/UI, cyano checkout edits
  or mutable sibling-repository dependency is required.

## Acceptance criteria

- Real native-context inputs admitted by 16 run end to end with reproducible
  predictions, provenance and verified coordinate exports; synthetic fixtures
  alone do not satisfy this ticket.
- Every new path and boundary is covered; fresh installation and offline examples
  pass. Native mapping integrity is distinguished from prediction accuracy.
- The adapter is ready for independent B evaluation and later consumer integration;
  no unsupported native-UTEX accuracy, calibrated-rate or biological RBS-boundary
  claim appears in output or documentation.

## Verification

Full runtime CI/coverage, independent coordinate fixtures supplied by B, fresh
wheel single/batch execution, performance bounds and exact source/model identities.

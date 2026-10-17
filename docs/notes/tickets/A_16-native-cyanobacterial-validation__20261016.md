# A_16-native-cyanobacterial-validation__20261016 — Active

- Scope: Build native cyanobacterial transcript-context, translation-start and translation-strength benchmarks with experimental evidence.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-17
- Current State: Tan context and Karlsen relative TE admitted with frozen splits. Direct TIS v3 source yields 91 primary and eight weak supported starts; outcome-blind stop queries contain 1018 candidates. Thiel reporter/context admission, independent secondary-study challenges and final evaluation remain active.
- Verification: All 107 owned benchmark tests pass, 100% statement/branch coverage (1346/550); targeted Ruff and scoped documentation validation pass. Actual upstream OSTIR/rebeca inference and synthetic numerical smokes pass; native partitions independently reviewed and reproduced. Source/evaluation details are in rbs-native-data-card.md, rbs-positional-evidence.md and rbs-upstream-comparators.md.
- Cleanup: Resolve only completed scope, distill reusable dataset/evaluation contracts, update indexes and GitHub issue, then remove the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/16
- Priority: P0
- Owner: Session B (`9677689a-1792176763`), Wave 2; branch `wave2/rbs-validation`, baseline `fc78dee42f934417f2bf905ae71b582903b7a949`.
- Dependencies: Source/licence review 01, benchmark protocol 12; supplies immutable data/contracts to 18 and final evidence to 06/13.

Read [native validation](../../validation/rbs-native-validation.md) and the
[Wave 2 program](../../validation/rbs-wave2-program.md). Tan 2018 is TSS/context
evidence; it is not direct RBS/TIS ground truth.

## Work

- Re-fetch and pin Tan S1/S2 and the exact UTEX assembly/annotation. Create a
  portable source extract and explicit transcript-context associations; audit
  alternate TSSs, reverse strand, historical/current CDS disagreements and
  leaderless candidates without altering the cyano consumer repository.
- Admit at least one native matched RNA/Ribo-seq TE dataset and one independent
  cyanobacterial reporter/context dataset, prioritizing Karlsen 2018 and Thiel
  2018. Add diurnal/stress studies as independent challenges only after overlap
  and assay audits. Investigate the direct TIS-Ribo-seq/proteogenomic lead.
- Separate evidence types and host/condition labels; identify sequence, source
  row, assembly, outcome, replicate, censoring, confidence and rights per record.
  Hold restricted raw data outside Git with hashes and reproducible permitted
  acquisition; public tests must not need private data.
- Freeze development/validation/final partitions before exposing outcomes to A.
  Preserve the earlier 2017 holdout. Audit sequence/orthogroup, reporter, study,
  repeated-condition and pretrained-model leakage with ticket 17.
- Implement independent metrics for exact and secondary tolerant TIS matching,
  conditional ranking, coverage, and permitted precision/recall; maintain the
  separate strength evaluator. Test coordinate offsets, alternative starts,
  negatives/unlabelled cases, ties, uncertainty and failures.
- Produce learning-curve/data-sufficiency evidence and a concrete optional UTEX
  prospective experiment proposal with CDS diversity, matched RNA/protein
  measurements, controls, replication, randomization, power/cost rationale and
  a final untouched panel. No wet-lab work or purchasing is authorized.

## Acceptance criteria

- Reproducible permitted extraction and immutable manifests for the admitted
  context, strength and positional evidence; explicit coverage and unresolved
  mapping/assay cases. A missing TIS source is a tracked remaining dependency,
  not a fabricated positional benchmark.
- Task-separated executable evaluators, meaningful tests, frozen split hashes
  and subgroup/uncertainty reports. TSS counts never become translation labels.
- A receives input contracts and development outcomes only; final outcomes and
  per-case final errors remain with the evaluator until the agreed release step.
- Scientific claims identify exact host, measured quantity and evidence tier;
  PCC 6803 evidence never becomes native-UTEX calibration by relabeling.

## Verification

Re-download/check source hashes, re-extract deterministically, validate both
strand mappings and assembly boundaries, test metric arithmetic on hand-checkable
fixtures, run all owned benchmark tests, and record exact pins/commands. Keep
uncompleted positional or prospective-validation work open.

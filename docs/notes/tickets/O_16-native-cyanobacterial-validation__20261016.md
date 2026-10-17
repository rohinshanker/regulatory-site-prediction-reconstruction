# O_16-native-cyanobacterial-validation__20261016 — Open

- Scope: Build native cyanobacterial transcript-context, translation-start and translation-strength benchmarks with experimental evidence.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Primary sources and admission gates identified; no new native benchmark or accuracy result implemented. Planned Wave 2 owner is Session B.
- Verification: Planning sources checked; source extraction, frozen splits, metrics and tests remain to be implemented.
- Cleanup: Resolve only completed scope, distill reusable dataset/evaluation contracts, update indexes and GitHub issue, then remove the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/16
- Priority: P0
- Owner: Unclaimed; reserved for Session B when Wave 2 is started by the user.
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

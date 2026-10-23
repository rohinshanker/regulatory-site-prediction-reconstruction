# RBS cross-host transfer evaluation

- Purpose: Distinguish transferable ordering, host calibration and recoding-effect prediction using independently measured outcomes.
- Scope: Evaluation design and source-admission status for E. coli, PCC 6803 and UTEX 2973; no new model execution or target-host accuracy claim.
- Last verified: 2026-10-21

## Present evidence and result status

The [machine receipt](../../benchmarks/rbs/host-transfer-admission.json) records the current decision. No new UTEX RBS accuracy estimate has been calculated. The repository's existing [PCC 6803 evaluation](rbs-wave2-results.md) did not pass its prespecified model-promotion gate; this different organism is not UTEX validation. Tan TSS/count evidence concerns transcription and cannot substitute for translation measurements.

The separate [failure-mode analysis](rbs-host-transfer-failure-analysis.md) uses
only existing public aggregates. It distinguishes scale, ordering, context,
measurement and coverage errors, with exact pinned fields in its own snapshot.
It does not complete the thesis audit, identify a UTEX-specific causal mechanism
or provide new accuracy measurements.

The Edinburgh record for [Schiavon Osorio's 2022 thesis](https://era.ed.ac.uk/items/a4bb4f3a-d175-4eaa-bbc6-0c70fb5f659b), DOI 10.7488/era/2453, reports an RBS library compared across E. coli, PCC 6803 and UTEX 2973, with host-dependent activity. That abstract is a source lead only. Full construct identity, exact numerical measurements, normalization, repeat structure and rights have not been admitted here. No values were digitized from figures, no correlations reconstructed from an abstract, and no source absence inferred from an incomplete audit.

The scoped source-admission assignment DEM-612 terminated with the provider's biology safeguard rejection before a dossier or source files were produced. It was cancelled without retry, disguise or rerouting. This is a provider execution block, not a finding that the thesis is unavailable or unusable. The audit and numerical evaluation remain pending; existing admission requirements are unchanged.

## Separate estimands

| Comparison | Required evidence | Permitted interpretation |
| --- | --- | --- |
| Same-part activity across hosts | Matched construct identities, host-specific measurements and consistent within-host normalization | Descriptive portability of those parts in those contexts; not predictor accuracy |
| Frozen mechanistic predictions versus target-host measurements | Exact model/backend/configuration and full relevant transcribed inputs, independently verified outcomes | Untuned target-host performance on the admitted endpoint |
| Separately calibrated model versus untouched target data | Calibration cohort distinct from test by sequence family/context; frozen coefficients before test outcomes | Benefit of that explicitly named host adaptation |
| Original versus recoded prediction differences | Paired measured outcomes for the corresponding original and recoded constructs | Accuracy of changes in the measured endpoint; not automatically discovery of internal initiation sites |

Mechanistic models still contain assumptions and empirical parameters. An independently established host input, such as a ribosomal sequence, is configuration; choosing coefficients using target outcomes is calibration. Keep the unchanged E. coli configuration, independently justified target configuration and any later fitted model separate. A monotonic scale adjustment cannot repair incorrect ranking.

## Admission before any scoring

Require the exact source file identities and applicable reuse terms; study/host/condition/assay and reporter identities; all attempted constructs and exclusions; full relevant transcribed sequence, leader/CDS junction and supplied start coordinate; evidence for transcript boundaries; and measured values with units, normalization and replicate structure. Preserve uncertainty in vector copy number and transcript abundance rather than calling total reporter output an initiation rate. Short RBS strings alone do not establish the surrounding folding context.

Tabulated primary measurements are preferred. Figure-only observations remain explicitly approximate and require their own extraction uncertainty and analysis decision; they cannot silently become exact raw measurements. Unknowns, censoring, below-background values and failures must not become zeros. A source aggregate correlation is not independently reproduced merely by transcribing it.

Before execution, freeze a separate immutable receipt containing the admitted input roster/hashes, predictor and backend identities, parameters, host configuration, resource limits, expected output accounting and analysis settings. This document is a design contract, not that execution receipt. There is no scoring authorization or complete candidate freeze implied by its existence.

## Analysis rules

First report attempted, source-eligible, prediction-successful and measurement-eligible denominators. Compare model coverage on the complete admitted set and metrics on explicitly identified common eligible cases. Preserve failure reasons; never select the successful subset without reporting its parent denominator.

Use tie-aware Spearman for ordering and show the measurement range and repeatability. Separate within-host ranking from cross-host activity correlation. Fold error requires a commensurate measured scale or a reference/calibration fixed independently of test errors. Do not calculate fold accuracy between arbitrary model units and raw fluorescence. An independent multiplicative reference preserves ordering; an outcome-fitted transformation changes the calibration claim.

Keep all hosts, replicates and conditions of related constructs together for partitioning. Group by shared leader family, reporter context and reused templates as supported by the source. Define uncertainty from actual biological replication and dependence; wells, cells and repeat reads do not increase the independent biological sample size. When a panel has only one shared family or lacks repeat-level values, report the resulting limit rather than manufacture population-level precision. Retain outliers unless independent predeclared assay QC excludes them.

A literature dataset inspected during this audit is exposed exploratory evidence. No test-set fitting, model selection, outcome-dependent case filtering or relabelling as untouched confirmation is allowed. A future confirmatory study needs its own frozen sampling plan, practical effect thresholds, failure policy and power calculation informed by a separate pilot. No universal transfer claim follows from one host or one reporter.

## Smallest next scientific step

The unresolved source audit must establish whether exact paired measurements and construct contexts exist. If they do, the first analysis is descriptive cross-host portability followed by a separately frozen untuned-model comparison; fitting is not needed to answer that initial question. If they do not, record precisely which evidence is missing before proposing data acquisition. Author contact, wet-lab execution and purchasing are separate actions and have not occurred.

The existing [prospective UTEX measurement proposal](rbs-utex-measurement-proposal.md) supplies assay/confounding and pilot-versus-confirmation guidance. Its single-host counts and budget do not cover a new multi-host study automatically. A paired-host extension needs a fresh laboratory feasibility and cost assessment. For the visualizer's recoding question, paired original/recoded measurements and any internal-initiation endpoint must be explicitly included; ordinary reporter-strength transfer alone cannot validate them.

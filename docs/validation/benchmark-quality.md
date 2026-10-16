# Benchmark quality and improvement contract

- Purpose: Assess published benchmark limitations and define stronger evaluation.
- Scope: Primary-source metric observations and planned independent validation; no new live run.
- Last verified: 2026-10-16

## Current evidence assessment

Checked 2026-10-16 against the primary sources below. These are published model
results, not a newly measured score for the current live server. We have not run
the server or our reconstruction. A paper's version and the deployed version
must be reconciled before assigning its metrics to production software.

| Calculator / evidence | Reported performance | What it establishes and misses |
| --- | --- | --- |
| RBS, 2009 original study | R² 0.54 for 28 existing RBSs; R² 0.84 for 29 designed RBSs; the latter average energy error corresponds to about 2.3-fold expression error | Results vary with construct selection; a designed panel does not establish broad native-sequence accuracy. |
| RBS, 2017 paper's summary of earlier validation | Across 495 characterized mRNAs, 57% within twofold and 83% within fivefold | Useful but substantial error remains. This is historical coverage, not a held-out score for today's v2.1.1 server. |
| RBS, 2020 Model Test System | Abstract describes 9,862 characterized systems, six compared models, 100 tested hypotheses and improved accuracy | Exact version-by-dataset metrics, filters and splits still need full-paper/supplement reproduction. Do not substitute the repository README's different database size or a third-party comparison table. |
| Promoter, 2022 | Random 90/10 split of 5,193 single-TSS variants: R² 0.80 on 520 test variants; three external in-vivo datasets: R² 0.60, 0.45 and 0.65 | Substantial external evidence, with domain-dependent performance. Correlation is not percentage accuracy, absolute-rate calibration, or genome-wide positional precision/recall. |
| Riboswitch, original study (2016) | 55% of 67 switches within twofold in activation ratio; Pearson R² 0.61 on 59 after eight outliers, Spearman 0.69 on all 67 | Moderate quantitative accuracy. Outlier and denominator choices matter; evaluate all examples and ON/OFF levels separately. |
| Riboswitch, protein-sensing extension (2023) | Full model: R² 0.48, 44% within twofold, N=34; optimized aptamer constraints: R² 0.64, 56% within twofold | The constraints were selected for best accuracy on these switches. The improvement requires independent held-out confirmation, and cell-free calibration differs from in-vivo calibration. |
| Operon, current documentation | Documents many submodels and outputs; no unified end-to-end accuracy benchmark established in this assessment | Component accuracy cannot be promoted into an overall Operon accuracy claim. Audit submodels and complete operons separately. |

The source assessment supports heterogeneous, sometimes sizable errors; it does
not support calling all calculators inaccurate or assigning one accuracy number
across organisms. Current deployed performance remains an empirical question.
For cyano, published synthetic UTEX RBS use and a poor PCC 6803 prediction result
have different scopes; neither supplies a native-UTEX genome-wide benchmark.

## Primary sources and checked locations

- [Original RBS paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC2782888/), results
  for existing and designed RBSs, Figures 2B/2E; XML hash in the source map.
- [2017 RBS paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5435973/), biophysical
  model description following equations 1–3; XML hash in the source map.
- [2020 Model Test System abstract](https://pubmed.ncbi.nlm.nih.gov/33054181/).
  Full-text quantitative audit remains ticket 12 work. The
  [public harness](https://github.com/reisalex/SynBioMTS) is a reuse candidate;
  inspect fitting/outlier filtering before adopting reported metrics.
- [2022 Promoter paper](https://www.nature.com/articles/s41467-022-32829-5),
  “Model training and validation” and “Model generality,” Figures 2–3 and
  Supplementary Figure 3. Located XML phrase: “remaining unseen test set
  (520 promoters, 10%).” Original PMC9440211 XML SHA-256:
  `b0418e683a6fd23906dc3e8329ef74dd166298aab39c64b54ec1f96428b2d625`.
- [Original Riboswitch paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4705656/),
  “Validating model-predicted requirements for riboswitch activation,” Figure 3
  and Supplementary Figure S11. Located phrase: “55% of all riboswitches had
  their ARs correctly predicted to within 2-fold.” XML SHA-256:
  `fa0d7350adf4b07bcdb2b818c779ffabf135c50a72318569232a725f0d1868a6`.
- [Protein-sensing Riboswitch paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10140043/),
  “Accuracy analysis and improvement by modifying aptamer structural constraints,”
  Figure 6C/E. Located phrase: “with 56% of the riboswitch variants achieving
  less than 2-fold prediction error.” XML SHA-256:
  `89d6e12a9d85af7b10b5dabc8764e5a4f2cc68ad977f19e74e9f77d223b10b8f`.
- [Operon documentation](https://docs.denovodna.com/docs/operon-calculator),
  Summary and Outputs: capability descriptions, not a validated accuracy table.

XML was read from the previously retrieved Europe PMC full-text files, with
the quoted passages mechanically re-matched. PMC browser requests returned
interstitials in this pass; no bypass was attempted. Re-fetch and pin the
supplementary raw measurements before reproducing metrics.

## Improve the benchmark before claiming an improved model

- Freeze sequence/study/family/host-grouped train, validation and final test
  partitions. Near-identical variants and repeated conditions from one construct
  must not straddle partitions. Add leave-one-study/host/aptamer-out evaluations
  when supported by the sample count; identify low-powered comparisons.
- Use experimental outcomes appropriate to the prediction: transcript abundance
  is not automatically initiation rate; fluorescence includes translation,
  maturation and degradation; growth or product yield is still more indirect.
  Record measurement noise, replicates, detection limits and normalization.
- Report all-case and explicitly filtered metrics with matching denominators,
  failure coverage, log-scale errors, twofold/fivefold fractions, rank correlation,
  calibration and uncertainty intervals. Do not refit slope/intercept or remove
  outliers on the final test set and call the result an untouched prediction.
- Site discovery needs position-tolerant precision/recall and a justified negative
  set, not just rate correlation at known starts. Unknown sites are not verified
  negatives. Control false discoveries on long sequences.
- A coin-funded live-reference panel measures behavioral agreement. Only paired
  experimental measurements measure accuracy against biological ground truth.
  More coins cannot by themselves create new experimental ground truth.

## Two maintained model tracks

Keep a **compatibility profile** aimed at reproducing a pinned published/live
model and a separately versioned **improved profile** aimed at better experimental
prediction. An improvement may intentionally disagree with the website; expose
that fact and evaluate both on identical frozen panels.

Prioritize verified implementation/parameter fixes, realistic transcript context,
host-specific calibration supported by data, better structural constraints and
kinetics, and measurement-aware uncertainty. Consider learned residuals or new
mechanisms only after simple baselines and ablations justify them. Do not assume
adding complexity helps: the 2022 promoter paper's quadratic interaction model
improved its fitted dataset but did not improve external performance.

Ticket 12 audits/reproduces benchmark quality. Ticket 13 implements and tests
improvements, RBS first. An improved model is promoted only after predeclared
held-out improvement with uncertainty and no unacceptable subgroup regression;
otherwise retain the baseline and report the negative result. Proposals for new
lab measurements or larger coin purchases remain concrete proposals until the
owner authorizes them.

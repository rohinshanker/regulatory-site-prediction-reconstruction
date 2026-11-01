# Frozen RBS Wave 2 evaluation

- Purpose: Preserve reproducible experimental results, their limits and falsifiable next experiments.
- Scope: PCC 6803 relative TE, conditional TIS selection, secondary condition/reporter transfer and separate hosted diagnostics.
- Last verified: 2026-10-17
- Evidence owner: Session B (`9677689a-1792176763`); runtime/model integration belongs to Session A.
- Planning baseline: `fc78dee42f934417f2bf905ae71b582903b7a949`.
- Machine-readable [result manifest](../../benchmarks/rbs/results/wave2-results-manifest.json) and byte-exact [model freeze](../../benchmarks/rbs/results/wave2-model-freeze.json).

## Decision and frozen experiment

**No native strength model passes the prespecified promotion rule.** The native
sequence model has a small measured gain over a training-median constant, and no
resolved gain over the strongest eligible calibrated upstream comparator. The
mechanistic hybrid remains coverage-ineligible. These outcomes do not support
native UTEX calibration, universal accuracy or hosted numerical equivalence.

The native champion and controls were selected on 1,465 training and 479 validation
genes before opening the final outcomes. The frozen final cohort contains **468
genes in 423 homology groups**. Grouping used the full current annotation, protein
homology and exact edit-similarity context edges; all conditions of a gene stay
together. The group heuristic does not certify true orthology. See the
[native data card](rbs-native-data-card.md) for every inclusion and mapping rule.

The finite budget was 24 fitted configurations: eight public-2014, eight native,
six fixed learning-curve fits and two train-only affine controls. No stochastic
fits or final-set search occurred. A froze scientific/export code at
`7547778c508d4a31b4a4f95df370923ce8bd07c3`, model metadata at
`dab5fb5956d12b57e0f8207bfded60dda370ec1c`, and all four model files. B verified
those file hashes without reading coefficients or scoring/training internals.
The corrected exporter preserves every earlier prediction record exactly; only
its code/collection identity changed. All prepared sequences, starts, aSD,
temperatures, hosts and identity sets were checked independently.

Every native method receives the same kind of train-only median log2 residual
intercept. Historical and OSTIR affine controls additionally use their fixed
training-only OLS log2 slope. Constant and OSTIR affine were the two eligible
validation references. Historical affine's validation coverage, 449/479, was below
95%; its conditional error did not make it eligible. The hybrid similarly lost
39 historical-valid validation cases and was excluded from promotion before final
scoring. This selection was not reconsidered after observing final coverage.

## Primary native strength results

[Complete primary aggregate](../../benchmarks/rbs/results/karlsen2018-final.json).
Errors are log2 units of the **HC RPF/RNA relative TE proxy**, not absolute
initiation rates. MAE/RMSE and rank use successful predictions; coverage always
uses all 468 eligible cases. No outliers were removed.

| Frozen method | Success / 468 | MAE | RMSE | Spearman rho |
| --- | ---: | ---: | ---: | ---: |
| Native sequence-v1, selected | 468 | 0.957226 | 1.238840 | 0.243990 |
| Constant training median | 468 | 0.989886 | 1.272112 | undefined |
| OSTIR, train-only affine | 467 | 0.973671 | 1.252964 | 0.202459 |
| Native hybrid, ineligible ablation | 423 | 0.939731 | 1.223515 | 0.308246 |
| Historical, intercept only | 445 | 5.195557 | 7.449310 | 0.159858 |
| Historical, train-only affine | 445 | 0.979096 | 1.261976 | 0.159822 |
| Footprint2017, intercept only | 445 | 5.138887 | 7.365622 | 0.127170 |
| Context2017, intercept only | 423 | 30.912379 | 69.078606 | 0.105406 |
| OSTIR, intercept only | 467 | 2.796606 | 4.046890 | 0.202459 |
| rebeca scalar checkpoint, intercept only | 468 | 3.630777 | 4.392945 | 0.067036 |

The two confirmatory comparisons use paired homology-group resampling, 10,000
replicates, seed 20261017, and individual 97.5% intervals. A positive gain means
reference MAE minus champion MAE. The required worthwhile point gain was 0.20.

| Reference | Common pairs / groups | Champion MAE gain | 97.5% interval | Promotion |
| --- | ---: | ---: | --- | --- |
| Constant | 468 / 423 | 0.032660 | [0.010912, 0.053840] | fails practical-gain threshold |
| OSTIR affine | 467 / 423 | 0.014808 | [−0.009560, 0.038680] | unresolved gain; below practical threshold |

The second gain uses its 467 common cases; subtracting the full-cohort MAEs in the
first table gives a different number. Coverage, historical-valid preservation,
rank-loss and sufficiently sized subgroup gates pass. Start-codon ATG/GTG,
genomic strand and source/current protein-length agreement/discrepancy are the
frozen strata. TTG has 14 cases and is descriptive, not a passed powered gate.
Constant correlation is undefined; the historical and nonconstant upstream rank
safeguards remain active. Original historical/OSTIR intercept comparisons are
explicitly descriptive, outside the two confirmatory contrasts.

The sequence model is within 2× for 284/468 and 5× for 440/468. Constant counts are
281/468 and 437/468; OSTIR affine counts are 287/468 and 432/468. These thresholds
are inclusive. Reported Wilson intervals are descriptive for dependent genes;
paired group intervals govern the comparison. Neither interval estimates
biological replicate uncertainty.

## Secondary condition transfer

[LC results](../../benchmarks/rbs/results/karlsen2018-lc-secondary.json) retain the
same 468 final genes/423 groups. With unchanged HC calibration, sequence MAE is
0.952980, constant 0.998336 and OSTIR affine 0.977833 (467 successful). Separately
fitting only the LC training-family intercept gives 0.946456, 0.990999 and 0.970035.
No feature, coefficient, slope or model selection changes. HC/LC are conditions
of the same source study and genes, not independent experimental studies.

[Diurnal results](../../benchmarks/rbs/results/karlsen2021-diurnal-secondary.json)
use 213 final genes in 203 inherited groups for each phase. Of these contexts,
210 already occur in the primary source and three are new. None of their groups
occurs in primary training. Across all admitted diurnal inputs, exact reuse is
986 contexts plus 14 newly inferred; 126 source rows remain unsupported. The five
phases are reported separately and are never pooled as 1,065 independent genes.

| Phase | Sequence, frozen HC MAE | Constant, frozen HC MAE | Sequence, phase-train intercept MAE | Constant, phase-train intercept MAE | OSTIR affine, phase-train intercept MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| BRISE | 1.214927 | 1.200911 | 0.685752 | 0.710402 | 0.687026 |
| ARISE | 1.392695 | 1.373101 | 0.646317 | 0.663938 | 0.646637 |
| MDAY | 1.590132 | 1.571779 | 0.725933 | 0.742878 | 0.727077 |
| BSET | 1.631602 | 1.612714 | 0.773540 | 0.785780 | 0.769914 |
| ASET | 1.328821 | 1.312206 | 0.730341 | 0.758030 | 0.738233 |

All three tabulated methods cover 213/213 per phase. Hybrid successes are 190/213.
The large scale change after per-phase calibration cannot be assigned solely to
biology: study, condition, cohort selection and abundance normalization differ.
Diurnal targets are ratios of geometric-mean sum-scaled abundances; paired
replicate TE and absolute initiation were not measured. The separate train-only
adaptation is descriptive. Its 95% family MAE intervals use 2,000 resamples and
are not simultaneous across models/phases. See the
[secondary source audit](rbs-secondary-native-studies.md) for normalization and
replicate limitations.

## Conditional translation-start selection

[TIS results](../../benchmarks/rbs/results/hadjeras2026-tis-secondary.json) use the
pinned 2026-07-30 v3 preprint, one study. The independently constructed universe
contains 165 supplied-stop queries and 1,018 in-frame candidate starts. Primary
labels are 91 sequence/frame-verified plain-evidence annotated starts; eight weak
starts form a separate secondary tier. One of 92 source plain rows fails admission.
Unlabelled rows never become negatives. No precision or PR-AUC is claimed.

| Fixed method | Primary queries with every candidate scored / 91 | Exact top-1 / 91 | Worst-tie MRR, all 91 | Weak-tier exact / 8 |
| --- | ---: | ---: | ---: | ---: |
| Prodigal 2.6.3 | 88 | 84 | 0.927739 | 6 |
| Native sequence-v1 | 91 | 68 | 0.851465 | 5 |
| Footprint2017 | 87 | 56 | 0.717609 | 3 |
| Historical | 87 | 54 | 0.707718 | 4 |
| rebeca | 91 | 48 | 0.675729 | 3 |
| Context2017 | 48 | 31 | 0.395879 | 1 |
| Native hybrid ablation | 48 | 28 | 0.394872 | 2 |
| OSTIR | 21 | 19 | 0.216117 | 1 |

Incomplete candidate scoring counts zero top-1/MRR in the all-positive denominator;
no successful-subset accuracy replaces it. Conservative tied top-1 and separate
±3-nt sensitivity are in the aggregate JSON. Prodigal uses unlabeled whole-genome
self-training and complete coding calls; start-window scorers have different
information. The common observable candidate universe makes this a conditional
localization comparison, not equal-context strength prediction or genome-wide
discovery. Prodigal's 3,704 complete and nine excluded partial genome calls were
projected without reading annotation starts or TIS labels. False positive genomic
calls cannot be assessed from this positive-ascertained annotated subset.

Fifty of the 91 primary true-start contexts exactly match the native TE cohort:
26 training, 13 validation and 11 final. Those models saw TE labels, not TIS labels,
but the sequence overlap forbids a wholly unseen-sequence claim. Among the 41
without an exact 200-nt primary context match, sequence recovers 27 and Prodigal
39. These fixed input-exposure strata remain descriptive; absence of an exact
match does not establish lack of distant homology or upstream pretraining exposure.

## Partially exposed 2017 reporter study

[2017 results](../../benchmarks/rbs/results/footprint2017-secondary.json) contain
27 newly measured constructs sharing a leader/template, with 18 measured relative
TE outcomes and nine explicit missing TE measurements. All methods score 27/27.
The AEB-1 normalization reference was fixed in advance; no test-set scale was fit.
Each assay includes one forced-zero control error and dependence on that control.

| Frozen method | Relative-TE MAE, n=18 | TE Spearman | Fluorescence MAE, n=27 |
| --- | ---: | ---: | ---: |
| Context2017 | 1.302297 | 0.862214 | 2.082264 |
| Footprint2017 | 1.631852 | 0.689087 | 2.447175 |
| Historical | 3.017518 | 0.334370 | 3.535094 |
| OSTIR | 2.921691 | 0.414338 | 3.589183 |
| Public2014 hybrid, selected external finalist | 3.249006 | 0.834280 | 4.469421 |
| Public2014 sequence | 3.461848 | undefined | 4.686589 |
| rebeca | 3.461848 | undefined | 4.686589 |

The last two methods return constant normalized predictions on this panel.
High rank correlation alone does not imply small relative error. The paper used
these constructs to select its footprint, and two published fluorescence values
were incidentally exposed during mechanism reading. This is one partially exposed
shared-template family; family-bootstrap uncertainty is undefined and promotion
is ineligible. Four fluorescence samples span two days; mRNA sample counts are
2, 3, 6 or 8. Median source CVs are 0.1225 fluorescence and 0.1715 mRNA, with maxima
0.5275 and 0.7194. Raw paired-replicate covariance is unavailable. No residual or CV
trimming, noise-ceiling estimate or independent-replicate inflation was applied.

The public2014 leave-one-source-family-out audits separately reproduce all eight
submitted configuration metrics: selected sequence family MAE 0.934651 and hybrid
0.914755. They verify submitted OOF predictions and selection arithmetic, not
independent retraining or fold isolation. Its 22 source design groups share one
reporter and contain near-similar leaders. Native deterministic learning curves
are nearly flat over their fixed nested subsets; they do not identify a noise
ceiling or prove that more biologically diverse data would be useless.

## Sources, rights and remaining measurement gaps

The [source ledger](../../benchmarks/rbs/native-sources.json),
[comparator artifact ledger](../../benchmarks/rbs/comparator-artifacts.json) and
[remaining-comparator gates](../../benchmarks/rbs/comparator-gates.json) pin the
underlying bytes, retrieval identities and component notices.

| Evidence | Admitted use | Material boundary |
| --- | --- | --- |
| Tan 2018, UTEX 2973, GCF_000817325.1 | 4,808 TSS/context rows and versioned CDS joins | Transcription starts, not RBS strength/TIS truth; source/current conflicts retained. |
| Karlsen 2018, DOI 10.1128/mSystems.00126-18; Figshare 6743276.v1 | 2,530 source genes; 2,412 admitted primary chromosome contexts | CC-BY-4.0; current GCF_000009725.1/RS_2025_06_29 differs from unrecovered paper-era annotation. Single endpoint libraries do not identify biological replicate noise. |
| Thiel 2018, DOI 10.1186/s12934-018-0882-2 | 32 constructs, 13 conditional GFP contexts, assay/sequence evidence | No exact numeric graph endpoints recovered; YFP/efe junctions incomplete; no fabricated means or quantitative accuracy claim. |
| Karlsen diurnal 2021, DOI 10.3389/fmicb.2021.657379 | 1,000 admitted chromosome genes, five phase-specific proxies | CC-BY-4.0 supplement; RNA/RPF replicate imbalance, transformed headers and abundance selection audited. |
| Hadjeras v3, DOI 10.64898/2025.12.20.695498 | Source-tiered conditional TIS evidence | CC-BY-NC-ND-4.0 source kept private; no raw labels/modified supplement redistributed. No raw-read/peptide revalidation. |
| Espah Borujeni 2017, DOI 10.1093/nar/gkx061 | 18 relative-TE / 27 fluorescence measurements | CC-BY-NC-4.0 raw final table private; partially exposed and used by original model. |
| Stress 2021, DOI 10.1128/mSystems.00943-21 | RNA/source-access audit only | RPF download repeatedly unavailable; no paired TE cohort admitted. |

An entirely open required path remains the project's reconstruction with separately
installed **RNAstructure 6.6, GPL-2.0-only**, using pinned binaries/tables. OSTIR
1.1.3 (GPL-3.0) with ViennaRNA 2.7.2 is an isolated optional research comparator;
Vienna's component redistribution notices remain relevant. rebeca uses the
unchanged MIT source and pinned scalar checkpoint
`5b17912c6a177db87dfc5008ecebb6c13c2095747748eface1fc72fa46b43b9b` from the
CC-BY-4.0 Zenodo deposit, with separate weight/data-provenance uncertainty preserved.
No upstream weights or restricted artifacts enter the release. Prodigal 2.6.3 is
GPL-3.0-or-later. EMOPEC's explicit reservation, SAPIENs' legacy runtime/weight scope,
GARDN's academic terms/import dependency, GeneLM's missing affirmative grants and
large weights, and Solaris' lack of a reusable pretrained universal estimator
remain named exclusions. Their located artifacts are not presented as executed
comparators. No guessed replacement model carries an upstream name.

## Hosted comparison and prospective experiment

The separate [live report](rbs-live-reference.md) reuses nine CSVs/17 candidates,
two accepted empty outputs and one form rejection. All three mechanistic profiles
match accepted candidate sets, but raw numerical parity is not established. Only
one non-control experimental ratio overlaps the diagnostic panel, insufficient
for an accuracy claim. Private numerical service-derived aggregates remain
separate from every experimental report above.

No new live jobs or credits were acquired. The ledger continues to reserve **11
coins at one coin per accepted job**. Actual debit is unreconciled; the last balance
observation was in Wave 1. A fresh check was unavailable because computer-use had
no enabled surface. No credentials were read or permission bypassed.

There is no admitted UTEX quantitative translation panel sufficient for native
specialization. The [optional measurement proposal](rbs-utex-measurement-proposal.md)
provides a 60-construct/180-culture pilot and a separately frozen
300-construct/900-culture confirmatory stage, with 144 new leader families crossed
with two of six CDS contexts, matched RNA/protein and three biological replicates.
Its conditional power assumptions and $66,720–118,320 combined allowance are
explicit, not a quote or funding commitment. No wet-lab work, contact or purchase
was performed.

## Ranked hypotheses for the next development cycle

These are future falsifiable experiments. The consumed final panels cannot tune
or validate the next candidate as untouched tests.

| Rank | Hypothesis and evidence | Fixed test and falsification criterion |
| --- | --- | --- |
| 1 | Assay-scale adaptation explains much more native error reduction than the present learned feature additions. OSTIR slope is 0.037857; historical slope is 0.008533; selected sequence gain over constant is only 0.032660. | Freeze scalar/affine/sequence contenders on development and compare on new matched RNA/protein leader families across multiple CDSs. Reject a useful sequence-specific advantage unless it reaches the predeclared 0.20 paired log2 gain with adequate coverage. |
| 2 | Context information can help some constructs, but folding failures prevent a usable coverage-complete hybrid. Native hybrid covers 423/468; TIS complete ranking covers only 48/91. | Repair/validate the backend boundary against independent valid-structure fixtures first. Freeze a declared failure policy and hybrid on development; test new families. Reject practical improvement if it loses baseline-valid cases or misses the same gain/subgroup gates. Do not selectively discard invalid structures using final performance. |
| 3 | Explicit coding-context mechanisms matter for designed coding hairpins more than methods returning constant predictions on this shared-leader panel. The fixed 2017 context profile has lower observed error than the learned external finalist, but that panel is not independent of the published mechanism. | Use new leader-by-CDS crossed constructs with matched RNA, independently varied structure and blinded controls. Reject the mechanism's added value if improvement disappears under fixed-reference normalization or held-out CDS contexts. |
| 4 | Native transcript boundaries, operon context and condition-aware assay normalization may matter more than additional same-study training rows. Genomic flanks are assumptions, and diurnal scale transfer is poor. | Acquire matched TSS/RNA/protein context evidence; freeze transcript admission and test new study/condition families against the same genomic-flank baseline. Reject if improved conditional error depends on dropping ambiguous/leaderless cases or final-condition fitting. |
| 5 | Conditional localization needs coding/stop evidence in addition to strength scoring. Prodigal recovers 84/91 versus sequence 68/91, with unequal context and positive ascertainment. | Freeze a localization combination on development, then collect independent corrected/novel starts and justified negative opportunities. Reject a genome-wide discovery advantage unless precision and recall improve with independently supported negatives; annotated positive recall alone is insufficient. |

## Reproduction and integrity

Use `benchmarks/rbs/` and `tests/benchmarks/`; no runtime/model imports are required
by the evaluators. The source cards describe acquisition/extraction and immutable
split regeneration. Optional comparator environments remain separate from package
requirements and offline tests. The public manifest pins all aggregate files and
source identities; private manifests additionally pin full source cases and each
prediction vector. Raw final outcomes/per-case errors stay outside Git and are
not supplied to A for tuning.

```sh
python -m benchmarks.rbs.native_evaluation "$PRIVATE_WAVE2/primary-final-manifest.json" "$OUT/primary.json" --stage final
python -m benchmarks.rbs.secondary "$PRIVATE_WAVE2/secondary-LC-manifest.json" "$OUT/LC.json"
python -m benchmarks.rbs.secondary "$PRIVATE_WAVE2/secondary-diurnal-manifest.json" "$OUT/diurnal.json"
python -m unittest discover -s tests/benchmarks
python -m coverage run --branch --source=benchmarks.rbs -m unittest discover -s tests/benchmarks
python -m coverage report -m
```

Positional reproduction uses `benchmarks.rbs.position.evaluate` on manifest-pinned
queries, private labels and each `records` prediction array, separately with
`source_tier="plain"` and `"weak"`. The 2017 runner uses
`benchmarks.rbs.evaluation.evaluate(..., reference_id="footprint2017:AEB-1")`, once
on source relative TE and separately on fluorescence, preserving the explicit
missing-TE eligibility. These are fixed report reproductions, not new tuning
runs. B's owned suite passes **161 tests, 100% statement/branch coverage
(2,149 statements / 900 branches)**. Independent review accepted numerical,
coordinate, failure, reuse, learned-boundary and secondary-calibration paths at
`9bb479f0472a5e3285659ed872762eb4bd386329`; the separate final-data audit independently reproduces all primary/secondary
reports with 9759 aggregate/pin assertions and zero numerical mismatches. It
uses its own standard-library arithmetic, including both 10,000-resample paired
intervals. Source joins were checked against ingested outcomes; previous source
extraction/projection reviews were not repeated. This does not certify independent
retraining or unseen upstream pretraining data. Audit hashes are in the result
manifest.

A handling exception remains explicit: the independent reviewer accidentally
emitted private experimental records into its own tool transcript. It reports
that none were transferred to Session A or included in deliverables. Further raw-
data review was stopped. No credentials or live-site exports were involved.
Public artifacts contain aggregates only; audit transcripts must not become
training/tuning feeds. Numerical verification does not erase this handling
exception.

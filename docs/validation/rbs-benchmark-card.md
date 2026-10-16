# RBS experimental benchmark quality card

- Scope: independently reproduced historical outputs and frozen new evaluation.
- Last verified: 2026-10-16
- Machine-readable evidence: [manifest](../../benchmarks/rbs/dataset-manifest.json),
  [audit](../../benchmarks/rbs/historical-audit.json),
  [commands](../../benchmarks/rbs/README.md).

## Reproduced results and remaining discrepancies

These are correlations of published predictions with measurements, not new
reconstruction results or current hosted accuracy. Squared correlation does not
measure calibration or predictive R².

| Source and exact denominator | Reported | Independent reproduction | Interpretation |
| --- | --- | --- | --- |
| [2009](https://doi.org/10.1038/nbt.1568), Figure 2B, 28 existing RBSs | R² 0.54 | 0.565145 for source ΔG versus ln(mean fluorescence) | Does not reproduce exactly; source is a later author-curated workbook, not proven identical to publisher bytes. No exclusion was chosen to force a match. |
| 2009 Figure 2E, 29 designed RBSs | R² 0.84 | 0.841250 | Reproduces to reported precision; model-designed sequences are not an untouched random sample. |
| [2014](https://doi.org/10.1093/nar/gkt1139), all 136 | R² 0.89; mean energy error 0.75 kcal/mol | ΔG/ln(fluorescence) R² 0.885796; standby MAE 0.766963 | Correlation reproduced; small energy-error discrepancy remains. |
| 2014 Figure 2G, 15 constructs | standby R² 0.78; error 0.66 | 0.780465; MAE 0.669164 | The relevant correlation is apparent versus predicted standby energy; ΔG-total correlation is a different quantity. |
| 2014 Figure 5A, 28 constructs | R² 0.83; error 0.79 | 0.820368; MAE 0.804232 | Does not reproduce to every reported digit; no fitted correction added. |

The 2014 supplement has 136 unique full sequences in 22 labelled design groups,
all sharing the 102-nt mRFP1 coding context. Whole rows are not independent studies.
These are exact supplied sequence windows, not complete sequenced plasmids: the
2014 supplement provides the first 102 CDS nucleotides; the 2017 workbook provides
275–311 CDS nucleotides plus a 44-nt leader. Both cover the declared local folding
windows, but do not support claims about distal context or complete-ORF discovery.
The paper fits a standby polynomial on 56 constructs and discusses 13 large-error
outliers. Our all-136 audit retains every row. Measurements are three exponential-
growth samples, not three independent days. Median reported SD/mean is 0.234230;
maximum is 0.536962; three constructs exceed 0.5. These summary statistics cannot
recover cell/day-level variance or correct attenuation of correlations.

## Two verified errors in the published evaluation harness

Pinned [SynBioMTS stats.py](https://github.com/reisalex/SynBioMTS/blob/d7d46af7981f90d2147cbc0463c5254b16c5c92c/synbiomts/stats.py)
contains two independently testable defects in `linear_complete`:

1. Lines 425–426 call default Pearson correlation for both Pearson and Spearman.
   The helper can compute Spearman, but that call omits its selector. The resulting
   table's two squared correlations are identical rather than independently ranked.
2. Lines 435–437 build histogram edges 1,2,…,10,20,… and then lines 491–493 label
   CDF elements 1,4,9 as 2×,5×,10×. Those bins actually end at 3×,6×,20×.

The [2020 primary supplementary workbook](https://acs.figshare.com/articles/journal_contribution/13096487)
contains cached v2.1 predictions and their error ratios, allowing verification
without running the old/private calculator:

| v2.1 source subgroup | N | Reproduced Pearson R² | Actual Spearman rho | Labelled “2×” | Actual within 2× | Actual within 5× |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kosuri 2013 | 8,848 | 0.279536 | 0.537674 | 73.6777% | 53.4358% | 89.1953% |
| Goodman 2013 | 7,931 | 0.006964 | −0.000781 | 45.3411% | 28.7480% | 65.3259% |

The labelled “2×” numbers exactly reproduce fractions below 3×; the other labels
likewise reproduce below 6× and 20×. The new harness tests explicit inclusive
2×/5× thresholds and true average-tie ranks. This correction changes the meaning
of published accuracy summaries; it does not imply anything about the current
server's outputs. Source table labels alone cannot establish the server version.

The stored predictions were calibrated on each evaluated subgroup: initial
regression, MAD-threshold-2 trimming, then a refit. Source outlier counts are
660/8,848 and 185/7,931. Predictions/metrics subsequently cover all subgroup rows;
these are fit exclusions, not denominators removed from the final table. Their
different fitted slopes (−0.174598 and −0.037287) further limit cross-study claims.
The old RMSE formula uses sqrt(1−R²)·SD(y), which need not equal residual RMSE after
trimmed refitting. Our audit uses cached predictions, performs no new refit and
computes residual errors directly against `TRANSL.RATE`, not `PROT.MEAN`.

## Denominators, context and leakage

The 2020 abstract's 9,862 is numerically 1,014 individually characterized plus
8,848 Kosuri constructs. The supplementary flow-seq table also includes 7,931
Goodman constructs, making 16,779 flow-seq rows and 17,793 when added to 1,014.
The SI's standby count is 174; its IC workbook contains 175 rows in that source
group. We have not established why those editorial/count differences arose.
The pinned SynBioMTS README says “over 16000,” which is compatible with the
broader flow-seq collection rather than the 9,862-record comparison subset; it
does not supply an exact row reconciliation or another independent cohort.
The full 2020 publisher main text was not accessible during this audit;
its primary SI was retrieved and inspected directly.

The IC compilation includes the 2014/2017 studies and 47 rows labelled unpublished
B. subtilis; it must never be randomly split and then called external validation.
The 8,848 Kosuri full sequences comprise only 111 distinct RBS sequences paired
with 112 promoter IDs and one reporter CDS. Random construct splits leak those
components. The Goodman table's constant CDS field is a shared reporter suffix;
N-terminal variants are in a separate column, so that field alone is not a CDS
family definition. Both flow-seq subgroups are MG1655, pEGRC, sfGFP at 30°C in
this compilation, unlike the DH10B/mRFP1 studies at 37°C. Filtering, binning,
protein/RNA normalization and saturation selection already occurred before the
published workbook. Raw sequencing-count processing was not independently rerun.

## Frozen evaluation and limits

The [protocol](rbs-evaluation-protocol.md) freezes 136 development records and the
entire 27-construct 2017 study, with zero cross-partition exact/≥0.85 regulatory-
window edit-similarity hits. The 2017 records share one designed template and
are not a holdout from the published model's original development: Figure 3C says
17 mRNAs were used for footprint selection, while the surrounding error-analysis
text says 16. The 495-mRNA historical compilation is excluded from the new holdout.

Only 18/27 new constructs have measured fluorescence/mRNA translation outcomes;
nine are explicitly `N/A`. All 27 have fluorescence, four measurements over two
days; mRNA n varies (2,3,6,8 among measured rows). Measurements use separate
fluorescence and RT-qPCR growth/sampling protocols. Their ratio is an informative
proxy with combined noise, not a direct count of initiating ribosomes. Report
eligible denominators before prediction coverage. Do not fill missing mRNA by
assuming constant abundance. No held-out prediction accuracy has been computed.

The isolated live form displays Version 2020; all 11 accepted diagnostic jobs'
input records report v2.1.1. Nine jobs exported 17 candidate rows with verified
coordinates and component sums; two explicitly returned no canonical starts.
The frozen 99-base leaderless input was rejected by the 100-base form minimum.
Returned thermodynamic settings and artifact hashes are recorded in the
[live manifest](../../benchmarks/rbs/live-acquisition.json); runtime source
identity and experimental accuracy remain unverified. The observed account
balance did not change; 11 advertised coins remain budgeted, with actual charging
unreconciled. DH10B was absent from the form's host results; the declared
MG1655 choice is a host mismatch for 2014 experimental comparison, not DH10B
calibration. There is no cyanobacterial accuracy or site-detection validation here.

# Experimental PCC 6803 supplied-start TE regression

This model predicts a log2 assay response for a supplied translation start. It
is a frozen experimental candidate that failed the independent promotion
criteria. It does not establish UTEX 2973 accuracy or a biological initiation
rate. Its target is Karlsen et al. (2018) HC relative ribosome-footprint/RNA
abundance, which also reflects elongation, RNA measurement and annotation effects.

Training uses 1,465 genes in 1,317 homology groups; validation uses 479 genes in
423 disjoint groups. All are admitted primary chromosome cases. Neither the
validation nor the evaluator-held final measurements fit weights, scaling or
calibration. The four fixed penalties are 0.01, 0.1, 1 and 10 per training row.
Selection uses calibrated validation MAE, then RMSE, then stronger penalty;
the selected model retains training-only weights. A median training residual
offset is stored in the selection report and tied to the artifact hash. The
CLI returns the raw score; evaluation applies the separately declared offset.

The sequence-only model selected penalty 1.0 and offset
`0.04659637563372265` log2. It covers every training and validation case and is
the native finalist. The energy/sequence ablation also selects penalty 1.0,
with offset `0.039102431228718926`, but scores only 1,293/1,465 training and
439/479 validation genes. It loses 39 historical-valid validation cases, so
fails the predeclared coverage gate and cannot replace the sequence finalist.

| Development diagnostic | MAE, log2 | RMSE, log2 | Spearman | Within twofold |
| --- | ---: | ---: | ---: | ---: |
| Training-median constant | 0.966571 | 1.250729 | Undefined | 291/479 |
| Sequence ridge | 0.939394 | 1.219720 | 0.207365 | 303/479 |

The small gain over a constant is more informative than a large apparent gain
over an upstream predictor with an unsuitable response scale. Native gene-to-gene
ranking remains weak. The independent comparison includes explicit train-only
scale-adapted upstream controls. No superiority claim follows from this table.

On the same 439 validation genes scored by the hybrid, sequence MAE is
0.949072, hybrid MAE is 0.931431 and constant MAE is 0.977534 log2. Hybrid
Spearman is 0.256214 versus sequence 0.218002. This small conditional gain does
not compensate for missing predictions. On all 2,530 input-only source records,
context2017 scores 2,234, retains 28 unsupported records and reports 268 backend
failures: 250 nonreciprocal connectivity tables, 17 missing outputs and one
crossing/inconsistent table. Direct development-case backend checks reproduce
invalid traceback output; none is repaired by discarding a structure silently.

A fixed learning-curve diagnostic uses nested subsets ordered by the SHA256 of
`wave2-learning-curve-20261017:` plus homology-group ID. The selected penalty and
validation cohort remain fixed; these curves do not select a new finalist.

| Training groups | Training genes | Validation MAE, log2 |
| --- | ---: | ---: |
| 329 (25%) | 380 | 0.943591 |
| 658 (50%) | 733 | 0.941597 |
| 987 (75%) | 1,096 | 0.938501 |
| 1,317 (100%) | 1,465 | 0.939394 |

This one deterministic subsampling curve is nearly flat. It suggests that more
rows alone would give limited gains with these features on this validation set;
it does not estimate a noise ceiling or rule out better features or measurements.
The 75% subset does not replace the full-training model.

The hybrid's fixed curve uses 333/646/964 training genes at 25/50/75% of its
admitted homology groups, with validation MAE 0.937272/0.929931/0.929186. Its
full 1,293-gene model gives 0.931431. It shows similarly small changes across
these nested subsets, on a different coverage cohort from the sequence curve.

## Frozen independent result

The final comparison contains 468 genes in 423 held-out homology groups. Model
weights, training-only offsets, controls and decision gates were frozen before
Session B evaluated these outcomes. The sequence model remains the selected
candidate; the hybrid remains a coverage-ineligible ablation.

| Final model | Successful / eligible | MAE, log2 on successful cases | Spearman | Within twofold / all eligible |
| --- | ---: | ---: | ---: | ---: |
| Training-median constant | 468/468 | 0.989886 | Undefined | 281/468 |
| Sequence ridge | 468/468 | 0.957226 | 0.243990 | 284/468 |
| Training-only OSTIR affine control | 467/468 | 0.973671 | 0.202459 | 287/468 |
| Energy/sequence ridge ablation | 423/468 | 0.939731 | 0.308246 | 259/468 |

The sequence model's paired MAE gain over the constant is 0.032660 log2, with
a 97.5% homology-group bootstrap interval [0.010912, 0.053840]. Against OSTIR
on their 467 common successful cases, the gain is 0.014808 with interval
[-0.009560, 0.038680]. Both fail the predeclared 0.20 practical-gain threshold;
the OSTIR interval also includes zero. Coverage, rank and eligible subgroup
gates pass, but **no promotion or superiority claim passes**.

About 60.7% of all final genes are within twofold, versus 60.0% for the constant.
This does not mean 60.7% of biological initiation rates were measured correctly:
the endpoint is an assay-derived relative TE proxy. The hybrid's lower
conditional error cannot be compared to full-coverage models without accounting
for its missing cases. Bootstrap intervals describe variation across gene groups,
not biological replicate noise. The source's primary TE endpoint has no
independent biological replicate.

See the [independent result card](../../../docs/validation/rbs-wave2-results.md)
for the full comparator, condition-transfer and localization reports. Models and
calibration are unchanged after these results. A further improvement attempt needs
a new development cycle and untouched evaluation; PCC 6803 findings do not
establish UTEX 2973 calibration.

## Reproduction and rights

Use [the learning contract](../../../docs/validation/rbs-learning-runtime.md)
and the adjacent exact model/selection/curve JSON artifacts. Sequence features
are fixed at `sequence-v1` (19 columns). Source/recipe commit for the full fit is
`38d79d039e208935c4cc2e55823844bc87fe426d`; the learning-curve code
is `870cd59a1f050d88431bd19825652acc46bdd9b3`. The canonical data release is
`f28c0fc47b6fce5631f8bd5d30730e85cc75c959`.
The hybrid full fit also uses `870cd59a1f050d88431bd19825652acc46bdd9b3`.
Its admitted input-only context cache SHA256 is
`67cfb1a178f17dce71f8efffa35578a9d7f48d620bb7f2c26cbf1ba860c43907`,
collected at `cde723baa240f4fa301f899b1f152592193bb9e4`, 60 seconds per
record and 3,600 per batch, with no deadline exclusions. The adjacent artifacts
record exact backend/model digests and every excluded development/source case.

The [development data](../../../benchmarks/rbs/karlsen2018-development.json)
SHA256 is `53ba87998de7e3d423fb7d6818db48a1bf93ede98bdb46bb6137b0119cfa39a4`.
The [split](../../../benchmarks/rbs/native-splits.json) SHA256 is
`d989341afcb3e463112e85134a322086d968a4cea6ad4b9cb4fa8cc893312409`.
Measurements are CC-BY-4.0, attributed to Karlsen et al., DOI
[10.1128/mSystems.00126-18](https://doi.org/10.1128/mSystems.00126-18),
Figshare [10.6084/m9.figshare.6743276.v1](https://doi.org/10.6084/m9.figshare.6743276.v1),
Table S2. Sequences are public NCBI sequence facts; no blanket CC licence is
asserted. Original code/model contributions follow GPL-3.0-or-later.

```sh
regsite-learned models/rbs/karlsen2018/sequence-v1.json examples/rbs-karlsen-native.json
```

The example is the lexicographically first admitted development-training gene,
chosen without using its response. It uses 100 nt of genomic flank at 30°C and
the annotated-tail aSD scenario `ACCUCCUUU`; transcript boundaries are unmeasured.
Current RefSeq annotation differs from the paper-era annotation for some genes,
and the source has no independent biological replicate for its primary TE endpoint.
These limitations and explicit host/domain warnings travel with the model.
The independent final evaluation did not promote this model.

# Experimental PCC 6803 supplied-start TE regression

This model predicts a log2 assay response for a supplied translation start. It
is an experimental development candidate, not an independently promoted RBS
predictor. It does not establish UTEX 2973 accuracy or a biological initiation
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
`0.04659637563372265` log2. It covers every training and validation case.

| Development diagnostic | MAE, log2 | RMSE, log2 | Spearman | Within twofold |
| --- | ---: | ---: | ---: | ---: |
| Training-median constant | 0.966571 | 1.250729 | Undefined | 291/479 |
| Sequence ridge | 0.939394 | 1.219720 | 0.207365 | 303/479 |

The small gain over a constant is more informative than a large apparent gain
over an upstream predictor with an unsuitable response scale. Native gene-to-gene
ranking remains weak. The independent comparison includes explicit train-only
scale-adapted upstream controls. No superiority claim follows from this table.

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

## Reproduction and rights

Use [the learning contract](../../../docs/validation/rbs-learning-runtime.md)
and the adjacent exact model/selection/curve JSON artifacts. Sequence features
are fixed at `sequence-v1` (19 columns). Source/recipe commit for the full fit is
`38d79d039e208935c4cc2e55823844bc87fe426d`; the learning-curve code
is `870cd59a1f050d88431bd19825652acc46bdd9b3`. The canonical data release is
`f28c0fc47b6fce5631f8bd5d30730e85cc75c959`.

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
These limitations and explicit host/domain warnings travel with the model. Any
final evaluation or promotion decision remains independently controlled by Session B.

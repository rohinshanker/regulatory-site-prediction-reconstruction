# Experimental 2014-development RBS regressors

These frozen artifacts are development candidates, **not independently promoted
models**. They predict log2 mean mRFP1 fluorescence in source arbitrary units.
They do not establish cyanobacterial accuracy or superiority to the strongest
available RBS calculator.

Training data: all 136 constructs in 22 source-labelled design families from
Espah Borujeni et al. (2014), DOI [10.1093/nar/gkt1139](https://doi.org/10.1093/nar/gkt1139),
DH10B, 37°C, aSD `ACCUCCUUA`, one shared mRFP1 coding context. The extracted
[dataset](../../../benchmarks/rbs/standby2014.json) is CC-BY-3.0 with attribution;
its SHA256 is `d74967eb964f1797138076ed12a35ef5f44c0ac3e87241e5186505503fd698f4`.
Original implementation and model contributions follow the repository GPL-3.0-or-later
licence. Source predicted/apparent energies and measured RNA/count fields are not
training features.

The [recipe](../../../docs/validation/rbs-learning-runtime.md) uses fixed 19-feature
sequence and 24-feature energy/sequence models. Four penalties per family were
selected by leave-one-source-family-out validation, with fold-local scaling and
intercepts. Both selected per-observation lambda 1.0, then fit all development rows.
Exact source/recipe commit: `05937604abb377940f45df15227da47559bcbf45`. The artifacts
contain data/cache/input checksums, training statistics, weights and provenance;
the adjacent selection JSON files retain all eight tested configurations.

| Development model | Mean family MAE, log2 | Row RMSE, log2 | Within twofold |
| --- | ---: | ---: | ---: |
| Training-fold constant mean | 1.342918 | 1.858073 | 51/136 |
| Historical, training-fold intercept | 1.448807 | 1.940519 | 46/136 |
| Footprint, training-fold intercept | 1.448807 | 1.940519 | 46/136 |
| Longer context, training-fold intercept | 1.492233 | 2.071020 | 70/136 |
| Sequence ridge | 0.934651 | 1.427707 | 75/136 |
| Context-energy/sequence ridge | 0.914755 | 1.337857 | 72/136 |

All rows have successful predictions. Mechanistic intercepts and the constant
mean are fitted using only each fold's training families. Ridge model selection
uses these same development folds, so its reported loss is a selection diagnostic,
not unbiased final-test accuracy. The improved family MAE is promising but does
not make the single-reporter dataset independent of its design history. Energy
features add only a small family-MAE benefit over sequence features here.

Separately, the frozen source-control-normalized historical and footprint profiles
give MAE 1.555669, RMSE 1.932227, 52/136 within twofold and 113/136 within fivefold.
Longer context gives MAE 1.597577, RMSE 2.084651, 58/136 within twofold and 103/136
within fivefold. These use a different, fixed-reference evaluation contract and
must not be mixed with the fold-calibrated table above. More context alone did
not consistently improve accuracy.

The learned output is a log2 assay score with explicit domain warnings. Constant
training features stay inactive, including codon/CDS features that do not vary in
this dataset. Changes to these inactive columns produce an explicit warning
and list of unlearned feature changes. Source-family separation is imperfect:
some families share identical local windows and closely related leaders, so
leave-family-out performance includes interpolation. Unseen reporters, start-codon classes, host strains, growth conditions
and native operons are unvalidated. Inference does not imply measured SD boundaries.
Experimental fluorescence is influenced by transcription, RNA/protein stability
and reporter properties as well as translation. The separate PCC 6803 experiment
must train on its own admitted TE development labels; these weights are not a
native-host calibration.

Run the explicit supplied-start example after installing the package:

```sh
regsite-learned models/rbs/standby2014/sequence-v1.json examples/rbs-learned.json
regsite-learned models/rbs/standby2014/context-energy-sequence-v1.json examples/rbs-learned.json
```

The sequence model is backend-free; the energy model requires the pinned separate
RNAstructure installation. Neither needs an account or network during inference.
Independent evaluation and any promotion decision remain with Session B under
the frozen evaluation contracts.

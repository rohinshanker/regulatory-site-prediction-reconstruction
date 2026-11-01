# Ranked falsifiable RBS improvement hypotheses

- Scope: Future RBS model improvements evaluated separately from compatibility.
- Purpose: ticket 13 experiment design; no production engine changes in this slice.
- Last verified: 2026-10-16
- Evaluation contract: [frozen protocol](rbs-evaluation-protocol.md).

First repair evaluation: use actual Spearman, correct fold thresholds, explicit
measurement eligibility and prediction-failure denominators. This corrects
reported evidence; it is not a model accuracy improvement. Preserve historical
compatibility and experimental accuracy as separate targets.

| Rank | Hypothesis and evidence | Controlled comparison and falsification | Data and cost |
| --- | --- | --- | --- |
| 1 | Explicit coding-footprint treatment improves prediction for structures crossing the initiation footprint. The 2017 primary study reports improvement on historical data; Salis v1, iDOG and hosted v2.1.1 have different footprint/context handling. | Freeze historical versus explicit 13-nt treatment with all other settings equal. Compare paired errors and coverage on the reserved study after commits/settings are locked. Falsified if benefit is absent or reversed; results remain inconclusive for generality with one family. Do not reselect footprint on the holdout. | Development feasibility checks on open 2014 data; 18 eligible translation outcomes/27 fluorescence outcomes in private 2017 data. CPU only initially; hosted panel optional. Need another independent study before promotion. |
| 2 | Published standby-site distortion, sliding and partial-unfolding mechanisms explain structured-leader failures better than v1's short-standby approximation. | Ablate each mechanism on 2014 source-labelled groups using grouped development validation, keeping their fitting history visible. Lock parameters, then test on a new independent structured-leader family/study. No “external” claim from reusing the 2014 fit set. | 136 open constructs with means/SDs and full leader context; no live coins needed for development. New independent structured-leader measurements are the limiting resource. |
| 3 | Candidate duplex enumeration, consistent energy evaluation and sufficient flanking context reduce structural-selection errors introduced by a backend substitution. | Hold all biological parameters fixed. Compare bounded candidate enumeration/settings, record structures and per-term deltas. Falsified if increased enumeration/context does not improve frozen experimental error or exceeds declared runtime/memory limits without benefit. Hosted agreement is a separate endpoint. | Pinned RNAstructure fixtures plus synthetic spacing/structure controls. CPU/resource measurements first; up to the declared 12 live diagnostics after billing reconciliation. |
| 4 | A development-fitted, study-aware calibration transfers better than a universal arbitrary fluorescence scale. Historical subgroup slopes differ markedly and expression combines transcription, translation and stability. | Compare fixed relative-reference normalization, constant-relative-rate baseline and a calibration fitted only on development. No test-set refit. Falsified if external-study residual bias/error does not improve, or improvement disappears when protein/RNA outcomes replace fluorescence. | Multiple independent studies/hosts with measured mRNA and matched controls required. Current 2014/2017 pairs are insufficient to establish cross-host calibration. Dataset work or new experiments, not extra coins alone. |
| 5 | Folding kinetics/ribosome drafting explains a subset of equilibrium-model failures. Published 2016 work is a source lead; a usable open kinetic implementation has not been validated here. | Predeclare sequence families and an open, pinned kinetic model before testing. Compare against equilibrium at matched expression/context; falsified by no improvement on an independent time/structure-stratified set. Keep low-confidence predictions explicit. | Additional primary kinetic data/source audit needed; do not adopt iDOG's broken optional Kinfold path. CPU cost likely higher and must be measured. |
| 6 | Sequence-specific spacer stacking improves beyond spacing length alone. The 2020 SI reports an Egbert fit R²≈0.83 but no significant overall improvement on 1,014 IC constructs. | Equal-complexity ablation, family-held-out development tests, then a new spacer-varied independent study. Falsified by no external benefit; do not infer success from the fitted Egbert subset or hosted use of a stacking term. | Existing data support a low-priority negative/limited hypothesis. New independent spacers/contexts would be needed to justify more complexity. |

For each experiment retain exact commit, source parameters, backend/table hashes,
host, temperature, candidate limit, runtime budget, calibration identity and
exclusions. The independent evaluator receives predictions only after these are
locked. Do not send held-out per-case errors back for tuning or repeatedly try
variants on the final set. A better match to v2.1.1 is not by itself evidence of
better measurement accuracy. Cyanobacterial adaptation requires independent
native data and lies outside this Wave 1 RBS evidence package.

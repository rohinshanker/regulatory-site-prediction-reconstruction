# RBS comparator selection and open improvement strategy

- Purpose: Select strong, task-matched mechanistic and learned comparators before engineering or claiming a better predictor.
- Scope: Primary-source planning audit on 2026-10-16; entries are candidates, not newly reproduced performance results.
- Last verified: 2026-10-16
- Evidence owner: Session B (`9677689a-1792176763`), accepted 2026-10-17; runtime/model implementation stays with Session A.

## Comparison roster

The first round should include a simple baseline, the frozen reconstruction,
one useful empirical/learned comparator and a stronger learned comparator when
its artifacts are usable. Do not spend the entire wave repairing obsolete
environments or downloading every candidate. A literature-only exclusion must
identify the exact missing artifact, rights restriction or installation failure.

| Candidate | Why include it | Domain and immediate gate |
| --- | --- | --- |
| Frozen Salis v1/RNAstructure reconstruction | Existing interpretable baseline and energy features; current 136-case results already frozen | Reference profile remains unchanged. Evaluate later published mechanisms as separate profiles. |
| [OSTIR](https://github.com/barricklab/ostir) | Independent maintained reconstruction descended from the same open Salis version; useful backend/implementation comparison | Uses ViennaRNA. Its GPL code does not remove the already identified dependency restriction. Optional separately installed comparison only after its complete terms are reviewed; do not make it required or call a backend substitution identical OSTIR. |
| Jaymin/iDOG and historical Salis | Detect prior implementation differences and reuse independent fixtures | Use existing source decisions. iDOG borrowed-wrapper provenance remains unresolved; never bundle it merely because the surrounding repository is MIT. |
| [EMOPEC](https://github.com/micked/EMOPEC), [Bonde et al. 2016](https://doi.org/10.1038/nmeth.3727) | Empirical SD activity and expression-tuning approach; a useful non-neural contrast | E. coli and limited context assumptions. No licence-named file was found in the inspected tree; verify headers, publication and data terms. This is unresolved, not a declaration that no licence exists. |
| [rebeca / Gilliot & Gorochowski 2024](https://doi.org/10.1093/nar/gkae491), [code](https://gitlab.com/Pierre-Aurelien/rebeca), [Zenodo](https://doi.org/10.5281/zenodo.11081336) | CNN–LSTM with cross-context transfer-learning experiments; especially relevant to a specialist model | Paper explicitly discusses context dependence and missing CDS context. Prefer a pinned pretrained inference smoke before retraining. Zenodo metadata is CC BY 4.0, but embedded code, pretrained weights and original datasets need separate review. `datasets.zip` is about 75 MB; `rebeca.zip` is 12.5 GB and `analysis.zip` 7.0 GB: inspect smaller repository artifacts first. |
| [SAPIENs / Höllerer et al. 2020](https://doi.org/10.1038/s41467-020-17222-4), [model](https://github.com/BorgwardtLab/SAPIENs), [assay processing](https://github.com/JeschekLab/uASPIre) | Large-scale measured sequence/function data and an ensemble of residual neural networks; trained weights available | 17-nt RBS library in a specific E. coli reporter context. `code/LICENSE.md` is BSD-3-Clause for code; `data/LICENSE.md` is CC BY-NC-ND. Check weight terms separately. Old TensorFlow 1.12/Keras 2.2.4 stack needs an isolated environment or numerically verified port, not silent reimplementation. |
| [Solaris / Zhang et al. 2022](https://doi.org/10.1021/acssynbio.2c00015), [author repository](https://github.com/mholowko/Solaris/tree/master/synbio_rbs) | Gaussian-process regression and batched design; plausible small-data/active-learning comparator | Local experimental domain, not a universal predictor. Repository metadata identifies Apache-2.0; inspect subfolder code and data notices, exact training cases and CPU inference. |
| [GARDN–SANDSTORM, 2025](https://doi.org/10.1038/s41467-025-59389-8), [code](https://github.com/AlexGreenLab/GARDN-SANDSTORM) | Recent predictive/design neural approach with experimentally tested RBS designs | Paper explicitly calls the repository licence academic. Audit exact permitted evaluation and redistribution; cannot become a required entirely-open runtime under an academic-only restriction. Generative performance is a separate task from native site prediction. |
| [RBSeval](https://github.com/gterai/RBSeval) | Accessibility plus EMOPEC regression offers a useful mechanistic-feature hypothesis | Inspected notice permits nonprofit use only and prohibits redistribution. Exclude from bundled/open runtime; optional permitted research comparison or published-results audit only. |
| [RBSDesigner](https://doi.org/10.1093/bioinformatics/btq458) | Historical alternative thermodynamic assumptions and accessibility | Paper describes precompiled software and UNAfold. Complete usable source and all terms are unverified; low priority if recovery becomes a distraction. |
| [Prodigal](https://github.com/hyattpd/Prodigal) and [GeneLM, 2025](https://doi.org/10.1093/bib/bbaf311), [code/weights](https://github.com/Bioinformatics-UM6P/GeneLM) | Appropriate baselines for translation-start localization, including an ML method | Gene/start identification is not translation-strength prediction. Audit training-genome overlap, pretrained model exposure and code/weight terms; no rate-accuracy comparison using their positional outputs. |

Other tools named “RBS”, RNA-binding-protein predictors, promoter BERT models,
eukaryotic 5′UTR predictors and gene finders are not automatically task-matched.
Add a candidate only after verifying what it predicts, its training labels and
its input domain. Refresh the primary-source search at execution time; a method
claiming state-of-the-art performance is a candidate to reproduce, not a result.

## Reproducible first-look identities

These pins locate the inspected primary material; they do not complete adoption
review. Session B records exact per-file licence/weight/data hashes and smoke
results in the source ledger before any reuse.

| Repository | Inspected commit |
| --- | --- |
| barricklab/ostir | `e0e9a894f6726845968de76054d6ae279b550a20` |
| BorgwardtLab/SAPIENs | `316a562e85379b03ba3bea8f5149391f59c581ed` |
| micked/EMOPEC | `f4c3665dfea6bb8655dac180b7913d280d4721a9` |
| gterai/RBSeval | `c5de3b3df60a9c11aacb5cc1e07b809ae9a4a2be` |
| mholowko/Solaris | `40620ab515a853222d6580733bd6a695969ab426` |

Full text was retrieved through Europe PMC's public `/{PMCID}/fullTextXML`
endpoint. Useful source identities and located evidence:

| PMCID | XML SHA-256 | Relevant location |
| --- | --- | --- |
| PMC6091082 | `7063969b6577a330390269bec64df5f22c696203239257cb06fc21ef5148f7d8` | Tan Results, “Transcriptional start sites”; data availability. |
| PMC11260469 | `5c2bc5ef88c6c6ffccfe24afc601b169693c4380511dd90a2c49043a27412694` | Discussion and data availability: context adaptation, CNN–LSTM and rebeca deposit. |
| PMC7363850 | `50446aea83adf521ae5102ca487249b10c5ba04c56cdfd8663fcd3685ea2e354` | Computational scripts/data and code availability: SAPIENs/uASPIre. |
| PMC5834881 | `aec3a032ebff073cc444b10c19866f30ffa8d55f75f46a235c5b063049a15fdb` | Thiel Results/Discussion: RBS–CDS context dependence. |
| PMC12050331 | `0281b7ec3eb1fc24756daa720c5da83beeee14448291e72d6510725649b339c7` | Code availability: academic licence; source experimental measurements. |
| PMC12222049 | `7426c893cdd818b7cf1acfd1c0e3343f989cbae6222ca1181f6d07a61adafa56` | GeneLM data availability: repository and trained weights. |

## Fair runners and score semantics

Every benchmark adapter records commit, artifact hashes, host, temperature,
full input preprocessing, missingness, supported codons, context length,
training/pretraining data exposure, optional environment and inference cost.
Native output scale stays intact. Transformations or calibration are fitted on
development only, identically for competing models. Do not coerce an expression
percentile into an absolute TIR or invent energy terms for a learned score.

Use common eligible cases plus each method's full-domain coverage. A method
requiring a fixed 17-nt input may need a declared restricted comparison and may
not support native full-transcript scanning. Compare equal information access:
sequence-only models cannot be fairly credited against a method given measured
Ribo-seq evidence. No target transcript measurements may leak into a deployment
model advertised as sequence-only. Freeze package/model seeds and bound tuning
compute for each contender. Check a port against upstream predictions before
calling it that method; otherwise give it a new model identity.

## Ambition and staged decision

The authorized research goal expands beyond reconstruction: pursue an entirely
open predictor that beats the strongest reproducible applicable methods on
independent experimental benchmarks. “Better than anything else” is an ambition,
not an acceptance claim that can be established by one reporter panel. State the
task, host, condition, date, comparators and uncertainty of every superiority claim.

**Recommended first specialization: cyanobacterial relative translation at
supplied starts, with UTEX 2973 as the desired deployment host.** Native TIS
localization is a separate endpoint. This is a planning inference: a narrower
domain reduces heterogeneity and matches the laboratory's needs, but scarce
target-host measurements may make fitting harder. PCC 6803 and UTEX 2973 cannot
be treated as one interchangeable calibration domain.

Compare a finite ladder, using grouped development data before final evaluation:

1. Constant/rank-naive baseline, simple SD-spacing or sequence-feature regression,
   and the frozen historical mechanistic model.
2. Later mechanistic profiles and realistic transcript/CDS context; ablate each.
3. Small-data regularized calibration/residual regression using mechanistic and
   sequence features; compare a sequence-only model and host-aware alternatives.
4. Transfer learning from a usable pretrained sequence model if learning curves
   and data rights justify it. Compare zero-shot, calibration-only and fine-tuned
   behavior on the same independent domains.
5. Structure-aware learned models or new architectures only if earlier results
   identify a repeatable unresolved error and enough independent labels exist.

Do not train a large network on 136 closely related constructs and call it a
general improvement. Model-generated pseudo-labels may support a declared
distillation experiment, but do not add experimental evidence or independence.
Retain the compatibility profile and publish any improved profile separately,
with weights, training recipe, admissible data provenance and uncertainty or
abstention behavior. No unsupported calibrated probability is permitted.

Apply the [native validation gates](rbs-native-validation.md) and existing
[improvement protocol](rbs-evaluation-protocol.md). If independent data are
insufficient, finish a tested baseline comparison and a costed prospective
measurement proposal. A negative or inconclusive result is useful completed
research; it is not a reason to fabricate an improved release.

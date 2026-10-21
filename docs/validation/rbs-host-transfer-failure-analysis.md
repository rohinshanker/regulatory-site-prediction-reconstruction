# Diagnosing RBS host-transfer failure

- Purpose: Distinguish scale error, sequence-ordering error, context mismatch and measurement mismatch before changing a predictor.
- Scope: Reinterpretation of existing public aggregates and admitted source evidence; no new prediction, fitting, source admission or UTEX accuracy estimate.
- Last verified: 2026-10-21

## What the existing results establish

The present evidence does **not** identify a single biological reason why an
E. coli-calibrated model would fail in UTEX 2973. It does establish that correcting
scale can leave poor ordering, and that changing transcript assumptions can change
predictions. Host, assay, condition and native-versus-designed sequence context
are confounded in the available comparisons. PCC 6803 is not UTEX.

The [machine snapshot](../../benchmarks/rbs/host-transfer-failure-analysis.json)
pins the existing public artifacts and copies only declared aggregate fields.
These are exposed, consumed cohorts. The snapshot does not re-execute their
evaluators, inspect private outcomes or independently reproduce source extraction.

### Scale correction did not repair native ordering

The [PCC 6803 evaluation](rbs-wave2-results.md) used 468 final genes in 423
homology groups. **Every method below already received a target-development,
train-only median log2 residual intercept.** The affine variants additionally
used a training-only slope. These results are not pure zero-shot E. coli-to-host
transfer, and do not evaluate the current package or current hosted service.

| Frozen method | Successful / 468 | MAE, log2 TE | Spearman rho |
| --- | ---: | ---: | ---: |
| Historical, intercept only | 445 | 5.195557 | 0.159858 |
| Historical, affine | 445 | 0.979096 | 0.159822 |
| OSTIR, intercept only | 467 | 2.796606 | 0.202459 |
| OSTIR, affine | 467 | 0.973671 | 0.202459 |
| Constant training median | 468 | 0.989886 | undefined |
| Native sequence-v1 | 468 | 0.957226 | 0.243990 |

Affine adaptation substantially reduced error without materially improving rank.
A positive affine transformation preserves exact ranks mathematically; the small
reported historical-rho difference is retained, not silently rounded into exact
equality or assigned an unverified cause. Shrinking a prediction toward a constant
can improve error when its range is excessive or its signal is weak. This does
not identify whether the cause is host biology, input error or assay noise.

The error columns use each method's successful cases: do not subtract the
445/467-case values from the 468-case constant as a paired improvement. The
published paired comparison gives sequence-v1 a **0.032660 log2 MAE gain** over
constant on 468 pairs (97.5% group-bootstrap interval 0.010912–0.053840), below
the frozen practical threshold of 0.20. Against OSTIR affine, the gain is
**0.014808** on 467 pairs (interval −0.009560–0.038680). Neither contrast passes
the full promotion rule. These intervals describe gene/family resampling, not
biological-repeat uncertainty.

### Transcript assumptions change the question being scored

The [UTEX context diagnostic](rbs-wave5-context-results.md) changed measured-TSS
versus genomic-flank input while retaining the frozen profiles. It used 24 loci,
31 source associations and 124 scenarios per profile, with only 57 distinct
prepared inputs. Per profile, 95 scenarios scored, 26 were unsupported and three
had no candidate. There were no execution failures; unsupported and no-candidate
are distinct from a low biological score.

| Profile / CDS anchor | Paired successes / 31 | Changed scores | Changed ranks |
| --- | ---: | ---: | ---: |
| Historical / current | 15 | 6 | 14 |
| Historical / historical | 25 | 9 | 22 |
| Context2017 / current | 15 | 7 | 12 |
| Context2017 / historical | 25 | 11 | 25 |

Each changed-count denominator is that row's paired-success count. Median score
change is zero in every row. A rank can move because another score moved. These
are small, selected, dependent model diagnostics at fixed 37°C and aSD
`ACCUCCUUU`, not measured expression changes, native calibration, an accuracy
comparison or genome-wide rates of failure. They make transcript/annotation
uncertainty a concrete concern without establishing which prediction is correct.

### Measurement and reporter context remain unresolved

The [native data card](rbs-native-data-card.md) records assumed genomic flanks,
unmeasured transcript boundaries, current-versus-source annotation differences
and one RNA/RPF library per primary endpoint. The target is relative RPF/RNA,
not an absolute initiation rate. Karlsen et al. measured altered ribosome
allocation and pausing under carbon starvation; occupancy therefore should not
be equated automatically with initiation or final protein abundance
([2018 primary study](https://journals.asm.org/doi/10.1128/msystems.00126-18),
Results, ribosome distribution/pausing analysis).

Thiel et al. found that downstream reporter context changed RBS activity
profiles in PCC 6803. Their proposed mRNA-interaction explanation was not resolved
by the examined structure predictions ([2018 primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5834881/),
Abstract Results and Discussion). Our [source audit](rbs-reporter-contexts.md)
recovered 13 conditional GFP contexts among 32 constructs, but no exact raw
numerical assay arrays. It supports a context hypothesis, not a new correlation,
proven folding mechanism or UTEX validation. Reporter fluorescence normalized by
OD is also not protein synthesis per transcript.

## Failure modes and distinguishing evidence

The following order prioritizes checks, not estimated causal probabilities.
The specific biological mechanisms in row four remain hypotheses; observations
in the other rows do not establish those mechanisms.

| Failure mode | Expected signature | Evidence that distinguishes it | Present conclusion |
| --- | --- | --- | --- |
| Scale or dynamic-range mismatch | Broad ordering survives, but all values are shifted or predictions spread too far. | On separate calibration data, compare an offset with an affine adaptation; assess unchanged ranking and common-case error on untouched data. Compare with a constant. | PCC 6803 affine errors improve strongly while rank remains weak. Scale repair alone is insufficient evidence of useful sequence discrimination. |
| Incorrect or incomplete sequence context | Predictions depend on transcript start, leader/CDS junction, annotation or supplied-start choice. | Resolve those inputs independently of outcomes; compare transcript-aware and genomic assumptions on the same eligible cohort, retaining unsupported cases. | UTEX predictions are context-sensitive. We cannot say which context gives more accurate translation strengths. |
| Endpoint, normalization or noise mismatch | Association changes between RNA-normalized synthesis, occupancy and accumulated reporter output, or between assay batches/conditions. | Matched endpoint definitions, independent biological repeats and explicit normalization; estimate repeatability separately from gene-resampling uncertainty. | Existing TE proxies and reporter summaries cannot identify a native initiation noise ceiling or isolate host effects. |
| Host-by-sequence interaction omitted or misweighted | Reliable rank reversals remain after input/assay reconciliation, and errors depend on sequence/context in a host-specific way. | Matched parts across hosts and multiple CDS contexts, with family-held-out tests; an interaction must improve prediction beyond host-wide scale correction on new data. | Plausible candidates include differential ribosome recruitment, RNA accessibility/processing, translation coupling and kinetics. None is identified as the cause in UTEX by these aggregates. |
| Computational coverage mismatch | A host/context subgroup lacks valid predictions or has a different candidate universe. | Count every attempted input and each status; compare common cases while separately evaluating all-case coverage and missingness. | Native/context coverage limits are observed. A missing score is not evidence that translation is absent. |

A shared anti-Shine–Dalgarno sequence tests only one input assumption; it cannot
establish that initiation-factor effects, RNA accessibility, cellular conditions
or the relative weights of modeled terms are shared. These are candidate
explanations, not host-specific facts established here. Similarly, a difference
between transcript assumptions can originate in folding input, alternative
transcripts or annotation mapping without any change in ribosome biochemistry.

Mechanistic tools avoid dependence on learned latent representations, but they
still simplify biology and use empirical parameters. More E. coli measurements
can improve estimation within that domain; they cannot by themselves identify
a missing host interaction. The testable question is whether a frozen model
retains useful ordering and effect sizes on the actual target task.

## Consequence for current-versus-recoded comparisons

For reasoning only, write a commensurate log endpoint as
`z = alpha(host, assay, condition) + beta(host) * s + g(host, sequence, context) + error`,
where `s` is the frozen model score and `g` denotes unmodeled dependence. This is
not a fitted or causally identified model; it is a decomposition of possible
errors. Positive `beta` changes range, while a sequence-dependent `g` can reorder
cases. Without matched observations these terms cannot be separated.

For a paired comparison with the same scale, assay and condition, the shared
offset cancels: `delta z = beta * delta s + delta g + delta error`. This explains
why absolute calibration might be unnecessary for useful directional predictions,
but **does not guarantee that recoding deltas are correct**. Recoding can change
the RNA context and other sequence-dependent effects represented by `g`; common
conditions and identical amino-acid sequence do not force those errors to cancel.
Near-zero changes also require measurement uncertainty, not a forced sign label.

Strength at a supplied annotated start, detection of internal initiation, and
biological gain/loss of a site are different endpoints. A candidate appearing
or disappearing after sequence editing establishes a changed candidate universe,
not experimental initiation. Absolute-strength or same-part transfer alone
does not validate the visualizer's recoding-effect or internal-site claims.

## Decision before another model-development cycle

1. Resolve input identity and report coverage before interpreting biological
   errors. Preserve ambiguous transcripts and unsupported starts explicitly.
2. Require a target-task measurement with known denominator and biological-repeat
   structure. Do not substitute TSS counts, predicted energies or raw fluorescence
   for initiation truth.
3. Test frozen predictions with independently justified host settings. Keep this
   configuration separate from any outcome-fitted offset, slope or features.
4. Compare scale-only adaptation with a constant and frozen sequence ordering on
   new families/contexts. Current consumed results may motivate hypotheses but
   cannot become a fresh test or determine new acceptance thresholds.
5. Only then assess a specific host/context interaction against a predeclared
   alternative. For recoding, require paired effect measurements; for internal
   sites, require positional evidence and justified negative opportunities.

This is the analysis order, not an approved wet-lab protocol, sample-size
calculation or claim that the needed matched data exist. Source admission and
any new execution freeze remain governed by [the transfer contract](rbs-host-transfer.md).
The separate rejected thesis-source assignment remains stopped; this analysis
uses only already admitted sources and public aggregate results. No new
biological experiment, model job or paid collection occurred.

## Snapshot verification

From the repository root, the following checks exact source bytes and copied
JSON fields; it does not verify prose semantics or recompute scientific metrics.
The file list is explicit in the new snapshot. No referenced private artifacts
are opened. Existing source licences/notices remain in the linked data cards
and source ledger; this snapshot redistributes no raw final outcomes.

```sh
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

receipt = json.loads(Path('benchmarks/rbs/host-transfer-failure-analysis.json').read_text())
sources = {}
for key, entry in receipt['artifacts'].items():
    data = Path(entry['path']).read_bytes()
    assert len(data) == entry['bytes'], key
    assert hashlib.sha256(data).hexdigest() == entry['sha256'], key
    if entry['path'].endswith('.json'):
        sources[key] = json.loads(data)
for projection in receipt['projections']:
    node = sources[projection['artifact']]
    for token in projection['pointer'].split('/')[1:]:
        node = node[token.replace('~1', '/').replace('~0', '~')]
    for field, value in projection['fields'].items():
        assert node[field] == value, (projection['pointer'], field)
print('Public source hashes and copied aggregate fields match.')
PY
```

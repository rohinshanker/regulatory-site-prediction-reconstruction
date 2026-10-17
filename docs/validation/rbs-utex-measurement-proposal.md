# Prospective UTEX 2973 translation-context benchmark

- Purpose: Cost a new, independently measured target-host challenge when existing labels cannot establish UTEX accuracy.
- Scope: Optional experimental design and funding proposal only; no wet-lab execution, contact, purchase or sequence order.
- Last verified: 2026-10-17
- Owner: Session B; laboratory owner decides feasibility and funding.

## Why this measurement is different

Tan supplies transcript boundaries, not translation outcomes. PCC 6803 RNA/RPF
ratios cannot establish accuracy in UTEX 2973. Thiel supplies useful reporter
contexts but no exact tabulated endpoint means in the recovered material.
Additional hosted-calculator coins supply predictions, not new biological labels.
The proposal measures a relative protein-per-mRNA proxy at supplied starts;
neither reporter fluorescence nor that ratio is an absolute initiation rate.

Primary UTEX leads remain distinct: the
[CyanoGate study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6501082/) compares promoter/
spacer contexts, while the
[hapalindole study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6724726/) screens
promoter-plus-native-RBS reporter constructs. They are not isolated RBS-strength
labels merely because RBS sequences occur in them. A bounded fresh retrieval of
their full XML returned HTTP 500 and the author-manuscript PDF returned 403;
no unverified quantitative rows or complete constructs were admitted from snippets.
This is an access/admission limit, not a claim that no UTEX experiment exists.

## Two separately gated stages

| Stage | Independent new leader families | CDS contexts | Assignments per leader | Test + control constructs | Biological cultures |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pilot and assay qualification | 24 | 6 | 2 | 48 + 12 = 60 | 180 |
| Frozen confirmatory challenge | 144 | 6 | 2 | 288 + 12 = 300 | 900 |

Use a balanced incomplete crossing: each leader appears with two of six distinct
CDS contexts, each context receives equal representation, and assignments are
randomized within sampling strata. Six contexts should span at least three
unrelated reporter proteins plus independently selected N-terminal sequence
contexts; do not describe synonymous variants of one reporter as six independent
proteins. Preserve exact full transcribed sequences, promoter/junction bases,
CDS identity and termination context. Keep the same verified integration locus
and copy-number strategy across constructs, and record segregation/genotype.

Half the leader families are sampled across native UTEX sequence/leader-length
strata; one quarter targets disagreement among the *frozen* models; one quarter
is a balanced mechanism challenge covering SD strength/spacing, local structure,
upstream starts and short leaders. Do not select only high predicted expression.
Cluster homologous/near-duplicate leaders and reused genomic loci before sampling.
Report representative and deliberately enriched strata separately: an enriched
panel does not estimate genome-wide prevalence or average native performance.

The pilot uses its own 24 families. Use it to qualify assay range, background,
maturation, RNA quantification, batch effects and the variance of paired model
errors. It may support a separately named UTEX calibration. Freeze all model
weights/calibration, exact final sequences, exclusions, randomization and analysis
before measuring the 144 new final families. No pilot family migrates into final.
If the pilot cannot resolve a stable RNA-normalized signal, stop and revise the
assay before funding the larger stage; do not force a fitted predictor from noise.

The 12 control constructs comprise a fixed low/high expression reference for each
CDS context. Include nonreporter background and assay blanks as technical controls
in each run. Blind sample identities and model predictions to acquisition staff.
Three biological replicates mean three independently grown cultures, randomized
across three days and plate positions, with genotype-verified independent isolates
where feasible. Repeated wells, cell events and repeated reads are technical
replicates; they do not increase the biological denominator.

## Host, conditions and measurements

Start with one predeclared condition, for example BG11 at 38°C, continuous
250 µmol photons m⁻² s⁻¹ and 0.5% CO₂, within the published UTEX cultivation
range in the [sucrose study](https://www.nature.com/articles/s41598-019-57319-5).
The laboratory must establish that its equipment and strain support this condition
before freezing the assay. Record actual irradiance, temperature, carbon supply,
culture density, growth phase, growth rate and collection time. Do not pool stress
or diurnal conditions into the primary endpoint; a second condition is a separate
budget and secondary estimand.

Collect RNA and protein readouts from matched culture aliquots. Use quantitative
RNA measurement with external standards and predeclared reference controls,
background-corrected calibrated reporter readouts, and growth/maturation controls.
Retain raw replicate-level values, detection limits, plate/batch IDs and technical
replicates. Record full DNA verification and test transcript boundaries in pilot
sentinels; unverified boundaries remain labelled assumptions. Protein accumulation,
degradation and reporter maturation remain possible confounders even after RNA
normalization. A protein-per-mRNA assay does not isolate every initiation mechanism.

Predeclare failed construction, wrong genotype, contamination, saturation and
below-detection policies from independent QC. Preserve all attempted constructs
and failures. Treat zeros/censoring using the measured assay limit, never an
arbitrary pseudocount or an error-dependent exclusion. Select normalization
controls before outcomes and propagate their shared uncertainty; do not optimize
the reference or slope on final errors.

## Endpoint and power assumptions

Primary endpoint: paired difference in absolute log2 error against two frozen
comparators, averaged over a leader family's two CDS assignments, after only
predeclared pilot/control calibration. Report coverage, 2×/5× fractions and genuine
Spearman separately. Resample complete leader families; show day and CDS-stratified
results and a hierarchical sensitivity. The primary inference is conditional on
these six chosen CDS contexts. Six contexts cannot establish universal CDS
generalization, and shared reporters/day effects can reduce effective sample size.

For planning only, with two comparisons and 97.5% two-sided intervals,
`n = ceil(((z(0.9875) + z(0.8)) * sigma / 0.20)^2)` gives:

| Assumed SD of paired family error differences (log2) | Approximate families for 80% detection power |
| --- | ---: |
| 0.50 | 60 |
| 0.75 | 134 |
| 1.00 | 238 |

These SDs are assumptions, not estimates from the existing studies. Thus 144
families is a conditional planning target, not a power guarantee. Re-estimate the
required budget from pilot variance, preserving final blinding. This formula tests
a nonzero true difference of 0.20; it does **not** give 80% probability of passing
an additional observed-gain ≥0.20 gate when the true effect is exactly 0.20.
For a claim that the lower confidence bound exceeds 0.20, power must instead use
the expected effect minus 0.20. No biological or statistical success is promised.

Reproduce the planning counts with Python's standard library:

```python
import math
from statistics import NormalDist
z = NormalDist().inv_cdf(0.9875) + NormalDist().inv_cdf(0.8)
print([math.ceil((z * sd / 0.20) ** 2) for sd in (0.50, 0.75, 1.00)])
```

## Budget, scope and release

The [vendor's public table](https://www.twistbioscience.com/products/genes?tab=overview),
checked 2026-10-17, lists a 300–500 bp gene fragment at USD 35 per sequence.
This anchors only short inserts; it is not a quote or a recommendation to order.
Existing master vectors/reporters and a suitable assembly strategy are assumed.
The remaining entries are explicit planning allowances requiring local quotes.

| Cost in USD | Pilot | Confirmatory stage |
| --- | ---: | ---: |
| Short-insert synthesis at listed price | 2,100 | 10,500 |
| Assembly and sequence QC, $40–80/construct allowance | 2,400–4,800 | 12,000–24,000 |
| Matched culture/RNA/protein consumables, $20–40/culture allowance | 3,600–7,200 | 18,000–36,000 |
| Shared setup/instrument allowance | 2,000–4,000 | 5,000–10,000 |
| Total including 20% contingency | **12,120–21,720** | **54,600–96,600** |

Both stages total **$66,720–118,320** under these assumptions, excluding salaries,
shipping, tax and new capital equipment. This is not an approved expenditure.
The arithmetic, assumptions and price-page hash are in
`benchmarks/rbs/utex-prospective-budget.json`. Reuse lab stocks where appropriate,
but do not assume a discounted price or free access to instruments. A smaller
pilot can answer assay feasibility; it cannot be advertised as a well-powered
144-family confirmation.

Before execution, the owner secures explicit reuse rights for chosen construct
parts and a public data plan: raw measurements and exact constructs under a
permissive data licence, source notices retained, preregistration and all exclusions
released alongside results. Keep final labels with an independent evaluator
during tuning. No author/lab member was contacted and no synthesis, account,
instrument time, credits or wet-lab work was purchased or executed in this wave.

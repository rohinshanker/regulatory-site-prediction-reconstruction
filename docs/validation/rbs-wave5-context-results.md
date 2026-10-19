# Independent RBS transcript-context sensitivity

- Purpose: Report a frozen measured-TSS versus genomic-flank diagnostic using unchanged RBS profiles.
- Scope: Tan 2018 UTEX 2973 transcript/annotation context; not translation accuracy, model fitting or a current/recoded sequence experiment.
- Last verified: 2026-10-19

Changing the supplied transcript boundary changed relative initiation estimates
and within-panel ranks, although the median log-score change was zero in every
profile/annotation group. This establishes input-context sensitivity. Tan's TSSs
are not measured translation strengths, so these differences cannot establish
that one boundary assumption or profile predicts translation better.

## Frozen source and execution

The source is Tan 2018 ([DOI](https://doi.org/10.1186/s13068-018-1215-8)), using
the existing source Table S1/current-annotation reconciliation and genome pins
in [native validation](rbs-native-validation.md). The deterministic stratified
panel contains 24 loci and 31 source associations, with four scenarios each:
current/historical CDS anchor crossed with measured-TSS/genomic-flank context.
All 124 scenarios run once under each unchanged profile. Four loci per declared
stratum were chosen by the predeclared selection key, not by output. This small,
stratified diagnostic is not a genome-weighted or independent-measurement sample.

Candidate `920215602a837b0fd2fed403512f3b3ed59bfda2`, installed wheel
`b87e7a34e09f1163e03dd69d5112307bc4cb3013e75b5ade0812cf7098ab449a`, uses the
separately installed RNAstructure 6.6 linker-3 backend. The original RBS equation
files remain byte-identical to the admitted baseline; package version 0.6.0rc1
is explicit. Full model/backend/settings hashes are in the machine-readable
aggregate and [collection acknowledgement](../../benchmarks/rbs/wave5-context-collection-ack.json).
Temperature 37°C and aSD `ACCUCCUUU` are fixed scenarios, not native calibration.

The two serial batches completed once with real exit 0, no retry or repacking,
and confirmed child-group cleanup. Every scenario is retained. The independent
extraction check reconciled all 248 returned contexts against frozen expectations;
212 non-null core payloads passed the complete public result schemas. The output
collector and metric tool import no runtime scorer. Read-only recovery reconciled
all archived inputs, intents, observations, hashes and final receipts.

## Coverage and paired changes

Coverage is identical for the two profiles. Each row below has 31 requested
source associations; missing or unsupported cases were not converted to scores.

| CDS anchor | Context | Scored | Unsupported | No candidate | Failed / not run |
| --- | --- | ---: | ---: | ---: | ---: |
| Current | Measured TSS | 15 | 15 | 1 | 0 |
| Current | Genomic flank | 24 | 7 | 0 | 0 |
| Historical | Measured TSS | 25 | 4 | 2 | 0 |
| Historical | Genomic flank | 31 | 0 | 0 | 0 |

Each profile therefore has 95 scored, 26 unsupported and three no-candidate
scenarios among 124. There are 106 prepared contexts, but only 57 distinct
prepared inputs; 78 rows belong to 29 repeated-input groups. Source associations
and annotations are not independent replicates. No outputs or IDs were deduplicated.

The following summaries use only associations with successful predictions for
both context assumptions. Change is measured-TSS minus genomic-flank `log_tir`
(the model's natural-log relative initiation score). “Changed” uses the frozen
absolute threshold greater than 1e-12. The median is zero in all four rows.

| Profile | CDS anchor | Eligible / requested pairs | Changed scores | Change min–max | Changed ranks |
| --- | --- | ---: | ---: | --- | ---: |
| Historical | Current | 15 / 31 | 6 / 15 | −4.58136 to 8.99490 | 14 / 15 |
| Historical | Historical | 25 / 31 | 9 / 25 | −1.64282 to 11.46175 | 22 / 25 |
| Context2017 | Current | 15 / 31 | 7 / 15 | −2.99295 to 122.40684 | 12 / 15 |
| Context2017 | Historical | 25 / 31 | 11 / 25 | −2.99295 to 183.04230 | 25 / 25 |

Ranks are higher-score-first exact-tie midranks within each fixed eligible pair
set. A rank can change even when that association's score does not, because
other scores move. Eight current-anchor and 14 historical-anchor eligible pairs
have identical prepared context. The aggregate preserves every energy term,
quartile, status combination and missing audit value. No outliers were removed,
no response scale was fitted and no cross-profile common-scale ranking or
significance test was performed. The large extrema are model outputs, not
measured fold changes or evidence of an equivalent expression effect.

## Reproduction and interpretation limits

The [protocol](promoter-wave5-evaluation.md#3-unchanged-rbs-transcript-context-sensitivity),
[collector boundary](rbs-context-collection.md) and [metric definitions](rbs-context-metrics.md)
define the execution and arithmetic. Recompute metrics from the private immutable
collection using the documented `benchmarks.rbs.context_metrics` command; do not
rerun this consumed stage as an untouched test. Source rows, sequences, raw reasons
and per-case outcomes remain with the independent evaluator. Published aggregates
carry no claim of hosted parity, translation improvement or cyanobacterial strength
calibration. The separate native Promoter TSS localization result is not combined
with this context diagnostic.

Artifact SHA256 values:

- Panel: `5cf8ec26ed614edc9b51eb94e5c13207e4ce94fab6e59cec06282893f3e85bf5`.
- Independent context expectations: `efbebe4485a5fe0131168446c8ef74c7de4a3b2b0f114bf1504a68a92a30a55a`.
- Private complete collection: `2cea4e9691b616dd6bfc9311eb2785dc4e58db8b0ed6b9198c5dc9b89db6d080`.
- Private attempt receipt: `c053144eb35a71ab95b30c3dc5aa9191ccb5f2b9c084050f8aa39493dca37774`.
- Private journal: `00cc015c7f137da3b9899ffdd974040c6bb944dd5c3f78d6964dc6f487161bca`.
- Aggregate metrics: `01cd3e117fc017124703e994b6bc63014400e130ae488a673e583b2ca274c6c1`.
- Independent context/schema audit: `49c8d26e83b48d37a8b561eb4b405e5fd7635c1d26a99e455816740eafb753f9`.

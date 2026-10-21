# Native Promoter count association

- Purpose: Reproduce a frozen exploratory model/count association with honest source and uncertainty boundaries.
- Scope: Offline producer benchmark tooling for the original-source native Promoter pilot; no runtime or browser admission.
- Last verified: 2026-10-21

This producer-side analysis uses a frozen, exposed Tan cohort to describe association between historical E. coli model rates at recorded UTEX TSS bases and source-reported initiation counts. It does not calibrate promoter strength, establish causal regulation, measure specificity, or admit predictions to the browser. The earlier fixed-grid Wave 5 analysis consumed Tan labels; this anchor-centered analysis is exploratory.

The machine-readable [protocol](../../benchmarks/promoter/count-association-protocol.json) is the authority for the endpoint, grouping, stratification, missingness and uncertainty rules. The [input manifest](../../benchmarks/promoter/count-association-inputs.json) binds seven explicit existing external inputs. Their contents are not vendored or fetched by this tool. BioCyc membership remains limited, attributed source annotation; it is not an open required calculator dependency.

## Frozen analysis

The primary endpoint is average-tie Spearman correlation of native anchor rate against the arithmetic mean of both control-condition replicates, including zero counts. The paired shuffled-anchor correlation and native-minus-shuffled difference use the same rows. No outliers are removed, no normalization factors or thresholds are fitted, and rates are not selected at the best-scoring offset. Separate condition and replicate endpoints, replicate agreement, and input-only strata are descriptive. A static sequence predictor cannot predict the published condition contrasts, which are excluded.

Exact current or native old-locus crosswalk links provide context, with ambiguous, conflicting and absent links preserved. Inferred TU membership supplies input-only connected groups and strata; it establishes neither complete operons nor biological independence. The retained TransTermHP CDS-overlap annotation supplies a separate same-strand proxy stratum; it does not establish termination between this TSS and its associated CDS. Incomplete origin coverage is never reported as a complete absence. Mapping uncertainty does not remove a record from the unstratified primary endpoint.

The fixed original runner cohort is recomputed from the pinned table and genome without running a predictor. Every excluded source record is retained with its reason. A report is admitted only with the expected input/model/runner identities and complete ordered selected roster, candidate curves, strand/origin mappings and deterministic shuffled controls. Missing or partial original reports fail admission; there is no successful-subset substitution.

The primary three endpoints use 2,000 paired cluster bootstrap draws with seed 2973 and percentile intervals. All grouping precedes outcomes; average ranks are recomputed within each draw. Undefined draws and endpoint denominators remain explicit. Fewer than 90% valid draws yields no interval. These intervals quantify this descriptive sample under its partial grouping assumptions, not generalization to an untouched study.

## Offline boundary

Preparation reads only the seven manifest paths under an explicitly supplied external input root. Evaluation reads only the explicit prepared artifact and report with caller-supplied digests. Both retain the protocol and manifest hashes. The tool does not discover private paths, import a scorer, resolve opaque provenance references, execute a predictor, retrieve sources or modify frozen inputs. Strict bounded reads and deterministic, atomic no-clobber output apply. New input or method versions require a new freeze before outcomes, never regeneration of pins to accept a failing artifact.

## Reproduce locally

Use Python 3.11 or later from the producer repository; the evaluator uses only the standard library. Keep the prepared and evaluation documents outside Git: they contain per-record counts, predictions and limited-rights context. The caller-supplied digests are trust inputs recorded at preparation or in A's source execution receipt, not recalculated expectations used to accept altered evidence.

```sh
python benchmarks/promoter/count_association.py prepare \
  --input-root /explicit/path/to/audited/consumer-inputs \
  --output /external/new-prepared.json
python benchmarks/promoter/count_association.py evaluate \
  --prepared /external/new-prepared.json \
  --prepared-sha256 55077acaaf5d4cb4449801257c3cab0abbf16ce66033a11f1395fc5ad6c2bbce \
  --report /external/original-pilot/report.json \
  --report-sha256 f4021ed3941a66b656df9e40f4a6a406b4cf59c651ec00dd7c54865080ebbc5f \
  --output /external/new-evaluation.json
PYTHONPATH=src:. python -m coverage run --branch \
  --source=benchmarks.promoter.count_association -m pytest -q \
  tests/benchmarks/test_promoter_count_association.py
python -m coverage report -m
```

Both outputs require fresh paths. Data/admission/write/link failures return exit 2 without a newly published result; collisions preserve the existing path. Successful exclusive linking is the publication commit point. A later temporary-file cleanup failure emits a warning naming the residual path and retains exit 0 and the complete final result. If cleanup fails after an earlier write/link error, that original error remains authoritative. The tool never requests elevated access or changes permissions.

Input JSON is limited to 64 MiB and depth 64; decoded FASTA is limited to 8,000,000 bytes. Output keys are sorted with indent 2, ASCII escapes, finite numbers and one trailing LF. Opaque model/source references remain explicitly unverified by this evaluator. Its source and tests at `7fe20c70a203280e5a05ba33c0836bd4b2d22d57` passed 156 synthetic tests, 100% of 574 statements and 136 branches.

## Pinned exploratory result

The protocol bytes were frozen at 2026-10-21 18:50:03 UTC, before the original run began at 18:50:24 UTC. The source wrapper is `regulatory_promoter.py` at consumer commit `f80836248243983beefbfe3f85c83914e5f9d01b`; its SHA-256 is `7d3440ad5239f216ec072dbaac49b430bbaa17d7b28674e18effadcc131f4766`. A's original-source execution receipt SHA-256 is `1366c8782ce15dc63e40665924ffa49c1881a4e6fa24543cd756c99cda9bb884`. These report identities supplement the pinned source/data manifest; the evaluator does not reopen the referenced model files.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Original pilot report | 25,515,500 | `f4021ed3941a66b656df9e40f4a6a406b4cf59c651ec00dd7c54865080ebbc5f` |
| Prepared input/context document | 13,463,278 | `55077acaaf5d4cb4449801257c3cab0abbf16ce66033a11f1395fc5ad6c2bbce` |
| Complete external evaluation | 7,257,466 | `bf0222d8145f6da7b6a1e69ea1364a9036cc1ab07627dc52f79be5d813c91057` |

All 2,475 gTSS source rows are accounted for: 1,597 selected; 613 excluded for repeated source locus, 264 for overlapping windows and one for an identical/reverse-complement window. There are 1,539 groups across the full source roster and 1,351 among selected anchors. All selected anchors have both replicate counts in every condition; no endpoint is reduced for missing counts. The selected current-locus joins are 1,571 unique and 26 unmatched. Primary estimates retain all 1,597.

| Primary control-count endpoint | Spearman value | 95% paired cluster percentile interval |
| --- | ---: | --- |
| Native anchor rate | 0.1726316664 | [0.1257583037, 0.2190856790] |
| Shuffled anchor rate | 0.0487794005 | [0.0021191541, 0.0964237923] |
| Native minus shuffled | 0.1238522659 | [0.0570631506, 0.1879017844] |

Every primary interval has 2,000 valid draws and zero undefined draws. The secondary condition means below use the same 1,597 anchors; they have no inferential intervals or significance claims. Repeated conditions and replicates are not pooled as independent observations.

| Condition | Native-rate/count-mean correlation | Replicate-count agreement |
| --- | ---: | ---: |
| Control | 0.1726316664 | 0.9695957855 |
| Dark | -0.0802063521 | 0.9926263661 |
| High light | 0.2045018352 | 0.9931348174 |
| High temperature | 0.1660225908 | 0.9703587728 |

Independent SciPy/NumPy arithmetic reproduced all emitted point estimates and six primary interval bounds, with maximum scalar difference 1.12e-16; all selected record fields, condition/stratum denominators and grouping partitions were reconciled separately from the evaluator. The original-source localization endpoint is a separate analysis owned by A. This weak count association does not turn localization near known TSSs into a quantitative native-strength model. No adjustment, fit, outlier exclusion or subsequent endpoint selection was made from these results.

The TU grouping and terminator strata are incomplete proxies. For selected anchors, 1,566 have observed source TU membership, five have no source TU data and 26 lack a current mapping. Same-strand predicted terminator/CDS overlap is observed for 111, complete-coverage non-overlap for 1,459, inapplicable for one and unmapped for 26. Empty declared strata remain explicit in the machine report. No positional or full-operon interpretation is inferred from source membership. All findings remain exploratory on an exposed, positive-only gTSS cohort, and do not establish regulatory effects of recoding.

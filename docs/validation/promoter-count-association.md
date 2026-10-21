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

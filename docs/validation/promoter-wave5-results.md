# Frozen native Promoter evaluation

- Purpose: Report source parity and positive-TSS localization separately from native calibration and expression accuracy.
- Scope: Wave 5 Session B, frozen Promoter 0.5.0rc1 candidate; no fitting, new website jobs or recoding-effect experiment.
- Evaluation date: 2026-10-19 UTC.
- Last verified: 2026-10-19

The frozen model recovered **36 of 292 in-window TSS positives (12.33%) exactly within its top ten positions per tile**. Allowing ±3 nt recovered **47/292 (16.10%)**. The corresponding 95% group-bootstrap intervals are 8.97–16.74% and 12.41–20.54%. It therefore localizes a minority of these source positives within the sampled windows. All requested computations completed; execution coverage is separate from positional recovery.

The constant-zero control recovered 1/292 exactly and 3/292 within ±3 nt at top ten under the predeclared genomic-coordinate tie break. It is an uninformative ordering control, not another biological model or a randomized baseline. These descriptive differences do not constitute a predeclared paired superiority test. No native-host calibration, specificity, expression-strength accuracy or biological recoding effect is established.

## Candidate, source and sampling

The candidate is `2dff23cb5697507281f7ffa73fc617d56989b40c`, wheel SHA256 `4443e3558c6c689373fe09af4eabc1530b4af2a166391773056a69053939b1ff`. The historical LaFleur source is pinned at `46da9132740bce30bccd107f02808adf2215e2f0`. The independently checked public source result passed 22 records, 424 states and four no-candidate outcomes at absolute/relative tolerance 1e-12. This establishes the admitted source/coordinate comparison, not agreement with an unversioned hosted website.

The [scientific protocol](promoter-wave5-evaluation.md), [analysis freeze](../../benchmarks/promoter/wave5-native-evaluation-freeze.json) and [collection acknowledgement](../../benchmarks/promoter/wave5-collection-ack.json) preceded native execution. A provided immutable source/resource/CI admission; B retained raw outputs and used no runtime scoring internals to construct independent expected results. No parameter, threshold, window, grouping rule, deadline or exclusion changed after outcomes.

[Tan et al. 2018](https://doi.org/10.1186/s13068-018-1215-8), publisher Table S1, supplies dRNA-seq TSS positives in *Synechococcus elongatus* UTEX 2973. The source workbook SHA256 is `098ecbd204cd1042a6edee1d2a500eaeca4efe034c503e2ade3db1c605e79b00`; source accessions, condition conflicts, rights and reconstruction commands remain in the [native source contract](rbs-native-validation.md) and [source ledger](../../benchmarks/rbs/native-sources.json). Article/data source files and full sequences remain external. This study was already known and its earlier consumer pilot exposed; it is not a newly untouched study.

The panel has 4,808 distinct point/strand positives, 292 in selected windows and 4,516 outside. The grid uses label-independent 1,000-base tiles, at most 128 tiles per replicon/strand, selected by the frozen SHA256 seed. It requests 366 transcript-oriented sequences, 183 per genomic strand, with 67 upstream and 19 downstream context bases. All 364,416 candidate positions are retained. The model uses its explicit E. coli calibration with UTEX 2973 target metadata marked extrapolated; RNA counts are neither translation labels nor transcript-mixture weights.

The sampling retains all small-replicon tiles while sampling chromosome tiles: 228/4,744 chromosome positives and 64/64 positives on NZ_CP006472.1 are in-window; NZ_CP006473.1 has no source positives. The conditional in-window result has a different replicon mix from the full source population. Neither it nor the all-positive sampling endpoint is an unweighted estimate of whole-genome sensitivity.

## Execution and denominators

The serial run completed 92/92 batches and 366/366 requests in 277.664 seconds against a 3,600-second stage ceiling. All 364,416 candidates scored; none was partial-context, failed, unsupported, unstarted, underflowed or overflowed. No record/site was filtered and no retry occurred. All 292 in-window labels belong to complete queries; the separately defined successful-position diagnostics therefore equal the primary recovery counts in this run.

Private raw results passed received-byte and authoritative-serialization caps, exact model/settings/parameter/projection identities, complete-roster/coordinate checks and exit/status reconciliation. The durable version-2 journal finalized; read-only recovery admitted adaptation. Candidate input transport was restricted to explicit strict-UTF-8 LF-only files, avoiding the frozen 0.5 CLI’s documented CRLF/stdin limitation. [Collection procedures](promoter-collection.md) retain the limit and interruption semantics.

Ranking uses lower raw learned `selected.terms.total`, with genomic point then local index for exact ties. Matching is one-to-one maximum cardinality within each query. Every out-of-window, incomplete or failed label remains unrecovered in the all-positive endpoint. A separate denominator of 292 reports conditional in-window recovery; its value does not replace the denominator of 4,808.

## All predeclared recovery endpoints

Each table entry is a percentage with its 95% group-bootstrap interval. The matched count is identical for both denominators; only the denominator changes. All 10,000 resamples were defined for every endpoint.

### Frozen model

| Top k | Tolerance (nt) | Matched | All 4,808 positives, % (95% interval) | In-window 292 positives, % (95% interval) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 8 | 0.166 (0.063–0.290) | 2.740 (1.167–5.000) |
| 1 | 3 | 24 | 0.499 (0.272–0.780) | 8.219 (5.578–11.236) |
| 5 | 0 | 25 | 0.520 (0.285–0.806) | 8.562 (5.851–11.765) |
| 5 | 3 | 33 | 0.686 (0.418–1.000) | 11.301 (8.108–15.696) |
| 10 | 0 | 36 | 0.749 (0.459–1.100) | 12.329 (8.974–16.740) |
| 10 | 3 | 47 | 0.978 (0.610–1.453) | 16.096 (12.414–20.543) |

### Constant-zero control

| Top k | Tolerance (nt) | Matched | All 4,808 positives, % (95% interval) | In-window 292 positives, % (95% interval) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 0 | 0.000 (0.000–0.000) | 0.000 (0.000–0.000) |
| 1 | 3 | 1 | 0.021 (0.000–0.062) | 0.342 (0.000–0.763) |
| 5 | 0 | 1 | 0.021 (0.000–0.062) | 0.342 (0.000–0.763) |
| 5 | 3 | 1 | 0.021 (0.000–0.062) | 0.342 (0.000–0.763) |
| 10 | 0 | 1 | 0.021 (0.000–0.062) | 0.342 (0.000–0.763) |
| 10 | 3 | 3 | 0.062 (0.000–0.163) | 1.027 (0.000–1.994) |

Uncertainty resamples the 1,966 frozen input-only groups, including out-of-window and zero-recovery groups, with 10,000 draws and seed 20261018. There are 138 groups with in-window positives; maximum group size is 64. Shared-query/context, exact-locus, nearby-position and fixed 15-mer similarity links prevent treating those linked labels as independent. The screen is not exhaustive homology detection or a proof of independence from all model-training sequences. Intervals condition on the source’s ascertainment and do not propagate raw-read mapping or biological replicate uncertainty.

## Rank ties and descriptive subgroups

For the 292 scored positives, model mean midrank was 190.545 and median midrank 117.5 in 1,000-position windows; 18 positives tied with another candidate. Optimistic and pessimistic top-1/5/10 exact-rank counts both equal 8/25/36. These exact-rank summaries are separate from tolerance matching. Every constant-control positive ties across its whole window: optimistic rank 1, midrank 500.5 and pessimistic rank 1,000. Its optimistic/pessimistic top-k counts are 292/0 for each declared k; deterministic top-k recovery uses the predeclared coordinate rule rather than either tie bound.

Subgroups below retain the global one-to-one matches. The columns list matched counts for top 1/5/10 at exact and ±3-nt tolerance, respectively. They are descriptive, with no subgroup intervals or source-category promoter-class claim. Zero-positive groups have undefined recovery, not zero specificity.

| Subgroup | All positives | In-window | Exact top 1/5/10 | ±3 nt top 1/5/10 |
| --- | ---: | ---: | --- | --- |
| NZ_CP006471.1 | 4744 | 228 | 7/20/30 | 19/28/38 |
| NZ_CP006472.1 | 64 | 64 | 1/5/6 | 5/5/9 |
| NZ_CP006473.1 | 0 | 0 | 0/0/0 | 0/0/0 |
| aTSS | 1380 | 77 | 1/6/8 | 5/8/9 |
| gTSS | 2475 | 158 | 5/16/24 | 15/21/33 |
| iTSS | 724 | 38 | 1/2/3 | 3/3/4 |
| nTSS | 229 | 19 | 1/1/1 | 1/1/1 |
| unclassified | 0 | 0 | 0/0/0 | 0/0/0 |

The accompanying [aggregate artifact](../../benchmarks/promoter/wave5-native-aggregates.json) retains all control subgroups, tie bounds, conditional diagnostics, coverage counts and full-precision endpoints. It contains no per-case outcomes, group identities or residuals.

## Limits and remaining evidence

This is positive-TSS localization, not a labelled negative benchmark. Unlabelled positions cannot establish precision, PR-AUC, FDR or specificity. TSSs do not establish complete promoter boundaries, translation initiation or native expression strength. There was no outlier removal, score normalization fitted to Tan, biological replicate weighting or read-count-to-strength conversion. No per-case error analysis is released for tuning this cohort.

GSE144621 remains reserved and unadmitted for a new strength challenge: repository/data redistribution rights, exact full reporter flanks and row identities, design/control denominator reconciliation, family/locus overlap and training exposure remain unresolved. The [admission record](../../benchmarks/promoter/gse144621-admission-update.json) distinguishes the article’s CC-BY-4.0 licence from a missing project-wide repository grant. No exposed published-column audit is relabelled as prospective validation.

The unchanged-RBS transcript-context stage and paired current/recoded validation have separate candidates, receipts and results. This Promoter stage used no folding, browser jobs, coins or cyano writes. Further scientific improvement needs a new development/evaluation protocol and suitable reserved evidence; this now-consumed cohort must not be tuned and reported again as untouched.

## Artifact identity and reproduction

| Artifact | SHA256 |
| --- | --- |
| analysis freeze | `1355ca6ab02d43c89050f033cb3c24d6018c819544ce043305b6945b89e0a2c0` |
| protocol acknowledgement | `261f47c79b3ca407a9816b27732cb4777ac41a00852901e8882ea8e8b401516b` |
| collection ledger | `1016c9a783e0f3ae69c996d5a7e77d7034e10deb3c9c80ad74d5d1947125f44a` |
| execution receipt | `e6f85a43c254d89ff83bcecfbe2d2408a97524afd86cfa49d71d9198bcca675d` |
| durable journal | `9ecf0a7a1e951843567333d4cfa1c05ec4bfb6e96c391053dee1b3c7c1dfd895` |
| constant-control metrics_sha256 | `8d9f8d05e5e6fb471b3a93d26bb0d9656eba4791a4882cff4ef19597fcd47498` |
| constant-control scores_sha256 | `ec4d103d35cc31f6c7e6985fe10d1230d5cb1032f47faa646a2ea21b36f43dc5` |
| constant-control uncertainty_sha256 | `b75a32fef9dfed89fb9fdda82f5493bb5638c14ec68ec9e7cd8af37fdc4d4012` |
| native metrics_sha256 | `1976c5632f26970cd3c75189aae8f289bfa87d1a0a7d616e2b14dacdacdc5bdb` |
| native scores_sha256 | `b11ceba1c56b67419b512cb696a3d0d8f3200054354668444160b94654e55e91` |
| native uncertainty_sha256 | `bf2e7fab35ce87627bf99125f67f59709490cd1120d64723f27231bd54185a32` |

The query, label, grouping, source and tool hashes are fixed in the analysis freeze. Native per-case outputs and group sufficient statistics are private; hashes identify the exact retained artifacts. Recomputing summaries from those preserved artifacts does not execute a predictor:

```sh
python -m benchmarks.promoter.native_metrics QUERIES.json SCORES.json LABELS.json GROUPS.json METRICS.json \
  --direction lower --top-k 1 5 10 --tolerance-nt 0 3 \
  --queries-sha256 f71f7d82f9ebf8b1f58c40851436000fbff9e139d07210794961e82720e251f5
python -m benchmarks.promoter.native_uncertainty METRICS.json INTERVALS.json \
  --metrics-sha256 METRICS_FILE_SHA256
```

Run once for the saved native scores and once for the frozen-rule constant-zero scores. Verify the label/group/score hashes above and in the freeze before loading. The constant document assigns `0.0` and `ok` to every declared candidate independently of runtime outcomes. The [adapter contract](promoter-runtime-adapter.md) describes rebuilding the plan and validating completed raw results before deriving scores; the read-only journal recovery gate also applies.

Root validation before collection passed the integrated 493-test/843-subtest benchmark suite at 100% of 3,804 statements/1,542 branches; after the final deadline fix, the affected collector passed 50 tests/130 subtests at 100% of 416 statements/118 branches. An independent reviewer approved that exact fix with 23 focused tests and additional deadline/durability probes. These software checks are separate from the native positional results above.

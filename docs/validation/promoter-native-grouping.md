# Native Promoter uncertainty groups and group bootstrap

- Purpose: Freeze input-only label groups before scoring and turn reviewed group sufficient statistics into cluster-bootstrap intervals.
- Scope: Deterministic stdlib tools tested on synthetic inputs; no scores, real labels or final outcomes.
- Owner: Session B (`9677689a-1792176763`); the frozen protocol and final collection stay with B.
- Last verified: 2026-10-18

The tools are [`native_groups.py`](../../benchmarks/promoter/native_groups.py)
and [`native_uncertainty.py`](../../benchmarks/promoter/native_uncertainty.py).
They implement the grouping and interval rules of output 2 in the
[Wave 5 evaluation protocol](promoter-wave5-evaluation.md) and consume the
documents of the [native query and metric tooling](promoter-native-tooling.md).
Coordinates are zero-based half-open. Outputs are canonical JSON created
exclusively with mode 0600 and never overwritten. Every failure exits 1.

## Groups are frozen from inputs only

Input is the pinned `native-rbs-evidence-1` envelope (file SHA-256 supplied by
the caller), its query document and its label projection, both canonical tool
output. The tool rebuilds the queries from the envelope and recorded settings
and re-projects the labels; both must equal the supplied documents exactly. No
score, metric, read count or other file is read. Rule constants are fixed in
code and recorded under `settings`; nothing is tunable from the command line.

Nodes are every projected label (in-window or out-of-window) and every selected
query. Edges:

| Rule | Connects |
| --- | --- |
| `label_query_attachment` | An in-window label and its query. |
| `query_interval_overlap_or_touch` | Two queries whose padded genomic segments overlap or touch (`[a, b)` and `[b, c)`) on one replicon, irrespective of strand. On circular replicons a segment ending at `L` touches one starting at 0. |
| `label_locus_tag` | Two labels on one replicon sharing an exact nonempty `source_locus_tag` from their preserved source rows. No alias or case folding. |
| `label_distance` | Two labels on one replicon at most 86 nt apart, either strand; circular replicons use `min(d, L - d)`. |
| `label_context_kmer` | Two labels whose distinct canonical 15-mer sets have Jaccard ≥ 1/2. |

Each label's context is 67 nt upstream, the TSS base and 19 nt downstream in
transcript orientation, extracted with the query builder's own padding: linear
replicons clip at their ends; circular padding wraps the origin at most once,
never repeats a base and shortens upstream first. Contexts of 87 nt are
`complete`, 15–86 nt `clipped` (still screened) and shorter ones `unavailable`
(no k-mer edge). Each 15-mer is canonicalized as `min(kmer, reverse
complement)`. The threshold is tested in exact integers,
`2·|A∩B| ≥ |A∪B|`. This is a fixed near-duplicate screen, not homology detection.

Candidate k-mer pairs come from an inverted index, so only pairs sharing a
15-mer are counted. Unlabelled queries may bridge labels. Label-free components
produce no group and are reported only as counts. A group's ID is the
lexicographically smallest member `label_id` (Python string order), never a
query ID. Results are independent of record, label and query order.

The output (`promoter-native-groups-1`) carries `labels_document_sha256` and
`groups` (every label to its group ID), as the metrics tool requires, plus
`inputs` (envelope file, query and label document hashes), `settings`,
`settings_sha256`, `tool_sha256` and `dependency_tool_sha256.native_inputs`.
`counts` gives label window totals, labels with locus tags, queries with labels,
edges per rule, context status and limit reasons, group number, sizes as
`[size, count]` pairs, the largest group and label-free query components.
No per-label context or sequence is emitted.

## Group-bootstrap intervals

Input is one canonical `promoter-native-metrics-1` document and its explicit
file SHA-256; no scores, labels or groups are joined. Before computing, the tool
checks schema, metric settings and `settings_sha256`, hash-shaped tool and input
identities, and in `overall` and every group: nonnegative integer counts (not
bool), complete ⊆ scored ⊆ in-window ⊆ all labels, `n_out_of_window`, the exact
top-k × tolerance roster, `matched` ≤ complete-query labels and each reported
fraction (`matched / denominator`, null for zero). Every group needs at least
one label, `n_groups` must match, and group counts and matches must sum to
`overall`. Any disagreement rejects the document.

| Setting | Value |
| --- | --- |
| Universe | All groups sorted by ID, including zero-denominator groups |
| Draws | 10,000; `random.Random(20261018)`; each draw is `choices(range(G), k=G)`, shared by every endpoint and both denominators |
| Statistic | Σ matched / Σ denominator over drawn groups, for each top-k × tolerance, all-label and in-window |
| Undefined | A draw with zero summed denominator is counted and omitted, never scored 0 |
| Interval | Sorted defined values `v`, `h = (n − 1)·q`, `v[⌊h⌋] + (h − ⌊h⌋)(v[⌊h⌋+1] − v[⌊h⌋])`, q = 1/40 and 39/40 |
| Eligibility | Groups with a positive denominator; fewer than 20 gives `insufficient_group_count` and point counts only |

Each endpoint row reports matched, denominator, point ratio, eligible groups,
status (`interval`, `insufficient_group_count` or `no_defined_resamples`),
resample, defined and undefined counts, and the interval. The receipt adds
settings and hash, the metrics document hash with its settings, tool and input
hashes, this tool's hash and the Python implementation and version: exact
reproduction needs the same PRNG implementation. No per-group or per-label
values are emitted. Intervals condition on this source's ascertainment and omit
read-mapping and biological-replicate uncertainty. They support no clinical,
translational, precision or genome-wide accuracy claim.

## Resource limits

Limits are checked before graph, pair or resample allocation. File reads stop
one byte past their limit.

| Item | Limit |
| --- | --- |
| Envelope / query / label / metrics file | 64 / 256 / 128 / 256 MiB |
| Grouped labels, queries | 20,000 (about four times Tan); 200,000 |
| Distinct edges per rule | 1,000,000 |
| Locus-tag or k-mer posting pair work, Σ C(m, 2) | 2,000,000 |
| Bootstrap groups, groups × draws, × columns | 500,000; 100,000,000; 1,000,000,000 |

On a synthetic Tan-sized input (4,808 labels and 366 queries on a 4 Mb circular
replicon; 1,927 groups; six endpoints) grouping took 0.3 s and the bootstrap
4.6 s with 150 MB peak RSS, using Python 3.14 on the shared macOS host.

## Reproduction

Run from the repository root with Python ≥3.11 and `PYTHONPATH=src:.`. Keep real
envelopes, labels, groups, metrics and receipts outside Git.

```sh
python -m benchmarks.promoter.native_groups ENVELOPE QUERIES.json LABELS.json GROUPS.json --source-sha256 ENVELOPE_SHA256
python -m benchmarks.promoter.native_uncertainty METRICS.json UNCERTAINTY.json --metrics-sha256 METRICS_SHA256
python -m pytest tests/benchmarks/test_promoter_native_groups.py tests/benchmarks/test_promoter_native_uncertainty.py --cov=benchmarks.promoter.native_groups --cov=benchmarks.promoter.native_uncertainty --cov-branch
```

The tests use only synthetic genomes and statistics and cover both modules
fully. A hand-designed fixture fixes every component: transitivity through
touching queries, the circular seam, tag-only and distance-only joins, a
cross-strand duplicate, the exact 1/2 boundary (48/96 joins, 47/96 does not),
clipped and unavailable contexts and an unlabelled-only query. An independent
O(n²) base-by-base graph and context walk checks randomized fixtures and
order invariance. Bootstrap tests cover constant, all-zero, all-hit and
all-zero-window inputs, fewer than 20 groups, hand percentiles, a plain-loop
reference, seed repeatability, undefined draws, tampering and CLI failures.

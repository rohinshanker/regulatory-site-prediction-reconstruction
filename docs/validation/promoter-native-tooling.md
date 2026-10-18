# Native Promoter query and positional-metric tooling

- Purpose: Build label-free genome-grid Promoter queries, project positive TSS labels separately and evaluate supplied scores by positional recovery.
- Scope: Deterministic stdlib tools for queries, separate source-label projection and supplied-score evaluation; tests use synthetic outcomes and import no runtime scoring engine.
- Owner: Session B (`9677689a-1792176763`); the frozen protocol, label extraction and grouping stay with B.
- Last verified: 2026-10-18

The tools are [`native_inputs.py`](../../benchmarks/promoter/native_inputs.py)
and [`native_metrics.py`](../../benchmarks/promoter/native_metrics.py). They
implement output 2 of the [Wave 5 program](wave5-program.md). Coordinates are
zero-based half-open. Tool outputs are canonical JSON (sorted keys, compact,
trailing newline), so a document's `*_sha256` identity equals its file hash.
Outputs are created exclusively and never overwritten; labels and metrics use
mode 0600. No output contains wall-clock metadata. Every failure exits 1.

## Queries are built before and without labels

Input is a pinned `native-rbs-evidence-1` envelope in the
[native input contract](rbs-native-input-contract.md) format. The caller supplies
the file SHA-256. The loader rejects duplicate JSON keys, NaN/Infinity and
overflowing numbers, and requires each genome to carry uppercase ACGT matching
`sequence_sha256`, nonempty identity fields and `linear`/`circular` topology.
Record IDs must be unique. The query builder never reads record contents.

For each genome and both strands, grid tile `k` covers genomic points
`[k*w, min((k+1)*w, L))`; the last tile may be partial. Tiles are ordered by
`sha256(canonical JSON [seed, genome_sha256, strand, k])` and the first
`max_tiles_per_genome_strand` are selected. Defaults are width 1000, cap 128 and
seed `wave5-tan-grid-v1`. The default settings identity is
`cb40bb489a5e7ed5f63bf8b796bca773e1a6392a38ee9d6c67369aecc2b05e04`. Pin the
final values in the frozen protocol before any score exists.

Every point in a selected tile is a candidate TSS. The sequence adds 67 nt
upstream and 19 nt downstream in transcript orientation: discriminator 10,
hex10 6, spacer 20, hex35 6, gap 1 and UP 24 give all 30 source states, and the
20-base ITR needs 19 bases after the TSS. Linear replicons clip at their ends.
Circular padding wraps the origin once. Padding is reduced so that no base
repeats; any shortfall comes from the upstream side first, keeping
downstream context.

| Query field | Meaning |
| --- | --- |
| `query_id` | `promoter-grid:GENOME:plus|minus:TILE`. |
| `strand`, `orientation` | Reference strand; sequence is transcript 5′→3′. |
| `tile_ordinal`, `selection_rank`, `selection_key` | Grid tile, rank and hash used to select it. |
| `candidate_genomic_interval` | Ascending genomic tile `[a, b)`. |
| `candidate_local_range`, `n_candidates` | Candidate TSS indices in the query sequence. |
| `sequence`, `sequence_sha256`, `sequence_length` | Normalized oriented DNA and its hash. |
| `segments` | Transcript-ordered `local`, `genomic` and `oriented` intervals. Plus: `g = g0 + i - l0`. Minus: `g = g1 - 1 - (i - l0)`; `oriented` is `[L - g1, L - g0)`, so reverse-complement point `t = L - 1 - g`. |
| `context`, `context_status` | Pads, shortfalls and `linear_edge`/`circular_no_repeat_limit`; `complete`, `clipped` or `no_full_state_support`. |
| `full_state_support_local_range`, `n_candidates_full_state_support` | Candidates with ≥67 nt upstream and ≥19 nt downstream; null when none. Partial-state handling is the runtime's. |

The document also carries `source.file_sha256`, `tool_sha256`, `settings` and
`settings_sha256`, per-genome accession/assembly/annotation/topology/hash/length,
and `queries_sha256`. Its `grid` and `grid_totals` give tile and point
denominators for every genome and strand: grid, selected and not-selected
counts. No TSS, CDS, read count, condition or model output enters a query.

## Explicit label projection

`project-labels` is invoked separately and is never called by the builder. It
first rebuilds the query document from the envelope and its recorded settings,
and requires exact equality. Rows sharing a genome, strand and TSS point become
one positive label (`tss:GENOME:STRAND:POINT`). Every source row is kept,
sorted by ID, with study, sheet/row, file hash, TSS type, transcript evidence,
one-based position, locus, mapping status, warnings, raw conditions and source
and reference nucleotides. CDS, leader, translation-evidence and S2 start-proposal fields are
dropped. No weights, negatives or translation labels are created.

Each label and row reports `in_selected_query` (with `query_id`/`local_index`)
or `out_of_window`; rows without a measured TSS report `no_measured_tss`. A
recorded one-based position must equal the zero-based point plus one.

## Metric inputs and definitions

Scores use `promoter-native-scores-1`: `query_document_sha256` and one
`results` row per query with exactly `request_id` (unique), `query_id`,
`status` and `candidates`. Status is `ok`, `failed`, `not_run`, `unsupported`
or `no_candidate`. An `ok` request must list each candidate local index exactly
once, with exactly `local_index`, `status` and `score`: a finite number for
`ok`, null otherwise. Other requests list no candidates. Labels must be the
projection's schema bound to the same query document, with reproducible window
membership. Groups use `promoter-native-groups-1`: `labels_document_sha256`
and exactly one supplied nonempty group per label. Groups are never inferred
from names.

Direction is required (`--direction lower` for the raw Promoter score). Within
each query, `ok` candidates are ranked by score. Ties break by genomic point
ascending and then by local index. Top-k positions are matched to that query's
labels within each predeclared tolerance (default top 1/5/10, ±0/±3 nt). The
matching is one-to-one and maximum-cardinality: one prediction never recovers
two positives. Ranks are within the declared window only.

The all-case endpoint (`recovery`, `exact_rank_tie_bounds`, `conditional_rank`)
keeps every label in the whole-label denominator. It credits only complete
queries: the request is `ok` and every candidate is `ok`. Out-of-window labels,
failed/not-run requests and partially scored queries count as unrecovered; no
winner is inferred from a partial ranking. The in-window denominator is
reported too. A separately named `conditional_successful_positions` summary
ranks labels whose own candidate scored, including partially scored queries,
over the scored-label denominator. It is not the all-case endpoint.

Coverage reports request/candidate status counts and complete and incomplete
`ok` queries. For each ranked positive the tool gives optimistic (better + 1),
midrank and pessimistic (better + tied) ranks, and the top-k counts under both
tie bounds. These bounds show whether the tie-break helped. No precision,
PR-AUC or FDR is reported, and unlabelled points are not negatives.

Empty subsets give null fractions with zero denominators, and no ranked
positives give null means. Per-group output repeats the same counts and rank
sums. These are sufficient statistics for B's separate group-level uncertainty
tool; this evaluator has no bootstrap. Repeated conditions are already one
label, so they are not independent samples. When competing labels in one window belong to
different groups, group credit follows the deterministic matching (labels by
local index, each taking the leftmost free acceptable prediction).

`subgroups` reports each declared replicon (including those with zero positives)
and the source categories gTSS/aTSS/iTSS/nTSS. Missing or unknown categories go
in `unclassified`. Duplicate source rows do not duplicate a label's membership;
a label with several categories belongs to each, and the number of such labels
is reported. Category totals therefore need not sum to the overall denominator.
All subgroup credits use the same global matches and ranks. The tool never
rematches after excluding competing labels from other categories. These are
descriptive summaries without subgroup confidence intervals; zero denominators
remain null.
Categories match exact source strings without case folding or whitespace repair.
A label with both a known type and an untyped/unknown row belongs to both the
known category and `unclassified`, and counts toward the overlap total. Original
type values remain in the separate label document. Tolerance-based category
credit can depend on nearby competing labels of another category because the
global matching assigns the earliest eligible label first, even when a later
label is an exact hit. The category summaries are descriptive attribution of
global recovery, not independent category-specific detection experiments.

## Resource limits

All limits are checked before allocation. File reads stop one byte past their
limit and fail rather than truncate.

| Item | Limit |
| --- | --- |
| Envelope / query / score / label or group file | 64 / 256 / 512 / 128 MiB |
| Genomes, genome length, records | 64; 20,000,000 nt; 200,000 |
| Tile width, cap, seed | 1–100,000; 1–100,000; 1–256 characters |
| Grid tiles (both strands), selected query DNA | 2,000,000; 100,000,000 nt |
| Queries, candidates, labels | 200,000; 10,000,000; 500,000 |
| Top-k / tolerance values | ≤8 unique each; k 1–1000; tolerance 0–100 nt |

## Reproduction

Run from the repository root with Python ≥3.11 and `PYTHONPATH=src:.`. Keep real
envelopes, labels, scores and metrics outside Git.

```sh
python -m benchmarks.promoter.native_inputs build-queries ENVELOPE QUERIES.json --source-sha256 ENVELOPE_SHA256 --tile-width 1000 --max-tiles-per-genome-strand 128 --seed wave5-tan-grid-v1
python -m benchmarks.promoter.native_inputs project-labels ENVELOPE QUERIES.json LABELS.json --source-sha256 ENVELOPE_SHA256
python -m benchmarks.promoter.native_metrics QUERIES.json SCORES.json LABELS.json GROUPS.json METRICS.json --direction lower --queries-sha256 QUERIES_SHA256 --top-k 1 5 10 --tolerance-nt 0 3
python -m pytest tests/benchmarks/test_promoter_native_inputs.py tests/benchmarks/test_promoter_native_metrics.py
```

Each command prints the output hash. The tests use only synthetic genomes,
labels and scores. They hand-check plus/minus mapping, circular origins,
partial terminal tiles, tiny genomes, clipping, repeated deterministic output,
pinned settings/query hashes, exclusion of envelope measurement fields,
competing-label matching against brute force, zero all-case credit for
partially scored queries, ties, empty subsets and all-failed requests.

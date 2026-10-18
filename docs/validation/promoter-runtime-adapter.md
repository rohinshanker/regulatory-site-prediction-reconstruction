# Promoter runtime adapter and complete-roster scores

- Purpose: Turn frozen native Promoter queries into exact public-runtime requests, then turn collected public results into complete-roster scores for positional metrics.
- Scope: Session B, ticket #34. Outcome-free stdlib tooling; it runs no runtime, computes no scores or model terms and reads no labels.
- Last verified: 2026-10-18

[`runtime_adapter.py`](../../benchmarks/promoter/runtime_adapter.py) implements
the [runtime contract](promoter-runtime.md) at public interface
`b8ef835e4faddb02ae47ee6450710b5eaf9158bd` (task baseline
`21cab40908cdc850735b41d1c84430e3ee0b14d9`). It sits
between the [native queries](promoter-native-tooling.md) and
[`native_metrics.py`](../../benchmarks/promoter/native_metrics.py), following
the [Wave 5 protocol](promoter-wave5-evaluation.md). No candidate, settings
receipt or owner release gate exists yet. The test identities and results are
synthetic fakes, not candidate receipts. Limits are reviewed ceilings, not
measured capacities; no speed or feasibility claim is made before A's
measurements. `candidate_commit` and `wheel_sha256` are caller assertions:
matching result identities does not prove which binary executed.

## Manifest

All values are explicit; nothing defaults. Commits are 40-hex and hashes
64-hex lowercase. Write the manifest with the `manifest` command so the file is
canonical.

| Field | Rule |
| --- | --- |
| `identity` | `candidate_commit`, `public_contract_commit`, `wheel_sha256`, `implementation_version`, `model_id`, `parameter_json_sha256`, `expected_model` |
| `identity.expected_model` | The receipt's exact result `model` object. It has the contract's twelve keys, restates `id`, `implementation_version` and `parameters.parameter_json_sha256`, has a nonempty `source` and at least one parameter identity besides the JSON hash, and keeps the public kind, unit, `not_modeled` and all-false `claims` |
| `settings.calibration` | `ecoli_mg1655` or `in_vitro` |
| `settings.host` | `null` or `{name (1..200, NFC), taxon_id (int > 0 or null)}`; metadata only |
| `settings.limits` | `request_bytes` ≤ 4,000,000; `records_per_batch` ≤ 100; `bases_per_record` ≤ 5,000; `bases_per_batch` ≤ 100,000; `sites_per_record` ≤ 5,000; `sites_per_batch` ≤ 20,000 |
| `settings.runtime_limits` | The receipt's exact effective `batch.limits` object (nonempty), separate from B's packing limits |
| `settings.seconds_per_record` / `seconds_per_batch` | positive, ≤ 120 / ≤ 3,600 |
| `settings.cli_calibration` / `cli_states` | The runtime CLI defaults actually passed: `null`, the record calibration / `selected` |

## Plan (`promoter-runtime-plan-1`)

`prepare` requires the canonical `promoter-native-queries-1` file and manifest,
each pinned by file SHA-256. The query document and every query must have exactly
the builder's keys, so no label field can enter. It validates:

- sequence hash, length and uppercase ACGT;
- one or two segments covering the sequence contiguously, each inside the replicon;
- the `oriented` field of each segment;
- the context pads/shortfalls and full-state support;
- the candidate range and count, and the genomic tile.

The projection origin is the first segment's genomic start (plus) or end − 1
(minus). `sequence_strand` is the query strand and topology comes from the
genome. Crossing follows the contract formula. Every segment must equal the
contract's map of its local run, so each base maps to its query coordinate.
Linear crossing and circular repeats fail.

Each query becomes record `q000000`, `q000001`, … with its sequence unchanged.
Clipped linear queries stay unpadded. The record has:

- the query's exact `candidate_local_range` as `{"mode":"scan","strands":["+"]}`;
- the projection;
- the manifest calibration, host and model pin;
- output `{"states":"selected","legacy_keys":false,"elements":false}`.

Batches are packed greedily in query order. A new batch starts when any
aggregate limit would be exceeded. Request size is the exact canonical file:
`{"defaults":{},"records":[…],"schema_version":"1.0"}`. A record that exceeds a
per-record limit or cannot fit alone fails preparation; nothing is dropped or
clipped.

The plan stores:

- query document, query settings, manifest, identity and settings hashes;
- the public contract commit;
- expected calibration from the public profile/host table;
- totals;
- per batch: its request document, SHA-256 and byte count, the request-to-query map, and the expected public `batch_id`.

`batch_id` is SHA-256 of compact sorted-key JSON of `input` (the exact request
document), `model` (`id`, `implementation_version`, `parameter_json_sha256`),
`limits` (`runtime_limits`), both deadlines, `cli_calibration` and `cli_states`.
Every generated request validates against A's
[request schema](../../schemas/promoter-request-1.0.schema.json) in the tests.

`export-request` writes one batch's exact bytes after checking its hash.

## Collection (`promoter-runtime-collection-1`)

```json
{"schema_version": "promoter-runtime-collection-1", "plan_sha256": "<plan>",
 "batches": [
  {"batch_index": 0, "request_sha256": "<planned>", "status": "completed", "exit_code": 1, "result_sha256": "<result file>"},
  {"batch_index": 1, "request_sha256": "<planned>", "status": "setup_failed", "exit_code": 2, "result_sha256": null},
  {"batch_index": 2, "request_sha256": "<planned>", "status": "execution_failed", "exit_code": -9, "result_sha256": null},
  {"batch_index": 3, "request_sha256": "<planned>", "status": "not_run", "exit_code": null, "result_sha256": null}]}
```

| Batch status | Exit code | Result |
| --- | --- | --- |
| `completed` | 0 or 1 (1 exactly when a record is `failed`/`invalid_input`) | public result file hash |
| `setup_failed` | 2 (documented setup error) | null |
| `execution_failed` | any other nonzero code (crash, signal, timeout) | null |
| `not_run` | null | null |

Every planned batch appears once, in order. Missing work is never inferred as
`not_run`, and there is no retry. Result files are supplied by `--result` and
matched by hash; each must be used exactly once. Identity-invalid result JSON
rejects the collection; it never becomes `execution_failed`. `adapt` takes the
exact collection bytes and their SHA-256, rebuilds the plan from the queries and
manifest, and requires the pinned plan hash.

For a completed result (strict JSON, ≤ 64 MiB), the adapter checks:

- schema `1.0` and a `model` equal to `expected_model` (no partial or anywhere-in-object matching);
- the planned `batch_id`, `limits` equal to `runtime_limits`, and deadlines equal to the manifest;
- batch counts, completeness and the exit code.

Each record must be present in order. For `ok`, `no_candidate` and `failed`
records it checks:

- the exact input hashes/length, calibration, scan and projection, and null metadata;
- every planned site, in order, with `psite1:` IDs sharing one scope;
- each site's local `+` TSS, genomic point/strand, context and coordinate state count;
- the selected state's complete `(d, s)`, state ID, finite terms/log score, score status and its local/oriented/genomic intervals;
- status/reason/attempted consistency: unattempted sites are `failed`/`deadline_exceeded`, `no_candidate` sites are attempted, and `nonfinite_arithmetic` needs an eligible state;
- an `ok` relative score that is finite and at least the smallest normal binary64 (never zero, negative or subnormal);
- record-status precedence and exact coverage, with the truncation reason drawn from actual failed sites.

`invalid_input` and `unsupported` records need empty `sites` and null
`prediction_id` and `coverage`. Each non-null `calibration`, `scan`,
`projection` and `input` field must equal the planned value. Any disagreement
rejects the whole collection.
It never becomes a missing or failed row. Only `selected.terms.total` is copied,
as a lower-better finite scalar. There is no log/relative conversion, and the
terms are not recomputed.

## Scores-2 (`promoter-native-scores-2`)

```json
{"schema_version": "promoter-native-scores-2", "query_document_sha256": "<queries>",
 "provenance": {"adapter_tool_sha256": "…", "plan_sha256": "…", "collection_sha256": "…",
                "score_field": "selected.terms.total", "score_unit": "source_dG_units"},
 "results": [{"request_id": "q000000", "query_id": "…", "status": "failed",
              "runtime_status": "failed",
              "candidates": [{"local_index": 67, "status": "ok", "score": -1.2}, "…"]}]}
```

There is one row per query, in query order. Each row lists every candidate
local index in order, for every status, with null scores for non-`ok`
candidates. Runtime status maps to request status:

- `ok`, `no_candidate`, `unsupported` and `not_run` are unchanged;
- `failed`, `invalid_input`, `setup_failed` and `execution_failed` become `failed`.

Rosters must agree with the status:

| Request (runtime) | Candidates |
| --- | --- |
| `ok` | ≥1 `ok`; the rest `no_candidate` |
| `failed` (`failed`) | `ok`/`no_candidate`/`failed`; ≥1 `failed` when nonempty |
| `failed` (`invalid_input`, `setup_failed`, `execution_failed`) | all `failed` |
| `no_candidate`, `unsupported`, `not_run` | all that status |

The adapter maps sites to candidates as follows: `ok` → `ok`, insufficient
context → `no_candidate`, and failed or unattempted → `failed`. Partial-state
sites that scored are `ok`.

Scores-1 behaviour and output bytes are unchanged; the tests pin them. With
scores-2, the all-case endpoint still credits only an `ok` request whose every
candidate is `ok`. Scored candidates of failed requests enter only
`conditional_successful_positions`. Unsupported, not-run and setup-failed rows
are never success. Scores-2 metrics add `score_schema`, `runtime_status`,
`candidate_status_all_requests` and `n_non_ok_queries_with_scored_candidates`
to `coverage`. They keep `promoter-native-metrics-1`, so the uncertainty tool
still applies. Direction stays an explicit `--direction lower`.

## Audit and privacy

The scores file and the audit `promoter-runtime-adapter-audit-1` are both
written exclusively with mode 0600. The audit binds:

- the plan, collection, scores, queries, manifest and settings hashes, plus the public identity;
- whole-collection counts of batch, runtime, request and candidate statuses, site reason codes and selected score statuses;
- partial-state, unattempted and tied-selection site counts, and complete and incomplete requests.

It has no per-batch ledger, per-case score, status-to-case link, reason text or
hash, error message, path or secret. The collection and scores stay private.

## Reproduction

Run from the repository root with `PYTHONPATH=src:.` and Python ≥3.11. Keep real
plans, results, scores and audits outside Git. Every failure exits 1 without
overwriting.

```sh
python -m benchmarks.promoter.runtime_adapter manifest MANIFEST.json --candidate-commit C \
  --public-contract-commit P --wheel-sha256 W --implementation-version V --model-id M \
  --parameter-json-sha256 H --expected-model MODEL.json --runtime-limits LIMITS.json \
  --calibration ecoli_mg1655 (--host-name NAME [--host-taxon-id N] | --no-host) \
  --cli-calibration none --cli-states none \
  --max-request-bytes N --max-records-per-batch N --max-bases-per-record N \
  --max-bases-per-batch N --max-sites-per-record N --max-sites-per-batch N \
  --seconds-per-record S --seconds-per-batch S
python -m benchmarks.promoter.runtime_adapter prepare QUERIES.json MANIFEST.json PLAN.json \
  --queries-sha256 Q --manifest-sha256 F
python -m benchmarks.promoter.runtime_adapter export-request PLAN.json 0 REQUEST-0.json --plan-sha256 PL
python -m benchmarks.promoter.runtime_adapter adapt QUERIES.json MANIFEST.json COLLECTION.json \
  SCORES.json AUDIT.json --queries-sha256 Q --manifest-sha256 F --plan-sha256 PL \
  --collection-sha256 CO --result RESULT-0.json
python -m coverage run --branch \
  --source=benchmarks.promoter.runtime_adapter,benchmarks.promoter.native_metrics \
  -m pytest tests/benchmarks/test_promoter_runtime_adapter.py \
  tests/benchmarks/test_promoter_native_metrics.py
```

Tests cover the following, all on synthetic outcome-free cases:

- the tiny fixtures, N=101 with origin 95/`+` and origin 5/`-`;
- the eight worked projection examples and a brute-force per-base projection check;
- circular plus/minus crossing and linear clipped queries, plus an empty range;
- every manifest, query, collection, result, site and CLI rejection;
- batching at each limit's exact boundary and one past it;
- partial, setup and execution failures, and the reviewed model/limits/`batch_id` probes;
- schema validity of every generated request;
- metrics integration on synthetic labels.

## Open contract questions

These b8ef835 result details are still open (asked of A in GH34). The adapter
fails closed on each stated assumption, and none is invented as a receipt value.

1. With no request `host`, the result `calibration.host` is assumed `null`. With no `metadata`, the record `metadata` is assumed `null`.
2. `input.normalization` text is only checked as a nonempty string.
3. Zero `status_counts` entries may be omitted. `seconds_per_record`/`seconds_per_batch` are `batch` fields.
4. `truncation.attempted_sites` is assumed to count `attempted: true` sites.
5. A `failed` record must list a failed site. An empty-scan record failed only by the batch deadline would be rejected.
6. Site scope and `prediction_id` hash payloads are not recomputed. Sites must share one scope, and `prediction_id` must be 64-hex.
7. The warning objects are not checked.

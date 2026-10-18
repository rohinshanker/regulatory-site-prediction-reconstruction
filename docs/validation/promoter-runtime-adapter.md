# Promoter runtime adapter and complete-roster scores

- Purpose: Turn frozen native Promoter queries into exact public-runtime requests, then turn collected public results into complete-roster scores for positional metrics.
- Scope: Session B, ticket #34. Outcome-free stdlib tooling; it runs no runtime, computes no scores or model terms and reads no labels.
- Last verified: 2026-10-18

[`runtime_adapter.py`](../../benchmarks/promoter/runtime_adapter.py) implements
the [runtime contract](promoter-runtime.md) at public interface
`5b890a3c307d366a828d95812f22a2b9975e6cfe` (task baseline
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
| `identity` | `candidate_commit`, `public_contract_commit`, `wheel_sha256`, `identity_model`, `expected_model` |
| `identity.identity_model` | The receipt's exact six-key object: `id`, `implementation_version`, `parameter_json_sha256`, `coefficient_array_sha256`, `intercept_array_sha256` (64-hex) and `source_commit` (40-hex) |
| `identity.expected_model` | The receipt's exact emitted `model` object with the contract's twelve keys. Its `id`, `implementation_version` and `parameters.parameter_json_sha256` equal `identity_model`, and it keeps the public kind, unit, `not_modeled` and all-false `claims`. No other nested key is read |
| `settings.calibration` | `ecoli_mg1655` or `in_vitro` |
| `settings.host` | `null` or `{name (NFC, ≤ max_host_name_chars), taxon_id (int > 0 or null)}`; metadata only |
| `settings.runtime_limits` | The receipt's complete effective `batch.limits` object with exactly the 20 public keys: positive integer counts and float deadline defaults/maxima, each no greater than the published ceiling, and each default no greater than its maximum. The published ceiling object is not a receipt |
| `settings.limits` | B packing limits `request_bytes`, `records_per_batch`, `bases_per_record`, `bases_per_batch`, `sites_per_record`, `sites_per_batch`. Each is no greater than the corresponding effective limit. `bases_per_record` also fits `max_raw_sequence_chars_per_record`, because requests are uppercase DNA |
| `settings.seconds_per_record` / `seconds_per_batch` | The actual deadlines: positive floats (`30.0`, never `30`) no greater than the effective maxima. The CLI converts integers to floats |
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
Record IDs and contigs must fit `max_id_chars` and `max_contig_chars`.
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

Hashes use the public runtime canonical bytes: sorted keys, compact separators,
`ensure_ascii=True`, `allow_nan=False`, UTF-8, no trailing newline. `batch_id`
hashes `input` (the exact request document), `model` (the `identity_model` `id`,
`implementation_version` and `parameter_json_sha256`), `limits` (the full
`runtime_limits`), both float deadlines, `cli_calibration` and `cli_states`.
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

For a completed result, the adapter bounds received bytes before strict JSON
parsing, then reserializes the complete parsed value with sorted keys, two-space
indentation, ASCII escaping and one trailing LF, exactly as the runtime contract
specifies. Both lengths must fit the effective `max_result_json_bytes`; equality
is allowed. Compact output cannot evade the authoritative size limit, and extra
wire whitespace cannot evade the received-byte limit. It then checks:

- schema `1.0` and a `model` equal to `expected_model` (no partial or anywhere-in-object matching);
- the planned `batch_id`, `limits` equal to `runtime_limits`, and float deadlines equal to the manifest;
- batch counts, completeness and the exit code.

Each record must be present in order. For `ok`, `no_candidate` and `failed`
records it checks:

- the exact input hashes/length and `normalization` `ascii-whitespace-uppercase-u-to-t-1`, calibration (host `null` when absent, `taxon_id` `null` when omitted), scan and projection, and null metadata;
- `prediction_id` recomputed from the literal payloads, with `scope_id` built over schema `1.0`, `identity_model`, calibration profile/host, normalized-DNA hash and projection, and `prediction_id` over the full 64-hex `scope_id`, resolved scan and output;
- every planned site, in order, whose `psite1:` prefix is the first 32 hex of that `scope_id`;
- each site's local `+` TSS, genomic point/strand, context and coordinate state count;
- the selected state's complete `(d, s)`, state ID, finite terms/log score, score status and its local/oriented/genomic intervals;
- status/reason/attempted consistency: unattempted sites are `failed`/`deadline_exceeded`, `no_candidate` sites are attempted, and `nonfinite_arithmetic` needs an eligible state;
- an `ok` relative score that is finite and at least the smallest normal binary64 (never zero, negative or subnormal);
- record-status precedence and exact coverage, with the truncation reason drawn from actual failed sites;
- for an empty scan, preflight `no_candidate` with exactly `reasons:["empty_scan"]`, `errors:[]`, the recomputed `prediction_id`, zero counts, true completeness and null truncation, whatever the batch clock. A `failed` zero-site record is rejected.

`invalid_input` and `unsupported` records need empty `sites`, null
`prediction_id`, `coverage` and `metadata`, and each non-null `calibration`,
`scan` or `projection` must equal the planned value. Their `input` object must
be complete. A planned sequence is a valid uppercase ACGT string within limits,
so the public rules leave no null raw hash or normalization triplet for it. Any
disagreement rejects the whole collection.
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
  --public-contract-commit P --wheel-sha256 W --identity-model IDENTITY_MODEL.json \
  --expected-model MODEL.json --runtime-limits LIMITS.json \
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
- independently built scope/prediction/site IDs: record ID and metadata excluded; scan/output change only `prediction_id`; host, taxon, projection, model and sequence change both; ASCII escaping and the full 64-hex scope digest;
- effective field, packing, deadline and result-byte limits;
- schema validity of every generated request;
- metrics integration on synthetic labels.

## Validation scope

This adapter validates the native-grid selected-state interface. It accepts
omitted zero entries in `status_counts` and checks `truncation.attempted_sites`
against the number of sites marked `attempted:true`. Rejected records may have
null calibration, scan or projection; any non-null value must match the plan.
Warnings must be a list, but warning objects are not interpreted or copied into
metrics. Runtime scoring, all-state parity and the runtime's own deadline
execution remain separate acceptance checks.

The independent synthetic regression in
[`test_promoter_native_v2_independent.py`](../../tests/benchmarks/test_promoter_native_v2_independent.py)
compares 1,000 fixed-seed complete-roster scenarios against exhaustive bipartite
matching. It checks primary and conditional recovery across ties, all eight raw
statuses, four top-k values and three tolerances without native outcomes.

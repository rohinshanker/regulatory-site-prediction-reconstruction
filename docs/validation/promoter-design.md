# Bounded Promoter design

- Purpose: Enumerate explicit substitutions toward caller-supplied historical Promoter log-score targets.
- Scope: Independently accepted original deterministic wrapper around the admitted predictor; no biological-performance or publication approval.
- Last verified: 2026-11-01

This uses the unchanged [historical Promoter model](promoter-model-card.md).
It does not recover the unavailable published/hosted optimizer, discover TSSs,
fit a model, infer host calibration or establish biological improvement. Scores
are natural logs of relative model scores, not measured transcription rates.
Every native warning and calibration/source identity remains visible.

## Request and constraints

`promoter-design-request-1` has exactly `schema_version`, `promoter`,
`target_log_scores`, `editable_positions`, `immutable_intervals`, `max_changes`
and `limits`. The nested `promoter` is one native `schema_version: "1.0"`
record, never a records/defaults envelope. Require explicit ID, sequence,
calibration, scan and output. Sequence is already uppercase ACGT, 1–1,000 bases.
Calibration is explicitly `ecoli_mg1655` or `in_vitro`; optional native host,
projection, model pin and metadata retain their original meaning. Output is
exactly `{"states":"selected","legacy_keys":false,"elements":true}`.

Scan is exactly `{"mode":"positions","positions":[...]}`, with 1–8 distinct
`{"strand":"+"|"-","tss":FORWARD_BASE}` entries in declared order. Each target
must have all 30 native states available before any predictor call: oriented
TSS `t` is the forward base on `+`, or `length-1-forward_base` on `-`, with
`t >= 67` and `t+20 <= length`. `target_log_scores` has the same length/order;
each finite number lies in [-1e6,1e6]. Booleans are not numeric settings.

The **complete-context admission window** is `[t-67,t+20)` in target orientation,
mapped to forward input half-open bounds on minus strands. Editable positions
are distinct input indices in the union of these windows, sorted canonically
for enumeration. Membership does not imply that a base affects the score:
neutral edits, including native unused ITR positions, remain ordinary candidates.
No feature-read mask or causal/regulatory interpretation is introduced.

`immutable_intervals` is an explicit list of nonempty input half-open intervals,
sorted by start, nonoverlapping and within sequence bounds. Adjacent intervals
are allowed; an empty list is explicit. Editable bases cannot intersect any
interval. All unlisted bases stay fixed. Users must explicitly lock any coding
bases they intend to preserve; no coding/assembly annotation is inferred.
No insertion/deletion, base normalization or hidden edit pruning is performed.

`max_changes` is an integer 0..min(2, editable count). Integer-valued JSON
numbers, including integral float spellings, follow native integer semantics;
booleans are excluded. Enumeration order is seed, increasing change count,
lexicographic combinations of sorted positions, then A/C/G/T replacement
products excluding each original base. Entire size is
`sum(comb(n,k)*3**k for k in range(max_changes+1))`; it must fit the declared cap.
There is no sampling, randomness, adaptive search or retry.

Limits have exactly `max_candidates` (integer 1–64), `seconds_per_candidate`
(finite >0, <=10) and `seconds_total` (finite >0, <=120). Pure native validation
and the complete search roster are prepared before scoring, without a predictor
validation call. Every candidate and confirmation uses the same float native
`seconds_per_record` and `seconds_per_batch`, both equal to declared
`seconds_per_candidate`; the remaining outer allowance never changes identity.
The outer monotonic deadline starts before preflight and controls admission.
Late completed outcomes are retained and mark the wrapper partial. This is a
cooperative budget, not a hard process timeout or strict end-to-end bound.

## Rows, ranking and confirmation

Every planned candidate is retained in order with index, candidate identity,
canonical DNA/hash, exact edits, native request/hash, attempt/status/reason,
native whole-envelope bytes/hash/admission flag, observed log-score vector,
absolute-error vector and objective or null. Each edit reports input position,
original/replacement bases and its oriented position/bases for every nominated
target. Mapping a base into a target orientation does not assert score influence.

Native admission checks model, calibration, input and batch/prediction/site/state
identities, exact target roster/order, complete-context/coordinate relationships,
selected output shape, finite score/log semantics and coverage/status consistency.
All-target success is required for ranking. Partial target success, ordinary
failures, unsupported/no-candidate outcomes and nulls are never zero-filled.
Failure statuses do not excuse model, request, roster or context contradictions.
Contradictions or predictor exceptions retain bounded evidence and stop further
admission, including confirmation. A bounded rejected object may remain opaque
failure evidence with `native_admitted: false`; its presence is not acceptance.
Non-object/oversized evidence has null payload and an exact pretty-JSON hash
when serialization permits. Nonfinite/unserializable evidence has null hash.

For a fully successful vector, objective is
`math.fsum(abs(observed[i]-target[i]) for i in range(n))/n`. An unrepresentable
objective is an explicit failure, never a rankable infinity. Rank by objective,
edit count, then lexicographic canonical input DNA. The best observed success
is a **proposal**. Recheck all sequence/edit/immutable/context constraints and
call the unchanged predictor freshly with identical declared settings. Verified
selection requires an admitted successful confirmation with the exact same
complete native-envelope hash. Failed, unstarted or mismatched confirmation
leaves selection null; never try an alternate proposal afterward.

`complete` means every candidate succeeded, confirmation matched and no outer
overrun occurred. `partial` has at least one observed success but some failure,
unstarted candidate, unsuccessful confirmation or overrun. `no_candidate` has
no fully successful candidate, including zero starts. `invalid_input` has no
admitted search roster. Coverage uses these exact counts:

| Field | Meaning |
| --- | --- |
| `planned` | Complete enumerated candidate count. |
| `attempted` | Candidates whose predictor call started. |
| `successful` | Candidates with admitted all-target success and a finite objective. |
| `failed` | `attempted - successful`, including admitted non-success outcomes. |
| `not_run` | `planned - attempted`. |
| `prediction_calls` | `attempted` plus one if fresh confirmation was attempted. |
| `all_candidates_scored` | `successful == planned`. |

Coverage also records outer deadline status and stop reason. A selection from incomplete
coverage is only the best verified observed success. Even complete enumeration
does not imply reaching the target or a global/biological optimum.

## Exact identities and result shape

Canonical hashes use SHA256 over sorted compact JSON, `ensure_ascii=True`,
`allow_nan=False`, UTF-8 and no newline. Only actual JSON types are admitted;
duplicate keys and nonfinite tokens are rejected. The validated request is
cloned, retaining supplied JSON number representation and editable-list order.
Canonical enumeration order is reported separately in `constraints`.

- `request_sha256`: canonical hash of that complete original parsed request.
- `algorithm`: exactly `id: "bounded-promoter-substitution-enumeration-1"` and
  `implementation_version` equal to the installed package version.
- `model`: the unchanged full native model object; `model_identity` is the native
  six-key identity (`id`, `implementation_version`, `parameter_json_sha256`,
  `coefficient_array_sha256`, `intercept_array_sha256`, `source_commit`).
- `design_id`: canonical hash of exactly `request_sha256`, `algorithm`,
  `model_identity`, resolved `targets` and resolved `limits`. Each target has
  index, strand, forward/oriented bases, target log score and input-coordinate
  `admission_interval`. Limits resolve integers to int and seconds to float.
- `sequence_sha256`: SHA256 of canonical uppercase DNA bytes.
- `candidate_id`: canonical hash of exactly `design_id`, `index` and
  `sequence_sha256`.
- `native_request_sha256`: canonical hash of the complete candidate native
  request; that object is retained. Native prediction/batch IDs keep their
  existing definitions and fixed per-call budget.
- `native_sha256`: SHA256 of the complete authoritative native envelope encoded
  with sorted keys, indent 2, ASCII escaping, finite numbers and a final LF.
  `native_bytes` records that byte length when serializable.
- `result_sha256`: canonical hash of the entire wrapper result excluding only
  itself. It includes elapsed time; stable design IDs need not imply identical
  wrapper result hashes between executions. Elapsed time ends at the final
  admission/confirmation decision, before wrapper hashing and serialization.

The result has exactly `schema_version`, `algorithm`, `model`, `model_identity`,
`request`, `request_sha256`, `design_id`, `targets`, `constraints`, `limits`,
`status`, `reason`, `coverage`, `candidates`, `proposal`, `confirmation`,
`selected`, `elapsed_seconds`, `warnings` and `result_sha256`. Request/result
schemas describe structure; runtime also enforces identity/count/coordinate
relationships. Invalid/setup/transport refusals use null request/model/design/
coverage/constraints/limits, empty targets/candidates and null proposal/
confirmation/selection, with stable concise reason codes and a result hash.

## Transport and verification

Raw and canonical request bytes each have an inclusive 65,536-byte cap. A native
retained envelope has a 131,072-byte authoritative pretty-JSON cap. The complete
wrapper has an inclusive 16,777,216-byte authoritative pretty-JSON cap. The JSON
CLI fully serializes before stdout; serialization/limit failure emits a bounded
typed refusal, or no prefix if even that refusal cannot fit. Binary stdin uses
`-`; file input must be regular and must not follow the final symlink. No output
file mode or external result importer. CLI exits are 0 complete, 1 partial/
no-candidate, 2 invalid/setup/transport, including output/write/flush failures.
Initial invocation is `python -m regsite.promoter_design_cli REQUEST`; A owns
later installed entry-point/package/README/CI integration.

Required focused checks cover independent enumeration/ranking/strand/immutable
invariants, admission boundaries and neutral edits, direct unchanged native
equality/fresh confirmation, every failure and unstarted denominator, fixed
native budgets and late outcomes, native contradictions, schemas, exact bytes,
stdin/files/no-follow/output errors, and full new statement/branch coverage.
Use only small original artificial inputs; no source retrieval, folding,
biological dataset, fitting or private benchmark. Independent exact-patch review
belongs to A; self-tests are engineering evidence, not scientific acceptance.
The accepted implementation at `87510bdfd53099b7fbbec174305ca676fdf66c46`
passed independent unchanged-predictor comparisons, including the 64-candidate,
eight-target bound, both strands, invalid requests and file transport.

Run the original example from a source checkout with `PYTHONPATH=src python -m
regsite.promoter_design_cli examples/promoter-design-single.json`. Focused tests
are `tests/test_promoter_design*.py`; isolate their pytest configuration with
`--noconftest`, disable plugin autoload and explicitly enable `pytest_cov` for
coverage of the three new modules. Keep coverage, pytest cache and basetemp
outside the checkout. Ruff check/format and mypy apply to these modules; schemas
resolve only against the checked-in native schemas, without network retrieval.

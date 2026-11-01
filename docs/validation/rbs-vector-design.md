# Bounded multi-target RBS design

- Purpose: Search explicitly allowed noncoding substitutions against several RBS model targets on one supplied sequence.
- Scope: Original enumeration wrapper of admitted component predictors; no new biological model, operon inference or calibration.
- Last verified: 2026-11-01

Contract frozen; implementation gates are pending.

## Input and coordinate contract

`rbs-vector-design-request-1` has exactly `schema_version`, `rbs`, `profile`,
`cds`, `target_tirs`, `editable_positions`, `max_changes` and `limits`.
`rbs` is one native RBS1.0 request with canonical uppercase ACGT DNA of
1–10,000 bases, explicit supported profile, anti-SD, host/temperature and strand
semantics from [the unchanged predictor](rbs-runtime.md). Optional native
metadata/defaults retain their native meaning; a host label is not calibration.
No scan or automatic start selection is allowed.

`cds` contains 1–10 objects with exactly `id`, `start`, `end`. IDs are unique,
1–128 characters without controls. Coordinates are genuine integer **oriented
transcript** indices, zero-based and half-open: `0 < start`,
`start+3 <= end <= length`, `(end-start) % 3 == 0`. Starts strictly increase.
Each nominated start codon must be supported by the native predictor, including
CUG. The exact native `start_positions` list equals these starts and contains
genuine integers. Overlapping coding intervals are allowed and their entire
union is immutable. No ORF, stop-codon, gene identity or annotation correctness
is inferred. All targets share the declared strand; opposite-strand genes need
separate requests.

`target_tirs` is an aligned list of finite positive JSON numbers, booleans
excluded, no larger than the maximum finite binary64 value. Resolved targets
retain CDS IDs, oriented intervals, corresponding ascending input intervals,
float target TIR and natural-log target TIR. They describe native relative
initiation scores, not protein abundance, expression ratios or measured rates.

`editable_positions` is a list of distinct genuine integer indices in the
supplied DNA orientation. Minus-strand oriented index is `length-1-input_index`.
An edit must lie in at least one nominated upstream window
`[max(0,start-profile.upstream_nt),start)` and outside **every** coding interval.
An upstream window may overlap another coding region; that region stays locked.
All unlisted bases are immutable. No insertion/deletion, inferred synonymous
recoding, sequence-risk filter or hidden pruning is performed.

`max_changes` is a genuine integer from0 to min(2,number of editable positions).
Enumerate seed, increasing edit count, lexicographic combinations of sorted input
positions and A/C/G/T replacement letters excluding the seed letter. The full
count is sum(comb(n,k)*3**k). Refuse before scoring if that count exceeds the
caller cap. Do not sample a larger space.

`limits` has exactly `max_candidates` (integer1–64), `seconds_per_score`
(finite positive number <=30) and `seconds_total` (finite positive number <=600).
The complete request, including original parsed number representations, remains
in output. Raw and canonical request limits are65,536bytes. Booleans are not
numeric controls; unknown fields, duplicate JSON keys, invalid UTF-8/nonfinite
JSON and noncanonical DNA are rejected. The shared strict JSON transport is
`regsite.design_io`; its schema names do not alter these common byte rules.

## Native scoring and validation

Each started candidate makes one unchanged native `rbs.predict` call containing
**all** nominated starts and the whole candidate sequence. Shared folding context
therefore changes wherever an allowed substitution affects any target. This does
not add translational coupling, drafting, elongation, decay, termination or a
joint protein-abundance model. The explicit native profile remains visible.

The declared native `seconds` is always the same float `seconds_per_score`;
`execution_seconds` may shorten it to the remaining whole budget. The whole
cooperative deadline starts before preflight. It is an admission/execution limit,
not an OS wall-time or memory quota. Once a native call returns, preserve its
late result and mark deadline overrun. Do not retry or launch another call after
an observed deadline or integrity contradiction. Unstarted candidates remain.

Before and after each call, require unchanged backend identity. Require the
complete expected native model object, schema, ID, normalized/oriented input
provenance and original prediction ID (including declared budget). Model identity
is derived from the existing profile and native source/parameter constants;
no prediction call is used as validation or parameter discovery. Validate the
exact start roster/order, native record/site status precedence, null/reason
semantics, start codons and scoring-window coordinates. For each success require
finite positive TIR and finite consistent log TIR. Preserve full native results,
including structures, energy terms, warnings and valid mixed failures; the
wrapper does not independently rescore those thermodynamic terms.

A valid failed native record may have no sites and a nonempty record reason
(e.g. session setup failure). All requested targets then remain `not_evaluated`
with that reason. A record containing sites must contain every requested start,
retain record reason null and use native precedence failed, unsupported,
no_candidate, ok. Successful sites in a mixed record keep their values and
per-target errors, but the candidate is not ranked. Invalid model/roster/shape/
coordinate/score identity stops further admission. Ordinary admitted native
failed/unsupported/no-candidate outcomes do not stop successful siblings or later
candidates. A thrown backend/OS/Unicode execution error is an attempted failure;
no fallback model is used.

Native authoritative bytes are `json.dumps(sort_keys=True,indent=2,
ensure_ascii=True,allow_nan=False)` plus one LF, encoded ASCII. Retain at most
524,288 bytes per native envelope, accounting also for six additional indentation
spaces per native line when nested. Compute the full authoritative byte count
and hash where serializable; an over-cap payload is omitted, its identity is
retained, and the integrity stop is explicit. This is bounded direct producer
output handling, not an external JSON importer.

## Objective, confirmation and result

A candidate is rankable only if all target sites succeeded. Objective is
`math.fsum(abs(observed_log_tir-target_log_tir))/number_of_targets`.
Rank by objective, edit count, then canonical DNA. Individual target status,
reason, TIR/log TIR and error are retained, including partial native vectors.
No missing or failed value becomes zero. This scalar is an explicit design
objective, not an expression-combination equation.

The best fully successful candidate is a proposal. Independently recheck its
entire sequence, allowed edit positions and every coding interval, then make one
fresh call with identical declared settings. Select only after exact native
whole-JSON byte-hash agreement and successful all-target confirmation within the
whole deadline. Failed, mismatched or unstarted confirmation leaves the proposal
visible with no selection; do not try an alternate candidate.

Top-level `rbs-vector-design-result-1` fields are exactly `schema_version`,
`status`, `reason`, `algorithm`, `request`, `request_sha256`, `design_id`, `backend`,
`model`, `targets`, `constraints`, `limits`, `coverage`, `candidates`, `proposal`,
`selected`, `confirmation`, `warnings`, `result_sha256`.

Algorithm is `{id:"bounded-rbs-vector-substitution-enumeration-1",
implementation_version:package version}`. Constraints contain sorted
`editable_positions`, `max_changes`, and the complete `coding_intervals`
(oriented `[start,end]` arrays, including overlaps). Limits retain resolved float
budgets, declared candidate cap and effective input/native/output byte caps.
No elapsed time or clock timestamp enters an otherwise deterministic result.

Each candidate contains `index`, `candidate_id`, `sequence`, `sequence_sha256`,
`edits` (`input_position`, `oriented_position`, `from`, `to`), `attempted`, `status`,
`reason`, `native_request`, `native_request_sha256`, `native`, `native_json_sha256`,
`native_bytes`, `native_admitted`, `targets` and `objective`. Each target result
contains `id`, `oriented_start`, `status`, `reason`, `tir`, `log_tir`,
`absolute_log_error`. Unstarted or unadmitted target results are explicit
`not_evaluated` with null scalars. Native-admitted non-success targets retain
the native status/reason. No target disappears from the requested denominator.

Proposal and selected objects contain `index`, `candidate_id`, `sequence`,
`sequence_sha256`, `edits`, `targets`, `objective`. Confirmation contains
`candidate_index`, `attempted`, `status` (`not_run`, `verified`, `failed`), `reason`,
`native`, `native_json_sha256`, `native_bytes`, `native_admitted`, `targets`,
`objective`. Confirmation is null only when there is no successful proposal.

Coverage contains `planned`, `attempted`, `successful`, `failed` (=attempted minus
successful), `not_run` (=planned minus attempted), `prediction_calls` (including
any confirmation), `all_candidates_scored` (=successful equals planned),
`deadline_exceeded`, and first `stop_reason` or null. `complete` requires every
candidate successful, selected confirmation and no deadline overrun. `partial`
has a successful proposal but incomplete/failed coverage or confirmation;
`no_candidate` has no fully successful candidate, including zero starts.
`invalid_input` has null request/model/backend/identity/constraints/limits/coverage,
empty targets/candidates and null proposal/selected/confirmation; its reason is
nonempty. Noncomplete reasons remain explicit. A completed search need not meet
any target, and partial coverage cannot establish a whole-neighborhood optimum.

Hashes use sorted-key compact finite ASCII JSON with separators `(',',':')`, no
LF, except the explicitly authoritative native JSON hash. `request_sha256`
hashes the original parsed request. `design_id` hashes exactly
`{request_sha256,algorithm,backend,model,targets,limits}`. `candidate_id` hashes
`{design_id,index,sequence_sha256}`. DNA hashes use exact ASCII sequence bytes;
`native_request_sha256` hashes the exact native request. `result_sha256` hashes
the complete result without that field. The original native prediction ID is
unchanged. Original number spelling/whitespace beyond parsed JSON is not retained.

## CLI and acceptance gates

The module CLI accepts one request file or binary stdin, optional explicit
`--backend-root` (or existing `REGSITE_RNASTRUCTURE`). File input is regular and
final-component no-follow; FIFO/directory/symlink inputs fail. Preflight precedes
backend opening; unavailable setup returns a typed refusal. Serialize the whole
result before stdout under the existing67,108,864-byte cap. Oversize/nonfinite
output becomes a small typed refusal; if even that cannot serialize, emit no
prefix and fail. Broken pipe/write/flush handling retains exit2. Exit0 is complete,
1 partial/no-candidate,2 invalid/setup/transport. No native binaries are bundled.

Tests must cover independent Cartesian rosters/order/ranking, all five profiles,
both strands, overlapping CDS locks/shared windows, identity/status/geometry
contradictions, partial native vectors, every deadline/confirmation path and all
numeric/byte/transport boundaries, with full new statement/branch coverage.
Use real artificial two-start native controls without experimental outcomes.
Independent review and A's installed/platform gates follow the exact committed
implementation. Keep full scientific/reference artifacts external and retain
all existing source/provider/private/consumer/publication holds.

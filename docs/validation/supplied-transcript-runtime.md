# Supplied-transcript library runtime

This document specifies the emitted `supplied-transcript-result-1` object from
`regsite.transcript.predict_transcript(document, backend=None)`. The request
contract is [supplied-transcript-contract.md](supplied-transcript-contract.md),
with the coordinator's explicit incompatible-start reason clarification below.
The library adds no scientific model or dependencies. The source-admission
limits in [operon-riboswitch-source-admission.md](operon-riboswitch-source-admission.md)
remain applicable.

The caller passes a parsed JSON object and, when any CDS is eligible, a previously
verified `RnaStructure.open(...)` instance. Invalid organization/settings and
setup, native-integrity or output-size failures raise `TranscriptError` without
returning a partial result. The caller's parser must reject duplicate keys,
invalid UTF-8, nonfinite JSON and received input above 1,000,000 bytes before
calling the library. A parsed object cannot retain duplicate keys or received
whitespace; these checks cannot be reconstructed by the library. The library
independently rejects non-JSON Python values, invalid UTF-8 strings, nonfinite
numbers and oversized canonical input. Root depth is zero; object keys and values,
and array elements, each count as nodes one level below their container. Limits
are depth 16, 20,000 nodes and 1,000,000 canonical bytes.
Projection `origin` and `contig_length` must have genuine integer types before
either predictor runs; integral floats and booleans are rejected, without
normalization or coercion.

## Execution and missingness

The native RBS request uses fixed ID `transcript-rbs`, exactly the DNA slice
`sequence[u:v]` (the RBS API performs its declared DNA-to-RNA normalization), `+`
strand, and all eligible transcript offsets in one shared record. The full
construct never supplies additional RNA context. Eligibility requires only
`u <= s` and `s+3 <= v`; annotation ends may extend beyond the transcript.
A CDS with an eligible start and end beyond `v` has warning `downstream_clipped`.
Incompatible CDSs retain their entire annotation and signed `s-u` offset, status
`incompatible_transcript`, and one ordered reason:

- `start_before_transcript` when `s < u`;
- `start_after_transcript` when `s >= v`;
- `start_codon_after_transcript` otherwise.

No eligible CDS means RBS `not_applicable` / `no_eligible_cds`, even if the whole
execution deadline has expired. No backend is required for that case. Otherwise,
a backend must be supplied before either component can score. An unavailable or
unverified backend is a setup error; it does not trigger a fallback model.

RBS runs first, followed by the public Promoter batch API with one record, fixed
ID `transcript-promoter`, full construct sequence, explicit calibration/host/scan,
and output `{states:"selected",legacy_keys:false,elements:true}`. A null host is
omitted in the native Promoter request; an absent taxon ID stays absent. Both
scan strands are independent of the supplied transcript. No predictor selects
or changes the transcript.

The whole deadline starts at library entry. Each started component retains its
fixed requested budget as `declared_seconds`, and native identities retain those
same declared record/batch budgets. The component's actual absolute deadline is
`min(whole_deadline, component_call_time + declared_seconds)`. RBS receives a
separate execution allowance of
`min(declared_seconds, remaining_whole_seconds)`; a delegating backend also caps
the native folding session's absolute deadline at the component deadline.
Native subprocess creation checks that deadline. Promoter's first batch clock
read returns `component_deadline - declared_seconds`; its native batch then adds
the unchanged declared allowance to obtain the actual deadline. Subsequent reads
use the real monotonic clock. Native preparation consumes the same execution
allowance. Execution is serial, with no retry.

Actual timestamps and remaining allowances are internal execution controls, not
result fields or identity settings. Identical successful requests therefore have
identical complete-result hashes even if their total budget is below the declared
component budgets and scheduling changes the remaining time. Native results are
retained in full; the complete-result hash excludes only `prediction_sha256`.

An unstarted component is `not_evaluated` / `deadline_exceeded`, retains its
request and roster and has null `prediction` and `declared_seconds`. This rule
also applies to an unstarted empty Promoter scan. A started empty scan instead
retains the real native `no_candidate` result. Already completed components do
not retroactively fail. Native RBS failures, unsupported starts, leaderless starts,
no-binding candidates, and successful siblings remain in the native result.
Missing sites after a native failure become per-candidate `not_evaluated` /
`missing_native_site`; the component retains its native failure reason. Native
Promoter sites with `attempted:false` become per-candidate `not_evaluated` with
their native reason. No missing value becomes zero.

Deadlines are cooperative execution limits between native operations, not an OS
wall-time or memory quota. Backend verification happens in the caller before
entry. Input checking, parameter loading, serialization and result integrity work
may finish after an execution deadline; they cannot start another folding process.

## Exact JSON shape

The following lists every wrapper-owned field. `NativeRbsResult` and
`NativePromoterBatch` mean the complete original component objects under their
existing public contracts, without per-CDS payload duplication. Lists below are
JSON arrays even when Python uses tuples for the Promoter roster.

```text
Result = {
  schema_version: "supplied-transcript-result-1",
  id: request.id,
  implementation_version: package version,
  status: "complete" | "partial" | "unavailable",
  request_sha256: hex SHA-256,
  prediction_sha256: hex SHA-256,
  request: original parsed request (including original numeric JSON types),
  settings: {
    seconds_per_rbs_record: float,
    seconds_per_promoter_record: float,
    seconds_total: float
  },
  limits: WrapperLimits plus {predictors: {rbs: RbsLimits, promoter: native LIMITS}},
  identities: {
    rbs: {
      profile: {name, model_id, upstream_nt, downstream_nt, footprint_nt},
      source_commit: pinned native RBS source commit,
      base_parameters: complete native MODEL_PARAMETERS,
      standby_parameters: complete native STANDBY_PARAMETERS,
      joint_parameters: complete native JOINT_PARAMETERS,
      backend: complete supplied backend.identity | null
    },
    promoter: {
      model: complete public promoter_io.model_identity(params)[0],
      calibration: {profile, K, beta, native_host, host, host_status, warnings}
    }
  },
  transcript: {
    annotation: original transcript annotation,
    sequence: sequence[u:v] as DNA,
    sequence_sha256: SHA-256 of that ASCII DNA slice,
    coordinates: Feature in construct coordinates
  },
  components: {
    rbs: Component with roster [transcript_offset, ...],
    promoter: Component with roster [[strand, construct_tss], ...]
  },
  cds: [Cds, ...],
  promoter_candidates: [PromoterCandidate, ...],
  coverage: {cds, eligible_cds, incompatible_cds, scored, complete},
  unsupported_capabilities: [
    "coupling", "elongation", "decay_stability", "termination",
    "native_operon_discovery", "joint_protein_abundance"
  ],
  warnings: [
    "component_scores_do_not_estimate_joint_protein_abundance",
    "supplied_annotations_are_not_independently_verified"
  ]
}
Component = {
  request: exact native request,
  roster: declared candidate roster,
  status: native record status | "not_evaluated" | "not_applicable",
  reason: native record reason/first native reason | wrapper reason | null,
  declared_seconds: requested component allowance float | null if never started,
  prediction: NativeRbsResult | NativePromoterBatch | null,
  coverage: {requested, returned, scored, not_evaluated, missing,
             incompatible (RBS only)}
}
Cds = {
  annotation: original CDS annotation,
  transcript_offset: signed integer s-u,
  eligible: boolean,
  warnings: [] | ["downstream_clipped"],
  annotation_coordinates: Feature in construct coordinates,
  site_index: index into components.rbs.prediction.sites | null,
  status: native site status | "not_evaluated" | "incompatible_transcript",
  reason: native site reason | wrapper reason | null,
  scalars: {scalar_name: Scalar, ...},
  features: {feature_name: Feature, ...}
}
PromoterCandidate = {
  strand: "+" | "-", construct_tss: integer,
  site_index: index into components.promoter.prediction.results[0].sites | null,
  status: native site status | "not_evaluated",
  reason: native site reason | wrapper reason | null,
  scalars: {scalar_name: Scalar, ...},
  features: {feature_name: Feature, ...}
}
Scalar = {value: finite number | null, unit: string, reason: string | null}
Feature = {
  native_interval: [a,b] | null,
  construct_interval: [a+offset,b+offset] | null,
  local_strand: "+" | "-",
  genomic: {contig, strand, runs: [[a,b], ...]} | null,
  reason: "feature_unavailable" | null
}
```

`identities.rbs` records the source parameter families even when a component was
not run. Only the explicit profile activates mechanisms; the native model object
retains the exact effective profile parameter representation for executed calls.
The calibration identity includes warnings, whereas the native record's public
calibration dictionary keeps warnings separately. Native backend/model,
RBS normalized input/provenance, and Promoter input hash/length, scan, calibration
and projection are checked against the declared calls before export.

`complete` means both component records finished with `ok` or `no_candidate`
(and no incompatible CDS), not that every candidate produced a score. Otherwise,
the wrapper is `partial` if at least one native site scored, or `unavailable`.
`coverage.scored` counts successful RBS and Promoter sites; it is not a joint
score. Component `missing` counts requested sites with null `site_index`;
`not_evaluated` counts per-candidate status independently. RBS counts exclude
incompatible CDSs except its explicit `incompatible` count. Returned native sites
remain in original order and every wrapper candidate points to that order.
Duplicate/unrequested native anchors, missing sites in a successful native
record, missing essential native fields, or contradictory coordinates/scores
raise `TranscriptError`.

RBS scalar keys are `tir`, `log_tir`, and every name in the runtime's public
`RBS_ENERGIES` list. Energy units are `kcal/mol`; TIR units are
`relative_initiation_score` and `ln_relative_initiation_score`. Promoter scalar
keys are `relative_transcription_score`, `log_relative_transcription_score` and
all names in `PROMOTER_TERMS`; their units are `relative_transcription_score`,
`ln_relative_transcription_score`, or the native `TERMS_UNIT`. All these keys
are present for missing/failed candidates too. Null values carry the native or
wrapper missingness reason, or `value_unavailable` for absent optional terms.
Non-null values have null reason. Native underflow/overflow reasons remain
explicit, and finite log scores can coexist with null relative scores.

A returned RBS site exports `start_codon`, `window`, `binding_interval`,
`standby_interval`, `coding_footprint`, `standby.original_hairpin`,
`standby.hairpin`, `standby.distal`, `standby.proximal`, and each present
`standby.downstream_hairpins.<index>`. `window` uses its native `input_interval`;
CT and cofold indices are not silently interpreted as construct coordinates.
Promoter exports `tss` plus `UP`, `gap`, `hex35`, `spacer`, `extended10`, `hex10`,
`discriminator`, `itr` from the selected model state. Selected windows and
orientation are checked with the public native geometry helpers. A missing site
has `{}` features. A returned site with a missing feature retains a null interval
and `feature_unavailable`. Half-open intervals are checked against their native
frame before any offset. Empty `[a,a)` intervals retain the exact boundary and
have zero genomic runs, including `[length,length)`; null stays distinct from
empty. Genomic runs use public `project_interval`, in site transcription order.
The RNA remains linear on a circular genomic projection.

## Identities and limits

`request_sha256` hashes the original parsed request with
`json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)`
encoded as ASCII, with no newline. `prediction_sha256` hashes the entire emitted
result with only that field omitted, using the same canonical representation.
Input integer/float distinctions therefore remain bound. Native component hashes
and identities stay intact inside their full results. Consumer scalar/export
rows must bind `prediction_sha256` to identify their complete JSON; transport and
comparative row formatting belong to the integrating interface.

`result_bytes` implements
`json.dumps(sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False) + "\n"`,
ASCII encoded. `predict_transcript` checks this complete representation, including
its final LF, against 33,554,432 bytes before returning. Equality is permitted.
The public serializer itself only serializes; callers exporting modified or
received result objects must independently enforce the same size cap.

The exact wrapper limits are:

```json
{
  "max_input_json_bytes": 1000000,
  "max_json_depth": 16,
  "max_json_nodes": 20000,
  "max_bases": 5000,
  "max_cds": 10,
  "max_promoter_sites": 512,
  "max_seconds_per_component": 120.0,
  "max_seconds_total": 240.0,
  "max_result_json_bytes": 33554432
}
```

The additional `limits.predictors.rbs` fields are
`max_normalized_bases_per_record:10000`,
`max_explicit_or_scanned_starts:1000`, `max_seconds_per_record:120.0`.
`limits.predictors.promoter` is the complete unchanged native effective limits
object. These are ceilings, not measured performance or admission claims.
Complete deterministic executions have stable wrapper identities; reduced
execution allowances alone do not change them. Deadline-dependent missingness
can change a result and its identity. A `not_applicable` RBS component never
starts, so its `declared_seconds` also remains null; the requested budget is
still preserved in `request.settings` and resolved `settings`.

## Focused verification and remaining integration

The owned tests cover the real public predictors with deterministic synthetic
structure sessions, all admitted profiles, full 10-CDS shared requests, malformed
input before scoring, unsupported and missing sites, successful siblings,
leaderless/short-leader/end-boundary starts, overlapping and clipped annotations,
all incompatible reasons, forward/reverse/circular projections, empty/null
features, native corruption, serial shortened budgets, absolute subprocess
blocking, preparation time, and unstarted empty-scan precedence. The
reproducibility checks compare the entire result and recompute its full hash
across different monotonic schedules with total budgets below component budgets.
Projection type checks reject floats and booleans atomically. Logarithmic
Promoter scalar units are checked for successful, no-candidate, unstarted and
deadline-failed sites. The bounded real integration test executes one RBS request,
serially, with the caller's pinned
backend and checks a positive native score plus real Promoter results.

Run from the worktree with `PYTHONPATH=src:.` and the assigned test Python:

```sh
python -m ruff check src/regsite/transcript.py src/regsite/transcript_geometry.py tests/test_transcript.py tests/test_transcript_geometry.py
python -m ruff format --check src/regsite/transcript.py src/regsite/transcript_geometry.py tests/test_transcript.py tests/test_transcript_geometry.py
python -m mypy src/regsite/transcript.py src/regsite/transcript_geometry.py
REGSITE_RNASTRUCTURE=/path/to/verified/RNAstructure python -m pytest tests/test_transcript.py tests/test_transcript_geometry.py --cov=regsite.transcript --cov=regsite.transcript_geometry --cov-report=term-missing
```

The coordinator owns CLI/parser/export, schemas, examples, shared package/CI,
fresh-install/resource admission, independent B fixture integration, ticket
updates and exact-patch review. This library document does not claim those gates
or scientific accuracy passed. No fitting, discovery, abundance calculation,
canonical/cyano edit, publication or dependency change is part of this slice.

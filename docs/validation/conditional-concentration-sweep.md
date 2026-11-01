# Conditional concentration sweep

- Purpose: Compare explicit ligand-total concentrations under one unchanged supplied-energy model.
- Scope: Bounded local orchestration of the existing conditional scalar component, without new inference or source admission.
- Last verified: 2026-10-31
- State: Implemented with focused tests and offline scalar CLI smoke; independent review and package/platform gates pending.

## Scientific boundary

Reuse the admitted [conditional model](conditional-aptamer-contract.md) and its
[source/parameter provenance](conditional-aptamer-runtime.md). The existing
`supplied_energy_response` implementation supplies every equation and numerical
convention. This wrapper introduces no fitted coefficients or alternative
occupancy law. Only `published2015_volume` occupancy is admitted: a supplied
fraction contains no concentration model to sweep.

Each point changes exactly `input.occupancy.ligand_total_molar`. The caller's
energies, affinity, RNA amount, solvent concentration, relative volumes,
temperature, beta, provenance and numerical settings remain fixed. The model's
ratio direction stays ON/OFF. Its supplied affinity/standard state need not equal
its effective half-response concentration. This is a conditional response under
assumptions, not a measured dose-response or a sequence-to-switch predictor.
No aptamer, affinity, cellular concentration, host or bound state is inferred.

## Request and complete roster

`conditional-sweep-request-1` contains exactly `schema_version`, `template`,
`ligand_total_molar` and `seconds_total`. The template is a complete admitted
`conditional-aptamer-request-1` supplied-energy/volume request. Its single original
ligand amount is explicitly replaced at every requested point; it is not inserted
as an additional baseline. Validate the whole template and point list before any
prediction. Reuse the component's pure validation rules; do not perform an extra
prediction as input validation.

The point list contains 1–64 finite nonnegative JSON numbers, excluding booleans.
Preserve supplied order and duplicate concentrations. Each index is a distinct
requested point; no sorting, interpolation, automatic logarithmic grid, adaptive
sampling or retry. Resolve point concentrations to finite floats and preserve the
complete raw parsed request separately. Zero ligand and zero RNA retain the
underlying model's distinct boundary semantics.

Total admission budget is finite and positive, at most 120 seconds. The template's
per-point `settings.seconds_total` stays unchanged (at most 30 seconds). Check the
outer clock before each call and after execution. This is a cooperative admission
deadline: a previously admitted point may run up to its declared native budget
past the outer deadline. No hard process/time guarantee is implied. A late final
point stays visible; the envelope is partial with `deadline_exceeded`, even if all
native points succeeded. Remaining points are explicit `not_run`. No subprocess
or folding backend is used by this supplied-energy mode.

## Result, identities and refusal

`conditional-sweep-result-1` retains algorithm/version, complete parsed request,
request hash, full expected native model, all planned point rows and coverage.
Each row binds its index, resolved mol/L concentration, exact generated native
request hash, attempted flag, status/reasons and complete native result or null.
Native JSON hashes use the unchanged authoritative conditional serializer, including
its final LF. Retain partial native response values and all warnings/errors; do
not convert nulls into zero or discard failed points.

Verify native request/model/profile/input/provenance/settings identity, status
and scalar-only result shape. An unexpected identity/shape or oversized native
record stops further admission, retaining every remaining row. Ordinary native
failed/no-mRNA/unsupported/invalid outcomes remain failures and do not silently
change the settings. An exception retains its explicit failure reason. The
selected concentration field is always the total ligand amount, never the solved
free ligand or complex amount.

Complete means all planned points succeeded within the cooperative admission
budget. Partial includes missing/failed/no-mRNA points or deadline overrun; invalid
input has no admitted roster. No best concentration, threshold, EC50 or prediction
interval is inferred. Inspect the native occupancy/response at each explicit point.

All canonical hashes are SHA256 over sorted-key compact ASCII finite JSON with
no newline. `request_sha256` binds the parsed sweep request. `sweep_id` hashes
exactly `{request,algorithm,model}`, where algorithm includes implementation version.
`result_sha256` binds the complete envelope excluding only that field, including
elapsed time. Repeated inputs can have stable sweep IDs and different result hashes.
Duplicate points intentionally share their generated request/native identities
when their native results match; their roster indices remain distinct.

Input is at most 65,536 received bytes and canonical parsed bytes. Each embedded
native result is bounded to 65,536 authoritative pretty bytes plus six bytes per
line for envelope indentation. An oversized record keeps its hash with null
payload when the authoritative native serializer returned bytes; rejection by that serializer's own cap has
no available native hash and also stops further points.
The complete authoritative envelope (sorted-key ASCII JSON, indent 2 plus final LF)
is capped at 8 MiB before stdout. Refusal never emits a selected/truncated prefix.
OS stream failures can still occur after a write begins. Binary stdin or regular
no-follow file input is supported. CLI exits are 0 complete, 1 partial, 2 invalid
input/setup/transport. JSON is the sole initial format; no job-runner, browser or
consumer admission is introduced.

## Required verification

Tests cover the complete roster and exact native-request substitution, unchanged
single-point result identity, duplicate/unsorted points, all input boundaries,
zero-ligand/no-RNA/repression cases, declared-model monotonicity and mass balance,
solver failure, native identity changes, retained nulls, before/during/final deadline
states and exact byte caps. Use independent analytic controls where applicable,
without treating generated values as experimental evidence. Every new runtime
statement/branch, CLI error and schema is covered. Finite independent review and
fresh offline installation precede acceptance; platform gates remain separate.

## Offline invocation

```sh
regsite-conditional-sweep examples/conditional-sweep.json > /absolute/external/curve.json
python -m regsite.conditional_sweep_cli examples/conditional-sweep.json
```

No folding installation or network is required. The committed artificial example
requests six concentrations, including zero. All concentrations are mol/L.
Structural contracts are [`conditional-sweep-request-1`](../../schemas/conditional-sweep-request-1.schema.json)
and [`conditional-sweep-result-1`](../../schemas/conditional-sweep-result-1.schema.json).
Resolve their native schema references from the same distribution; runtime requires
only the Python standard library. Inspect `points[index].native.response` and its
occupancy diagnostics, alongside each point's status/reasons and full provenance.
Do not infer unrequested concentrations or an experimental EC50 from this curve.

The pure native validation helpers are reused inside the same package so template
admission does not introduce a second numerical/model implementation. Tests compare
each generated point byte-for-byte with an independent direct native invocation
and verify the equal-volume zero-switching quadratic and its boundary behavior.
The focused library/CLI/schema tests require no native process and cover all new
runtime statements/branches. Exact source pins, review and fresh-install evidence
are required separately for a release candidate.

# Conditional concentration sweep

- Purpose: Compare explicit ligand-total concentrations under one unchanged supplied-energy model.
- Scope: Bounded local orchestration of the existing conditional scalar component, without new inference or source admission.
- Last verified: 2026-10-31
- State: Contract first; implementation and independent review pending.

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
line for envelope indentation. An oversized record keeps its hash with null payload.
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

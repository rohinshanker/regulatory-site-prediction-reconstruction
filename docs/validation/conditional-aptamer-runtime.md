# Conditional aptamer library contract

The library entry point is
`regsite.conditional.predict_conditional(document: object, backend_root: str | Path | None = None) -> dict`.
It accepts raw JSON-compatible objects and returns exactly the proposed
`conditional-aptamer-result-1` fields in `conditional-aptamer-contract.md`.
The transport may use `invalid_result(code="invalid_json", message="Invalid JSON")`
for malformed, nonfinite, duplicate-key or oversized wire JSON. This factory has
null request identity and validated fields. `result_bytes(result)` is the bounded
authoritative UTF-8 JSON serializer (sorted, ASCII escaped, two-space indentation,
one final LF). The transport must additionally enforce its 65,536-byte wire cap
and reject duplicate keys; the library enforces the same cap on compact canonical
reserialization. Result bytes are capped inclusively at 1,000,000.

Input fields and profile settings are exact, mandatory and have no defaults.
Settings seconds resolve to floats. `request_sha256` identifies the complete
original parsed finite request, before that resolution. Invalid subobjects remain
null; independently validated ID, profile, input, provenance and settings survive
other validation failures. Unsupported profiles/features have `unsupported` status.
Execution and numerical failures use `failed`; completed components survive with
dependent fields null. `complete` is true only for `ok`. No-mRNA occupancy reports
`no_mrna`, null fraction/response ratios and `complete=false`.

`response.metastability_factor` is the effective correction: one outside the
strict-positive branch, and the logistic factor within it. `metastability_applied`
identifies that branch. A failed solve retains its last finite bracket, residual
and iteration count; concentrations/fraction already solved survive a later
volume-fraction range failure. Such a result remains failed and incomplete.

The structural backend root is explicit or comes from `REGSITE_RNASTRUCTURE`.
Only the exact independently admitted original Fold/efn2 binary hashes and table
manifest are accepted. No version-check jobs are added: there are at most four
processes per request, sequential, without retries. Other platform builds require
independent fixture admission and a changed parameter identity. The library does
not accept the existing patched RBS backends by substitution.

The volume solver requires both relative bracket width
`(high-low)/min(mrna_total_molar,ligand_total_molar) <= 1e-12` and scaled stationary
residual `<= 1e-12`. This also bounds occupancy uncertainty. It uses at most the
explicit `max_iterations` (1–256), within `seconds_total` (at most 30 s).
An exact interior zero collapses the bracket. Boundary cases use zero iterations
and null residual. Positive totals require a representable interior root;
rounding to an endpoint, underflow, overflow or exhaustion is an explicit failure.

Both profiles preserve supplied assumptions and warn that native calibration is
absent. Canonical RNA energies do not supply constrained ribosome binding,
occupancy or translation. Supplied energy bases are caller assertions, including
their unknown identities; no physical Kd/empirical-beta equivalence is assumed.
The independently expressed algebra uses natural logs, equal free/complex RNA
volume, an explicit molar standard and strict-positive metastability correction.
At exactly zero switching cost it remains uncorrected; its positive-side limit
is discontinuous. Volume sums above one are warnings, without a new packing law.

Source identity is the admitted source-manifest SHA-256. The separately packaged
`conditional-parameters-1.json` pins the gas constant, numerical conventions,
limits and backend flags; its bytes are integrity checked. Source article and
supplement remain external under CC-BY-NC-4.0. New independently authored code,
conventions and synthetic tests use GPL-3.0-or-later. RNAstructure is separately
installed under GPL-2.0-only; no engine code, source figure or fitted table is
copied or linked.

Validation refusals use `invalid_object`, `unexpected_field`, `missing_field`,
`invalid_string`, `invalid_number`, `invalid_position`, `position_out_of_range`,
`invalid_provenance`, `invalid_hash`, `invalid_range`, `invalid_constraint` and
the specific constraint codes in the component contract. Parsed nonfinite or
non-JSON Python values use `invalid_json`; byte/depth/node violations use
`input_limit`. Maximum nesting depth is 16 and the traversal cap is 20,000 nodes,
including object keys. Unsupported schema/profile/temperature/affinity/occupancy,
unadmitted constraints and negative supplied structural cost are explicit
`unsupported` results. All failures have ordered unique reason codes and
`{code,message}` diagnostics with no raw request or installation paths.

Execution errors distinguish `parameter_integrity`, `backend_identity`,
`backend_unavailable`, `backend_failed`, `backend_timeout`, `backend_output`,
`invalid_ct`, `invalid_energy`, `constraint_violated`, `resource_limit`,
`deadline_exceeded`, `negative_structural_cost`, `numerical_range` and
`nonconvergence`. `result_bytes` raises `ConditionalError` with `result_limit`
when an externally supplied result exceeds its authoritative byte cap. Library
results fit the cap by construction under the validated input/state bounds.
Backend output pipes are drained together with a combined 1,000,000-byte limit;
on failure the captured prefixes are hashed and only that exact child is killed
and reaped. Generated files also have bounded reads. Sequence bounds and fixed
flags bound the workload; no operating-system memory quota is asserted.

Reproduce from a checkout with the locked development environment and the
separately installed admitted original backend:

```sh
REGSITE_CONDITIONAL_TEST_BACKEND=/path/to/original/RNAstructure PYTHONPATH=src \
python -m pytest tests/test_conditional.py tests/test_conditional_math.py \
  tests/test_conditional_backend.py --cov=regsite.conditional \
  --cov=regsite.conditional_math --cov=regsite.conditional_backend --cov-branch
ruff check src/regsite/conditional*.py tests/test_conditional*.py
ruff format --check src/regsite/conditional*.py tests/test_conditional*.py
mypy src/regsite/conditional*.py
git diff --check
```

The real integration test executes all nine canonical fixtures and one public
structural request (21 Fold/efn2 processes, sequential). A missing backend skips
that test and does not satisfy structural admission. For arithmetic-only edits,
`-k 'not real_original'` avoids repeating unchanged native jobs. The frozen 17
numerical and 21 refusal cases are consumed only as independent fixture data;
no independent reference implementation is imported. Additional tests cover
CT corruption, process output/timeouts, bounds, deterministic identities,
near-standard affinity cancellation, tiny/unequal totals, range failures,
partial results and all runtime statements/branches. CLI/schema integration,
fresh-wheel tests, whole-CLI resource admission and other-platform backend
admission belong to the integrating coordinator.

## Command-line transport

`regsite-conditional REQUEST.json` accepts one explicit request, or `-` for
standard input. `--backend-root /path/to/original/RNAstructure` selects the
structural installation; otherwise that profile uses `REGSITE_RNASTRUCTURE`.
The supplied-energy profile requires no backend. No scientific setting is
inferred from the command line.

The transport reads at most 65,537 raw bytes before strict UTF-8 decoding and
rejects inputs above 65,536 bytes. Duplicate object keys (including nested keys),
nonfinite constants and malformed JSON produce a complete `invalid_input`
receipt with no request identity. Parsed invalid requests retain the library's
field validation and identity semantics. JSON output always uses the authoritative
serializer above, including when the terminal encoding differs from UTF-8.

Exit 0 means `ok`; exit 1 means `failed` or `no_mrna`; exit 2 means
`invalid_input` or `unsupported`. Every one of these statuses has a JSON receipt.
An input/output access failure or output-size rejection also exits 2, with a
fixed stderr message and no intentional partial JSON. A downstream broken pipe
can of course have received a prefix before the operating system reports it.
There are no retries. Raw I/O failures do not disclose installation paths.

```sh
regsite-conditional examples/conditional-supplied-half-occupancy.json
regsite-conditional examples/conditional-supplied-volume-fifth.json
regsite-conditional examples/conditional-hairpin-structure-control.json \
  --backend-root /path/to/admitted/original/RNAstructure
```

The first two examples are synthetic algebra controls, not physiological
concentrations or aptamer predictions. The last is a supplied canonical RNA
hairpin, not evidence of ligand binding. Binary64 scalar inference is portable;
the structural profile currently admits only the recorded original arm64 binary
identities. Other builds need independent canonical-fixture admission before
runtime acceptance. Successful scalar CI on another platform does not establish
structural-backend admission there.

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
Only a certified exact interior zero collapses the bracket. Boundary cases use zero iterations
and null residual. Positive totals require a representable interior root;
rounding to an endpoint, underflow, overflow or exhaustion is an explicit failure.

The numerical convention is
`natural_logs_equal_rna_complex_volume_explicit_molar_standard_strict_positive_zero_uncorrected_binary64_kd_guarded_certified_min_total_bracket_3`.
The source manifest, physical constants, scientific assumptions and backend pins
retain their existing identities; the parameter hash additionally binds the
certification method below. The public result shape and error-code vocabulary
are unchanged.

With direct binding energy, keep `G_on - G_off + G_bind` as one exact rational
combination of the supplied
binary64 energies through the metastability sign decision, its beta product and
the occupancy equation. The separately displayed structural cost is rounded
once; it is not reused to form switching energy. Otherwise a small positive
switching cost can round to zero and select the discontinuous wrong branch.
Unrepresentable displayed fields fail explicitly while other representable
components survive.

Kd continuation has an additional admission gate. Enclose
`G_on-G_off + R*T*ln(Kd/standard)` from the exact input values and the binary64
`GAS_CONSTANT`, using the same bounded 80/160-digit log method. The rounded
binding energy remains an independent diagnostic. Scalar switching/correction
and actual response may continue with the binary64 converted binding only when
the composite enclosure proves the same strict-positive, negative or exact-zero
branch. A rounded zero agrees only with a proven exact composite zero; there is
no epsilon around zero. If a different branch is proved or the sign cannot be
resolved within the two fixed precision stages and deadline, return `failed`,
`numerical_range`, `complete=false`. Switching energy, metastability fields and
actual response stay null. Cost, binding, log maximum ratio and its representable
linear value survive. A supplied fraction and its concentration ratio are also
independent and survive; dependent volume occupancy remains uncomputed, with
null fraction, concentrations, volume fractions and solver.

Even after branch admission, volume occupancy uses the **unrounded composite
energy enclosure**, multiplied by exact beta. It never treats the displayed
rounded affinity or switching energy as the exact energy of a physical root.
Each stationary enclosure includes both endpoints of that energy interval and
both possible residual-scale endpoints. Signs and stopping bounds are therefore
conservative for the entire admitted composite enclosure. If that enclosure
prevents a certified stationary sign at the two bounded precisions, fail with
`numerical_range` and retain the last certified bracket. This may refuse a
mathematically defined root; no wider precision search is promised. This is the
exact admitted Kd domain: branch agreement and, for an interior volume solution,
certifiable signs and both stopping bounds under the unrounded energy enclosure.
Scalar response values remain binary64 approximations within the certified
branch; their values are not advertised as interval-certified. Exact
`Kd=standard` gives a zero binding enclosure and preserves the exact-zero rule.

Every bisection update uses a certified stationary sign, not the sign of a
rounded float residual. At each candidate, form `b/(m-b)` and `Vl*(l-b)/Cs` as
exact fractions of the original input values and candidate. Independently of
the caller's Decimal context, divide those fractions at 80 decimal digits with
directed floor/ceiling rounding. Monotonicity of ln and Decimal's correctly
rounded nearest/even ln give log enclosures by widening each endpoint result
one adjacent Decimal value outward. `ln(1)` is exactly zero and needs no
widening. Convert these finite decimal bounds back to exact fractions for
weighted addition, the exact direct energy or Kd composite enclosure, its beta
product, and residual scaling.
Thus rounding of a large ligand total cannot erase its difference from free
ligand, and a float zero cannot supply an interval guarantee.

If the resulting sign interval straddles zero, repeat once at 160 digits.
If neither stage proves a strict sign or an exact zero interval, return
`numerical_range` with the last certified bracket retained. Each solver iteration
uses at most two stages (eight endpoint ln calls); the existing 256-iteration
cap and deadline apply. No unbounded precision escalation is permitted.
The residual stopping test uses the entire certified scaled interval within
the tolerance, and the relative width test uses exact rational endpoint
subtraction. `scaled_residual` reports the binary64-rounded midpoint of that
interval for diagnostics; it is not itself the sign certificate. A nonzero
midpoint outside binary64 range is an explicit numerical failure. Regression
checks cover the strict-positive cancellation boundary, widely separated
concentration scales, second-stage certification, unresolved near cancellation,
and independent high-precision signs at the reported bracket endpoints. Kd
regressions cover rounded-zero refusal at 0.9 M versus a 1 M standard, both
adjacent float RNA costs, equal Kd/standard, preserved independent partial values,
and successful/refused volume continuation at small relative volumes. Independent
240-digit endpoint checks distinguish the composite root from the root obtained
by treating the displayed rounded affinity as exact.

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

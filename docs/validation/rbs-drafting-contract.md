# Supplied-rate stationary drafting contract

- Purpose: Implement the admitted three-state calculation without inventing sequence-derived rates.
- Scope: Frozen implementation/evaluation interface version 1; implementation independently reviewed and integrated in 0.12; B’s separate numerical verification pending.
- Last verified: 2026-10-21

This separate component uses the independently admitted
[2016 stationary mathematics](rbs-kinetics-source-admission.md). It does not alter
any existing RBS profile, infer rates from sequence, or predict calibrated protein
expression. Caller rate provenance is retained as an assertion, not verified
measurement evidence. No backend or new dependency is required.

## Request and domain

The library entry is `regsite.drafting.predict(request)`. The CLI entry is
`regsite-drafting PATH`, with `-` for stdin and module invocation
`python -m regsite.drafting_cli`. It writes one authoritative result to stdout.

The envelope has exactly `schema_version: "drafting-request-1"` and `records`.
There are 1–100 records. Each has exactly these keys:

```json
{
  "id": "artificial-1",
  "rates": {"a1": 2, "a2": 1, "a_fold": 3, "a_elong": 10},
  "rate_unit": "per_model_time",
  "rate_provenance": "Artificial scalar control; no experimental calibration."
}
```

IDs match `[A-Za-z0-9_.:-]{1,128}` and are unique. `rate_provenance` is a
nonblank string of at most 1,024 Unicode code points, retained without trimming.
`rate_unit` is `per_second` or `per_model_time`; all four rates use that common
inverse-time unit. Choosing seconds is a caller assertion and adds no calibration.
No defaults, metadata, host, sequence, energies, geometry or folding settings exist.

Rate values are finite binary64 numbers after explicit conversion from JSON
numbers; booleans and numbers that cannot convert finitely are invalid.
Accepted domain: `0 < a2 <= a1 < a_elong`, `a_fold >= 0`. Negative zero folding
normalizes to positive zero. This deliberately restricts the component to the
published fast-clearance regime and inhibitory-folding interpretation. Other
finite rate combinations are `unsupported_domain`, never silently clamped.

Wire input and the API object's canonical JSON are each limited to 1,048,576
bytes. Strict UTF-8 JSON rejects BOM, duplicate object keys and nonfinite tokens.
The authoritative result is `json.dumps(sort_keys=True, indent=2,
ensure_ascii=True, allow_nan=False) + "\n"`, at most 4,194,304 bytes. These
limits apply independently; do not equate compact and pretty sizes.

## Output

The envelope keys are exactly `schema_version`, `model`, `request_sha256`,
`status`, `reason`, `coverage`, `warnings`, `records`, `prediction_sha256`.
`schema_version` is `drafting-result-1`. `model` has exactly:

- `id: "espahborujeni2016-supplied-rate-stationary-1"`;
- `implementation_version`: the installed package version;
- `source_doi: "10.1021/jacs.6b01453"`;
- `theory_sha256: "a9ded599cbb0313d610267cb9fbdfd21abb1bdb7a467894701fa9b295f3fd6d6"`;
- `backend: null`;
- `rate_origin: "caller_supplied"`.

`warnings` always states that rates/provenance are unverified caller inputs,
stationary memoryless states omit traffic and transcript turnover, throughput is
initiation-region passage rather than completed protein production, and neither
native-host accuracy nor hosted parity is established. Exact warning strings are
implementation text; schemas require the invariant warning set.

Each accepted-roster record has exactly `index`, `id`, `status`, `reason`,
`input`, `occupancies`, `throughput`. `index` is its original zero-based position.
`input` is the normalized valid record above or null for malformed records.
Successful `status: "ok"` has `reason: null`, occupancies keyed `accessible`,
`folded`, `occupied`, and throughput `{ "unit": RATE_UNIT, "quantity": Q }`.
Every quantity Q has exactly `value`, `ln_value`, `representation`:

| Representation | value | ln_value |
| --- | --- | --- |
| `finite` | positive finite binary64 | finite natural log of the positive theoretical quantity |
| `exact_zero` | 0 | null; the mathematical log is minus infinity |
| `underflow` | null | finite natural log retained when binary64 rounds to zero |

Only folded occupancy with `a_fold == 0` is an exact zero. Underflow is never
reported as biological absence. Occupancy linear values are at most 1. Tiny
rounding of logarithms is expected; do not require exact `exp(ln_value) == value`.
When a valid computation cannot retain finite logs, return `numerical_failure`
with null occupancies/throughput and a reason; never emit NaN or infinity.

Malformed records are `invalid_input`; valid normalized rates outside the domain
are `unsupported_domain`. Both retain their index and valid ID, use a concise
reason code, and have null occupancies/throughput. Malformed IDs become null.
The whole envelope is `partial` if any accepted-roster record is not `ok`, else
`complete`; reason is null. Coverage is exactly `requested_records`,
`evaluated_records`, `successful_records`, `complete`. All admitted records are
evaluated, including refusals; `complete` is true only when all records succeed.

Invalid envelope/type/roster bounds, duplicate IDs, object-size or wire/JSON errors
produce envelope `invalid_input`, a reason, null coverage, and empty records.
Request hash is null when canonical JSON cannot be safely formed. CLI exits are
0 complete, 1 partial, 2 invalid envelope/transport. No timer or deadline is
needed for this bounded scalar operation. Output serialization failures use a
small typed invalid-input result within the same cap.

## Arithmetic and identities

For `a=a1`, `b=a2`, `f=a_fold`, `e=a_elong`, use the admitted weights `be`, `fe`,
`b(a+f)`. Normalize them to P1/P2/P3; throughput is `e*P3`. Direct unscaled
products overflow for legitimate finite inputs. Use stable log-domain or equally
justified arithmetic, with explicit zero-fold handling. Preserve finite log
throughput even when an intermediate occupancy underflows. No empirical constant,
fitted intercept, historical 2500 multiplier, or equilibrium-to-time conversion
is introduced.

Canonical hash bytes use sorted keys, compact separators `(',', ':')`,
`ensure_ascii=True`, `allow_nan=False`, UTF-8, and no newline. `request_sha256`
hashes the parsed request before numeric normalization, if canonicalizable within
the object cap. `prediction_sha256` hashes the entire output envelope before
adding that field. There are no timestamps or randomness. Numerically equal
requests with different JSON number forms can have different request hashes.

## Acceptance

All six immutable rational fixtures must agree with the admitted derivation.
Independent tests cover balances, normalization, finite clearance, equal binding,
no-fold boundary, common rate scaling, singular/out-of-domain refusal, extreme
finite rates, representation transitions, and identity/error/serialization
contracts. For ordinary representable values use relative tolerance 1e-11;
finite log comparisons use absolute tolerance 1e-10. Subnormal linear values
require correctly rounded-range comparisons rather than impossible relative
precision. B owns independent cases and must not inspect runtime internals while
constructing them. Neither artificial arithmetic nor code coverage establishes
biological accuracy. Sequence-to-rate inference, time calibration, transient
dynamics and future frozen experimental evaluation remain open under #4/#12.

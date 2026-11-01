# Coupling 0.14rc2 identity and transport

- Purpose: Specify the exact public interface needed for an independent saved-result checker.
- Scope: Frozen 0.14.0rc2 source; no candidate execution, numerical expectations or biological evaluation.
- Last verified: 2026-11-01

This supplements the [coupling contract](operon-coupling-runtime.md) for source
`ebff076d14789735b56e71501ccfaa5b2b0f82fc`. The
[machine-readable contract](../../models/coupling/0.14.0rc2/public-contract.json)
contains the complete model object, ordered warnings, limits and source pins.
A derived it from immutable source syntax without importing or executing the
scorer. It does not replace the later candidate freeze and execution receipt.

## Hash payloads

Canonical bytes are exactly:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"),
           ensure_ascii=True, allow_nan=False).encode("ascii")
```

The SHA256 hexadecimal digest excludes any trailing newline. `request_sha256`
hashes the entire parsed request before validation or sequence normalization;
no fields are removed and no settings are resolved or converted. Thus numeric
JSON `1` and `1.0` have distinct canonical spellings and hashes, as do `0.0` and
`-0.0`. Whitespace, input key order and alternative encodings of the same parsed
string do not affect identity. Ordinary JSON integer tokens remain Python
integers; float/exponent tokens become finite binary64 values. Reject duplicate
keys, nonfinite numbers and excessive nesting before admission.

`prediction_sha256` hashes the complete result object with only that top-level
key absent. It includes model, request hash, settings, warnings, all record
fields and coverage, including nulls, order, reasons and failures. There is no
elapsed-time field. The supplied time budget is included in both identities.

## Wire representation and limits

CLI output is the canonical result bytes followed by exactly one LF, without a
BOM. It is compact ASCII JSON, not indented JSON. The complete encoded output,
including LF, must be at most 4,194,304 bytes; equality is accepted. Serialization
finishes before stdout is written. A saved-result checker should independently
bound received bytes, require the authoritative spelling and recompute the
prediction hash after removing its field. Do not substitute a pretty-JSON cap
or a new serialization convention.

CLI input accepts at most 1,048,576 received bytes of strict UTF-8 JSON. The
library separately allows at most 6,291,456 canonical object bytes. Containers
at depth 32 are rejected (root depth zero). There are 1–100 records and a finite
budget strictly above zero and at most 60 seconds. Settings and valid energy
objects are returned as supplied, preserving number types and provenance text.

## Failure and missingness

Every admitted record has `index`, `id`, `status`, `reason`, `geometry`,
`energies`, `coefficient`, `scores` and `unfolding_correction`. The last is always
null because this component does not implement unfolding correction.

| Record status | Reason | Retained fields |
| --- | --- | --- |
| `ok` | null | Full valid geometry, supplied energies, coefficient and all scores |
| `unsupported_distance` | `no_admitted_distance_coefficient` | Valid geometry and supplied energies; coefficient and scores null |
| `numerical_range` | `linear_score_outside_binary64` | Geometry, energies, coefficient and all five score objects; each finite log remains, only unrepresentable linear values are null |
| `not_evaluated` | `time_budget_exhausted` | Valid record ID if available and original index; geometry, energies, coefficient and scores null |

Deadline checks occur before and after each record. If the latter observes an
overrun, that record becomes `not_evaluated` too; later records remain present.
Neither numerical-range records nor unsupported records count as successful.
Top-level `complete` requires every record `ok`; otherwise an admitted envelope
is `partial`, with top-level reason null. Coverage partitions the complete
roster into successful, failed-or-unsupported and not-evaluated counts.

Invalid envelopes return `invalid_input`, no accepted records, null settings and
coverage, the same model/warnings and a bound prediction hash. Request identity
is present when finite canonicalization succeeded, otherwise null. Record-level
validation failures are defined by the existing schema/geometry contract and
are distinct from the prospective valid/unsupported numerical fixture roster.
CLI exits are 0 complete, 1 partial and 2 invalid input or transport failure.
Transport failure can occur without a JSON result and must remain a failure.

The four warnings are ordered and literal in the machine-readable contract.
Its null backend and historical source parameters must remain exact; substituting
a newer package version changes model identity even when equations match.
This interface clarification grants no acquisition, fitting, native-host
calibration, complete Operon or publication acceptance.

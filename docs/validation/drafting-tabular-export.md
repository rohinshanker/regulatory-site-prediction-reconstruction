# Drafting tabular export

- Purpose: Inspect supplied-rate stationary records with explicit native identities and numerical representations.
- Scope: `drafting-csv-1` producer-owned projection; implementation checked locally, independent review pending.
- Last verified: 2026-10-31

`regsite-drafting REQUEST --format csv` writes UTF-8 CSV. `--format json` and
the default preserve the authoritative [drafting JSON contract](rbs-drafting-contract.md).
Use `-` for stdin; module invocation is `python -m regsite.drafting_cli`.
No output-file mode, external-result importer, backend or new calculation is added.

## Rows and fields

One `result` metadata row comes first, followed by every native `record` in
original order, including invalid input, unsupported domain and numerical failure.
An invalid envelope still has its result row. Nothing is sorted, filtered or
merged. Exact 42-column order:

```text
csv_schema_version,row_type,schema_version,model_id,implementation_version,source_doi,theory_sha256,backend_json,rate_origin,request_sha256,prediction_sha256,json_sha256,result_status,result_reason,requested_records,evaluated_records,successful_records,complete,warnings_json,record_index,record_id,record_status,record_reason,rate_unit,rate_provenance,a1,a2,a_fold,a_elong,accessible_value,accessible_ln_value,accessible_representation,folded_value,folded_ln_value,folded_representation,occupied_value,occupied_ln_value,occupied_representation,throughput_unit,throughput_value,throughput_ln_value,throughput_representation
```

The first 19 metadata columns repeat on every row. Record-only cells are blank
on the result row. Coverage is copied from native JSON; null coverage stays
blank, including `complete`, rather than inventing zero requested records.
`backend_json` is blank for the current null backend; structured backend metadata
and `warnings_json` use compact sorted finite JSON with ASCII escaping.

Normalized supplied rates, their common unit, caller provenance and native
status/reason strings are retained. Missing/null cells are blank; numeric zero
is `0.0` and booleans are `true` or `false`. Numbers use Python's deterministic
round-trippable string representation, without rounding or unit conversion.
Every occupancy and throughput retains its `value`, `ln_value` and
`representation` triple:

| Native representation | Linear value | Natural log |
| --- | --- | --- |
| `finite` | Positive finite value | Finite value |
| `exact_zero` | `0.0` | Blank |
| `underflow` | Blank | Finite value |

A blank underflow value is not zero or biological absence. Throughput remains
initiation-region passage in the supplied rate unit; it is not calibrated
expression or completed protein production. Provenance remains a caller assertion.

`json_sha256` hashes the existing full authoritative JSON bytes, including their
final LF. Native `request_sha256` and `prediction_sha256` are copied unchanged.
CSV is a documented projection: it does not reconstruct nested key layout,
redundant normalized input ID or authoritative JSON byte spelling. Retain the
bound native JSON for the complete result and existing scientific limitations.

## Transport and failures

Python standard-library `csv` uses comma delimiters, normal double-quote escaping
and CRLF record terminators. Embedded quotes, commas, Unicode and newlines remain
text; leading spreadsheet formula characters are not rewritten. Treat these
fields as text when importing into a spreadsheet.

Both authoritative JSON and complete CSV must fit the existing 4,194,304-byte
result ceiling. Encoding and serialization finish before any stdout write.
An unencodable surrogate or serialization/limit failure produces the existing
small `invalid_input` result with reason `result_serialization_failure` in the
selected format, exit 2. If even the refusal cannot fit, no success prefix is
written. Input errors also use the selected format. Stdin, regular-file,
output-error and broken-pipe behavior is unchanged; exits remain 0 complete,
1 partial, 2 invalid input/transport.

## Verification boundary

Focused exporter/CLI tests cover exact columns/row order, all record/envelope statuses,
null coverage, both units, finite/exact-zero/underflow distinctions, identity and
JSON-byte binding, quoting/newlines/Unicode/surrogates, exact size limits,
stdin/files/options and output failures. Default and explicit JSON were compared
byte-for-byte with the frozen pre-export CLI on ten existing/artificial request
cases, including malformed input and surrogate text. Run the two focused modules
with external test/cache/coverage paths and `--noconftest -p pytest_cov`, covering
`regsite.drafting_export` and `regsite.drafting_cli`; no backend fixture is needed.
Local checks pass all 56 tests and all 85 statements/18 branches. Independent
exact-patch review is pending. Full coverage and independent review are
engineering checks, not new numerical or biological accuracy evidence. No model,
source, fixture, schema or prediction-hash change is implied.

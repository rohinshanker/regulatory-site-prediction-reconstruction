# Supplied-energy coupling tabular export

- Purpose: Inspect every supplied-energy coupling record with its native identity and numerical missingness.
- Scope: Implemented `coupling-csv-1` projection; independent exact-patch review and package gates pending.
- Last verified: 2026-11-01

`regsite-coupling REQUEST --format csv` projects the existing producer result.
`--format json` and the default retain the authoritative
[JSON contract](operon-coupling-runtime.md). The exporter accepts producer-owned
in-memory results; it is not an external-result importer, validator or predictor.

## Columns and rows

One `result` row comes first, then every `record` in native roster order. Invalid
envelopes still have one result row. No sorting, filtering or successful-prefix
output occurs. The fixed 58-column header is:

```text
csv_schema_version,row_type,schema_version,model_id,implementation_version,model_sha256,request_sha256,prediction_sha256,json_sha256,result_status,result_reason,seconds_total,requested_records,returned_records,successful_records,failed_or_unsupported_records,not_evaluated_records,warnings_json,record_index,record_id,record_status,record_reason,coordinate_system,strand,sequence_length,sequence_sha256,oriented_sequence_sha256,distance_nt,upstream_id,upstream_start,upstream_end,upstream_oriented_start,upstream_oriented_end,upstream_start_codon,upstream_stop_codon,downstream_id,downstream_start,downstream_end,downstream_oriented_start,downstream_oriented_end,downstream_start_codon,downstream_stop_codon,upstream_total_kcal_mol,downstream_independent_total_kcal_mol,beta_mol_per_kcal,energy_provenance,coefficient,upstream_independent_value,upstream_independent_log_value,downstream_independent_value,downstream_independent_log_value,reinitiation_contribution_value,reinitiation_contribution_log_value,downstream_total_value,downstream_total_log_value,fold_change_value,fold_change_log_value,unfolding_correction
```

The first 18 columns repeat envelope metadata on every row, except `row_type`.
Record-only fields are blank on the result row. Coverage copies native requested,
returned, successful, failed-or-unsupported and not-evaluated counts; null
coverage remains blank. Warnings use compact sorted finite JSON with ASCII
escaping. Settings retain the supplied `seconds_total` without conversion.

`model_sha256` hashes the whole model using the native canonical JSON spelling.
Request and prediction hashes are copied unchanged. `json_sha256` hashes the
complete authoritative native JSON bytes, including their final LF. Retain that
JSON: CSV cannot reconstruct its object nesting or full model/source/parameter
metadata and cannot independently verify its hashes.

Geometry, when available, uses `fragment-relative-0-based-half-open`. Unqualified
CDS start/end columns refer to normalized input coordinates; `oriented` columns
refer to transcript orientation. Both are ascending and include the complete
terminal stop codon. Copy both unchanged, including on the minus strand. The
sequence and oriented-sequence hashes identify their respective normalized RNA;
distance is the native oriented downstream start minus upstream end. No assembly,
genomic locus, codon inference or coordinate conversion is added by export.

Supplied energies, common beta, caller provenance, coefficient and all five
linear/natural-log score pairs are copied without recomputation or rounding.
`numerical_range` keeps its available logs and finite linear values; a null
linear value is blank, never zero. Integer zero is `0`, float zero retains its
native `0.0` or `-0.0` spelling. Unsupported distance keeps valid geometry and
energies while coefficient/scores stay blank. Invalid and unattempted records
remain, with their native reason and all unavailable fields blank. The absent
unfolding correction is always blank. These are relative supplied-energy scores,
not calibrated rates, abundance, host-transfer or complete Operon predictions.

## Transport and verification

Use UTF-8 without BOM, comma delimiters, minimal standard-library CSV quoting
and CRLF row terminators. Quotes, commas, CR/LF, Unicode and caller text remain
unchanged. Formula-like text is not rewritten; import text columns as text.
Null/inapplicable cells are blank; the original JSON disambiguates omitted
structure from explicit null. Both authoritative JSON and complete encoded CSV
must fit the existing 4,194,304-byte ceiling, including final newline/header/
quoting. Exact equality is accepted. Bound accumulation and finish serialization
before stdout; cap or UTF-8 encoding failure gives exit 2 with no output prefix.
An output-device error may still interrupt the final write, as with JSON.

Existing stdin/file handling and exits remain: 0 complete, 1 partial, 2 invalid
envelope or transport. Malformed input produces the native refusal in the selected
format; unreadable input produces the existing generic diagnostic without a
result. No fallback format, output file mode or new calculation is added.

Focused verification covers exact columns/order, all statuses and coverage,
both-strand overlapping CDS intervals, all scalar/log/null fields, native byte/
hash regression, malformed input, byte boundaries, text encoding and output
errors. Use only existing producer examples and artificial software cases.
Independent review and combined package/platform gates are separate. B's #81
numerical fixtures/candidate are untouched; this export does not validate them.

Focused local checks pass 43 tests with 100% coverage of all 81 statements and
18 branches across exporter and CLI. Ruff/format pass four changed Python files;
mypy passes both source files. Default and explicit JSON bytes, exits and stderr
match frozen 0.16rc2 on eight existing/artificial request controls, including
invalid JSON/envelopes, unsupported distance, Unicode and surrogates.
No 0.14rc2 candidate call or B #81 fixture was used. These checks establish
projection compatibility, not an independent numerical or biological evaluation.

```sh
PYTHONPATH=src python -m pytest --noconftest -p pytest_cov \
  tests/test_coupling_export.py tests/test_coupling_cli.py \
  --cov=regsite.coupling_export --cov=regsite.coupling_cli --cov-branch \
  --cov-report=term-missing --cov-fail-under=100
python -m ruff check src/regsite/coupling_export.py src/regsite/coupling_cli.py \
  tests/test_coupling_export.py tests/test_coupling_cli.py
python -m ruff format --check src/regsite/coupling_export.py src/regsite/coupling_cli.py \
  tests/test_coupling_export.py tests/test_coupling_cli.py
python -m mypy src/regsite/coupling_export.py src/regsite/coupling_cli.py
```

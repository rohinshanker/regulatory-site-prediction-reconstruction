# Conditional result CSV projection

- Purpose: Inspect admitted conditional-calculator results as bounded UTF-8 CSV.
- Scope: Standalone producer export; no new inference, schema or backend admission.
- Last verified: 2026-10-31
- State: Independently reviewed standalone projection; package/platform and scientific acceptance remain separate.

`regsite-conditional REQUEST.json --format csv` projects the existing
[conditional result](conditional-aptamer-runtime.md). The default and explicit
`--format json` retain the authoritative JSON serializer and existing exit codes:
0 for `ok`, 1 for `failed`/`no_mrna`, 2 for `invalid_input`/`unsupported` or a
transport/serialization error. The [scientific contract](conditional-aptamer-contract.md)
and its assumptions apply to both formats.

```sh
regsite-conditional examples/conditional-supplied-half-occupancy.json --format csv
regsite-conditional examples/conditional-supplied-volume-fifth.json --format csv
```

These supplied-energy examples are artificial algebra controls. CSV does not
establish aptamer binding, native accuracy or complete sequence-to-switch inference.
The exporter consumes a producer-owned result; it does not load external results,
discover a backend, run a predictor or recalculate biological values.

## Rows and missing values

The fixed header is followed by exactly one `result` row, every recorded `state`
in producer order, then one `response` row if that object exists. Failed and
`not_run` states remain rows. An invalid envelope still produces its result row.
`state_count` and `response_present` explicitly distinguish absent components.
There is no interpolation, filtering, reordering or concentration sweep.

Null and inapplicable scalar cells are empty. Native nonempty IDs/text remain
literal text. Fields permitting an empty collection use compact JSON: `[]`
differs from a null empty cell. Empty native reason arrays therefore remain `[]`.
An empty result ID is not admitted by the producer; an empty ID cell denotes null.
Row type determines which other cells apply. Booleans are `true`/`false`; integers
and finite floats retain Python's decimal representation without rounding or
normalization. Real zero is never an empty cell. JSON-valued cells use sorted-key,
compact, finite ASCII JSON, preserving array order. Text is quoted by stdlib CSV
with minimal quoting, doubled quotes, CRLF records, UTF-8 and no BOM; embedded
CR/LF and Unicode text remain data.
An escaped lone surrogate can exist in authoritative ASCII JSON but cannot be
encoded as UTF-8 CSV; CSV rejects it through the existing output-error boundary,
without replacing characters or changing JSON behavior.

## Fixed column order

Version `conditional-csv-1` has the following groups, concatenated in this order.
The order within each group is exact.

| Group | Columns |
| --- | --- |
| Repeated identity/status | `csv_schema_version`, `row_type`, `schema_version`, `id`, `profile`, `request_sha256`, `json_sha256`, `model_id`, `implementation_version`, `source_manifest_sha256`, `parameter_sha256`, `convention_id`, `backend_sha256`, `result_status`, `complete` |
| Result | `state_count`, `response_present`, `structural_cost_kcal_mol`, `reasons_json`, `warnings_json`, `errors_json` |
| State | `state_index`, `state_id`, `state_status`, `state_reasons_json`, `sequence_sha256`, `constraint_sha256`, `structure`, `pairs_json`, `fold_energy_kcal_mol`, `efn2_energy_kcal_mol` |
| Response | `ligand_binding_kcal_mol`, `switching_kcal_mol`, `log_ar_max`, `ar_max`, `ar_conc`, `ar_actual`, `metastability_factor`, `metastability_applied`, `occupancy_mode`, `occupancy_status`, `occupancy_fraction`, `mrna_free_molar`, `ligand_free_molar`, `complex_molar`, `mrna_balance_error_molar`, `ligand_balance_error_molar`, `volume_mrna_free`, `volume_ligand_free`, `volume_complex`, `volume_sum`, `solver_iterations`, `bracket_low_molar`, `bracket_high_molar`, `scaled_residual` |

All identity/status columns repeat on every row. Result/state/response columns
appear only on their respective row types. Result reasons, warnings and errors
retain their exact ordered arrays and messages. `state_index` starts at zero and
records original order; `state_id` retains `unconstrained` or
`constraint_compatible`. State reasons and pairs retain their arrays. Pairs are
full supplied-sequence zero-based points, not genomic intervals. The structural
profile's absent Fold header energy remains null even when efn2 energy is zero.

Scalar energy fields remain kcal/mol; concentrations and solver brackets remain
mol/L. Volume fractions, occupancy and response ratios are dimensionless.
`log_ar_max` is a natural logarithm; all AR ratios retain native **ON/OFF**
direction, including repression below one. The metastability factor and occupancy
fraction remain distinct. Solver bounds/residuals/iterations and independently
computed partial values survive failed calculations. No-mRNA response ratios and
fraction stay null. A valid log ratio does not fill a missing linear ratio.

## Identity, omissions and limits

`request_sha256` is the producer's existing parsed-request identity.
`json_sha256` is SHA256 of the exact authoritative `result_bytes` output,
including its final LF. It is an export binding; this native schema has no
prediction/result hash, and the exporter invents neither. `backend_sha256` is
null when backend identity is null, otherwise SHA256 of that complete object
encoded as sorted-key compact finite ASCII JSON with no trailing LF. All other
model/source/parameter/convention fields retain their native values.

Keep the bound native JSON. CSV omits the complete validated input, provenance,
effective settings, backend object and native job receipts. The JSON hash binds
those bytes but does not independently verify omitted contents, supplied energy
bases, execution or scientific validity. This documented projection is not a
lossless replacement for JSON or source/native receipts. Never regenerate native
scientific values from rounded or spreadsheet-edited CSV.

Both authoritative JSON and encoded CSV must fit the existing inclusive
1,000,000-byte result ceiling. Serialization finishes before stdout; an encoding
or cap rejection emits no CSV prefix. Output streams can still receive a prefix
before reporting an operating-system write failure. Existing fixed diagnostics,
stdin/file input behavior and broken-pipe exit handling remain. The input cap
stays 65,536 bytes. There is no output-file mode, importer, dependency, generic
schema flattening, new JSON schema version or job-runner change.

## Focused verification

Use the existing development interpreter with this tree's `src` on PYTHONPATH.
Remove `MULTICA_TOKEN`, `TYPESAFE_API_KEY` and `PYTHONHOME` from check environments
without displaying values. Keep pytest caches, temporary files and coverage
outside the checkout. Focus on `tests/test_conditional_export.py` and
`tests/test_conditional_cli.py`, with full statement/branch coverage of
`regsite.conditional_export` and `regsite.conditional_cli`; run scoped Ruff,
format and mypy checks. Artificial scalar requests need no native backend.
Structural export tests use producer-shaped artificial state objects, including
failures and unstarted states. A owns native/platform/package gates.

Tests must independently freeze the literal header/order and native JSON hash;
cover statuses, partial values, units/direction, null/zero/false, Unicode/quotes/
newlines, empty arrays, both byte caps at exact boundaries, transport errors and
broken pipes; compare default and explicit JSON against the frozen original CLI.
No new native/folding/version process or biological data is required for this export.

The implementation has 70 passing focused tests with full 110-statement and
26-branch exporter/CLI coverage; independent exact-patch review reproduced all
70 without warnings or skips. A separate ten-case artificial module check
compares default and explicit JSON bytes/exit/stderr with the pre-export CLI at
`ef46acd69b16021d1d83c4de5c65a682ad37faad`, including malformed input, unsupported
requests, no-mRNA, Unicode, lone-surrogate and missing-backend cases. CSV rows
bind the same JSON and preserve corresponding exits; the unencodable surrogate
case instead produces the documented clean output refusal. No native process
is needed. This verifies transport/projection behavior, not scientific accuracy.

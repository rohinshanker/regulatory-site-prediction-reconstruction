# Intrinsic-termination tabular export

- Purpose: define a deterministic CSV projection for external inspection.
- Scope: standalone intrinsic-termination results; fragment coordinates only.
- Last verified: 2026-10-22

`regsite-termination REQUEST --format csv` projects the result of the existing
request execution. `--format json` is the default and retains its byte/hash
contract. `termination_export.csv_bytes(result)` accepts an in-memory result
produced by the existing runtime; it is not a public result importer, schema
validator or hash verifier. No scientific calculation or backend discovery
occurs during export. Read the [runtime](intrinsic-termination-runtime.md) and
[source](intrinsic-termination-source.md) contracts for score meaning and limits.

## Fixed columns and rows

CSV projection version `termination-csv-1` has the following exact header order;
this does not change the `termination-result-1` JSON schema:

```text
csv_schema_version,row_type,schema_version,model_id,implementation_version,model_sha256,request_sha256,prediction_sha256,result_sha256,result_status,result_reason,record_index,record_id,record_status,record_reason,sequence_length,sequence_sha256,attempted,candidate_count,candidate_id,candidate_status,coordinate_system,strand,hairpin_start,hairpin_end,tail_start,tail_end,confidence,hairpin_score,tail_score,native_id,native_context,native_printed_confidence,native_notes
```

Always emit one `envelope` row first, including invalid envelopes with no accepted
records. Then emit each `record` row in the producer's roster order, immediately
followed by every retained `candidate` row in its existing canonical order.
Do not sort again, filter, merge overlaps or manufacture candidates. Each record
survives even when invalid, unsupported, unattempted, timed out, backend-failed
or successfully empty. Each candidate keeps its canonical ID, status and native
ID/context/notes. Candidate IDs are scoped to their record; the full identity is
the result hash, record index and candidate ID.

| Columns | Meaning |
| --- | --- |
| `csv_schema_version` through `result_reason` | Repeated envelope binding. `schema_version` is the original JSON version; `model_id` is the fixed model/profile ID. `model_sha256` is SHA256 of the existing canonical JSON encoding of the whole model object, including backend identity. Other hashes/status/reason are copied unchanged. |
| `record_index` through `candidate_count` | Blank on envelope rows; otherwise repeated record metadata. Sequence length/hash describe the normalized input when available. `attempted` retains the adapter-invocation meaning. `candidate_count` is blank for null candidates and `0` for a successful empty search. |
| `candidate_id` and `candidate_status` | Present only on candidate rows, copied unchanged. |
| `coordinate_system` | Always `fragment-relative-0-based-half-open`. It does not identify an assembly, contig, locus or transcript mapping. |
| `strand`, `hairpin_start`, `hairpin_end`, `tail_start`, `tail_end` | Candidate-only coordinates, copied from the ascending half-open intervals on the recorded strand. No one-based conversion or reverse-strand remapping. |
| `confidence`, `hairpin_score`, `tail_score` | Original background score or null, plus unmodified native printed cost strings. No units, efficiencies, probabilities or readthrough labels are inferred. |
| `native_id`, `native_context`, `native_printed_confidence`, `native_notes` | Original native bookkeeping. Boundary-ambiguous confidence stays null; no value is recovered from raw output. |

Empty cells represent null or fields inapplicable to the row type. A candidate's
empty confidence cells mean unknown, never zero. Integer zero is written `0`;
booleans are `true`/`false`. `native_notes` is a non-null string on candidate rows,
so its empty cell there is the original empty note. Valid record IDs and non-null
reason/hash fields are nonempty, so their null representation is unambiguous.
Integer fields use base-10 text; score strings retain their exact native spelling,
including trailing zeros or exponent notation. No locale conversion or formulas
are generated. Import text fields as text when viewing CSV in a spreadsheet.

Use UTF-8 without a BOM, comma separators, CRLF row terminators and Python stdlib
CSV minimal quoting. Double quotes inside quoted cells are doubled; embedded
commas, CR and LF remain within quoted cells. Header and row order are stable.
The exporter does not mutate the result or change its prediction/result hashes.

## Projection and transport boundary

CSV deliberately omits settings, warnings, coverage/background detail, expanded
model/backend metadata and execution captures. The model hash and original
prediction/result hashes bind those omitted fields to the complete JSON result;
CSV alone cannot reconstruct or verify them. Retain the native JSON and execution
receipts. This is a documented projection, not a lossless replacement.

Complete CSV serialization must succeed before stdout is touched. Count encoded
UTF-8 bytes, including header, quotes and CRLF, against the existing 33,554,432-byte
ceiling; the exact ceiling is accepted and one byte beyond is refused. Incremental
buffer checks bound accumulation while retaining an all-or-error serialization
step. Output-device failures can still interrupt the final write, as with JSON.
Keep the existing stdin/regular-file/no-follow handling and generic output-error
diagnostic. Exit 0 means complete, 1 partial, and 2 invalid input or transport error.
An invalid JSON/envelope response still receives its CSV envelope row; a file-read
or serialization failure produces no response prefix.

Use the existing artificial requests in `examples/termination-*.json`. Focused
verification must cover exact headers/row order, both strands, overlaps, boundary
ambiguity, every envelope/record status, null versus zero, text escaping, byte
limits, CLI inputs/options/errors/broken output, and default/explicit JSON identity.
From a development environment with `PYTHONPATH=src`, run the following focused
checks. Exclude `MULTICA_TOKEN` and `TYPESAFE_API_KEY` from child-test environments;
do not print environment or authentication values.

```sh
python -m pytest tests/test_termination_export.py tests/test_termination_cli.py --cov=regsite.termination_export --cov=regsite.termination_cli --cov-branch --cov-report=term-missing --cov-fail-under=100
python -m ruff check src/regsite/termination_export.py src/regsite/termination_cli.py tests/test_termination_export.py tests/test_termination_cli.py
python -m ruff format --check src/regsite/termination_export.py src/regsite/termination_cli.py tests/test_termination_export.py tests/test_termination_cli.py
python -m mypy src/regsite/termination_export.py src/regsite/termination_cli.py
```

An optional native export smoke uses `examples/termination-single.json` and an
explicit already verified backend manifest. It should produce one envelope, one
record and one candidate: hairpin `[70,86)`, tail `[86,101)`, strand `+`, confidence
`78`, and native cost strings `-11.8`/`-3.87583`. This is an original artificial
transport control, not biological accuracy evidence. Independent exact-patch
review and combined package/platform gates remain separate from focused checks.

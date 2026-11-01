# Independent coupling numerical evaluation

- Purpose: Check the admitted supplied-energy reinitiation equations and complete-CDS coordinates independently of runtime implementation.
- Scope: Frozen 0.14.0rc2 artificial supplied-energy evaluation; no biological accuracy or host-transfer evaluation.
- Last verified: 2026-11-01

The [protocol](../../benchmarks/operon/coupling-numeric-protocol.json) fixes 24
artificial records before oracle implementation. It uses only the admitted
[source contract](operon-coupling-source.md), [public runtime contract](operon-coupling-runtime.md),
request/result schemas and five original scalar source fixtures. Exact source
bytes are pinned. Scorer modules, implementation tests, candidate outputs, source
workbooks and private outcomes are not expectation inputs.

The evaluated candidate is independently package-reviewed 0.14.0rc2, source
`ebff076d14789735b56e71501ccfaa5b2b0f82fc`. The completed run below used reviewed public model/runtime/material identities,
a separate frozen execution receipt and explicit B acknowledgement before A's
one-shot acquisition. A later candidate needs its own reviewed freeze; newer
engineering packages cannot silently substitute.

The roster includes positive and mirrored negative strands; admitted distances
-4, 0, 3 and 25; valid unsupported distances -7, -1 and 26; equal and unequal
energies; finite, overflowing and underflowing linear values with retained natural
logs. It is one 24-record batch, preserving every case and native missingness.
The independent reference uses 80-digit Decimal arithmetic. The protocol records
log tolerances and linear relative/ULP tolerances before outputs exist. No zero
or null is substituted for a valid positive quantity.

Conformance is to these fixed numerical tolerances. At extreme supplied energies,
a mathematically equivalent binary64 calculation can lose precision when
subtracting nearly equal large logarithms. Such a mismatch requires diagnosis;
it does not by itself contradict the published equations or demonstrate
biological inaccuracy. The report retains the original tolerances and every
mismatch. Independent artificial conditioning controls test this interpretation;
they are not candidate results and do not change the protocol or expectations.

Complete-CDS geometry matters independently of a scalar coefficient domain.
Distance -3 overlays a required stop with a required start; at -5, the invariant
third start base G would be the first stop base. Those distances are not used as
valid native unsupported-distance witnesses. The original scalar fixtures can
still test whether their coefficients are undefined. This distinction does not
admit an additional biological mechanism.

The [reference](../../benchmarks/operon/coupling_reference.py) evaluates direct
exponentials and sums in 80-digit Decimal arithmetic, independently of the
candidate's specified log-space calculation. Decimal expectations retain both
linear quantities and natural logs. Inputs use the decimal spelling of each
finite JSON number; coefficients are the exact admitted decimal constants.
The [fixtures](../../benchmarks/operon/coupling-numeric-fixtures.json) retain all
24 requests, expected record fields, Decimal values and five source checks.
Eleven cases expect `ok`, seven expect `numerical_range` and six expect
`unsupported_distance`. These are prospective expectations, not candidate results.

Regenerate to a **new**, explicitly named file; an existing output is never
overwritten. The SHA below is the independently committed protocol trust input,
not a digest silently derived from the protocol under test:

```sh
python -m benchmarks.operon.coupling_reference prepare \
  --protocol benchmarks/operon/coupling-numeric-protocol.json \
  --protocol-sha256 9390e29f40eb3ef0f2b09bfe36ab6df8a523369de203d7e096ee70a5494ddc64 \
  --root . --output /explicit/new/fixture.json
```

The record-structure/accounting layer checks all six native statuses, complete
field sets, finite scores, status/null/reason consistency and exact coverage
partitions before numerical comparison. Unexpected valid failures remain in
the full case roster and fail conformance; they are never omitted or counted
as successful numerical checks. Invalid structure/accounting fails admission.
The saved-result checker verifies the separately pinned freeze and acquisition
receipts before admitting candidate outputs.

Transport and identity admission remain separate from numerical/geometry
conformance. Consistently rehashed artificial mutations must
reach semantic guards. Every new path requires focused tests; no candidate,
folding, network or scorer import belongs to those tests. A finite existing-root
review precedes fixture/protocol/code freeze and later execution.

The [outcome-free 0.14rc2 identity supplement](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/194f515a8d132abfee7fe8ac97e0d8b8395bd9f3/docs/validation/coupling-identity-0.14rc2.md)
fixes both hash payloads, ordered warnings and compact ASCII wire serialization.
Its [public JSON contract](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/194f515a8d132abfee7fe8ac97e0d8b8395bd9f3/models/coupling/0.14.0rc2/public-contract.json)
is 2,385 bytes, SHA256
`7a236d9ef4b1a42ac48c11244eb6a637b48e98e02191478edd4322f109b0f018`.
The checker pins it alongside the unchanged protocol and numerical fixture;
source-file references inside it are opaque and are never opened. Request hashes
preserve original parsed numbers/strings. Prediction hashes omit only the
prediction hash field itself. Authoritative output is compact sorted ASCII finite
JSON plus one LF, inclusive cap 4,194,304 bytes. It is not pretty JSON.

The additive [geometry identity supplement](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/51f9e21e215d47f30506ecf21b36301de37a167e/docs/validation/coupling-geometry-identity-0.14rc2.md)
defines the sequence-hash payloads. Its [geometry JSON contract](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/51f9e21e215d47f30506ecf21b36301de37a167e/models/coupling/0.14.0rc2/geometry-contract.json)
is 1,370 bytes, SHA256
`0c623e8b2c64608a5945ecccf73cdedeeaa1072cda657df751680827b97d03ee`.
The checker pins this separately, leaving the original protocol, fixtures and
public contract unchanged. It confirms the existing expected hashes: normalize
with `"".join(value.upper().split()).replace("T", "U")`, then SHA256 the UTF-8
RNA bytes in supplied orientation for `sequence_sha256`; for the oriented hash,
reverse-complement the entire normalized sequence only on the minus strand.
There is no wrapper, header, NUL or newline. Admitted ACGU bytes encode identically
in ASCII and UTF-8. Referenced source files remain opaque and unopened.

## Frozen execution and saved-result input contract

Implementation does not authorize acquisition. After finite independent tooling
review, A prepares the freeze and complete runtime/material receipt; B checks and
acknowledges them before A's single original 0.14rc2 batch invocation. A retains
complete output, exit, elapsed time and failure evidence without retry. An aborted
or unverifiable attempt cannot produce a successful-prefix report.

The checker opens only ten explicitly named files in the supplied directory:
`freeze.json`, `acquisition.json`, `protocol.json`, `fixtures.json`,
`public-contract.json`, `geometry-contract.json`, `request.json`, `result.json`,
`stderr.bin` and `execution.json`. It additionally hashes its own source file. No path from a JSON
reference is traversed. Every pin has exactly `bytes` (nonnegative integer,
not boolean or float) and `sha256` (64 lowercase hex digits). Pin types are checked
before equality, including the acquisition's pin of the freeze. Both CLI trust hashes come
from A's separate immutable handoff; never derive a trusted hash silently from
the artifact being checked.

`freeze.json` has exactly these fields:

| Field | Required value |
| --- | --- |
| `schema_version` | `coupling-numeric-freeze-1` |
| `candidate` | Complete, unchanged protocol `candidate` object |
| `inputs` | Pins for `protocol.json`, `fixtures.json`, `public-contract.json`, `geometry-contract.json`, `request.json`, and `tool` (this checker source) |
| `runtime` | A's complete nonempty frozen runtime identity object, preserved verbatim |
| `argv` | Complete nonempty string array for the one invocation |
| `environment` | Exact explicitly selected, nonsecret string-to-string child environment; excludes MULTICA_TOKEN, TYPESAFE_API_KEY and PYTHONHOME |
| `limits` | Exactly `{"wall_seconds":30.0,"stdout_bytes":4194304,"stderr_bytes":65536}` |

`acquisition.json` has exactly `schema_version` (`coupling-numeric-acquisition-1`),
`freeze` (pin of the complete pre-execution freeze bytes), and `outputs` (pins
for `result.json`, `stderr.bin`, `execution.json`). It is created after the one
attempt and never substitutes for the pre-execution freeze/acknowledgement.

`execution.json` has exactly:

- `attempts`: integer 1;
- `argv`, `environment`, `runtime`: exact complete copies from the freeze;
- `request_sha256`: hash of the actual received request **file bytes**, distinct
  from the result's canonical parsed-request hash;
- `exit_code`: integer 0 for a complete result or 1 for partial;
- `elapsed_seconds`: finite nonnegative measured time, at most 30;
- `stop_reason`: null for an admitted attempt;
- `stdout_bytes`, `stderr_bytes`: exact captured byte counts; stderr must be empty.

The caller must retain failed acquisition artifacts too. Timeout, overflow,
stopped work, unexpected exits, nonempty stderr, changed identities or invalid
output fail admission; this command neither repairs nor executes anything.

```sh
python -m benchmarks.operon.coupling_reference check \
  --directory /explicit/saved-acquisition \
  --freeze-sha256 HASH_FROM_PRE_EXECUTION_RECEIPT \
  --acquisition-sha256 HASH_FROM_A_HANDOFF \
  --output /explicit/new/report.json
```

Exit 0 means all 24 artificial cases conform, including expected unsupported and
numerical-range outcomes. Exit 1 writes a complete all-case report with semantic
mismatches. Exit 2 indicates admission or IO failure and writes no replacement
report. Outputs are deterministic sorted indented ASCII JSON with one LF, created
atomically with mode0600 and no overwrite. An existing report remains untouched.

The report separates native successful counts from numerical conformance:
expected unsupported/null behavior can conform without being a successful native
prediction. It binds every consumed file, the original candidate and all 24 case
results, and carries the fixed numerical tolerances and their interpretation.

Each case keeps its original `mismatched_fields` and `conforms` decision. The
additive `numeric_mismatches` list describes those mismatched scalar fields for
which either compared value is numeric. Each entry retains `path`, `expected`
and `observed` without substituting for null, plus `absolute_error_decimal` and
`relative_error_decimal`. Absolute error is `abs(observed - expected)`; relative
error divides that magnitude by `abs(expected)`. For logarithmic scores the
absolute quantity is a difference in natural-log units; for linear scores the
relative quantity is the fractional error, not a percentage. Coordinate errors
remain in coordinate units.

Error magnitudes are Decimal **strings** calculated from the exact stored
binary64/integer values, rounded to 80 significant digits with `ROUND_HALF_EVEN`.
This diagnostic arithmetic is separate from the frozen numerical reference and
comparison tolerances. Text preserves magnitudes outside binary64 range without
infinity or a fabricated zero. Both magnitudes are null unless both compared
values are numeric; relative error is also null when expected is zero. A null
expected linear score remains null, never an inferred finite or infinite value.
Non-numeric/container mismatches stay in `mismatched_fields`; the new list does
not expand them into invented scalar observations. No diagnostic changes
pass/fail or classifies the cause. Artificial cancellation and gross-error
controls on identical field paths must retain distinct quantitative diagnostics.

The report does not independently prove that an execution receipt truthfully
records a process: A's reviewed collector/material checks remain an external
trust boundary. Runtime files and bytecode are not inspected here, and local
file/path swaps after verification are not prevented by this offline checker.


Focused artificial checks (use an existing development environment):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  -p pytest_cov --confcutdir=tests/benchmarks \
  tests/benchmarks/test_coupling_reference.py \
  --cov=benchmarks.operon.coupling_reference --cov-report=term-missing
ruff check benchmarks/operon/coupling_reference.py tests/benchmarks/test_coupling_reference.py
ruff format --check benchmarks/operon/coupling_reference.py tests/benchmarks/test_coupling_reference.py
mypy benchmarks/operon/coupling_reference.py
```

The benchmark module uses only stdlib and imports no candidate modules. Its
import-boundary test combines a static import allowlist with a fresh, instrumented
module namespace: producer imports are rejected even if already cached. Other
full-suite tests may legitimately load producer modules first; their presence is
not evidence that this checker imported them. Artificial preloaded sentinels and
injected forbidden imports test this distinction without loading a scorer. Tests
use the existing schema validator only to check artificial envelopes against
the pinned public schemas. This is software/arithmetic verification, not a
replacement for the required independent review or later frozen execution.

Passing this evaluation would establish numerical and coordinate conformance of
the supplied-energy component. It would not establish experimental accuracy,
host transfer, sequence-derived energies, full Operon prediction, the unresolved
unfolding correction, consumer admission or publication.


## Frozen 0.14rc2 results

The [complete independent report](../../benchmarks/operon/coupling-numeric-results.json)
and [identity/accounting receipt](../../benchmarks/operon/coupling-numeric-receipt.json)
retain **22/24 conforming cases and two precision failures**. The acquisition
passed admission: all 24 requested records returned, none were unstarted, and no
transport, material-integrity or schema failure was reported. A made one original
candidate invocation; B executed only the saved-output checker. No retry,
expectation change or tuning occurred.

| Expected and observed status | Requested / returned | Conforming | Nonconforming |
| --- | ---: | ---: | ---: |
| `ok` | 11 / 11 | 11 | 0 |
| `numerical_range` | 7 / 7 | 5 | 2 |
| `unsupported_distance` | 6 / 6 | 6 | 0 |
| **All cases** | **24 / 24** | **22** | **2** |

Native `successful` is 11/24, distinct from conformance 22/24. Its
`failed_or_unsupported` count of 13 consists of seven expected numerical-range
records and six expected unsupported distances; these are not 13 process
failures. `not_evaluated`, `invalid_input` and `unsupported_geometry` counts are
all zero. The 18 supported records have 180 score slots: 154 expected numbers and
26 expected nulls. Four numeric slots differ; all nulls, geometry, record
identities, coefficients and statuses conform. Unsupported records retain null
scores and are included in the all-case denominator.

Both failures are fold-change precision discrepancies at the two supplied-energy
limits. Each has the two mismatched fields `/scores/fold_change/log_value` and
`/scores/fold_change/value`. The full report preserves exact compared values and
80-digit Decimal error diagnostics; the table rounds only displayed errors.

| Case | Expected fold | Observed fold | Absolute log error | Relative linear error |
| --- | ---: | ---: | ---: | ---: |
| `upper_energy_bound` | 1.072 | 1.0719999999886614 | 1.0577067000e-11 | 1.0577152752e-11 |
| `lower_energy_bound` | 1.22 | 1.219999999973867 | 2.1420448748e-11 | 2.1420388232e-11 |

These exceed the original applicable 1e-12 tolerances and remain failures.
No causal diagnosis was assigned and no scorer internals were read. The
pre-execution artificial conditioning controls and this evaluation do not make
biological-accuracy claims. Any later numerical correction needs separate runtime
review and a separately frozen candidate; this original result must remain
unchanged. These 24 artificial cases are now consumed conformance evidence.

The native batch exited 1 for its valid partial status, with 27,656 stdout bytes,
zero stderr, null stop reason and 0.08595145799999998 seconds elapsed as recorded
by A. The independent checker also exited 1, for the two precision failures.
Exit 1 here is a completed all-case evaluation, not admission failure.

Exact identities:

- Checker: `456091f9cf86ede228b38408d2399bd14bfc39da`, SHA256 `defd3e4ca97714069f171e7dcb88052453fe35000ba921ed4dd6d2900b242c19`.
- Freeze: 16,675 bytes, SHA256 `fc3a3347a498506d84b32409f3230530475446e00c9d89ed2d7ecf5370465eae`.
- Acquisition receipt: 593 bytes, SHA256 `99f539ea79573d82b4457fbb449c035c4bf386324f011e277c04f38249bc3a87`.
- Independent report: 11,009 bytes, SHA256 `609b85e8c4e6570d2db560b09f0ffc2f880981cc6617f34746ac0049d3772d18`.

The small [acquisition bundle](../../benchmarks/operon/coupling-numeric-acquisition/)
contains unchanged raw output, request, execution/freeze/acquisition receipts,
public identity definitions, one-attempt/authorization/material metadata and B's
ACK. It omits installed code, archives and external review logs. The existing
protocol and fixture are shared without duplication. References to installed
files and external receipts are opaque; reproducing this checker does not
independently repeat or prove A's original process/material checks.

Reproduce only the saved-result verification from the repository root using
Python 3.11 or newer. The command selects identical checker bytes from the
integration commit, retained in main ancestry independently of B's branch:

```sh
audit_dir=$(mktemp -d)
for name in freeze.json acquisition.json execution.json result.json stderr.bin request.json public-contract.json geometry-contract.json; do
  cp "benchmarks/operon/coupling-numeric-acquisition/$name" "$audit_dir/$name"
done
cp benchmarks/operon/coupling-numeric-protocol.json "$audit_dir/protocol.json"
cp benchmarks/operon/coupling-numeric-fixtures.json "$audit_dir/fixtures.json"
git show c0b7d010edab0490f6bcb45a22eed2c298c1d45a:benchmarks/operon/coupling_reference.py > "$audit_dir/coupling_reference.py"
python "$audit_dir/coupling_reference.py" check \
  --directory "$audit_dir" \
  --freeze-sha256 fc3a3347a498506d84b32409f3230530475446e00c9d89ed2d7ecf5370465eae \
  --acquisition-sha256 99f539ea79573d82b4457fbb449c035c4bf386324f011e277c04f38249bc3a87 \
  --output "$audit_dir/report.json"
checker_status=$?
test "$checker_status" -eq 1
cmp "$audit_dir/report.json" benchmarks/operon/coupling-numeric-results.json
```

This requires no predictor, folding backend or network. Keep the expected checker
exit 1; do not weaken the comparison to obtain exit 0. The broader Operon and
benchmark parents remain open. This evaluation grants no full-Operon, native-host,
sequence-derived-energy, consumer or publication approval, and starts no further
wave.

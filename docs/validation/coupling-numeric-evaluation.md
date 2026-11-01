# Independent coupling numerical evaluation

- Purpose: Check the admitted supplied-energy reinitiation equations and complete-CDS coordinates independently of runtime implementation.
- Scope: Artificial-only #81 oracle/protocol preparation; no candidate execution or biological evaluation.
- Last verified: 2026-11-01

The [protocol](../../benchmarks/operon/coupling-numeric-protocol.json) fixes 24
artificial records before oracle implementation. It uses only the admitted
[source contract](operon-coupling-source.md), [public runtime contract](operon-coupling-runtime.md),
request/result schemas and five original scalar source fixtures. Exact source
bytes are pinned. Scorer modules, implementation tests, candidate outputs, source
workbooks and private outcomes are not expectation inputs.

The reserved candidate is independently package-reviewed 0.14.0rc2, source
`ebff076d14789735b56e71501ccfaa5b2b0f82fc`. This reservation grants no execution
authority. A supplies complete public model/runtime/material identities after
oracle review, then a separate frozen execution receipt; B acknowledges it before
A's one-shot acquisition. Newer engineering packages cannot silently substitute.

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
It does not independently prove that an execution receipt truthfully
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

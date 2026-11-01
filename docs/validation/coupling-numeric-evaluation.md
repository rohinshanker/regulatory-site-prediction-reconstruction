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
The saved-result checker still requires its public identity supplement and
acquisition binding before it can admit candidate outputs.

Transport and identity admission remain separate from numerical/geometry
conformance. Consistently rehashed artificial mutations must
reach semantic guards. Every new path requires focused tests; no candidate,
folding, network or scorer import belongs to those tests. A finite existing-root
review precedes fixture/protocol/code freeze and later execution.

The public contracts do not yet state literal request/prediction hash payloads,
the full warning text or authoritative output serialization. A has been asked for
an outcome-free public supplement; B will not guess from runtime internals.
This requirement must be resolved before checker acceptance or collection.

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

The benchmark module uses only stdlib and imports no candidate modules. Tests
use the existing schema validator only to check artificial envelopes against
the pinned public schemas. This is software/arithmetic verification, not a
replacement for the required independent review or later frozen execution.

Passing this evaluation would establish numerical and coordinate conformance of
the supplied-energy component. It would not establish experimental accuracy,
host transfer, sequence-derived energies, full Operon prediction, the unresolved
unfolding correction, consumer admission or publication.

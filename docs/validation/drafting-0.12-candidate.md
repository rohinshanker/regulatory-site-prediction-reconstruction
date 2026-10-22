# Supplied-rate drafting 0.12.0rc1 development candidate

- Purpose: Bind the reviewed stationary drafting component to an installed local package.
- Scope: Mathematical and software verification with passing platform gates; independent numerical tooling remains explicit.
- Last verified: 2026-10-21

The [package receipt](../../models/drafting/0.12.0rc1/package.json) identifies
source `356abc2d40198a95f807967a38126a14b0f3d0c9`. All three drafting modules
match independently reviewed `c75ca5d24efdff2077c882b4edb495a2864c8c4a`; the
five termination modules retain their separate reviewed identities. Existing
model profiles and earlier immutable packages are preserved.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 189,790 | `a95abeeca03360e94b2d79a469520c62cfb8d45ff505dc6395032d9aa2f6c11b` |
| Source distribution | 5,242,143 | `2d9f42fe24419faf4ab9be16273af3aba5d275edd578bc4d0a40cc9813706954` |

The execution-host artifact root is
`/Users/Rohin/.cache/regsite-wave7-integration-20261021/drafting-0.12-installed`.
Preserve `dist/`, `receipt.json` and `installed-byte-check.json` when relocating
them. All 54 installed runtime files match the frozen source. The wheel includes
no native executable or thermodynamic/background table. The source archive
contains the new request/result schemas and all three examples. Compressed
rebuild byte identity is not claimed.

## Installation and meaning

Follow the [offline installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction)
using the exact source and locked development tools. Run the installed command
from an external environment:

```sh
/external/runtime/bin/regsite-drafting /source/examples/drafting-single.json
/external/runtime/bin/regsite-drafting /source/examples/drafting-batch.json
/external/runtime/bin/regsite-drafting /source/examples/drafting-unsupported.json
```

The unsupported example intentionally exits 1 and retains the input record with
null quantities. Malformed envelopes exit 2. Read the
[drafting contract](rbs-drafting-contract.md) for all status, unit, identity and
representation rules. No folding engine, account or network is required.

The calculation returns stationary accessible, folded and ribosome-occupied
probabilities and initiation-region throughput from four explicitly supplied
rates. It does not infer those rates from sequence, predict completed protein
production or establish a biological time scale. The caller's unit/provenance
remain inputs, not evidence of calibration. This command is separate from the
job runner's unchanged five-kind interface.

Tiny positive quantities can have null linear values with finite logarithms;
this underflow state is distinct from exact zero and failed calculations. The
implementation uses exact rational arithmetic on normalized binary64 inputs
before rounding outputs. No empirical coefficient was fitted.

## Verification boundary

At the exact source, 6,972 local tests passed with zero skips and nine warnings.
All 17,506 measured statements and 6,514 branches were covered. Ruff, formatting
and mypy passed. Original RNAstructure, the separately admitted conditional
backend and the source-built termination engine were enabled.

The fresh package passed 30 checks: coupling controls, all five runner kinds,
termination cases and drafting single/batch/unsupported, six admitted rational
controls, an extreme underflow case and duplicate-key refusal. The extreme case
retains positive throughput even when the occupied probability rounds to zero.
Prediction hashes, CLI exits and installed/source identities were checked.
These are artificial software/mathematical cases, not experimental measurements.

Independent arithmetic/schema review accepted 258 focused tests with full
coverage of 171 statements and 44 branches. A separate reviewer challenge used
100 artificial rate combinations; its maximum absolute log error against the
Decimal reference was 2.27e-13, within the 1e-10 contract tolerance. Both schema
findings were repaired and rechecked. This review is distinct from B's reserved
independent numerical fixture/checker stream, which remains pending.

Separate package integration review accepted the frozen source and focused
workflow/documentation repair `e73c1b2`, with no remaining finding. Installed
smoke assertions bind all model fields and request/prediction hashes, and failed
CI smoke checks expose bounded diagnostics. The runtime files are unchanged.

[CI 39703039920](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39703039920)
passed all eight jobs at `efe90fcb3b7b788fcd0c2920b68f79eeccae3551`: macOS 14
and Ubuntu 24.04, each with Python 3.11 and 3.14, plus four Promoter resource
jobs. Each runtime job passed 6,971 tests with full coverage and one declared
exact-original conditional-backend skip; the local suite above enables that
backend. Each repaired-folding variant also passed 3,000 tests. Native termination
and fresh installed-package smoke checks passed on all four platforms. Runtime,
schema, example, dependency and packaging-source bytes match the frozen source;
later commits contain receipts, documentation and workflow repairs. This receipt
does not retroactively mark older failed package-source CI runs successful.

No current hosted equivalence,
cyanobacterial calibration, biological improvement, consumer admission or
publication is claimed. Sequence-to-rate inference and new experimental
validation remain open under the parent RBS refinement program.

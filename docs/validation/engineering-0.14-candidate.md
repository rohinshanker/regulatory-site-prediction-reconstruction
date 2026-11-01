# Engineering package 0.14.0rc1

- Purpose: Install the reviewed bounded design, concentration sweep and portable exports in one local package.
- Scope: Software and supplied-model verification; scientific benchmarks retain separate frozen candidates.
- Last verified: 2026-10-31

## Immutable package

The [package receipt](../../models/integration/0.14.0rc1/package.json) binds source
`d12a03feb83f579634df43bbce6203b222b88f70`. The engineering package incorporates
accepted bounded RBS design `73ac57a`, concentration sweep `ef1da8f`, conditional
CSV `00f7f7c`, termination CSV and the earlier admitted calculator components.
It retains the job runner's existing five-kind interface. The separately held
0.13 component-dispatch work is absent.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 206,621 | `35e64e4aee8213619e89e4db7dbf846284bf2961150d3a965c139b577b9218d1` |
| Source | 5,411,950 | `f7a4f36a4473eab7b9a6e88e413404257bb6772ea8b1c89f80b2417a31422f7a` |

Execution-host artifacts are under
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.14-installed`.
Preserve `dist/`, `receipt.json`, `installed-byte-check.json` and the complete
external smoke outputs when relocating them. All 61 runtime source files match
the wheel and fresh installation; all 72 schema/example files match the source
archive. The wheel contains no folding executable or thermodynamic/background
table. Compressed rebuild byte identity is not claimed.

Build and install with the locked development tools using the
[offline procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction).
The receipt records exact commands, archive hashes and output identities. Fresh
inference runs offline with no account or coin balance. Required native engines
remain separate, explicitly identified installations with their own licences.

## New tools and meaning

```sh
regsite-design /source/examples/rbs-design-single.json --backend-root /absolute/RNAstructure
regsite-conditional-sweep /source/examples/conditional-sweep.json
regsite-conditional /source/examples/conditional-supplied-half-occupancy.json --format csv
regsite-termination /source/examples/termination-single.json --format csv --backend-manifest /absolute/backend.json
```

The [RBS designer](rbs-design.md) exhaustively tests only the admitted small
upstream substitution space. It preserves every candidate, fixes coding bases,
ranks the selected model's log-distance to a caller target, and independently
rescores the best observed sequence before selection. Completing the search does
not guarantee that the target was reached or that expression improves in cells.

The [concentration sweep](conditional-concentration-sweep.md) evaluates exactly
the ordered ligand totals supplied by the caller, including duplicates. Its
energy, affinity, RNA amount and volume assumptions are unchanged across points.
It preserves nulls/failures and uses a cooperative admission deadline. It is not
sequence-to-switch inference, a measured dose response, affinity fitting or an
EC50 estimate. The [conditional CSV](conditional-tabular-export.md) and
[termination CSV](termination-tabular-export.md) preserve their declared rows
and native identities; retain full native JSON for omitted fields and verification.

## Verification boundary

Fresh installation executed the repository's complete installed-example workflow
from an external source snapshot, with no PYTHONPATH or dependency downloads.
All commands and assertions passed, with 58 saved output files and empty stderr.
The new assertions bind package version, exact requests, complete candidate/point
rosters, model/backend identities, fresh design confirmation and authoritative
JSON/CSV hashes. Existing RBS, native adapters, learned examples, Promoter, paired,
transcript, coupling, drafting, termination and five-kind job examples also ran.
These examples are artificial/software controls, not new experimental evidence.

Independent code review accepted all three new feature slices after bounded
repairs. The scalar sweep also passed independent high-precision quadratic,
mass-balance and boundary controls. The design tests exercise both strands using
the real backend. Independent package/workflow review accepted the exact archives, all runtime and
schema/example identities, entry points and added CI assertions. The combined
suite at the frozen source passed 7,516 tests with zero skips and full coverage
of 18,940 statements and 6,858 branches. Real original RBS/conditional and
termination backends were enabled. Eight test-harness warnings came from module
entry-point re-execution and a deliberate duplicate archive-name case. Ruff,
formatting, the documented runtime/evaluator mypy gates, ticket checks and 689
local Markdown file links passed. An exploratory wider benchmark type-check
found preexisting dependency annotation/stub gaps outside that documented gate;
no claim of repository-wide mypy cleanliness is made.

All eight jobs passed in [CI41266499984](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/41266499984)
at `db2919a8886aa1453c32553228c26679a5d7d4b8`, whose runtime, tests and workflow
equal the frozen source. Each macOS14/Ubuntu24.04 and Python3.11/3.14 runtime job
passed 7,515 tests, with one declared exact-original-conditional integration skip
and full measured coverage; that integration passed locally above. Each also
passed both 3,233-test repaired-backend selections and fresh offline installation.
The four Promoter resource jobs passed. These checks do not grant publication
approval or transfer acceptance to a later source version.

The 479-gene PCC 6803 development recheck runs the unchanged frozen 0.12 candidate,
not this package. New source versions cannot inherit a biological evaluation by
name. Existing consumed cohorts remain consumed; UTEX calibration, recoding-effect
accuracy, current hosted equivalence, main/tag/package publication and visualizer
admission remain separate and unestablished by these software gates.

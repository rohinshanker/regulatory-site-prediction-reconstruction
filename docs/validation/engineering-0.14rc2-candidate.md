# Engineering package 0.14.0rc2

- Purpose: Install the reviewed calculator workflows with lossless declared drafting CSV fields.
- Scope: Software verification; scientific candidates and publication remain separate.
- Last verified: 2026-10-31

## Frozen package and installation

The [receipt](../../models/integration/0.14.0rc2/package.json) binds exact source
`ebff076d14789735b56e71501ccfaa5b2b0f82fc`. It adds the independently accepted
[drafting CSV export](drafting-tabular-export.md) to the
[0.14.0rc1 engineering features](engineering-0.14-candidate.md). Existing model
parameters, scoring equations and five-kind job interface are unchanged.
The held eight-kind component-dispatch work is absent.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 208,568 | `14ac432db000abd2a680c52e3968081d03ab937419fca08ca8ddaf6433226ac6` |
| Source | 5,438,652 | `887cee014014b67bb863430eb2d9e07bfe49a3e7ae2b989f1e741cab4ba76b15` |

Execution-host artifacts are in
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.14rc2-installed`.
Preserve both archives, the receipt, installed-byte check and smoke outputs.
All 62 runtime files match source, wheel and fresh installation; all 72
schema/example files match the source archive. No native executable or
thermodynamic/background table is bundled. Compressed rebuild identity is not
claimed. Use the [locked offline build/install procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction);
no account, coin balance or runtime dependency download is required.

```sh
regsite-drafting /source/examples/drafting-batch.json --format csv
regsite-design /source/examples/rbs-design-single.json --backend-root /absolute/RNAstructure
regsite-conditional-sweep /source/examples/conditional-sweep.json
```

Drafting CSV is a fixed projection of supplied-rate results. It retains every
record, native request/prediction and authoritative JSON hashes, plus separate
value/log/representation fields. Exact zero, unavailable values and underflow
remain distinct. It does not infer rates from sequence or validate expression
in cells. Keep full native JSON for omitted metadata and verification.

## Verification and limits

The full local suite passed **7,554 tests, zero skips**, with 100% measured
coverage of **18,990 statements and 6,872 branches**. Original RBS/conditional
and termination backends were enabled. Eight existing test-harness warnings
cover module entry-point re-execution and a deliberate duplicate archive name.
Required Ruff/format checks pass for 260 files; documented runtime and scoped
evaluator type checks pass. This is not a claim of repository-wide mypy coverage.

Fresh offline installation executed the complete installed-example workflow
from an external snapshot with no PYTHONPATH. All commands/assertions passed,
with **64 saved output files** and empty smoke stderr. The additional drafting
controls verify all 42 columns, ordered records, native identities and JSON
hashes, unsupported cases, exact zero, underflow and a finite minimum-subnormal
throughput. Software controls are not experimental observations.

A independently accepted C's exact export implementation `67a755e` using 18 CLI
comparisons against unchanged rc1 JSON and artificial controls. Documentation
clarifications are in `4836824`; runtime/test bytes did not change. C independently accepted A's rc2 package and installed assertions, checking both
archives, 143 source/contract files, all 64 outputs, 68 wheel RECORD entries and
all 42 cells across ten saved CSV rows. Exact rc2 platform CI remains pending;
prior rc1 success cannot replace it. These are branch
artifacts, not a published release or consumer admission.

The completed PCC 6803 acquisition used frozen **0.12.0rc1** source
`356abc2d40198a95f807967a38126a14b0f3d0c9`; its independent biological analysis
is separate. Do not inherit that evaluation onto this package by version name.
No UTEX calibration, recoding-effect accuracy, current hosted equivalence,
complete Operon inference or sequence-to-switch prediction is established here.

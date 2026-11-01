# Provisional engineering package 0.16.0rc1

- Purpose: Install bounded multi-target RBS design alongside the admitted calculator components.
- Scope: Local software gates pass; independent implementation/package review, platform CI, scientific evaluation, consumer admission and publication remain separate.
- Last verified: 2026-11-01

## Frozen source and artifacts

The [receipt](../../models/integration/0.16.0rc1/package.json) binds source
`7b4ae1e43297d2c70b54286776eee191e32753e4`. It adds
[multi-target RBS design](rbs-vector-design.md) to the
[0.15 engineering package](engineering-0.15-candidate.md), with the new command
`regsite-rbs-vector-design`. Existing native equations, source/parameter identities
and the five-kind job runner remain unchanged. The held eight-kind dispatcher
is absent. Neither new implementation nor package review is yet accepted.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 226,554 | `cdbcc73ef79487edd1a270631ad1f244c2e749342cd7473cf5d6a6ebff42d757` |
| Source | 5,521,876 | `93c72e9b947bea5635627d866f10b4608a7dfef37c498940d159ce46d1d0782d` |

Execution-host artifacts are preserved in
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.16-candidate-installed`.
The external receipt SHA256 is
`dd2e228daa052f9cb24236798603fbdda1f9f3334761a4229a1e189710b8e1a4`.
All **67 runtime files** match source, wheel and fresh installation; all
**78 schema/example files** match the source archive. Fifteen command entry
points are available. No native executable or thermodynamic/background table
is bundled. No compressed rebuild identity is claimed. Reuse the
[locked offline installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction).

```sh
regsite-rbs-vector-design /source/examples/rbs-vector-design.json --backend-root /absolute/RNAstructure
regsite-promoter-design /source/examples/promoter-design-single.json
regsite-conditional-sweep /source/examples/conditional-sweep.json
```

The new request supplies one transcript, one to ten ordered CDS intervals,
component-relative initiation targets and explicitly permitted upstream edits.
Every coding interval is immutable, including overlaps. The entire admitted
neighborhood contains at most 64 candidates and two substitutions. Complete
successful target vectors are ranked by mean absolute natural-log target error;
every failure or unstarted candidate remains visible, and the proposed winner
is freshly confirmed. A complete search need not reach the requested targets.
This does not infer translational coupling, joint protein abundance or gene
annotations, and it does not establish biological improvement.

## Verification and interpretation

The combined local suite passed **7,992 tests and 1,551 subtests with zero skips**,
with 100% measured coverage of **19,712 statements and 7,020 branches**. Real
original RBS/conditional and termination backends were enabled. Eight existing
test-harness warnings concern module re-execution and a deliberate duplicate
archive name. Lint/format checks pass for 275 files; the documented typing checks
pass for 78 runtime/tool files plus the separately scoped evaluator.

That suite and static checks ran at `76feb514`. The package source differs only
in the installed comparison assertions: they now use the contracted resolved
float time budget and compare native results in their JSON wire representation.
Runtime code, unit tests and package metadata are identical. Source equivalence
is pinned in the receipt; the corrected installed assertions were executed in
the fresh installation from the exact package source.

The complete CI installed-example body passes offline without PYTHONPATH,
producing **74 saved outputs**, with empty smoke stdout/stderr. New artificial
controls exercise plus/minus multi-target searches and an invalid candidate cap.
Every candidate is compared against a direct unchanged installed scorer call;
the checks cover rosters, full native payloads, constraints, objectives, ranks,
fresh confirmation and hashes, plus reflected start coordinates and equal
component quantities across strands. These are engineering controls, not
experimental measurements or evidence of native-host calibration.

The new implementation at `953906a` has 259 focused tests with full coverage of
304 statements and 62 branches. Saved real native controls also pass final
admission replay and request/result schema validation. Independent review by
existing C and exact-source platform checks are pending; self-tests do not
replace them. A retains the separate final integration gate. No release tag,
package publication, main merge or consumer admission follows from this receipt.

The PCC 6803 scientific acquisition remains frozen at **0.12.0rc1**, source
`356abc2d40198a95f807967a38126a14b0f3d0c9`, with B's independent analysis separate.
Do not transfer its evaluation to this package by version name. Native UTEX
calibration, recoding-effect accuracy, current hosted optimizer parity, complete
Operon behavior and sequence-to-switch prediction remain unestablished.

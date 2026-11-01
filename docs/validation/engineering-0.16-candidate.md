# Provisional engineering package 0.16.0rc1

- Purpose: Install bounded multi-target RBS design alongside the admitted calculator components.
- Scope: Local, fresh-install and platform software gates pass; independent implementation/package review, scientific evaluation, consumer admission and publication remain separate.
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
admission replay and request/result schema validation.

[Platform run 41276194527](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/41276194527)
passed all eight jobs at `22f881eb02f985350101374b21a40432586638b2`, whose
runtime, tests, schemas, package configuration and workflow equal the frozen
package source. macOS 14 and Ubuntu 24.04 each passed Python 3.11 and 3.14
runtime and Promoter resource jobs. Each runtime job passed 7,991 tests with one
declared original conditional structural-pair skip, both 3,492-test repaired
backend selections, and the fresh offline installation. The separately admitted
original conditional pair passed in the local zero-skip suite. Every measured
statement and branch is covered on each platform; statement totals vary with
Python version and are recorded separately in the receipt.

Independent implementation and package review by existing C remain pending;
self-tests and CI do not replace those reviews. A retains the separate final
integration gate. No release tag, package publication, main merge or consumer
admission follows from this receipt.

## Resource control and saved-output checks

One predeclared artificial search exercised the maximum roster of 64 candidates
and ten targets on a 655-base transcript, with one allowed substitution among
21 upstream positions. All 64 candidates and all ten targets per candidate
succeeded. A fresh confirmation brought the total to 65 native record calls;
every coding interval stayed fixed and the nine unaffected downstream sites
retained their complete native results.

The run took 319.628 seconds, produced 3,624,395 JSON bytes and reached 12,053,508
peak traced Python bytes, including serialization but excluding native-process
memory. It used the original RNAstructure 6.6 backend, historical profile,
37 degrees Celsius, null host, 20 seconds per native record and a 600-second
cooperative total deadline. The receipt includes the exact artificial request,
predeclared plan and immutable request/result/script hashes; raw output stays
outside the repository in `vector-resource-64x10/` beside the package artifacts.
Reproduction uses that request with the installed `regsite-rbs-vector-design`
command and the matching admitted backend. This is one maximum-roster case,
not worst-case sequence or structure complexity, a performance guarantee, or
biological evidence.

The saved plus-strand, minus-strand, semantic-cap-refusal and maximum-roster
outputs also pass the frozen request/result schemas. All 75 retained native
records, containing 670 native sites, pass the original native-result schema.
The cap-refusal request is syntactically valid and fails semantic preflight as
intended. These checks used saved bytes without another scoring invocation.

The PCC 6803 scientific acquisition remains frozen at **0.12.0rc1**, source
`356abc2d40198a95f807967a38126a14b0f3d0c9`, with B's independent analysis separate.
Do not transfer its evaluation to this package by version name. Native UTEX
calibration, recoding-effect accuracy, current hosted optimizer parity, complete
Operon behavior and sequence-to-switch prediction remain unestablished.

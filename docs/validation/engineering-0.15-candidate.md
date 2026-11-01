# Engineering package 0.15.0rc1

- Purpose: Install bounded RBS and Promoter design alongside admitted calculator components.
- Scope: Software verification; scientific evaluation, consumer admission and publication remain separate.
- Last verified: 2026-11-01

## Frozen package and installation

The [receipt](../../models/integration/0.15.0rc1/package.json) binds exact source
`597edc4ef9b965b661e019cb8dffaa01d361a03c`. It adds the independently accepted
[Promoter design wrapper](promoter-design.md) to the
[0.14.0rc2 engineering package](engineering-0.14rc2-candidate.md). Native model
equations, source/parameter identities and the five-kind job interface are
unchanged. The held eight-kind component dispatcher is absent.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 218,203 | `d76be00b056716f388be15375daf14d52972379155bf46869ea5615a36da5eac` |
| Source | 5,479,549 | `1335165c628fe1c07ada515d21df331e16a5fac61eeabe399eca6f4d9174d354` |

Execution-host artifacts are in
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.15-installed`.
Preserve both archives, receipt, installed-byte check and saved outputs.
All 65 runtime files match source, wheel and fresh installation; all 75
schema/example files match the source archive. Fourteen command entry points
are available. No native binary or thermodynamic/background table is bundled.
Compressed rebuild identity is not claimed. The
[locked offline installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction)
requires no hosted account, coins or runtime dependency download.

```sh
regsite-promoter-design /source/examples/promoter-design-single.json
regsite-design /source/examples/rbs-design-single.json --backend-root /absolute/RNAstructure
regsite-conditional-sweep /source/examples/conditional-sweep.json
regsite-drafting /source/examples/drafting-batch.json --format csv
```

Promoter design enumerates the entire admitted neighborhood, at most 64 DNA
candidates and two substitutions, against one to eight nominated TSS targets.
It ranks complete successful score vectors by mean absolute natural-log error,
retains every failed/unstarted candidate and freshly confirms its proposed
sequence. Targets describe the selected historical model/calibration. They are
not measured rates, and complete search does not mean a target was reached.
All unlisted bases remain fixed; callers must explicitly lock coding bases.
No gene inference, synonymous-recoding guarantee or expression-gain claim is made.

## Verification and boundaries

The combined local suite passed **7,733 tests and 1,551 subtests, zero skips**,
with 100% measured coverage of **19,408 statements and 6,958 branches**. Real
original RBS/conditional and termination backends were enabled. Eight existing
test-harness warnings concern module re-execution and a deliberate duplicate
archive name. Required lint/format checks pass for 268 files; documented typing
checks pass for 76 runtime/tool files and the separately scoped evaluator.
This does not claim repository-wide type-check coverage.

Fresh offline installation ran the complete CI installed-example body from an
external snapshot without PYTHONPATH. Every command/assertion passed, with
**69 saved output files** and empty smoke stderr. New controls check both-strand
Promoter targets, neutral-edit tie selection, explicit locked bases, all native
results/hashes, full roster/objective/confirmation and an invalid candidate-cap
refusal. These are artificial software cases, not experimental observations.

A independently accepted C's exact implementation `87510bdf` after reading its
bounded delta and running 42 controls prepared against the unchanged prior
installed scorer. C's 179 focused tests have full new statement/branch coverage.
Independent review of A's package integration and the exact 0.15 platform CI
remain pending. Prior package checks cannot replace either gate. These are
branch artifacts, not a published release or production consumer admission.

The PCC 6803 acquisition used frozen **0.12.0rc1** source
`356abc2d40198a95f807967a38126a14b0f3d0c9`; B's independent biological analysis
is separate. Do not transfer that evaluation to this version by name.
No native UTEX calibration, recoding-effect accuracy, current hosted optimizer
parity, complete Operon model or sequence-to-switch prediction is established.

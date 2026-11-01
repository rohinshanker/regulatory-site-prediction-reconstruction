# Engineering package 0.17.0rc1

- Purpose: Install the reviewed local calculator suite and its bounded export/design interfaces.
- Scope: Frozen engineering package; scientific evaluation identities, consumer admission and tagged/registry publication remain separate.
- Last verified: 2026-11-01

## Identity and installation

The [package receipt](../../models/integration/0.17.0rc1/package.json) binds source
`7446866cdfdcedcccaca6d97573dbf38c0868312`. This includes the independently accepted
0.16rc2 confirmation repair and adds the [coupling CSV projection](coupling-tabular-export.md).
Other model equations, parameters, schemas, dependencies and the five-kind job
runner are unchanged from the accepted 0.16rc2 package. The implementation version
and derived identities change explicitly; old scientific results retain their
original candidates.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 229,034 | `5b687ae11dc3568f53f85c14c609b39042b1a27bef29bcd51f149a7770a4a18e` |
| Source | 5,572,632 | `609f36e4c059e1657c6ed30fffd8103615cf4a2c7b5db843b1f22fe7b1af1726` |

The execution-host artifacts are in
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.17-installed`.
The build/install receipt is 39,833 bytes with SHA256
`5df44127127394873d4486059cf8fc534a2899299c0ccd6c7fd159f2e97a6b9f`.
All 68 runtime files match source, wheel and installation; all 78 schema/example
files match the source archive. Fifteen commands are installed. The wheel has no
required Python runtime dependencies and bundles no native backend or table.

Use the [offline installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction)
with these archives, or build from the pinned source. Install native backends
separately under their [source/licence and build contracts](rbs-runtime.md#installation-and-reproducibility).
The following supplied-energy commands need no folding installation:

```sh
regsite-coupling /source/examples/coupling-single.json
regsite-coupling /source/examples/coupling-batch.json --format csv
regsite-coupling /source/examples/coupling-unsupported.json --format csv
```

The unsupported control exits 1 while retaining its record. CSV contains one
result row and every native record in producer order, with 58 columns preserving
nulls, both coordinate representations, supplied energies, score/log pairs and
native identity references. Keep JSON for the complete model, settings and
warnings; CSV is not a round-trip interchange format or a new scoring method.

## Verification and merge gate

At the frozen source, **8,024 tests and 1,551 subtests pass, zero skips**, with
100% measured coverage of **19,766 statements and 7,036 branches**. The real
admitted original RBS/conditional and termination backends are enabled. Eight
existing test-harness warnings remain. Lint/format checks cover 277 files; typing
passes for 79 files plus the separately scoped evaluator. The committed-doc check
covers 139 Markdown files and 759 relative file targets, with no broken targets;
it does not validate external URLs or anchors.

Fresh offline installation without PYTHONPATH passes the exact CI smoke body:
**77 saved outputs**, empty streams, 78.271 seconds. The three added CSV outputs
are compared with their native JSON, including both strands and unsupported
records. Existing single/batch, supplied-component, design, resume and failure
controls remain exercised.

Independent native Codex review accepted both the exact source changes and the
new archive/install/output identities without findings. The final package-review
receipt SHA256 is `f5a77180bf2d4b70eeb28a749ed96021b0d02c27f77fe85442f265cab6b72c1e`.
This reuses earlier implementation reviews and does not claim new scientific
validation. The separate installed-CI delta review receipt SHA256 is
`462daafbf7e3c0b3b2b98a76920df7d3b84622249c4808696be4a51c6ca8fc11`.

Before main integration, require the complete eight-job workflow on the final
PR head: Ubuntu 24.04/macOS 15, Python 3.11/3.14, runtime and resource jobs.
Check the exact commit and every conclusion; an earlier passing candidate does
not satisfy a changed runtime. Later documentation-only changes can retain this
frozen archive identity only after a byte comparison of source, tests, schemas,
examples, dependencies and workflow plus fresh documentation checks.

## Scientific and delivery limits

The [native PCC 6803 report](rbs-native-development-recheck.md) belongs to frozen
0.12.0rc1 and reports weak consumed-study associations. Neither this package nor
successful searches establish UTEX calibration, recoding-effect accuracy, protein
production, current hosted equivalence or superior biological designs. Full
Operon inference and sequence-to-switch prediction remain incomplete. B's #81
independent coupling evaluation is still open; its partial checker is excluded.
Held #68 dispatch and the separately held cyano preview remain excluded. This
source integration does not publish a tag, registry package or consumer website.

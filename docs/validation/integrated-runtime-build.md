# Integrated development runtime

- Purpose: Reproduce the combined local calculator package while preserving earlier immutable candidate identities.
- Scope: Historical/refined RBS, historical Promoter, paired comparison, supplied-transcript orchestration and bounded conditional-aptamer components; no release or consumer admission.
- Last verified: 2026-10-21

The [package receipt](../../models/integration/20261021/package.json) binds source
`2f68daa2df6a9681ef7f11a116f52ffbdb1c13d9`, all 41 wheel runtime members and the
produced archives. This development build combines the reviewed supplied-transcript
component with the original-backend installer, unchanged-output Promoter
optimization and independent native-pilot tooling. Version `0.8.0rc1` remains a
development identifier: use the full source and artifact hashes to distinguish
this build from the earlier [frozen transcript candidate](transcript-0.8-candidate.md).
It neither replaces that candidate nor transfers its admission to new bytes.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Python wheel | 146,699 | `62120453d94e38d9c54152b271cf193ef65c23137849aa17c15a7da8e9bf27e9` |
| Source distribution | 5,006,989 | `245ce7d9afb26e823f981072d4562a032839857a2ad7a03917dcf64a641589d7` |

The execution-host archive root is
`/Users/Rohin/.cache/regsite-integrated-runtime-20261021`. Preserve the archives,
`package.json`, `offline-smoke.json` and their build/check drivers together when
relocating them. Archive hashes identify those produced containers; a byte-identical
tar/gzip rebuild is not claimed. No executable backend or native per-record pilot
report is inside the wheel. The source distribution includes both new benchmark
tools, tests, pinned manifests and the separate backend licence.

## Build and install offline

Use a clean checkout of the source commit, the locked development tools and
`SOURCE_DATE_EPOCH=1792611571`. With those tools already available:

```sh
SOURCE_DATE_EPOCH=1792611571 python -m build --no-isolation
python -m venv /external/fresh-runtime
/external/fresh-runtime/bin/python -m pip install --no-index --no-deps dist/*.whl
```

Run outside the source tree with `PYTHONPATH` and `PYTHONHOME` unset and
`PYTHONNOUSERSITE=1`. The package has no third-party Python runtime dependency.
RBS-based commands require the separately installed, identified RNAstructure
executables in the [runtime contract](rbs-runtime.md). The structural conditional
profile retains its exact original-binary admission rule; building another
original backend does not satisfy that gate.

The fresh installed check ran 22 commands across all seven entry points. It
exercised real RBS single/batch execution and all five mechanistic profiles;
native-coordinate and learned-model examples; Promoter single/batch/GFF3;
unchanged, indel and RBS paired comparisons; all three supplied-transcript
examples; and both portable conditional-energy examples. JSON schemas and
transcript identities passed. CSV rows bound the complete paired/transcript
JSON hash. Unsupported/no-candidate records remained visible, an incompatible
transcript retained its partial exit 1, and invalid UTF-8 returned exit 2.
The installed module path was inside the fresh environment. These are software
and artificial-example checks, not new biological evaluation.

## Verification boundary

The full combined suite at `e15ce2acbc6ead9101ce1b00e1dcff819d861327` passed
5,658 tests with zero skips and 100% of 15,140 measured statements and 5,904
branches. Ruff, formatting and mypy passed. Real original and conditionally
admitted folding binaries were enabled. The package source has identical runtime,
tests, tooling and frozen parameters; subsequent changes add documentation and
the external-artifact manifest. Independent reviews admitted the exact transcript
integration, source-parity checker and count evaluator. The existing installer
branch tests separately cover 126 statements and 56 branches at 100%.

Use the repository CI on the exact proposed integration head to verify supported
Python/platform combinations and the unchanged resource limits. Local success
does not stand in for a remote CI result, a public release, or consumer approval.
The [native pilot](promoter-native-pilot-results.md) separately establishes
historical-source fidelity and reports weak native count association. It supplies
neither current hosted equivalence nor calibrated cyanobacterial predictions.

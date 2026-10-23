# Offline jobs development package

- Purpose: Install and verify the reviewed external-artifact job runner with the existing local calculators.
- Scope: Exact `0.10.0rc1` development package; no new biological model, consumer admission or publication.
- Last verified: 2026-10-21

The [package receipt](../../models/integration/0.10.0rc1/package.json) binds source
`95e95e0db455df332df6bf7b12e6eb4f03c39cf5`, all 46 wheel runtime files and the
archives below. Earlier frozen candidates, including
[coupling 0.9](coupling-0.9-candidate.md), remain unchanged. Intrinsic termination
is absent from this package.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 169,659 | `d0573aac9d03560512998f3799f76d236f4bba6cc79edb22087cd4825e9b626b` |
| Source distribution | 5,134,838 | `9e953e9d72572e957db4c81e3dedaa9e19b86950f9b4235612d9cdc19f769f2a` |

The execution-host archive root is
`/Users/Rohin/.cache/regsite-wave7-integration-20261021/jobs-0.10-installed`.
Preserve `dist/`, `receipt.json` and the example campaigns together when relocating
them. Archive hashes identify these produced files; a byte-identical compressed
archive rebuild is not claimed. Full native outputs remain external.

## Installation and reproduction

Check out the exact source and use the locked development tools:

```sh
python -m build --no-isolation
python -m venv /external/jobs-runtime
/external/jobs-runtime/bin/python -m pip install --no-index --no-deps dist/*.whl
/external/jobs-runtime/bin/regsite-jobs run --manifest /source/examples/jobs-synthetic/manifest.json --output-dir /external/new-campaign
/external/jobs-runtime/bin/regsite-jobs verify --manifest /source/examples/jobs-synthetic/manifest.json --output-dir /external/new-campaign
/external/jobs-runtime/bin/regsite-jobs resume --manifest /source/examples/jobs-synthetic/manifest.json --output-dir /external/new-campaign
```

Replace the absolute placeholders with existing parent/source paths; the new
campaign directory must not already exist for `run`. Run outside the source
tree with `PYTHONPATH` and `PYTHONHOME` unset. The synthetic manifest runs Promoter
and supplied-energy conditional requests without a folding engine. The separate
`examples/jobs-backend/manifest.json` covers RBS, paired RBS and supplied-transcript
requests; provide an explicit admitted `--backend-root` to `run` and `resume`.
The installed check used the separately identified RNAstructure linker-3 variant
for those three requests. It did not broaden conditional backend admission.

Read the [job contract](offline-calculator-jobs.md) before interpreting results.
`succeeded` means the existing command exited zero within the declared checks;
the runner keeps outputs opaque and does not assess scientific accuracy. Resume
requires the exact runtime identity and does not repeat verified terminal jobs,
including terminal failures. Native calculator limits remain unchanged.

Calculator execution is supervised. Identity checks and filesystem operations
use cooperative deadlines with the documented overhead. Captured-output limits
are accounting bounds, not an OS disk quota; native scratch is outside them.
Receipts bind bytes and declared identities, not authenticity or predictions.

## Validation boundary

Independent review and focused repair rechecks cover runner
`136d6ffbcdb741776992a462c6742d892395f063`, including crash/restart ownership,
accepted bytecode identity, truncated/error output accounting, special files,
deadline reporting and authoritative resume. The runner's 199 focused tests
cover all 844 new statements and 178 branches. Reused independent reviews cover
the unchanged coupling component and B's public Wave4 receipt checker.

The complete local suite at the exact package source passed 6,341 tests, with
zero skips, eight warnings and 100% measured coverage of 16,623 statements and
6,282 branches. Ruff, formatting and mypy passed. Original RNAstructure and the
separately admitted exact conditional backend were enabled.

The fresh package passed 18 checks: build/install, reinitiation single/batch and
error/Unicode cases, and both example campaigns through run, verify and resume.
Every request had exactly one attempt after resume. Deliberately changed owned
output bytes caused corruption refusal; restoring them restored verification.
All 46 installed runtime files matched source bytes. These software cases do
not establish native biological accuracy or hosted equivalence.

[Exact-source CI](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39694268202)
failed its Linux/Python 3.14 job because a test assumed process group 1 was
absent or inaccessible. That assumption does not hold on the GitHub runner.
The replacement test uses a simulated permission error and a reaped process
group owned by the test; runner logic is unchanged. This original candidate is
not CI-approved. The correction is being validated as `0.10.0rc2`; its package
receipt is separate. Main merge, release/tag publication and consumer admission
remain separate gates.

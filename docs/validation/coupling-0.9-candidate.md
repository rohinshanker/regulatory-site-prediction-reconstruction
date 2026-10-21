# Supplied-energy reinitiation development package

- Purpose: Reproduce the independently reviewed reinitiation component in a fresh local package.
- Scope: Explicit adjacent-CDS geometry and caller-supplied initiation energies; no full Operon, native calibration, release or consumer admission.
- Last verified: 2026-10-21

The [package receipt](../../models/coupling/0.9.0rc1/package.json) binds source
`c74ff8fac2331ba1e1e1836d953ea69036133b85`, all 45 wheel runtime files and the
produced archives. This is a separate `0.9.0rc1` development candidate; earlier
RBS, Promoter, paired, transcript and conditional candidates remain immutable.
The separate offline job runner and intrinsic-termination proposal are absent
from this candidate.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 154,389 | `2c9a16b3a68ca90ddbc5be3d42d3b089bcfe80fc564989a4c766bb33bfc00643` |
| Source distribution | 5,051,834 | `93effbd16311dbc5f8e00f6d4f53686b9d832e24dbc6831a811f17127c552be1` |

The execution-host archive root is
`/Users/Rohin/.cache/regsite-wave7-integration-20261021/coupling-0.9`.
Keep its archives, `receipt.json` and build/check driver together when relocating
them. Container hashes identify these exact produced files; a byte-identical
compressed archive rebuild is not claimed. Full example outputs remain external.

## Installation and use

With the locked development tools available, check out the exact source and run:

```sh
python -m build --no-isolation
python -m venv /external/coupling-runtime
/external/coupling-runtime/bin/python -m pip install --no-index --no-deps dist/*.whl
/external/coupling-runtime/bin/regsite-coupling examples/coupling-single.json
/external/coupling-runtime/bin/regsite-coupling examples/coupling-batch.json
/external/coupling-runtime/bin/regsite-coupling examples/coupling-unsupported.json
```

Run outside the source tree with `PYTHONPATH` and `PYTHONHOME` unset. Reinitiation
uses only the Python standard library and no folding engine. The unsupported
example intentionally exits 1 with a retained unsupported-distance record and
null scores. Supported zero-energy controls return total scores 1.072 at distance 0
and 1.22 at the −4 overlap, including the reverse-strand example. These values test
arithmetic and coordinate handling, not biological accuracy.

Read the [source boundary](operon-coupling-source.md) and
[runtime contract](operon-coupling-runtime.md) before supplying energies. Their
common convention is caller-declared and cannot be verified from a number alone.
The unresolved published RNA-unfolding expression remains outside this component.

## Verification boundary

Independent source/math review and exact implementation repair review cover
code `180d8bd41f4ac34205939e83f25da1cc10974ae5`. The component's 274 tests cover every
new statement and branch. The fresh package check passed build, installation
and five CLI cases: single, batch, unsupported geometry, the original 100-record
Unicode transport regression, and malformed-input refusal. All 45 installed
runtime files match the source bytes.

The combined local suite at the exact package source passed 5,932 tests, with
zero skips, eight warnings, and 100% coverage of 15,365 measured statements and
5,970 branches. Ruff, formatting and mypy passed. Real original folding and
the existing exact admitted conditional binaries were enabled for the old
components. Those checks do not expand conditional backend admission.

[Cross-platform CI](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39689533173)
is recorded separately and was pending when this receipt was written. Local
success does not establish a remote CI result, hosted equivalence, cyanobacterial
accuracy or consumer approval. Main merge, package/tag publication and consumer
admission remain separate gates.

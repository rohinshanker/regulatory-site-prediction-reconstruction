# Conditional 0.7.0rc1 candidate

- Purpose: Reproduce the admitted conditional-state and supplied-energy package with explicit numerical and backend boundaries.
- Scope: Immutable development candidate; no full sequence-to-switch or native efficacy claim.
- Last verified: 2026-10-18

Source `163802fddd3e49c8d72380167d661c7d8291f41b` is frozen in
[draft PR46](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/46).
The [candidate receipt](../../models/conditional/0.7.0rc1/candidate.json) binds
source, schemas, parameters, exact-patch review and installed execution. Runtime
semantics are in the [conditional contract](conditional-aptamer-runtime.md);
the [independent equation contract](conditional-aptamer-contract.md) and canonical
fixtures establish the admitted mathematical components.

| Artifact | SHA-256 |
| --- | --- |
| Wheel | `9aeaeb5b636247768f1ea34e871fb3269f3f2ea419d39df76976dc483967b17d` |
| Source archive | `cf9bbb7640809cecdd5c9d64fcb93d27c69b02eae85559fc862c1c64bcaf09fb` |
| Installed execution receipt | `1026d320a470268786f47df0bb2a8844e226bbb2d666c832a9ca5dfd954de1fa` |
| Parameters | `99bb08423e2d321947e1cf5bb8cc3061bd99ab02414bff4d25377b5003f51b3f` |

The wheel contains independently expressed GPL-3.0-or-later Python code and no
folding executable. Every wheel runtime member matched the clean source manifest.
The original GPL-2.0-only RNAstructure installation remains separate. Install
with `pip install --no-index --no-deps WHEEL.whl`, clear `PYTHONPATH` and
`PYTHONHOME`, disable user sites, and run outside the source tree. All nine saved
[requests](../../models/conditional/0.7.0rc1/requests/) have corresponding full
[outputs and timing records](../../models/conditional/0.7.0rc1/outputs/).

```sh
regsite-conditional examples/conditional-supplied-half-occupancy.json
regsite-conditional examples/conditional-supplied-volume-fifth.json
regsite-conditional examples/conditional-hairpin-structure-control.json --backend-root /path/to/admitted/original/RNAstructure
```

The scalar profile needs only Python. The structural profile currently requires
the exact independently verified original macOS arm64 Fold/efn2/table identities;
other platform builds must pass independent canonical fixtures and receive a
separate admission before use. General platform builds are not implicitly allowed.
No shared-library linking or proprietary dependency is introduced.

## Validation and numerical limits

Exact runtime/CLI/schema integration `624fa4f` passed independent final review,
476 tests, and 100% of 747 statements and 320 branches. Regression checks cover
energy cancellation at the strict-positive discontinuity, certified Kd branch
agreement, unrounded composite volume-root enclosures, malformed modes and a
real closed-output-pipe subprocess. Unresolved arithmetic refuses with retained
independent components. Scalar values within a certified branch remain binary64
approximations; the documentation does not claim interval-certified response ratios.

The fresh installed package passed all three examples and six fixed synthetic
resource/boundary cases. All nine results validate against the public schema.
Known scalar ratios are 2.5 and 8/7; the hairpin control's efn2 energy is -11.2
kcal/mol. Four structural requests used 16 sequential executable jobs in total.
Deadline and one-iteration cases failed explicitly with complete diagnostic JSON.
On macOS arm64/Python 3.14.7, the largest output was 14,513 bytes, peak whole-process
RSS was 85,458,944 bytes and the slowest call was 0.477 seconds. These single-run
samples include 200-nt full, unpaired and no-op constraints. They are finite
checks, not worst-input guarantees, experimental validation or an OS memory quota.

The [installed receipt](../../models/conditional/0.7.0rc1/receipt.json) preserves
exact input/output/raw-timing hashes, exit codes, process counts, source epoch and
artifact identities. Reproduce timing with macOS `/usr/bin/time -l` around each
CLI call; retain failures rather than rerunning them selectively. Do not rewrite
the frozen receipt. The source archive identity is recorded; bit-identical
rebuilding of its tar/gzip container has not been claimed.

All eight jobs in [CI39183611595](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39183611595)
remain an explicit final package gate. The scalar profile runs fresh offline
on Linux/macOS and Python 3.11/3.14 in that matrix. Structural portability is not
inferred from those scalar checks. Final successful CI must be recorded separately
before claiming full package admission. Parent #9 retains constrained ribosome
states, pseudoknots, ligand/steric inference, native calibration and full switch
prediction; this candidate supplies neither a discovery tool nor a recoding optimizer.

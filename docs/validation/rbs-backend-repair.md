# RNAstructure traceback repair admission

- Purpose: Install, identify and validate the separate repaired folding engine.
- Component: rnastructure-6.6-traceback-1, GPL-2.0-only.
- Source: RNAstructure 6.6, archive SHA-256 1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3.
- Patch SHA-256: 01307e31001131c5693a99e4fe50db8a251c75ccde72e9049c07e94c6e456a10.
- Patched algorithm.cpp SHA-256: 5b1f4e4aa87c8e5d058e2787bd7da7dc12ba42bf443a718ab51859cd4eb52de4.

## Scope and scientific identity

The [separate component](../../backends/rnastructure66/README.md) repairs
intermolecular traceback state transitions in algorithm.cpp. It retains the
upstream dynamic-programming recurrence, thermodynamic tables and enumeration
limits. It does not discard invalid candidates, guess replacement base pairs,
or substitute missing energies. Source analysis and independent structural
fixtures are in that component; its GPL-2.0-only implementation remains outside
the GPL-3.0-or-later Python package and communicates through ordinary files and
standalone processes. The repository/source distribution includes the separately
licensed patch/build component; the Python wheel does not bundle its code or
executables. Preserve corresponding source and notices with any separately
distributed engine binaries.

The repair prevents multiple tied decompositions from entering one traceback and
keeps constrained intermolecular WMB2 states distinct from unrestricted W2 and
ordinary WMB states. Correcting an earlier trace may change subsequent candidate
enumeration, even when the original output happened to be reciprocal. Therefore
this is an explicit new backend variant, not a transparent replacement. Model
parameters and backend identity remain separate: any mechanistic profile can use
the selected installation, but the prediction identity and backend warning change.
The original installation and frozen Wave2 artifacts remain intact.

## Installation and verification

Use a fresh user-owned directory and an already installed compiler/SDK. The
builder refuses an existing destination, verifies source and patch identities,
validates archive paths, applies with zero fuzz and verifies the patched source
before compiling with at most two make jobs. It needs no administrator access.
If a compiler/SDK is missing, disclose that separate installation requirement
before attempting any privileged action.

```sh
python3 backends/rnastructure66/build.py \
  --archive /path/to/pinned/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-1 --jobs 2
export REGSITE_RNASTRUCTURE=/new/user-owned/rnastructure66-traceback-1/RNAstructure
.venv/bin/regsite examples/rbs-single.json --profile standby2014
.venv/bin/regsite examples/rbs-batch.json --profile standby2014
```

The source archive is available from the [official versioned release](https://rna.urmc.rochester.edu/Releases/rnastructure-6.6/RNAstructureSource.tgz).
The builder writes traceback-build.json beside the source/executables. At runtime,
all 45 pinned RNA parameter files and all three version strings are checked as
before. If that receipt is present, the adapter additionally requires the known
component/licence/source/patch identities, current executable hashes, matching
recorded parameter hashes and the retained patched source hash. A malformed or
inconsistent receipt fails admission; it does not fall back to upstream identity.
Receipt parsing is limited to 500,000 bytes. The result includes variant,
build_provenance and the exact receipt-byte hash alongside executable/table
identities. These are reproducibility checks, not a signed build attestation.
An installation without the receipt retains the original adapter behavior and
explicit expected-source/binary hashes; binary ancestry is not thereby proven.

Frozen learned models remain unchanged. Their existing backend/model signature
check warns when energy features come from another installation or model revision.
Do not treat such inference as a reproduction of the frozen training calculation.
Sequence-only learned inference remains independent of the folding backend.

## Validation gates and limits

Run the component's independent checker against **both** installations, then the
full runtime suite with the repaired installation. Missing component-engine
variables fail instead of silently skipping tests.

```sh
RNASTRUCTURE66_ORIGINAL=/path/to/original/RNAstructure \
RNASTRUCTURE66_PATCHED="$REGSITE_RNASTRUCTURE" \
  python3 -m unittest discover -s backends/rnastructure66/tests -v
.venv/bin/python -m pytest --cov=regsite --cov=benchmarks.rbs \
  --cov=experiments.rbs --cov-report=term-missing
```

CI builds both versions, runs the component and runtime gates, then installs the
wheel in a fresh environment and runs offline single/batch examples with explicit
backend selection. The two-engine comparison is required because valid outputs
can change; unchanged controls alone do not establish full regression safety.
Source/patch pins and fixtures must not be changed merely to make a failing
platform pass. Diagnose differences before admitting a new variant.

The structural panel uses deterministic synthetic sequences and public
**development** sequences, never private final outcomes. Validity requires
complete sequence identity, reciprocal canonical pairs, noncrossing structure,
unpaired linkers and independent fixed-state reevaluation. Exact snapshots retain
native and reevaluated energies separately. The repaired backend still shows
DP-versus-efn2 discrepancies in some candidates; the runtime reevaluates all
returned structures with efn2 --simple and warns about differences. Consequently
neither global energy optimality, NUPACK equivalence, hosted equivalence nor
improved experimental accuracy follows from passing these gates. Existing bounded
search, window, time and missingness contracts remain applicable.

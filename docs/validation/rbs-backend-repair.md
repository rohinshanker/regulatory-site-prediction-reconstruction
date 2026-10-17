# RNAstructure traceback repair admission

- Purpose: Install, identify and validate the separate repaired folding engine.
- Scope: Separate GPL-2.0-only source, executables and runtime admission.
- Last verified: 2026-10-17
- Component: rnastructure-6.6-traceback-2, GPL-2.0-only.
- Source: RNAstructure 6.6, archive SHA-256 1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3.
- Patch SHA-256: 2d599e7fa9f6581b605350508163c4aa14458ebb8f444c096e5f923c8742d671.
- Patched algorithm.cpp SHA-256: 6300df34e26fe674b6e87260cee69617130c015910e3ed67fd1b45aa1e2dca6c.

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
keeps intermolecular W2/WMB2 states distinct from ordinary W/WMB states.
Each new state follows its own unchanged fill recurrence, including boundary,
dangle and modified-base guards. Correcting an earlier trace may change subsequent candidate
enumeration, even when the original output happened to be reciprocal. Therefore
this is an explicit new backend variant, not a transparent replacement. Model
parameters and backend identity remain separate: any mechanistic profile can use
the selected installation, but the prediction identity and backend warning change.
The original installation and frozen Wave2 artifacts remain intact.

## Installation and verification

Use a fresh user-owned directory and an already installed compiler/SDK. The
builder refuses an existing destination, verifies source and patch identities,
preflights the existing macOS developer-tool selection before any extraction,
validates archive paths, applies with zero fuzz and verifies the patched source
before compiling with at most two make jobs. It needs no administrator access.
If a compiler/SDK is missing, disclose that separate installation requirement
before attempting any privileged action.

```sh
python3 backends/rnastructure66/build.py \
  --archive /path/to/pinned/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-2 --jobs 2
export REGSITE_RNASTRUCTURE=/new/user-owned/rnastructure66-traceback-2/RNAstructure
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
native and reevaluated energies separately. The component gate additionally checks 14,000 extracted fill/trace transitions
with a compiled harness; its synthetic energy functions establish state
correspondence, not thermodynamic accuracy. The repaired backend still shows
DP-versus-efn2 discrepancies in some candidates; the runtime reevaluates all
returned structures with efn2 --simple and warns about differences. Consequently
neither global energy optimality, NUPACK equivalence, hosted equivalence nor
improved experimental accuracy follows from passing these gates. Existing bounded
search, window, time and missingness contracts remain applicable.

Session B’s independent [structural fixtures](rbs-structural-fixtures.md) include
an exhaustive tiny topology oracle. Native bifold omits two valid four-base duplex
topologies within 3 kcal/mol of the independently evaluated minimum. Repairing
traceback corruption does not make the bounded candidate search exhaustive.
Keep this candidate-coverage limitation separate from invalid-output failures.

A remaining ordinary-W/linker traceback failure is reproduced by synthetic seed
484, index 17, in the original and repaired engines. Both exit zero with errors
and no CT. This is outside the repaired W2/WMB2 transitions; [issue #26](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/26)
records the exact input, source-state trace and next repair scope. The adapter
returns failed with null scores/energies, including on reverse-strand input.
Independent review found 69/70 valid fresh searches after repair versus 66/70
original, with this one remaining failure retained in the denominator.

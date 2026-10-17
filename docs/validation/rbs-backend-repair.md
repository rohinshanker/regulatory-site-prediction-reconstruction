# RNAstructure repair admission

- Purpose: Install, identify and validate the separate repaired folding engine.
- Scope: Separate GPL-2.0-only source, executables and runtime admission.
- Last verified: 2026-10-17
- Components: rnastructure-6.6-traceback-2 and rnastructure-6.6-linker-3, GPL-2.0-only.
- Source: RNAstructure 6.6, archive SHA-256 1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3.
- Traceback-2 patch SHA-256: 2d599e7fa9f6581b605350508163c4aa14458ebb8f444c096e5f923c8742d671.
- Traceback-2 algorithm.cpp SHA-256: 6300df34e26fe674b6e87260cee69617130c015910e3ed67fd1b45aa1e2dca6c.

- Linker-3 patch SHA-256: 2ef6ef61496b034110f4151e2fc1aec77cbd011c88a36bcef574be0dfecebb2d.
- Linker-3 algorithm.cpp SHA-256: b19a9ad1634f7e8f7669410b1eb7f5e8c27542f073054acb65647891e62ddbc7.

## Scope and scientific identity

The [separate component](../../backends/rnastructure66/README.md) repairs
intermolecular traceback state transitions in algorithm.cpp. Traceback-2 retains
the upstream dynamic-programming recurrence. Linker-3 adds the missing linker-centre
marker to two ordinary WMB nucleotide-addition terms. Both retain thermodynamic
tables and enumeration limits. It does not discard invalid candidates, guess replacement base pairs,
or substitute missing energies. Source analysis and independent structural
fixtures are in that component; its GPL-2.0-only implementation remains outside
the GPL-3.0-or-later Python package and communicates through ordinary files and
standalone processes. The repository/source distribution includes the separately
licensed patch/build component; the Python wheel does not bundle its code or
executables. Preserve corresponding source and notices with any separately
distributed engine binaries.

The traceback-2 repair prevents multiple tied decompositions from entering one traceback and
keeps intermolecular W2/WMB2 states distinct from ordinary W/WMB states.
Each new state follows its own unchanged fill recurrence, including boundary,
dangle and modified-base guards. Correcting an earlier trace may change subsequent candidate
enumeration, even when the original output happened to be reciprocal. Therefore
this is an explicit new backend variant, not a transparent replacement. Model
parameters and backend identity remain separate: any mechanistic profile can use
the selected installation, but the prediction identity and backend warning change.
The original and traceback-2 installations and frozen Wave 2 artifacts remain intact.
Linker-3 is a separately selected cumulative component, never a replacement behind
the traceback-2 identity. Its ordinary fill correction can alter candidate lists
even when traceback-2 previously returned valid structures.

## Installation and verification

Use a fresh user-owned directory and an already installed compiler/SDK. The
builder refuses an existing destination, verifies source and patch identities,
preflights the existing macOS developer-tool selection before any extraction,
validates archive paths, applies with zero fuzz and verifies the patched source
before compiling with at most two make jobs. It needs no administrator access.
If a compiler/SDK is missing, disclose that separate installation requirement
before attempting any privileged action.

```sh
.venv/bin/python backends/rnastructure66/build.py \
  --archive /path/to/pinned/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-2 --jobs 2
export REGSITE_RNASTRUCTURE=/new/user-owned/rnastructure66-traceback-2/RNAstructure
.venv/bin/regsite examples/rbs-single.json --profile standby2014
.venv/bin/regsite examples/rbs-batch.json --profile standby2014
.venv/bin/python backends/rnastructure66/build.py \
  --archive /path/to/pinned/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-linker-3 --jobs 2 \
  --component rnastructure-6.6-linker-3
REGSITE_RNASTRUCTURE=/new/user-owned/rnastructure66-linker-3/RNAstructure \
  .venv/bin/regsite examples/rbs-standby-hairpin.json --profile joint_standby
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
Without a receipt, a retained `src/algorithm.cpp` must match the pinned pristine
upstream hash; patched or unknown source fails admission. This prevents a lost
receipt from silently relabelling a source-containing patched installation.
Binary-only installations retain the legacy expected-source/binary identity
behavior, and source files/receipts do not prove binary ancestry. A frozen
experiment must independently pin each actual executable's bytes before and after
collection, rather than trusting a self-reported receipt or source tree.

Frozen learned models remain unchanged. Their existing backend/model signature
check warns when energy features come from another installation or model revision.
Do not treat such inference as a reproduction of the frozen training calculation.
Sequence-only learned inference remains independent of the folding backend.

## Validation gates and limits

Run the component's independent checker against **all three** installations,
then the full runtime suite separately with each engine. Use Python 3.11 or newer;
a shell alias named `python3` may still point to an unsupported older interpreter. Missing component-engine
variables fail instead of silently skipping tests.

```sh
RNASTRUCTURE66_ORIGINAL=/path/to/original/RNAstructure \
RNASTRUCTURE66_PATCHED=/path/to/traceback-2/RNAstructure \
RNASTRUCTURE66_LINKER3=/path/to/linker-3/RNAstructure \
  .venv/bin/python -m unittest discover -s backends/rnastructure66/tests -v
.venv/bin/python -m pytest --cov=regsite --cov=benchmarks.rbs \
  --cov=benchmarks.promoter --cov=experiments.rbs --cov-report=term-missing
```

CI builds all three versions, runs the component and full runtime gates, then installs the
wheel in a fresh environment and runs offline single/batch examples with explicit
backend selection. The three-engine comparison is required because valid outputs
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

## Ordinary W/WMB linker correction

Synthetic seed 484, index 17 reproduces an ordinary-W failure in the original and
traceback-2 engines: both exit zero with errors and no CT. Linker-3 corrects its
source invariant. Only the centre linker base carries the `INTER` diagonal flag;
ordinary W strips add a 14,000 energy marker when removing that centre. Ordinary
WMB additions previously omitted it, creating a normal-scale ordinary-loop value
that W inherited but its traceback could not reproduce. Adding the same marker
to those two WMB additions preserves boundary/forced-double-strand guards and
leaves the W2/WMB2 exterior-loop recurrences and V closures unchanged. This is
an offset convention, not mathematical infinity. Full source reasoning and pins
are in the [component](../../backends/rnastructure66/README.md).

Independent exact-patch review covered commits `aaa0532c` and `945436ed`
(Multica DEM-513). It applied both cumulative patches independently to the pinned
archive, reproduced the failing cells, and checked 14 adversarial sequence/settings
cases, including swapped/reversed strands and 273.15–353.15 K. Linker-3 passed
14/14 versus 12/14 for traceback-2; across 102,546 instrumented fill cells,
normal-scale linker-edge violations fell from 3,054 to zero. Wrapped coordinates,
ordinary V values and UBSan were checked. Three multi-branch topologies absent
from bounded linker-3 enumeration remained reproducible under explicit constraints:
the guard does not globally prohibit a branch enclosing the linker.

The component's versioned fixtures cover 60 seeded synthetic, 12 development and
40 fresh synthetic inputs. Linker-3 yields valid output for all 112, preserves all
eight earlier fixtures, and changes 6/60, 1/12 and 2/40 outputs relative to
traceback-2 without changing their native minima. Candidate changes and native vs
reevaluated-energy discrepancies remain recorded. The old failed reproducer stays
an explicit null-score runtime regression on original/traceback-2; linker-3 must
complete it on both strands with context, standby and joint profiles.

The fix does not establish exhaustive enumeration, NUPACK/hosted equivalence or
experimental accuracy. Broader SHAPE, modified-base and constraint combinations
remain outside this scoped validation. Required gate commands above must pass
for each admitted build; the receipt is not a cryptographic provenance signature.

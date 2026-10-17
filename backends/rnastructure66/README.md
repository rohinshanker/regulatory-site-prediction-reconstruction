# RNAstructure 6.6 intermolecular traceback repair

This optional, separately installed **GPL-2.0-only** component repairs
intermolecular traceback in the pinned RNAstructure 6.6 source. It supplies a
source patch, an unprivileged builder and independent structural regressions.
It does not install into or modify the shared engine. The application continues
to communicate through standalone executables and sequence/CT files; no engine
source or library is copied into `src/regsite`.

`manifest.json` pins the upstream archive, original source file, patch and
patched source by SHA-256. The included `LICENSE` is upstream `gpl.txt`.
The full upstream source, `ReadMe.txt`, `gpl.txt`, attribution headers and data
tables remain in each independently built installation. Preserve that source
and its notices when distributing binaries. The component scripts and fixtures
are also GPL-2.0-only, an explicit exception to the repository-wide default.
The RNAstructure authors retain their original copyrights; the patch changes
only `src/algorithm.cpp`.

## Source diagnosis and contract

Two defects violate the traceback invariant: a stack item must select exactly
one decomposition from the recurrence of its own state, passing each child
that child's recorded energy.

1. In upstream `trace`, the paired `V` state tests an intermolecular `WMB2`
   decomposition even after another exterior/multibranch decomposition has
   set `found`. If energies tie, both decompositions enter the stack. They
   overlap, so subsequent `SetPair` calls overwrite one side of existing pairs.
   The new guard preserves the first already-selected decomposition.
2. `WMB2` (an intermolecular exterior fragment with at least two branches) shares
   the ordinary `WMB` state tag and incorrectly strips bases using unrestricted
   `W2`. Its left extension also compares a `WMB2` value but pushes a `W2`
   energy; extensions can run after a split was already chosen. This can lose
   the branch constraint, select multiple continuations or enter an impossible
   traceback state. A distinct stack tag traces `WMB2` directly. Ordinary `WMB`
   retains its own recurrence; `W2` delegates to `WMB2` when that alternative
   supplies its energy.

The new handler follows the existing fill recurrence at upstream lines
5450–5468, including the strand-boundary exclusions and linker adjustment:

```text
WMB2(i,j) = min(
    W2(i,k) + W2(k+1,j),                      k != N,
    WMB2(i+1,j) + linker_adjustment(i),       i != N,
    WMB2(i,j-1) + linker_adjustment(j),       j != N+1)
linker_adjustment(x) = init - INFINITE_ENERGY if INTER(x), otherwise 0
```

Each extension retains the `WMB2` tag and energy. Each split pushes two `W2`
fragments. The two child intervals are disjoint. Tests independently check
reciprocal canonical pairs, nesting, linker exclusion, exact sequence identity
and complete fixed-structure energy reevaluation.

The patch leaves the fill recurrence, thermodynamic tables, scientific
constants, percentage/diversity windows and requested traceback count intact.
It does not skip malformed candidates or repair CT pairs after prediction.
Correcting a traceback can change even a previously reciprocal output if that
output came from the wrong recurrence. Consequently this is a new backend
identity and requires a fresh model evaluation; it is not a byte-compatible
replacement or evidence of improved experimental accuracy.
Candidate-pair heap ordering is unchanged, but corrected traces can mark
different pairs and therefore change later enumeration and tie-resolved output.

## Reproductions and energy limits

The two public development inputs are read from
`benchmarks/rbs/karlsen2018-development.json`, using only the first 100 sequence
bases, normalized T→U, and `ACCUCCUUU`. Settings are:

```text
bifold leader.fa asd.fa output.ct --maximum 100 --percent 100 --window 0
       --loop 30 --temperature 303.15 --alphabet rna
```

- `karlsen2018:SGL_RS10810`: original structure 75 is nonreciprocal; the
  original raw CT SHA-256 is
  `5e1442afa77382fcc9d0cb1dbe6ca8c7632fba0c9b1bb5f7032f74acf2428891`.
  Instrumentation shows the exterior choice sets `found`, then the tied
  `WMB2` choice is pushed as well.
- `karlsen2018:sll0085`: original exit status is zero despite traceback error
  2 and no CT. The same duplicate `V` choice enters an invalid continuation.

Both repaired searches produce 100 valid structures. Synthetic inputs are
independent of those development sequences: Python `random.Random(6603)` draws
uniformly from `ACGU`, first 30 sequences of length 60, then 30 of length 100.
Frozen cases 30, 33 and 54 exercise pair corruption, duplicate continuation and
the state mismatch. The hand-checkable hairpin, unpaired strand and duplex are
unaffected controls. Their first evaluated energies are −1.2, 0 and −11.6
kcal/mol at 310.15 K; the hairpin has pairs (1,9), (2,8), (3,7).

`efn2 --simple` is a separate fixed-structure evaluation path, not an independent
thermodynamic parameter source. Its energies still differ from some native DP
energies: 32/100 and 39/100 structures in the two development reproductions,
respectively. Those mismatches are frozen explicitly, not converted into an
equality assertion or suppressed. They preclude claiming energy-objective
equivalence or a globally optimal search. Every emitted structure is reevaluated;
the simple controls agree exactly between DP and `efn2`. Fixture hashes exclude
machine paths and CT labels while retaining all ordered structures and energies.

## Reproducible installation

Prerequisites: Python 3.11+, an already installed C++ compiler, `make`, `patch`
and the pinned source archive. On macOS, already installed command-line developer
tools/SDK are required; the builder obtains the SDK with `xcrun` and sets both
SDK include flags. No administrator access, new developer tools, account or
network is needed when the archive is present. Inspect available memory and
disk before compiling; at most two make jobs are allowed.

```sh
python3 backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-1 \
  --jobs 2
```

The archive SHA-256 must be
`1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`.
The builder refuses an existing destination and a mismatched archive/patch,
validates archive paths, applies with zero fuzz, checks the patched source and
builds serial `Fold`, `bifold` and `efn2`. Failed builds remain for diagnosis;
retry into a new directory. The standalone engine root is
`/new/user-owned/rnastructure66-traceback-1/RNAstructure`.
Set `DATAPATH` to that root's `data_tables` when calling its tools directly.

`RNAstructure/traceback-build.json` records the source/patch identities, build
command, platform, machine, executable hashes and all installed table hashes.
The builder removes inherited make/architecture/compiler tuning variables.
Upstream's platform detection selects the target architecture; inspect the
build log and receipt, especially when Python or its subprocesses run under
Rosetta. `--no-optimize` adds upstream `optimize=off` for a fresh diagnostic
build. Every independently compiled executable has its own binary identity.

## Component gate

Run from the repository root; no third-party Python packages or application
imports are used. Both engine variables are mandatory and missing engines fail
the gate instead of skipping it. Keep the original installation read-only.

```sh
RNASTRUCTURE66_PATCHED=/new/user-owned/rnastructure66-traceback-1/RNAstructure \
RNASTRUCTURE66_ORIGINAL=/path/to/unmodified/RNAstructure \
python3 -m unittest discover -s backends/rnastructure66/tests -v
git diff --check
```

The gate exercises builder rejection contracts, checker corruption cases,
eight frozen fixtures, the full 60-input seeded synthetic panel and 12 unique
development leaders selected by normalized-sequence SHA-256 order. It reads no
experimental outcomes, private final tables or fitted models. The synthetic
panel requires 60/60 repaired searches valid against 54/60 original; 44 outputs
are identical and 10 originally valid outputs change. Exact snapshots,
including energy mismatches, are in `tests/fixtures.json`.

Validation is scoped to these deterministic cases and settings. It is not an
exhaustive proof of RNAstructure correctness, support for every constraint or
platform, or whole-genome/model validation. The coordinator owns application
admission, backend/model identity changes and the repository-wide release gate.

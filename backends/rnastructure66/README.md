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

Component identity: **rnastructure-6.6-traceback-2**. The two newly isolated
states, `WMB2` (tag 3) and `W2` (tag 4), select one decomposition from their own
fill recurrence and pass each child its recorded energy. This is a scoped
contract for these handlers, not a correctness claim for all upstream states.

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
3. Upstream `W2` shares tag 0 with ordinary multiloop `W`. Their penalties
   differ, so a tie can select an unrelated recurrence. Tag 4 admits only the
   fill's `W2` strips, stems, modified-base alternatives and `WMB2` delegation
   (upstream lines 5080–5182 and 5468). Ordinary `W` can no longer strip or
   decompose through `W2`; `W2` cannot fall through to `W` or coax choices.

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
fragments with tag 4. The two child intervals are disjoint. The fill's `k == j`
term adds an empty right fragment (`INF`). It cannot improve a reachable finite
or linker-offset cell: if its left value carries the linker offset, a `WMB2`
extension already supplies that lower value. The trace omits the empty child
and fails with a traceback error if no legal transition matches.

`V` to `WMB2` closures now require the fill's `j-i > 2*minloop+4` and `i != N`;
right/both dangles also require `j != N+1`. `W2` strips and dangles retain the
fill's `N`, `N+1` and `j != 1` exclusions. Modified stems use the fill's inner
`can_pair` and `SINGLE` predicates and register the actual outer pair. The
upstream asymmetric direct-stem predicate `mod[i] || (mod[j] && ...)` is
preserved, including its limitations. No new forced-unpaired check is added
to strips that the fill itself admits. Chemical modifications, forced pairs,
SHAPE/covariation and other constraint combinations still require full engine
validation; the repair does not certify their upstream semantics.

Tests independently check
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
respectively. The census records connectedness, the number of immediate child
branches in the linker-containing loop, and exact `efn2 - native` deltas:

- Disconnected structures have no interstrand pair. `efn2` adds initiation,
  while their native DP energy does not; the dominant delta is +4.1 at 303.15 K
  (+4.3 at 310.15 K). Other upstream differences can combine with that offset.
- In connected linker loops, `efn2` minimizes coax/dangle arrangements and adds
  initiation (`src/structure.cpp`, `ergmulti` intermolecular branch), while the
  `W2`/`WMB2` fill has no coax term. Negative deltas in branched linker loops
  are therefore compatible with differing energy objectives; the census alone
  does not prove the cause of every mismatch.
- Small positive deltas remain in the untouched one-branch `erg2` path; the
  review found +0.1/+0.4/+0.7 examples already present upstream. A +0.2 delta
  also occurs with single-strand `Fold`. Their exact cause is unresolved.
- For connected linker loops with at least two child branches, the regression
  gate rejects positive deltas above +0.2. Two fresh synthetic counterexamples
  from review (seed 484, index 3; seed 4840, index 18) have five such anomalies
  upstream, from +1.1 to +1.7, and none with the repaired engine. This property
  is independent of snapshots; unexplained large errors are not accepted by
  updating a hash.

These distinctions preclude claiming energy-objective equivalence or a globally
optimal search. Every emitted structure is reevaluated;
the simple controls agree exactly between DP and `efn2`. Fixture hashes exclude
machine paths and CT labels while retaining all ordered structures and energies.

## Reproducible installation

Prerequisites: Python 3.11+, an already installed C++ compiler, `make`, `patch`
and the pinned source archive. On macOS, already installed command-line developer
tools/SDK are required; the builder obtains the SDK with `xcrun` and sets both
SDK include flags. It first runs the non-prompting `xcode-select -p` preflight,
before extraction or patching, and fails with instructions when tools are absent.
It never invokes developer-tools installation. No administrator access, new developer tools, account or
network is needed when the archive is present. Inspect available memory and
disk before compiling; at most two make jobs are allowed.

```sh
python3 backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-2 \
  --jobs 2
```

The archive SHA-256 must be
`1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`.
The builder refuses an existing destination and a mismatched archive/patch,
validates archive paths/types and explicitly uses the `data` extraction filter,
applies with zero fuzz, checks the patched source and
builds serial `Fold`, `bifold` and `efn2`. Failed builds remain for diagnosis;
retry into a new directory. The standalone engine root is
`/new/user-owned/rnastructure66-traceback-2/RNAstructure`.
On early Python 3.11 without the backported tar filter API, the explicit
regular-file/directory allowlist and fresh destination provide the safe
extraction path; links and traversal paths are rejected before creating it.
Set `DATAPATH` to that root's `data_tables` when calling its tools directly.

`RNAstructure/traceback-build.json` records the source/patch identities, build
command, compiler version, platform, machine, actual executable architectures,
executable hashes and all installed table hashes.
The builder removes inherited make/architecture/compiler tuning variables.
Upstream's platform detection selects the target architecture; inspect the
build log and receipt, especially when Python or its subprocesses run under
Rosetta. `--no-optimize` adds upstream `optimize=off` for a fresh diagnostic
build. Every independently compiled executable has its own binary identity.

## Component gate

Run from the repository root with an installed C++ compiler; no third-party Python packages or application
imports are used. Both engine variables are mandatory and missing engines fail
the gate instead of skipping it. Keep the original installation read-only.

```sh
RNASTRUCTURE66_PATCHED=/new/user-owned/rnastructure66-traceback-2/RNAstructure \
RNASTRUCTURE66_ORIGINAL=/path/to/unmodified/RNAstructure \
python3 -m unittest discover -s backends/rnastructure66/tests -v
git diff --check
```

The gate exercises builder rejection contracts, checker corruption cases,
eight frozen fixtures, the full 60-input seeded synthetic panel and 12 unique
development leaders selected by normalized-sequence SHA-256 order. It reads no
experimental outcomes, private final tables or fitted models. The synthetic
panel requires 60/60 repaired searches valid against 54/60 original; 44 outputs
are identical and 10 originally valid outputs change.
The development panel enforces 12/12 repaired versus 11/12 original valid,
with one previously valid output changed. Exact version-2 snapshots and mismatch
censuses are in `tests/fixtures-traceback2.json`, pinned to the new patch identity.
`tests/fixtures.json` is preserved byte-for-byte from commit `52809e1` as the
version-1 baseline; its hash is checked by the gate. All eight ordered outputs
remain identical in version 2. New census metadata is attributed separately.

The gate also extracts the actual handlers and unchanged fill from the pinned
source and compiles a small deterministic DP-table harness with UBSan. It checks
12,000 `W2` and 2,000 `WMB2` cells, boundaries, ties, modified-base/constraint
predicates and failure paths without waiting for a sequence panel to visit them.
Thermodynamic functions in that harness are stand-ins; it establishes local
state correspondence, while the real tools supply structural/energy evidence.

Validation is scoped to these deterministic cases and settings. It is not an
exhaustive proof of RNAstructure correctness, support for every constraint or
platform, or whole-genome/model validation. The coordinator owns application
admission, backend/model identity changes and the repository-wide release gate.

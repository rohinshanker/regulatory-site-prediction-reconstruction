# RNAstructure 6.6 standalone builds and intermolecular traceback repair

This optional, separately installed **GPL-2.0-only** component repairs
intermolecular traceback in the pinned RNAstructure 6.6 source. It supplies a
source patch, an unprivileged builder and independent structural regressions.
It does not install into or modify the shared engine. The application continues
to communicate through standalone executables and sequence/CT files; no engine
source or library is copied into `src/regsite`.

`manifest.json` pins the upstream archive, original source file, patch and
patched source of version 2 by SHA-256; `manifest-linker-3.json` pins the
cumulative version-3 patch described below. `manifest-original.json` pins the
unmodified source with `patch: null`. The included `LICENSE` is upstream `gpl.txt`.
The full upstream source, `ReadMe.txt`, `gpl.txt`, attribution headers and data
tables remain in each independently built installation. Preserve that source
and its notices when distributing binaries. The component scripts and fixtures
are also GPL-2.0-only, an explicit exception to the repository-wide default.
The RNAstructure authors retain their original copyrights; both patches change
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

A residual **upstream ordinary-`W`/linker traceback failure remains**. With
those same settings, synthetic seed 484/index 17 supplies leader
`GGAGGGUAUAACAGUGAGUCACCUGAGGUGGUAAGGUUUGGAUAACUGCGUCUUAGCAGU`
and anti-SD `ACCUCCUUU`. Both original and repaired engines print five
`error # 2` messages, report `A traceback error occurred`, exit **0**, and
write **no CT**. The public structural review traced it to unchanged tag-0
ordinary `W` fragments containing the linker centre; the cause of their finite
fill values is resolved in version 3 below; the traceback-2 engine does not
repair that recurrence. The independent runner rejects the result, and the
gate requires the original and traceback-2 engines to fail closed on this
exact input while linker-3 returns 100 valid structures. Callers must inspect errors and CT presence
rather than accepting exit status alone. Passing the 60-input panel below does
not establish total coverage: the review's separate 70-input probe had 69 valid
repaired searches versus 66 original (correcting its earlier 40/40 claim to
39/40 on the initial subset). Application admission must preserve explicit
backend failures.

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

## Version 3: ordinary `WMB` linker-centre guard

Component identity: **rnastructure-6.6-linker-3**. Its cumulative
`linker.patch` contains every traceback-2 hunk verbatim plus one fill hunk;
`manifest-linker-3.json` pins the patch, the post-image
(`b19a9ad1634f7e8f7669410b1eb7f5e8c27542f073054acb65647891e62ddbc7`) and the
predecessor identities. The traceback-2 component, its manifest and its
fixtures are unchanged and remain the builder default. Version 3 is a new
backend identity: the runtime adapter rejects its build receipt with
"build receipt identity/hash mismatch" until admission is reviewed, and the
frozen models were not trained with it.

### Root cause

bifold folds strand one, the linker `III` and strand two as one sequence;
only the linker centre `c = ct->inter[1]` carries `fce(c,c) & INTER`. The
ordinary multibranch recurrence `W` refuses to leave that centre unpaired: its
single-nucleotide strips `e[4]`/`e[5]` add `INFINITE_ENERGY` when the stripped
base is the centre (upstream `src/algorithm.cpp` lines 4980–4994 and
5019–5027). A loop containing the linker is instead an intermolecular exterior
loop, represented only by `W2`/`WMB2` with the `data->init - INFINITE_ENERGY`
marker and closed by `V` through `wmb2(i+1,j-1) + penalty + INFINITE_ENERGY`
(lines 4766–4808, "don't add the multiloop penalties").

The ordinary `WMB` recurrence breaks that invariant. Its nucleotide-addition
terms, added "for the sake of coaxial stacking" (lines 5217–5222), strip `i` or
`j` at `mbl_nucleotide` cost with no `INTER` test. `WMB(c,j) = WMB(c+1,j)` and
`WMB(i,c) = WMB(i,c-1)` therefore stay finite, and `W = min(W, WMB)` inherits
them. The ordinary multiloop closure and coaxial terms of `V` (lines
4497–4765) then price a loop containing the linker as a penalised multibranch
loop, which can beat the intermolecular closure. The traceback has no matching
transition: the tag-0 `W` handler strips `i` only when
`energy == W(i+1,j) + mbl_nucleotide` (lines 780–795), and the bifurcation
search tests `W` splits, coaxial pairs and `W2`/`WMB2` (lines 965–2136), never
`WMB(i+1,j)`.

Instrumented reproduction of seed 484/index 17 (N = 72, c = 62): the
`V(43,90)` closure pushes `W(61,88) = −154` through a coaxial term; the handler
strips 61 and fails at `W(62,88) = WMB(62,88) = WMB(63,88) = −154` because
`W(63,88) = −155`. The remaining errors are `W(35,62) = WMB(35,61) = −79` with
`W(35,61) = −84`, and `W(62,84) = WMB(63,84) = −144` with `W(63,84) = −155`.
`mbl_nucleotide` is 0 at 303.15 K, so the strip and the addition tie exactly.

### Repair, invariant and evidence

The hunk adds the identical marker to both `WMB` nucleotide-addition terms,
`+ ((fce.f(x, x) & INTER) ? INFINITE_ENERGY : 0)`, and changes no handler:
every finite ordinary `W`/`WMB` cell is again produced by a transition the
existing handlers test. The resulting fill invariant is that `W(i,j)` and
`WMB(i,j)` lie at least `INFINITE_ENERGY` above normal scale whenever
`i ∈ {c−1, c}` or `j ∈ {c, c+1}` (modulo N on the wrapped side), because
linker bases cannot pair and the centre may not be stripped. A scratch
instrumented build checked every fill cell of the 60-input panel, the 12
development leaders and seed 484/17: 0 violations with the guard, 21,758
finite centre-edge cells without it, and in both builds 0 offset-scale values
in intervals that exclude the centre and 0 offset-scale `V` cells. `W2`/`WMB2`
still strip the centre for free as upstream designed; such cells can only be
closed through the `+ INFINITE_ENERGY` closure and are never traced.

Real-engine evidence, all with `efn2 --simple` reevaluation:

- Seed 484/17 returns 100 valid structures (MFE −23.3 kcal/mol in both DP and
  efn2, 33 native/efn2 mismatches, no connected multibranch delta above +0.2).
- All eight traceback-2 fixtures are byte-identical on linker-3.
- 60-input 6603 panel: 60/60 valid, 54 identical to traceback-2, 6 changed
  (indices 20, 38, 40, 43, 44, 58). Development panel: 12/12, 1 changed
  (index 8). Fresh seed-26003 panel of 40: original 38/40, traceback-2 40/40,
  linker-3 40/40, 2 changed (indices 23, 37). The MFE never changes. Every
  structure that disappears is a connected linker loop with at least three
  branches whose native energy exceeds efn2's by 1.9–3.3 kcal/mol, i.e. a
  multibranch-penalised loop wrapped around the linker; its replacement is a
  structure whose native energy matches its topology. Two inputs keep a
  structure whose native energy rises (−31.8→−30.0, −29.7→−29.0, −23.5→−23.3)
  because the cheaper path was the invalid one.
- Five hand-checkable boundary strands (tiny and pure duplexes, no possible
  pairs, a duplex adjacent to the linker, SD/anti-SD at strand ends), five
  ordinary `Fold` controls (MFE and suboptimal), two `Fold` constraint files
  (forced single/double strand and a forbidden pair) and three
  `bifold --intramolecular` runs are identical across the original,
  traceback-2 and linker-3 engines.
- A compiled harness extracts the ordinary `W` strips and the guarded `WMB`
  terms from the installed source and checks on 40,000 synthetic cells that
  both apply exactly the same marker, including forced-double-strand and
  strand-boundary cases; removing or misplacing the guard is rejected. The
  traceback-2 `W2`/`WMB2` harness passes unchanged on the version-3 source.

Remaining limits: the known negative connected-loop deltas (efn2 coaxial
stacking versus the coax-free `W2`/`WMB2` fill) and the small positive
one-branch deltas remain; the bounded candidate search is still not
exhaustive; constraint, SHAPE and modified-base combinations other than those
listed are not exercised in bifold; and structural validity does not imply
biological accuracy.

## Reproducible installation

Prerequisites: Python 3.11+, an already installed C++ compiler, `make`, `file`
and the pinned source archive; repaired builds also require `patch`. On macOS,
already installed command-line developer tools/SDK are required; the builder obtains the SDK with `xcrun` and sets both
SDK include flags. It first runs the non-prompting `xcode-select -p` preflight,
before extraction or patching, and fails with instructions when tools are absent.
It never invokes developer-tools installation. No administrator access, new developer tools, account or
network is needed when the archive is present. Inspect available memory and
disk before compiling; at most two make jobs are allowed.

```sh
python3 backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-original \
  --jobs 2 --component rnastructure-6.6-original
python3 backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-traceback-2 \
  --jobs 2
python3 backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /new/user-owned/rnastructure66-linker-3 \
  --jobs 2 --component rnastructure-6.6-linker-3
```

`--component rnastructure-6.6-original` explicitly selects pristine source and
skips every patch operation. The source hash is checked before and after
compilation. The default remains traceback-2; the other names select pinned
cumulative patches. Unknown names and contradictory manifests are refused
before anything is created. This is a reproducible installation recipe, not a
promise of bit-identical binaries or biological validation.

The archive SHA-256 must be
`1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`.
The builder refuses an existing destination and a mismatched archive/patch
(the version-3 patch SHA-256 is
`2ef6ef61496b034110f4151e2fc1aec77cbd011c88a36bcef574be0dfecebb2d`),
validates archive paths/types and explicitly uses the `data` extraction filter,
applies with zero fuzz, checks the patched source and
builds serial `Fold`, `bifold` and `efn2`. Failed builds remain for diagnosis;
retry into a new directory. The standalone engine root is
`/new/user-owned/rnastructure66-traceback-2/RNAstructure`.
On early Python 3.11 without the backported tar filter API, the explicit
regular-file/directory allowlist and fresh destination provide the safe
extraction path; links and traversal paths are rejected before creating it.
Set `DATAPATH` to that root's `data_tables` when calling its tools directly.

Original builds write `RNAstructure/original-build.json`, with
`patch_applied: false`, `patch_sha256: null`, pristine `source_sha256`, archive
hash/byte count, and the same compiler/build/platform/executable/table identities
as repaired builds. They never write `traceback-build.json`; runtime repaired
identity discovery and model identities remain unchanged. A receipt binds the
recorded files but is not independent proof of provenance or new platform
admission. The original engine root is
`/new/user-owned/rnastructure66-original/RNAstructure`.

Repaired builds retain `RNAstructure/traceback-build.json`, recording source/patch
identities, build command, compiler version, platform, machine, actual executable architectures,
executable hashes and all installed table hashes.
The builder removes inherited make/architecture/compiler tuning variables,
including `GNUMAKEFLAGS`, `MAKEFILES` and `RNA_INCLUDE_CUDA`.
Upstream's platform detection selects the target architecture; inspect the
build log and receipt, especially when Python or its subprocesses run under
Rosetta. `--no-optimize` adds upstream `optimize=off` for a fresh diagnostic
build. Every independently compiled executable has its own binary identity.

## Component gate

Installer unit tests use only synthetic archives/files and mocked subprocesses;
no engine, application import or download is needed:

```sh
python3 -m unittest discover -s backends/rnastructure66/tests -p test_build.py -v
```

Run from the repository root with an installed C++ compiler; no third-party Python packages or application
imports are used. All three engine variables are mandatory and missing engines fail
the gate instead of skipping it. Before running predictions, the gate compares
`traceback-build.json` component, source-archive, patch and patched-source pins
with the manifest, hashes the actual patched source and all three executables
against the receipt, and checks the original source against its upstream pin.
These consistency checks detect stale or changed installations; the receipt is
not independent proof of binary provenance. Keep the original installation read-only.

```sh
RNASTRUCTURE66_PATCHED=/new/user-owned/rnastructure66-traceback-2/RNAstructure \
RNASTRUCTURE66_LINKER3=/new/user-owned/rnastructure66-linker-3/RNAstructure \
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

`tests/test_linker3.py` and `tests/test_linker_fill.py` add the version-3
checks listed above against `tests/fixtures-linker3.json`, which also pins the
traceback-2 manifest and fixture hashes; the version-2 modules and snapshots
are unchanged.

The gate also extracts the actual handlers and unchanged fill from the pinned
source and compiles a small deterministic DP-table harness with UBSan. It checks
12,000 `W2` and 2,000 `WMB2` cells, boundaries, ties, modified-base/constraint
predicates and failure paths without waiting for a sequence panel to visit them.
Thermodynamic stand-ins depend deterministically on their coordinate and
orientation arguments; child costs are recomputed using the selected outer
pair, inner pair and dangling bases. A mutation test requires rejection of
`penalty(i,j)` substituted for `penalty(i+1,j)` in the extracted left-dangle
handler. This establishes local state and energy-call correspondence under
synthetic costs; it does not establish physical equivalence. The harness does
not model SHAPE, and full constraint/modified-base behavior remains unverified
through the real engine. The real tools supply the scoped structural/energy evidence.

Validation is scoped to these deterministic cases and settings. It is not an
exhaustive proof of RNAstructure correctness, support for every constraint or
platform, or whole-genome/model validation. The coordinator owns application
admission, backend/model identity changes and the repository-wide release gate.

# Intrinsic-termination source boundary

- Purpose: Admit a complete external candidate scorer before implementing an optional adapter.
- Scope: C child #62 of #8; DEM-619 admits complete source for separate build/synthetic smoke; corrected runtime contract and executable admission remain pending.
- Last verified: 2026-10-21

## Source and terms

The [author distribution](https://transterm.cbcb.umd.edu/) supplies a complete
C++ implementation, Makefile, usage manual and `expterm.dat` background table.
The [manifest](../../benchmarks/termination/source-manifest.json) pins the
1,827,662-byte upstream ZIP, all 32 text members and the primary
[Kingsford et al. 2007 paper](https://doi.org/10.1186/gb-2007-8-2-r22).
Bundled `transterm` and `2ndscore` binaries were not extracted or executed.
Sources stay in external storage; no genome, predictions or experimental
supplements were acquired. No source-wide search or model fitting is required.

Primary C++ headers say GNU GPL version 2.0. Debian's maintained 2.09-5
[copyright metadata](https://sources.debian.org/src/transtermhp/2.09-5/debian/copyright/)
labels the package GPL-2.0+. Conservatively preserve the primary GPL-2.0 grant;
do not use this discrepancy to broaden redistribution rights. The required
background table is in the same distribution with no separate restriction found.
The Python package must invoke a separately installed executable. Do not vendor,
link or bundle engine source, copied engine code, binary or parameter table in
the GPL-3.0 Python package. Retain the engine source and notices in the separate
installation. The paper is CC-BY-2.0.

The archive calls itself 2.09; `transterm.cc` prints 2.08 and `USAGE.txt` starts
with 2.07. A banner alone cannot establish identity. Pin source archive, required
table, compatibility patch and built executable separately. The maintained
[Debian null-pointer patch](https://sources.debian.org/src/transtermhp/2.09-5/debian/patches/0002-read_seq-return-NULL-instead-of-false.patch/)
changes three `return false` pointer returns in `read_seq` to `return NULL` for
modern compilers. It does not change scoring. Any compiled variant must identify
that patch and the compiler; do not silently call it unmodified upstream code.
Pin build flags to `-g -O3 -Wall -pedantic -std=c++11 -ffp-contract=off`,
with assertions enabled and no `-DNDEBUG` or `-ffast-math`. Record compiler,
version, standard library and full command. Any additional portability patch
requires its own pinned identity and focused review.

## Admitted meaning proposed for review

This is a **candidate motif score**, not a termination-efficiency or readthrough
model. The primary paper defines a hairpin-plus-T-tail search on both strands,
a heuristic hairpin score and a random-background quality score. It does not
establish a native-cyanobacterial probability or reconstruct De Novo DNA's model.
Temperature-dependent thermodynamic inference is not an input: these fixed
heuristic costs are not an executed RNAstructure/ViennaRNA free-energy model.

With `x0=1`, the 15-base tail score is `-sum(x1..x15)`, where each successive
factor is 0.9 for T and 0.6 otherwise (A on the reverse genomic strand).
Hairpin pair costs are GC=-2.3, AU=-0.9, GU=1.3, mismatch=3.5 and gap=6;
loop cost is `length-2` for loops 3–13. The native search uses gapped dynamic
programming and dominance filters; a wrapper must not substitute a simple
palindrome detector. Preserve native scores at their printed precision.

Default search constants are maximum hairpin extent 59, minimum stem 4,
loop lengths 3–13, at least 3 T bases in the following six-base window,
strict hairpin score < -2 and tail score < -2.5. The first tail-adjacent
hairpin base cannot be T. Native dominance pruning is part of the algorithm;
return all native retained candidates, not every theoretical structure. The
minimum-stem check applies to the genomic-right arm only; a gapped opposite arm
can be shorter. Mirror symmetry is not guaranteed for gapped candidates. The
paper differs in its inclusive-cutoff and stem/extent wording; this profile
preserves executable behavior, including strict internal cutoffs.

The required table contains 30 AT-content grids (26% through 84% by 2%),
25 by 25 histogram bins each and a 20,000,000-base random sample size.
For cumulative count R and sample size L, the published score is
`(-100/log(L))*log(max(1,R)/L)`. Native code cumulatively sums the table and
truncates this transformed value to an integer. With contraction disabled, table selection compares
`abs(float(k) - 100.0*(AT_count/length))` in ascending table order using strict
`<`. Only equal computed binary64 distances choose the first/lower table; an
exact mathematical tie can round toward the upper table (55/100 chooses 56).
Retain counts, selected table and an exact rational tie flag. Outside the
26–84% table domain, the nearest endpoint table is used. Scores outside the
table's energy extent use edge bins. Preserve the original table and scoring constants; no recalibration
or empirical measurements are in this task. The footer records the original
parameters; it is provenance, not an instruction to execute calibration.

The [original scalar fixtures](../../benchmarks/termination/synthetic-fixtures.json)
check tail arithmetic, one fixed hairpin's cost and the confidence transform.
They are exact-mathematics controls with a 1e-12 numerical comparison tolerance,
not native bit patterns or claims about candidate selection/biological accuracy.
Keep these frozen bytes, including the valid signed-zero representation. The
native DP uses float32 and output uses six significant digits. Parse printed
costs as decimal strings; printed hairpin `-2` can represent a native value just
below the strict cutoff and must not be rejected by reapplying `< -2`.

## Proposed fragment contract and open checks

Use the manual's section 10 mode for an explicitly supplied unannotated fragment:
two two-base bookkeeping annotations at 1..2 and (N-1)..N, both forward, exactly
as its coordinate example states. These are synthetic boundaries, not inferred
genes. The manual's prose calls them tail-to-tail, but its ascending coordinates
produce same-direction genes according to `CoordsReader`; preserve that fact.
Use `--all-context -c 0 -S` to emit all candidates surviving native pruning.
The shared dominance-pruning vector can remove a candidate on the other strand,
particularly the rightmost member of a bidirectional pair. `--all-context`
cannot restore it; do not synthesize missing mirror candidates. Keep default start/end cuts (0/25); `populate_events` clamps trimming
so these two-base boundaries remain intact. Do not invent real gene annotations.

For this mode, source `ATContent` counts interior bases `[2,N-2)` as the
intergenic background and the four outer bases as the synthetic GENE
background. Conservatively require nonzero AT and GC counts in both groups;
source table lookup asserts `0 < AT_fraction < 1`. Return the counts, fractions
and selected tables with an explicit synthetic-boundary warning. A forward
hairpin starting at zero-based position 1 ties the first boundary-end event;
unstable event ordering can assign its GENE background. Retain such a candidate
with null admitted confidence and an explicit boundary-ambiguity status. Never
interpret a nonzero native exit, including SIGABRT, as no candidates. Preserve
raw context codes only as bookkeeping labels; canonically order candidates by
ascending start/end/strand instead of treating native TERM numbers as stable IDs. This mode is documented
as lightly tested by the author; no genome-annotation accuracy follows.

For length N, the native zero-based reference-anchor ranges are `[59,N-16)`
on `+` and `[16,N-59)` on `-`. These are tail-adjacent hairpin anchors, not
intervals of every base examined by dynamic programming. Length 75 is accepted
by the native guard but has zero anchors; expose that zero coverage explicitly.
Do not pad input or extrapolate candidates at unavailable flanks. Native TERM
coordinates are one-based inclusive and reversed for minus-strand hits; map to
ascending zero-based half-open hairpin intervals and preserve strand. Tail
intervals use the following 15 oriented bases. A no-candidate result is not
experimental evidence of absent termination.

## Execution and interpretation limits

Accept only uppercased A/C/G/T after explicit whitespace normalization, with a
fragment cap of 100,000 bases (engineering limit). Reject N/U/IUPAC, NUL, FASTA
headers and every other symbol before native input. Pass exactly one fragment
per process: native confidence preparation otherwise pools backgrounds across
sequences. Generate a fixed safe chromosome ID, FASTA before coordinates, and
no blank coordinate rows. Require stack limit at least 8 MiB; the native DP
allocates approximately 8 MB on its stack. Never approach the native one-million-
base buffer boundary, which has an off-by-one write. `-S` is mandatory because
native sequence display can read before the buffer for early forward hairpins.
The wrapper may slice supplied sequence itself if sequence output is needed.

The shipped histogram saturates many cells at 100 and includes every structure
in the same score bin. Scores depend on the supplied context, including the
candidate's own bases in its background. Preserve that context for comparisons;
no calibrated efficiency or false-positive-per-length interpretation follows.
No generation log proves the bundled calibration script produced this exact
historical table; retain the table bytes as the source of truth. No inherited
76-point biological decision threshold is applied. The table footer also spells
`--uwin-length`, while the actual option is `--uwin-size`; do not execute it.

DEM-619 independently verified source completeness/terms, scalar formulas,
parameter bins, fragment geometry and source limits. Its source finding ledger
is retained in the active ticket; runtime admission awaits targeted native
controls and exact implementation review. Tiny smoke controls must include
lengths 74/75, simple gap-free mirrors, position-dependent bidirectional pruning,
bookkeeping-boundary overlap and the 27/100 AT tie. Source review does not
certify compiled parity, candidate correctness, experimental accuracy or package
integration.


## External executable smoke boundary

The [native smoke manifest](../../benchmarks/termination/native-smoke-manifest.json)
pins the separate ARM64 executable, compiler flags, library versions and all11
original artificial controls. Apple Clang21 needed explicit existing SDK and
C++ header paths; no toolchain installation or additional source patch was used.
Only the maintained three-line null-pointer patch changed source. The successful
serial build took17.14seconds and reported168,894,464bytes maximum resident
memory; `/usr/bin/time` separately reported3,507,232bytes peak footprint for its
measured process. These are distinct measurements, not interchangeable whole-tree
peak estimates. The largest smoke process reported2,473,984resident bytes and
1,933,624bytes peak footprint. Runtime stack was16MiB, set in the launching shell
before Python/native execution; the inherited8176KiB was below this contract.
No host-wide resource limit changed.

All11 cases completed:10 native successes and the expected length74 exit3.
Length75 has zero anchors, while length76 has one per strand. Both positive and
reverse controls retained the intended gap-free hairpin with the native printed
scores, but their complete rosters differ; no universal mirror property is
asserted. The rightmost bidirectional control retained only its reverse copy;
placing another candidate to its right retained both copies. Both left-boundary
controls used contextF in this build, including the uniform-GC diagnostic;
this does not remove the source-level unstable-event ambiguity or justify a
cross-build guarantee. The adapter still flags boundary overlap and withholds
admitted confidence there. The27/100 AT control confirms executable acceptance;
its saturated100 score cannot independently distinguish the26 and28 tables.
The binary64 selection claim remains source/arithmetic evidence pending a
non-saturated discriminating control or focused independent check.

Full stdout/stderr and invocation receipts remain in the external source cache.
The manifest records their byte identities and the complete candidate roster;
these artificial outputs are not measurements. The native header's date and
parameter-file path are execution metadata, not model version identity. Runtime
admission and final adapter verification still require the focused DEM-619
reconciliation and implementation review. The upstream cross-translation-unit
`set_max_len_loop` return-type discrepancy is explicitly submitted for disposition;
no silent extra compatibility patch was applied.

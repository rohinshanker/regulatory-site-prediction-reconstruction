# Intrinsic-termination source boundary

- Purpose: Admit a complete external candidate scorer before implementing an optional adapter.
- Scope: C child #62 of #8; TransTermHP 2.09 proposal, independent review and executable smoke pending.
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
The proposed Python adapter invokes a separately installed executable; neither
source, binary nor table is copied into the Python package. The paper is CC-BY-2.0.

The archive calls itself 2.09; `transterm.cc` prints 2.08 and `USAGE.txt` starts
with 2.07. A banner alone cannot establish identity. Pin source archive, required
table, compatibility patch and built executable separately. The maintained
[Debian null-pointer patch](https://sources.debian.org/src/transtermhp/2.09-5/debian/patches/0002-read_seq-return-NULL-instead-of-false.patch/)
changes three `return false` pointer returns in `read_seq` to `return NULL` for
modern compilers. It does not change scoring. Any compiled variant must identify
that patch and the compiler; do not silently call it unmodified upstream code.

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
return all native retained candidates, not every theoretical structure.

The required table contains 30 AT-content grids (26% through 84% by 2%),
25 by 25 histogram bins each and a 20,000,000-base random sample size.
For cumulative count R and sample size L, the published score is
`(-100/log(L))*log(max(1,R)/L)`. Native code cumulatively sums the table and
truncates this transformed value to an integer. The nearest AT table is selected,
with the lower table winning ties. Scores outside the table's energy extent use
edge bins. Preserve the original table and scoring constants; no recalibration
or empirical measurements are in this task. The footer records the original
parameters; it is provenance, not an instruction to execute calibration.

The [original scalar fixtures](../../benchmarks/termination/synthetic-fixtures.json)
check tail arithmetic, one fixed hairpin's cost and the confidence transform.
They are not claims about native candidate selection or biological accuracy.

## Proposed fragment contract and open checks

Use the manual's section 10 mode for an explicitly supplied unannotated fragment:
two two-base bookkeeping annotations at 1..2 and (N-1)..N, both forward, exactly
as its coordinate example states. These are synthetic boundaries, not inferred
genes. The manual's prose calls them tail-to-tail, but its ascending coordinates
produce same-direction genes according to `CoordsReader`; preserve that fact.
Use `--all-context -c 0 -S` to retain both orientations and all native retained
candidates. Keep default start/end cuts (0/25); `populate_events` clamps trimming
so these two-base boundaries remain intact. Do not invent real gene annotations.

For this mode, source `ATContent` counts interior bases `[2,N-2)` as the
intergenic background. Require nonzero AT and GC counts there before scoring;
source table lookup asserts `0 < AT_fraction < 1`. Return the chosen background
fraction/table and explicit synthetic-boundary warning. This mode is documented
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

Before runtime admission, independently verify source completeness/terms,
scalar fixtures, annotation/background semantics, anchor/strand conversion and
the narrowly proposed score meaning. Then compile one explicitly identified
external variant and run tiny original synthetic positive, negative and mirror
controls in a reserved process slot. Source review does not certify executable
parity, candidate correctness, experimental accuracy or package integration.

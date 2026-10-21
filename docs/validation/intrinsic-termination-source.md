# Intrinsic-termination source boundary

- Purpose: Define the pinned source, numerical behavior and meaning of the optional external candidate scorer.
- Scope: Source-admitted TransTermHP fragment profile; exact adapter review and common package integration remain separate gates.
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
with assertions enabled and no `-DNDEBUG`, `-ffast-math` or `-flto`/whole-program optimisation. Record compiler,
version, standard library and full command. Any additional portability patch
requires its own pinned identity and focused review.

## Admitted score meaning

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

## Fragment contract

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
no blank coordinate rows. Raise only the owned child soft stack limit to at least 8 MiB, failing closed when the hard limit forbids it; the native DP
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

## Source admission and frozen controls

Independent source review verified completeness, terms, scalar formulas, parameter
bins, fragment geometry and source limits. Its focused reconciliation recomputed
all 19 original native confidences and tail costs and checked the input/output
identities. This admits the source contract; it does not certify biological
accuracy, genome-scale behavior or other toolchains.

The [native smoke manifest](../../benchmarks/termination/native-smoke-manifest.json)
pins the original separately built ARM64 executable and 11 artificial controls.
They cover lengths 74/75/76, gap-free reverse orientation, cross-strand pruning,
boundary overlap and a saturated AT tie. Preserve their complete rosters and raw
byte identities. Ten controls exit successfully; length 74 deliberately exits 3.
Length 75 has no reference anchors. Both boundary controls emit context F on the
recorded build; this does not remove the source-proven G event-order possibility.

The [non-saturated tie control](../../benchmarks/termination/native-tie-control.json)
was constructed independently before execution. Its interior has 27 AT bases
out of 100. The pinned table predicts score 78 at table 26 versus 76 at table 28.
The native binary emits one candidate at one-based 71..86, hairpin `-11.8`, tail
`-3.87583`, score 78. This distinguishes those tables on the recorded build;
it is neither an empirical measurement nor universal compiler-parity evidence.

## Selected build profile

In addition to the three-return Debian NULL patch, the selected build corrects
`search.h`'s `set_max_len_loop` declaration from `int` to `void`, matching its
definition. The independent reviewer found the mismatch inert in the original
separately compiled, non-LTO build and explicitly admitted the one-token fix.
No scoring implementation is changed. The source manifest pins the original and
patched bytes. Do not apply additional compatibility patches without pinning and
focused review.

The [admitted build receipt](../../benchmarks/termination/admitted-build-manifest.json)
records the corrected executable and complete replay of all 12 controls.
Outputs and exit statuses match the original build after normalizing only the
build-date and parameter-file-path lines. The original fixtures and receipts
remain unchanged. Record the effective binary architecture and deployment/SDK
target; a compiler's default target banner does not prove its selected target.

The [adapter build receipt](../../benchmarks/termination/adapter-build-manifest.json)
records the output of the repository's actual offline builder, its compiler and
source identities, and complete CLI outputs. Every separate build needs its own
receipt and the unchanged controls. See the [runtime guide](intrinsic-termination-runtime.md)
for build and verification commands, resource limits and remaining admission gates.

## Source-to-adapter checks

Normal context codes are F on + and f on -. Admit G only for a forward hairpin
starting at zero-based index 1. Both F and G at that position retain geometry and
printed costs with null admitted confidence; every other unexpected context fails
the entire record. Check native gene/H2T counts against the retained context
classes. Native '%AT' labels actually contain fractions. Compute backgrounds
from exactly the normalized sequence sent to the engine.

Raise the owned child's soft stack limit to at least 8 MiB before exec, preserving
its hard limit and failing closed on insufficient hard limit or setup error.
The actual adapter works from the recorded 8176 KiB parent limit without changing
the parent or host. The selected-build controls have also been replayed under an
8 MiB child limit. No privilege or shell workaround is part of the adapter.

Source identity, build parity, wrapper correctness and experimental accuracy are
distinct checks. Preserve every failed, unsupported and unevaluated input in the
wrapper receipt. Successful native empty rosters establish only that this fixed
search retained no candidate for the supplied fragment.

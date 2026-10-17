# Standby accessibility reconstruction

- Purpose: Specify the complete finite calculation and its scientific limits.
- Profile: standby2014-rnastructure-6.6-reconstruction-1; CLI standby2014.
- Result contract: [schema 1.2](../../schemas/rbs-result-1.2.schema.json).
- Source review: 2026-10-17; no experimental parameters fitted in this reconstruction.

## Primary source and provenance

Espah Borujeni, Channarasappa and Salis, *Translation rate is controlled by
coupled trade-offs between site accessibility, selective RNA unfolding and
sliding at upstream standby sites*, Nucleic Acids Research 42(4), 2646–2659
(2014), [DOI 10.1093/nar/gkt1139](https://doi.org/10.1093/nar/gkt1139).
The article is CC BY 3.0. This is an original implementation of its published
scientific relationships, licensed GPL-3.0-or-later with this runtime; no
proprietary executable or ViennaRNA code is included.

The admitted [Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3936740/fullTextXML)
has SHA-256 3410c14d94f74845fe5ffa8d879bd33144909c0fc72e439bc91e9ca032333a39.
The [supplement archive](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3936740/supplementaryFiles)
contains supp_gkt1139_nar-02492-r-2013-File009.pdf, SHA-256
a36ae7d252442865f4dc813ceb34022e2c0e01899c02fca61012d97c6558ffaf.
Retrieval date: 2026-10-17. A separate specification reviewer independently
retrieved matching files and inspected equations 3/5 and supplement pages 6–7,
Figure S3, before reading implementation source.

| Relationship | Primary location |
| --- | --- |
| Hairpin modules, proximal/distal lengths, height and height cap | Methods, Biophysical model calculations, paragraphs 6–7 |
| Distortion quadratic and coefficients | Methods equation 3 and following paragraph |
| Opening closing base pairs and minimizing combined cost | Results, Coupled energetic trade-offs; Figure 3; supplement Figure S4 |
| Noncooperative selection of one module | Results, Non-cooperative binding; Figure 4 |
| Sliding coefficient 0.2 kcal/mol/nt and downstream height sum | Results, The ribosomal platform can slide; Figure 5 |
| Combined penalty | Equation 5 and Figure 6 |
| Base-only and individual branch orientations | Supplement pages 6–7, Figure S3C–D |

## State and geometric definitions

This profile combines the existing 100-nt upstream/100-nt downstream context and
13-nt coding footprint with the new standby calculation. Those context/footprint
choices are documented in [rbs-mechanisms.md](rbs-mechanisms.md). It is not a
recovered release of the RBS Calculator. Historical, footprint2017 and
context2017 retain their previous calculation and schemas.

The existing bounded cofold-plus-spacing rule selects the mRNA–aSD pairing
**before** standby optimization. The prefix before its first paired mRNA base
is folded separately, then assembled into the bound complex as before. Its
exterior paired components define the original standby modules. A module's D
and P are the lengths of the adjacent contiguous unpaired gaps; the same gap
can be P for one candidate and D for the next. Internal loops do not count as
exterior gaps until their enclosing pairs have opened. With no hairpins,
H=D=0 and P is the entire prefix length, including a possible empty prefix.
An empty context is flagged and is not evidence of an accessible native site.

For a pair-tree node, let u be directly enclosed unpaired bases and k the number
of immediate child pair nodes. The height calculation is:

- No children: H = 1 + u/2.
- One child: H = 1 + u/2 + Hchild.
- Two or more children: B = 1 + (u+k)/2; H = B + sum(Hchild−0.5)/(k+1).

The branched expression averages the base-only orientation B and each
individual retained-branch orientation B+Hchild−0.5. A collapsed branch counts
as one nucleotide, following Figure S3. Counting half the total contour on
unequal sides of bulges/internal loops, and applying the expectation recursively
at nested junctions, are explicit reconstruction conventions. Fractional heights
are retained. Accessibility uses the averaged height capped at 15; sliding uses
uncapped averaged heights. The paper does not uniquely specify cap/average order
for extreme branches or a separate branched sliding geometry.

The accessible surface is A = 15 + D + P − min(H,15). The printed distortion
polynomial is q(A) = 0.038 A² − 1.629 A + 17.359 kcal/mol. The paper describes a
zero-penalty accessibility plateau but does not provide a piecewise continuation.
The reconstruction uses q below its first root (19.8187875437 nt), and zero at
and above that root. This is continuous, nonnegative and nonincreasing. It avoids
an artificial increase at long accessible lengths. The threshold is derived from
the rounded published coefficients, not a recovered production constant.

## Opening search and energy accounting

For each original exterior hairpin, enumerate every ancestor-closed subset of
removed pairs: a pair can open only after all its enclosing pairs have opened.
All other original exterior components remain unchanged and no new pairs form.
After a branched component splits, each remaining daughter component can be the
selected module. When the original component dissolves entirely, its merged gap
between neighboring components becomes an unstructured candidate with H=D=0.
This extends the published simple closing-pair procedure into a precisely defined
branched search; simultaneous opening across different original modules and
refolding into new base pairs are excluded. Branch opening can also reduce the
heights crossed during sliding; that coupling is a reconstruction extension.

The state-count recurrence is C(node) = 1 + product(C(child)). The complete
unique count is 1 + sum(C(root)−1), sharing the unchanged state across modules.
Count before enumeration, saturating above 512. More than 512 states returns
unsupported with an explicit state-limit reason; it never reports a partial
minimum. A 47-nt structure consisting of one outer pair enclosing nine separate
three-base loops already has 513 states. Length alone does not imply support.

Each admitted fixed structure is reevaluated in the **full bound complex** with
the same sequence, aSD, temperature and RNAstructure settings. Thus dangling and
coaxial interactions are retained. Raw unfolding cost is Eafter−Ebefore. The
charged cost is max(0, raw cost), because this profile treats opening as a
nonnegative penalty. A negative raw difference can occur when the assembled
baseline is not the evaluator's global minimum; it is exposed, and any such
search state emits a warning. Clipping is a declared reconstruction policy,
not an assertion of exact thermodynamic consistency.

For each module/state:

- Distortion = the accessibility function above.
- Unfolding = the charged fixed-state energy difference.
- Sliding = 0.2 times the sum of effective heights of downstream exterior roots.
- Standby = distortion + unfolding + sliding.

Select minimum standby; exact ties prefer fewer opened pairs, the earliest
original module, then the earliest remaining core. No cooperativity or
multiplicity bonus is added. Total initiation energy is the **original** bound
complex energy + spacing + start-codon energy − unbound mRNA energy + standby.
The changed complex energy is diagnostic and is not added again. The historical
2500 exp(−dG/2.222) score transformation remains fixed, with explicit provenance.
The source paper reports beta approximately 0.45; no silent scalar recalibration
is made here.

## Output, failures and limits

Schema 1.2 replaces the old signed standby energy with positive dG_standby,
dG_distortion, dG_unfolding and dG_sliding, plus signed dG_unfolding_raw. The
standby object records original/remaining hairpin, D/P intervals and lengths,
raw/accessibility/downstream heights, downstream hairpin intervals, opened pairs,
state count, original-module count and independently reoptimized no-opening,
no-sliding and no-distortion ablations. These ablations are mechanistic
comparisons, not candidate models selected against measured outcomes.

All intervals use normalized supplied-sequence coordinates and strand. Opened
pairs use zero-based, transcript-oriented window coordinates, matching structure
pair lists. The old standby_interval is null because a composite module is not
one contiguous four-base unpaired site. Before/after structures remain explicit. The native adapter additionally projects
module intervals into genomic segments in genomic_sites.standby_module, including
circular crossings. GFF3 retains its established feature set; full module geometry
is available in JSON.
A failed energy evaluation or timeout fails the site; it does not skip the state.
Other request, batch and subprocess limits remain in [rbs-runtime.md](rbs-runtime.md).
The prefix is at most 100 nt; at most 512 fixed states are evaluated per selected
binding candidate, within the existing record deadline. This finite search is
not exhaustive across alternative binding sites, refolded structures or kinetics.

## Verification and interpretation

Run the primary-source arithmetic, independent structural fixtures and real
backend integration tests:

```sh
REGSITE_RNASTRUCTURE=/path/to/separate/RNAstructure \
  .venv/bin/python -m pytest tests/test_standby.py tests/test_standby_runtime.py
.venv/bin/regsite examples/rbs-single.json --profile standby2014
.venv/bin/regsite examples/rbs-batch.json --profile standby2014
```

The full release gates remain mandatory. Synthetic fixtures cover asymmetric
loops, nested branches, shared gaps, height caps, uncapped sliding, complete
opening, all branch-opening subsets, negative deltas, deterministic selection,
resource rejection, failures, schema missingness and both strands. Their energy
oracles are explicitly synthetic; they establish algebra and state semantics,
not biological predictive accuracy. RNAstructure remains a different backend
from the paper's ViennaRNA 1.8.5/Turner1999 calculations. Drafting, stacking,
kinetics and translational coupling remain unimplemented.

Any experimental comparison must freeze this profile, code, backend identity and
settings first. Previously consumed Wave2 final outcomes cannot become a fresh
holdout. Public 2014 development data may diagnose behavior but cannot establish
independent superiority, native cyanobacterial calibration or hosted equivalence.
Website collection and coin purchases are deferred for this wave.

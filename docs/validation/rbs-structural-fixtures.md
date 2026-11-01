# Independent structural fixtures

- Purpose: Test folding output integrity and bounded enumeration independently of RBS scoring.
- Scope: Pinned RNAstructure 6.6 observations, synthetic topology oracles and public development-only failures; no biological accuracy claim.
- Last verified: 2026-10-17

## Source and independence

The [14-case panel](../../benchmarks/rbs/structural-panel.json),
[raw fixture archive](../../benchmarks/rbs/structural-fixtures/manifest.json) and
[independent audit](../../benchmarks/rbs/structural.py) do not import or inspect
the reconstruction's runtime or scoring implementation. Synthetic inputs were
chosen from structural properties. Two native leaders come from the already
public Karlsen 2018 development collection. Study attribution/selection follows
its CC-BY-4.0 deposit; the actual leaders are extracted NCBI genomic sequence
facts, not Figshare nucleotide data. The corrected panel separately pins
GCF_000009725.1 / annotation RS_2025_06_29, FASTA/GFF hashes and both minus-strand
intervals. No blanket Creative Commons licence is asserted for NCBI. These are
assumed 100-nt genomic flanks, not measured transcript boundaries; measurements
are not copied into this panel. No consumed final data selected the
fixtures.

RNAstructure source archive SHA-256 is
`1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`.
All 679 C/C++ source/header files in the existing fixture build directory were
byte-compared to that archive, with no differences. Executable hashes are in
`baseline/observations.json`; a source-directory comparison does not by itself
prove a binary's build ancestry. The unchanged table manifest is
`ece4c4b535783cb4e03c7ce8f243d09be84a165ecd113b1d20941b5ed8b69501`.
The collector verifies this manifest and every named table before running.
These are separate GPL-2.0-only executables, not linked or vendored code.

Primary interface specifications are the official
[CT and constraint formats](https://rna.urmc.rochester.edu/Text/File_Formats.html),
[bifold](https://rna.urmc.rochester.edu/Text/bifold.html),
[AllSub](https://rna.urmc.rochester.edu/Text/AllSub.html) and
[efn2](https://rna.urmc.rochester.edu/Text/efn2.html) manuals. Their copies in the
pinned source archive were inspected. `bifold` explicitly describes suboptimal
enumeration as heuristic. Its `--intramolecular` switch **forbids** intramolecular
pairs; it does not enable them. Lowercase bases are forced single stranded.
The three `I` positions are an artificial unpairable linker, not biological bases.

## Independently checkable numerical controls

At 310.15 K with the pinned RNA tables:

| Input | Structure (one-based CT pairs) | Hand calculation, kcal/mol |
| --- | --- | --- |
| `GGGAAACCC` | (1,9), (2,8), (3,7) | 3-nt hairpin 5.4 + two GG/CC stacks of −3.3 = **−1.2** |
| `GGGG` + `CCCC` | (1,11), (2,10), (3,9), (4,8), with III at 5–7 | Association 4.1 + three GG/CC stacks of −3.3 = **−5.8** |
| `AAAAAAAAA` | No pairs | **0.0** |
| `gggAAACCC` | Lowercase Gs unpaired; no remaining compatible pairs | **0.0** |

Located parameter entries: `rna.loop.dg`, hairpin size 3; `rna.stack.dg`,
GX/CY table row G, column C; `rna.miscloop.dg`, intermolecular initiation.
`rna.triloop.dg` has no special entry for the GAAAC loop. These simple GC
structures do not need terminal-AU or dangling-end terms. At 303.15 K the same
hairpin has observed Fold/efn2 energy −1.7; that temperature result is an engine
regression observation, not a separate hand-derived thermodynamic validation.

The independent recursion enumerates every noncrossing canonical topology for
these tiny inputs, including lonely pairs: **20** hairpin topologies and **70**
duplex topologies. The latter count also follows independently from
`sum(C(4,k)^2, k=0..4) = C(8,4) = 70`. All were written as CT before evaluation
with `efn2 --simple --ne`. Both hand-checked minima are unique. Energy evaluation
still shares the external engine; exhaustive topology generation is not an
independent implementation of all thermodynamic terms.

## Enumeration and failure findings

The duplex has five unique topologies within 3 kcal/mol of its minimum under
fixed-structure efn2 evaluation. Native `bifold --maximum 100 --percent 100
--window 0 --loop 30` returns four structures, only three of those five. Two
ordinary contiguous three-pair structures are omitted:

- CT pairs (1,11), (2,10), (3,9): **−4.0** kcal/mol.
- CT pairs (2,10), (3,9), (4,8): **−3.5** kcal/mol.

They have no lonely pairs. A successful, reciprocal native traceback therefore
does not establish exhaustive enumeration or a globally optimal downstream RBS
score. Correcting an upstream traceback defect and replacing the heuristic with
an exhaustive search are distinct changes with distinct identities.

For the hairpin, `AllSub --absolute 3 --percent 1000` returns nine CT records
but six distinct topologies, matching the six exhaustive topologies in that
efn2 band. Two equal partner arrays carry native header energies −1.0 and −0.2;
both reevaluate to −1.0. Retain record order, native energies and reevaluated
energies separately. Neither CT topology uniqueness nor universal header/efn2
equality is a valid invariant. This observation alone does not identify which
internal dangling-state choices caused the different headers.

The unmodified backend reproduces all three public failure diagnostics:

| Input | Observed failure |
| --- | --- |
| Public short leader `UGGCUUGACGGCGUCAUUCCUAUUAUCAAAGCAAU` + `ACCUCCUUA` | Nonreciprocal pair at CT 40:3 |
| Development `karlsen2018:SGL_RS10810` leader + `ACCUCCUUU`, 303.15 K | Nonreciprocal pair at CT 37:109 |
| Development `karlsen2018:sll0085` leader + `ACCUCCUUU`, 303.15 K | Exit status zero, traceback error on stderr and **no CT file** |

Raw malformed collections remain in the archive. The audit rejects the whole
collection rather than silently removing unknown candidates. A zero process exit
is insufficient evidence of a successful fold. There are 11 successful and three
failed baseline cases; this is a deliberately selected diagnostic panel, not a
population coverage estimate.

## Repair acceptance and reproduction

Before a repaired backend is admitted, pin its new source/patch/binary identity,
rerun this panel into a new directory, and require valid complete CT collections
for the three former failures. Check sequence, lengths, backbone numbering,
canonical and reciprocal pairs, unpaired linkers, no crossing pairs, finite
energies, constraints and both connected/disconnected outcomes. A parser-only
repair or dropping malformed members does not satisfy this gate. Preserve all
prior valid control structures/energies or explain differences against a new
specification. A claimed exhaustive search must additionally recover all tiny
oracle topologies within its declared energy objective and interval, including
the two omitted duplex topologies; native heuristic counts are not that contract.

```sh
python -m unittest discover -s tests/benchmarks -p test_structural.py
python -m benchmarks.rbs.structural benchmarks/rbs/structural-panel.json \
  /absolute/path/to/RNAstructure /new/output/directory
```

The collector requires independently installed `Fold`, `bifold`, `AllSub` and
`efn2`; the original runtime installation may build only the first, second and
fourth. It caps each subprocess at 30 seconds and refuses an existing output
directory, preventing stale CT reuse. Offline tests need no backend, account or
network. Focused tests cover all new statements and branches, including malformed
outputs, table drift, process errors, missing files and timeouts. A source-only
patch changing accepted syntax must update these expectations explicitly.

For exhaustive reproduction, call `enumerate_small` for `GGGAAACCC` and
`GGGGIIICCCC`, serialize with `to_ct`, then run `efn2 input.ct energies.txt
--simple --ne --temperature 310.15`. The archived oracle CT files and energies
are byte-pinned. No fixture implies hosted equivalence, NUPACK equivalence,
standby-model correctness or better experimental translation prediction.

## Standby equation and geometry handoff

[Analytic fixtures](../../benchmarks/rbs/standby-analytic-fixtures.json) preserve
facts from Espah Borujeni et al. 2014, DOI `10.1093/nar/gkt1139`, independently of
Session A's implementation. Primary XML SHA-256 is
`3410c14d94f74845fe5ffa8d879bd33144909c0fc72e439bc91e9ca032333a39`;
supplement `gkt1139_nar-02492-r-2013-File009.pdf` SHA-256 is
`a36ae7d252442865f4dc813ceb34022e2c0e01899c02fca61012d97c6558ffaf`.
Supplement pages 6–7 / Figure S3 were rendered and visually checked.

A two-branched hairpin has **three** orientations in this construction, including
the base-stem orientation with both branches collapsed. A three-branched hairpin
has four. An unused branch contributes one extra nucleotide to the collapsed
multibranch loop. Averaging only leaf-arm heights misses the central orientation.
The paper explicitly caps H at 15 in the surface-area equation; that cap must not
silently propagate into sliding. Its reported sliding penalties 0, 3.0, 4.8 and
7.8 correspond to downstream height sums 0, 15, 24 and 39 with coefficient 0.2.

The printed quadratic coefficients yield **−0.021 at surface area 20**, **−0.066
at 20.5**, and **0.151 at 24**. The paper's separate example says 0.02 at 20.5
and zero at 24. Keep raw polynomial arithmetic distinct from physically motivated
nonnegative/saturating reconstruction rules; the exact hidden precision or
piecewise policy has not been recovered from these passages. Do not silently
fit that missing policy to the already consumed experimental panel.

The analytic fixture includes a hand-specified unfolding landscape where opening
two pairs minimizes distortion plus unfolding cost, while minimizing distortion
alone selects a different state. The unfolding costs are explicitly **synthetic
test inputs**, not measurements or folding results. These checks establish scalar
arithmetic and elementary geometry only; nested/asymmetric branch extraction and
an exhaustive selective-unfolding domain require a separate explicit model
specification. Run `python -m unittest discover -s tests/benchmarks
-p test_standby_analytic.py` for exact Decimal checks.

Raw CT/energy files are unchanged by the provenance correction; both original
and corrected panel hashes remain in observations. A scoped Git attribute permits
trailing spaces only in byte-preserved executable progress captures. It does not
relax source/test/document whitespace checks. Timeout diagnostics are retained as
captured bytes under the correct prediction/energy stage filenames.

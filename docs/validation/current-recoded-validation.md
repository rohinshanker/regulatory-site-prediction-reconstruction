# Independent current-versus-recoded comparison validation

- Purpose: Test coordinate correspondence and prediction accounting before comparing current and recoded constructs.
- Scope: B ticket #39; label-free synthetic benchmark fixtures and producer-side validation. A owns runtime/portable exports.
- Last verified: 2026-10-18
- Authorization: `457ac340d1bf66fed976896015f13f3ed8d08c54`; publication and consumer admission remain separate.

## Frozen input meaning

`paired-edit-input-1` describes two explicit DNA strings in the same forward
sequence frame, their identities, topology and a sorted edit list. Edits use
zero-based half-open current-sequence intervals and exact replacement strings.
Reapplying them must reproduce the supplied recoded string byte for byte.
Reject any produced prefix longer than that supplied string before allocating
its map entries; later edits cannot shrink an already produced prefix.
No alignment algorithm, nearest-coordinate join or annotation-name inference
creates correspondence. Inputs are synthetic uppercase ACGT, not native outcomes.

Edits have unique IDs, nonoverlapping ranges and distinct starts. An insertion
has an empty source range and nonempty replacement; a deletion has nonempty
source and empty replacement. Empty-to-empty edits are invalid. Adjacent edits
are allowed. Cross-origin edits must be explicitly split in the declared frame;
implicit origin rotation, inversion and rearrangement are outside this version.
Identical strings with no edits form the unchanged-sequence control.

Unchanged segments map one to one. Equal-length substitutions preserve explicit
positional correspondence and mark substituted bases. Unequal-length replacement
blocks leave every replaced source base and every inserted target base unmatched;
this deliberately avoids inventing an alignment within the block. Forward and
inverse maps must agree exactly wherever either is defined. An unchanged base
outside edits must retain its nucleotide.

## Points, intervals and strand

A point identifies a base. Half-open feature intervals identify base sets and
must never use the point transform on their right endpoint. Map every interval
base in transcription order, then reconstruct ascending half-open runs in that
same traversal order. Missing bases and insertion-created gaps remain explicit;
a bounding interval cannot stand in for a split or incomplete feature.

Synthetic cases include both strands, both projection sequence strands and
linear/circular topology. Projection uses the public rule
`g = origin + direction * local_base` with modulo only for circular contigs;
genomic strand composes local site strand with sequence strand. Each supplied
sequence has its own length/origin/projection. A circular interval can use an
unrolled end greater than sequence length, but spans at most one full traversal.
Origin wrapping must not duplicate a base. Empty intervals map to empty base
sets, not a guessed insertion-boundary point.

The benchmark must retain current/recoded sequence hashes, exact edit hash,
projection identities and candidate IDs. Reverse-complement and circular-origin
controls test equivalent geometry. Direct per-base enumeration is the independent
expected-result method; no scoring implementation supplies expected coordinates.

## Candidate and outcome accounting

Each sequence has its own complete declared candidate universe. Match candidates
only when an explicit mapped anchor and local strand identify exactly one
counterpart under the same calculator/anchor definition. RBS start-codon anchors
and Promoter TSS anchors are distinct universes. A feature crossing an edit is
reported separately from its anchor mapping.

Report unmatched source/target coordinates separately from mapped anchors absent
from the opposite candidate universe. Use descriptions such as deleted coordinate,
inserted coordinate and mapped anchor not requested/eligible. None proves a
biologically lost or gained regulatory site. Do not turn an unobserved experimental
site into a negative or learn a score threshold from Tan outcomes.

A numerical difference requires both candidates to have successful finite scores
with equal model, parameter, backend, calibration and scoring-setting identities.
Input hashes and coordinates are expected to differ; resource limits/deadlines
and completeness remain independently visible. Retain every failed, unsupported,
not-run and unmatched candidate with a null difference and an explicit reason.
Never substitute zero, silently drop a failure or use only successful pairs as an
all-case endpoint. Log-score differences are not probability or expression changes.

Unchanged sequence/model/settings controls require identical candidate rosters,
coordinates and deterministic scores within the calculator's declared numerical
tolerance; deadlines/failures are reported rather than forcing equality. A changed
model/settings control must be marked incomparable, even if numerical values happen
to match. Include label-free substitutions, insertion/deletion,
unequal replacement, boundary/circular edits, start-anchor creation/removal,
partial features and partial execution in the frozen synthetic panel.

## Execution boundary

Freeze synthetic inputs and expected edit/coordinate/accounting artifacts before
reading producer results. B may prepare and test these independently while A
implements the public comparison/export contract. A's immutable candidate and
settings receipt is required before runtime comparison. Per-case synthetic
expectations may be public; native/final outcomes remain private with B.
This contract is a validation oracle, not a replacement comparison runtime or
cyano visualizer implementation. No native accuracy or recoding-effect claim
follows from passing it.

## Frozen synthetic implementation

[`edit_maps.py`](../../benchmarks/recoding/edit_maps.py) is an independent
benchmark oracle, not a production comparator. `build_map` validates exact edits
against both supplied sequences and returns both partial base maps. `map_interval`
enumerates every base, keeps nulls and returns split runs plus separate complete
mapping and contiguous-path flags. `project_base` checks the declared projection
and composes strands. `pair_candidates` validates caller-supplied complete rosters,
requires four separate SHA256 identities (model, settings, backend, calibration)
and retains every unmatched or unsuccessful candidate. A finite difference that
overflows binary64 remains null with `nonfinite_delta`.

The [12 literal input/map fixtures](../../benchmarks/recoding/synthetic-edit-fixtures.json)
are synthetic. They cover unchanged sequence, declared no-change edit,
substitution, internal/initial/terminal insertion, deletion, unequal replacement,
adjacent edits, whole replacement and circular-origin controls. Literal expected
forward/inverse maps were written independently of the implementation. Tests
exhaust their interval paths on both strands and enumerate small-contig genomic
projections. Fixed candidate fixtures check geometric unmatched reasons,
unchanged sequence/model controls, each identity mismatch, zero versus null,
all four unsuccessful statuses on both sides and overflow propagation. No
score in these tests comes from a predictor or an assay.

```sh
PYTHONPATH=src:. python -m coverage run --branch --source=benchmarks.recoding \
  -m pytest -q tests/benchmarks/test_recoding_edit_maps.py
python -m coverage report --fail-under=100
```

The oracle bounds synthetic sequences to 10,000 bases and 20,000 candidate
anchors per side. It is intentionally small enough for exhaustive geometry
checks. Its returned map is used in memory; it does not accept an unverified
serialized mapping as authority. A's producer runtime and exports must receive
an independent exact-candidate check against these frozen expectations before
this ticket's implementation comparison can be resolved.

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

The exact nested input shape is:

```json
{
  "schema_version": "paired-edit-input-1",
  "pair_id": "insertion-example",
  "topology": "linear",
  "current": {"id": "current", "sequence": "ACGT"},
  "recoded": {"id": "recoded", "sequence": "ACTTGT"},
  "edits": [{"id": "e0", "start": 2, "end": 2, "replacement": "TT"}]
}
```

Objects admit exactly the displayed keys. IDs are nonempty strings of at most
128 characters; both sequences have 1–10,000 bases; at most 10,000 edits are
allowed. Coordinates are genuine integers, excluding booleans. The producer
`paired-regulatory-request-1` places this object under `pair`, alongside an
explicit `calculator`, `current_request`, `recoded_request` and `settings`.
Predictor requests bind each side's ID and normalized sequence and supply its
own scan/strand/projection. This example describes geometry only; it is not a
complete predictor request or a scoring-feasible RBS construct.

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
and Promoter TSS anchors are distinct universes. RBS correspondence additionally
requires all three start-codon bases to map to the other codon in transcription
order: `[b,b+1,b+2]` on local `+` and `[b,b-1,b-2]` on local `-`. The complete
path must fit inside the supplied string; circular genomic projection does not
wrap its codon. Equal-length motif substitutions can still correspond. If a
same-strand mapped anchor exists but the three-base paths disagree, retain both
candidates as unmatched with `interrupted_codon`. Without such an anchor
counterpart, the reason remains `mapped_anchor_absent`, even if internal codon
bases are also disrupted. A feature crossing an edit is reported separately
from its anchor mapping.

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

That original `paired-prediction-audit-1` helper checks generic anchor-based
score accounting. Its accepted pairs alone do not establish the additional RBS
three-base correspondence requirement. Use the codon-specific expectations below
when evaluating RBS matching; Promoter matching uses its mapped TSS anchor.

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

## Calculator-sized synthetic pairs

The [nine long pairs](../../benchmarks/recoding/runtime-pair-fixtures.json) use
explicit 197–203-base synthetic backbones, with 18 supplied sequences, 17 literal
RBS start candidates and 4,108 full-context Promoter positions across both local
strands. They contain no measurements or predicted score expectations. The file
SHA256 is `9ea3b25074c01502d8149dba99edc2e6cf6011f6940f9d5b3a074bfdcadb357c`.

These inputs cover unchanged sequences, a declared no-change substitution,
plus-strand creation/removal, minus-strand creation, indels before an anchor, unequal replacement
of an anchor and circular reverse projection. Every side has its own projection
and complete candidate universe. The insertion case deliberately retains a
reverse-strand TTG created across its junction: its anchor maps to an existing
base, so it is a newly eligible candidate at a mapped coordinate, not a newly
inserted anchor. Literal codon lists are checked by independent direct enumeration.

Promoter ranges in this **benchmark panel** are oriented TSS ranges `[67,L-19)`;
they are not a combined public scan request. For local `-`, convert each TSS `t`
to forward base `L-1-t` (equivalently forward range `[19,L-67)` in increasing
order). Every listed position has all 30 source states. RBS lists include only
ATG/GTG/TTG codons fully inside the supplied string; circular genomic projection
does not silently add a codon across that string's ends. Feature probes preserve
split intervals and unmatched bases independently of anchor matching.

The test uses synthetic zero scores solely to verify matching/difference
accounting; these are explicitly not model outputs. Actual paired RBS/Promoter
execution, resource/failure coverage and numerical unchanged controls require
A's versioned public comparison candidate and an execution receipt. This panel
must not be presented as experimental evidence of a recoding effect.

```sh
PYTHONPATH=src:. python -m pytest -q tests/benchmarks/test_recoding_runtime_panel.py
```

## Three-base RBS correspondence

The separate [19-case panel](../../benchmarks/recoding/rbs-codon-correspondence-fixtures.json)
has SHA256 `4dcd59ec3195178e93aa575524572ea94f012433701a615effb4fc7cb94283e6`.
It preserves 19 current and 21 recoded candidates: six matched pairs and 16
unmatched rows specifically caused by interrupted codon correspondence. Literal
maps and expected partitions were fixed before implementing the
[codon oracle](../../benchmarks/recoding/codon_pairs.py). The earlier 12-map and
nine-long-pair files retain their original bytes.

`match_rbs_candidates(document, current, recoded)` revalidates the original
`paired-edit-input-1`, then accepts ordered rosters of exactly `{id,base,strand}`.
It neither discovers motifs nor reads scores. IDs are nonempty and at most 128
characters; coordinates are genuine integers; each side has unique IDs and
anchor/strand pairs and at most 20,000 candidates. A caller must preserve failed
candidate geometry when constructing these rosters. All three bases must fit,
including for circular inputs. The returned `rbs-codon-correspondence-1` keeps
both local/mapped paths, matched IDs, and both unmatched lists in their respective
input orders. Every candidate belongs to exactly one pair or unmatched entry.

For example, inserting `TG` after the first base of `ATG` gives `ATGTG`.
The old codon path `[0,1,2]` maps to `[0,3,4]`, while the new codon at anchor 0
uses `[0,1,2]`: both anchors are retained as `interrupted_codon`. The additional
`GTG` at anchor 2 has an inserted coordinate. On the reverse complement, the
same requirement holds in decreasing local-index order. By contrast, a declared
equal-length `ATG`→`GTG` substitution preserves all three positions and matches.

Other cases cover third-base insertion/deletion, internal unequal replacements,
intact shifts, changed strand, changed motif eligibility, whole replacement and
circular nonwrapping. Short strings test geometry only, not RBS scoring feasibility.
The tests enumerate each complete ATG/GTG/TTG roster independently, then check
all small single edits using distinct position tokens, sparse rosters and inverse
edits. Boundary/refusal, ordering, empty rosters and input preservation checks are
included. These tests do not establish numerical score or partial-record handling
in A's comparator; those require its immutable public result and execution receipt.

```sh
PYTHONPATH=src:. python -m coverage run --branch --source=benchmarks.recoding \
  -m pytest -q tests/benchmarks/test_recoding_edit_maps.py \
  tests/benchmarks/test_recoding_runtime_panel.py \
  tests/benchmarks/test_recoding_codon_pairs.py
python -m coverage report --fail-under=100
```

## Public paired-result audit and frozen execution panel

[`runtime_check`](../../benchmarks/recoding/runtime_check.py) imports only B's
edit/codon oracles and standard-library helpers. `build_requests()` returns the
36 explicit requests and a byte/count manifest from the unchanged long-pair
fixture. `check_result(original_request, received_bytes, expected_limits)` checks
strict JSON, received and authoritative result-byte caps, public identity/hash
payloads, candidate rosters, three-base codon matches, feature/genomic mapping,
scalar extraction/deltas, units, ordering, warnings and all failure/null counts.
Caller-supplied limits must be the candidate's complete effective limits,
including its nested predictor limits; public ceilings are not an admission.

Valid integral numeric coordinates and anti-SD normalization follow the public
component contracts; raw input values remain intact in request hashes. Missing
Promoter projection strand resolves to `+`. Invalid inputs retain their raw
identity rather than receiving invented normalized values. Regression tests
cover these defaults and normalization distinctions, including `0` versus `0.0`.

This is a wrapper audit, not an independent scorer. Its returned scope is
`public_hashes_geometry_extraction_arithmetic_accounting` and
`native_prediction_admitted` is false. Root separately verifies the installed
candidate/model/backend, public result schemas, native input bindings and
source-parity admission. Hash consistency alone cannot establish model equations,
selected-state correctness or biological accuracy.

The [preparation](../../benchmarks/recoding/wave5-paired-preparation.json) pins
candidate `920215602a837b0fd2fed403512f3b3ed59bfda2`, verified package CI, the
reviewed checker and every request's exact bytes/hash before collection. There
are 18 Promoter jobs with 4,108 positions and 18 historical RBS jobs with 17
explicit starts; empty lists remain explicit. Promoter uses 30 seconds per side,
RBS 60; the serial stage is capped at 3,600 seconds, with a 30-second process-exit
allowance inside that stage. Each outer job timeout is the smaller of fresh
remaining stage time and twice its side budget plus that allowance. No retry,
adaptive repacking, extra predictor jobs or optional standby profile is planned.
Existing unchanged-sequence pairs supply identity controls. Artificial public
result mutations test missing/failure propagation separately from actual scoring.

The compact ASCII request-list SHA256 is
`035ff8875ef9bca9c158a7b6ad7c72db15ef52fb242ce3247c7d7b8aa412ed8d`.
Execution still requires a reviewed durable collector and explicit B
acknowledgement. Candidate-universe changes remain separate from biologically
lost/added regulation; the synthetic panel contains no experimental outcome.

Root reproduced 264 tests and 17 subtests at 100% of 640 statements/256 branches
across the four recoding modules. Independent exact-patch review approved the
normalization repair at `1286daef57109099ff328425534e6507f1c4e155` after 167
focused tests and adversarial probes; the original 36-job manifest is unchanged.

```sh
PYTHONPATH=. python -m coverage run --branch --source=benchmarks.recoding \
  -m pytest -q --confcutdir=tests/benchmarks \
  tests/benchmarks/test_recoding_edit_maps.py \
  tests/benchmarks/test_recoding_runtime_panel.py \
  tests/benchmarks/test_recoding_codon_pairs.py \
  tests/benchmarks/test_recoding_runtime_check.py
python -m coverage report --fail-under=100
```

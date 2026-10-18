# Paired regulatory prediction runtime contract

- Purpose: Compare supplied current and recoded sequences without confusing geometric changes, model scores and measured regulation.
- Scope: A ticket #41; producer library/CLI and portable results. Implementation follows the Promoter candidate freeze.
- Last verified: 2026-10-18

This is an implementation contract, not an executed comparator. B's independent
`paired-edit-input-1` convention and frozen synthetic maps are authoritative for
geometry; see B ticket #39. The calculator models remain unchanged. No optimizer,
new fitted threshold, experimental improvement or consumer admission is implied.

## Input and identity

`regsite-compare INPUT` accepts one `paired-regulatory-request-1` object:

```json
{
  "schema_version": "paired-regulatory-request-1",
  "pair": {
    "schema_version": "paired-edit-input-1",
    "pair_id": "synthetic-pair",
    "topology": "linear",
    "current": {"id": "current", "sequence": "ACGT"},
    "recoded": {"id": "recoded", "sequence": "ATGT"},
    "edits": [{"id": "e0", "start": 1, "end": 2, "replacement": "T"}]
  },
  "calculator": "promoter",
  "current_request": {},
  "recoded_request": {},
  "settings": {"seconds_per_side": 30.0}
}
```

The empty predictor requests above illustrate nesting only; executable examples
must supply complete valid requests. `current_request` and `recoded_request` are
the existing calculator's single-record requests, including matching side IDs
and sequences. Their normalized DNA must exactly match the corresponding `pair`
sequence. Do not infer a strand, scan, host, anti-SD or calibration from an edit.
The pair strings and replacement strings are strict uppercase ACGT, bounded by
10,000 bases per side; the selected predictor may impose a smaller bound.
Edits require distinct IDs and starts, sorted nonoverlapping current-forward
half-open ranges; no empty-to-empty operation. Applying the exact edits must
reproduce the recoded string. Equal-length replacements explicitly align bases
by position; unequal replacements leave all bases inside each block unmatched.
No sequence alignment or nearest-position matching fills those gaps.

`calculator` is `rbs` or `promoter`. RBS `settings` includes an explicit existing
profile and finite per-side deadline; the CLI takes the separately installed
backend path. Promoter uses the explicit calibration/output/scan in each request
and its installed parameter identity. A backend path is not part of scientific
identity; verified executable/table hashes are. Every effective model, parameter,
backend, host/calibration and score-setting identity is retained on both sides.
The supplied requests and edits are bound by compact sorted finite JSON hashes.
No cached predictions or caller-asserted score files are accepted in this version.

The runtime executes each complete supplied request locally. It may report
different valid settings as incomparable, preserving both predictions; it must
not coerce one side's settings to make a difference calculable. Malformed pair
geometry or inconsistent request sequences is an atomic setup error. Individual
predictor failures remain explicit results. JSON input/output byte, candidate,
edit and wall-time limits are measured and fixed before this comparator freezes.

## Candidate correspondence

Keep both original candidate rosters in full and in their declared order. A
Promoter anchor is its local TSS base; an RBS anchor is the first translated base
of its oriented start codon. For a reverse RBS request with oriented start `s`,
the local anchor is `L-1-s`; its codon path is the next two decreasing local
indices. Never compare the RBS oriented index directly with a local Promoter TSS.

Candidate matching requires the same calculator, local strand and an explicitly
mapped anchor. RBS additionally requires all three codon bases to map contiguously
in transcription order to the opposite codon. This distinguishes an intact anchor
from a codon interrupted by an edit. Candidate motifs may differ after a declared
substitution; report that difference without changing the correspondence rule.
Require at most one counterpart; ambiguous candidate identities are rejected.

Retain distinct reasons for an unmapped source anchor, an unmapped target anchor,
a mapped anchor absent from the other candidate roster, and an interrupted codon.
These are coordinate or candidate-universe changes. They are never labelled
biologically gained/lost regulatory sites. Report both unpaired sides; a failed
or missing prediction cannot erase an expected candidate from the accounting.

## Scores, features and portable output

`paired-regulatory-result-1` contains the pair/edit identities and maps, both
complete predictor results, a comparison roster, coverage counts, warnings and
an explicit completion status. Comparison rows name both candidate IDs where
available. Null means unavailable; it is never a zero score or zero difference.

Only successful finite values under equal model/parameter/backend/calibration
and scoring settings receive `recoded - current` deltas. Retain resource policies
and completeness separately; a partial record's successful sites are diagnostic
comparisons, not a complete pair. A finite-input subtraction that overflows is
null with `nonfinite_delta`. RBS energy and initiation-score differences retain
their existing units; Promoter learned terms never become physical energies.
Log-score differences are not probabilities or measured expression changes.

Each reported model feature retains its source interval, strand, candidate/model
identity and native predictor semantics. To compare a feature, map every base
through the edit map in transcription order, retain missing bases, and reconstruct
ascending half-open runs in that order. An insertion-created gap stays a split
path. Report complete mapping and contiguous mapping separately; a bounding
interval cannot hide a split or missing segment. Compare windows after mapping;
do not claim a binding motif was created merely because a model window moved.

Each side's optional genomic projection is independent and explicit, including
its own origin, contig length and sequence strand. Circular maps span at most
one traversal. An edit crossing the declared origin is split explicitly; no
implicit rotation, inversion or genomic context construction is performed.
The model itself still scores only supplied context and never invents flanks.

The portable JSON export is suitable for a downstream visualizer adapter but
does not alter that repository or bypass its admission rules. Predictions,
measured TSSs and transferred annotations remain separate evidence types.
Threshold classifications and design/optimization modes are outside this first
comparison version; raw scores and missingness remain available to callers.

## Verification and execution order

Freeze the Promoter candidate first, then implement this scope in a separate
worktree so B can evaluate the immutable earlier candidate. Reproduce all B
literal edit fixtures and compare every interval/base path on both strands,
including circular boundaries. Test unchanged-sequence controls, no-change edits,
substitutions, insertion/deletion, unequal replacements, overlaps and malformed
maps. Reject stale sequence/model identity and unrequested settings coercion.

Exercise all failure and limit branches, candidate creation/removal, partial
features, explicit unsupported predictions and nonfinite differences. Run real
offline paired RBS and Promoter examples and a fresh wheel install. New runtime
modules require full statement/branch coverage and an independent exact-patch
review. B evaluates the frozen public result contract against its independent
synthetic fixtures before this scope closes. Biological validation of recoding
effects remains a separate experimental task.

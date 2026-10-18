# Paired regulatory prediction runtime contract

- Purpose: Compare supplied current and recoded sequences without confusing geometric changes, model scores and measured regulation.
- Scope: A ticket #41; producer library/CLI and portable results. Edit geometry and predictor orchestration proceed in an isolated branch against the reviewed public runtime; evaluation and release bind an immutable candidate.
- Last verified: 2026-10-18

This contract describes the locally executable paired library. B's independent
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
edit and wall-time limits below are enforced provisionally. Parent resource
measurement and an immutable receipt are required before this comparator freezes.

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

Implement the comparator in a separate worktree against the reviewed public
RBS/Promoter interfaces. Preserve the Promoter candidate branch and artifacts
while its resource/CI receipt completes; comparator development cannot mutate
that earlier evaluation candidate. Final comparator evaluation binds its own
immutable package/settings receipt. Reproduce all B
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


## First executable integration boundary

The library entry point is `regsite.paired.predict_pair(document, backend=None)`;
`PairError` reports atomic setup failures. It takes raw JSON-compatible documents,
never a caller-constructed edit map or cached prediction. The pure edit factory
is the sole geometry validation entry point. A separately verified `RnaStructure`
object is required for RBS inference; Promoter needs no folding backend.

The exact required outer keys are the six shown above. An optional `projections`
object is permitted only for RBS, with exactly `current` and `recoded` keys, each
null or a complete public projection. Promoter projections remain inside its
existing side requests; supplying both representations is rejected. A missing
RBS projections object resolves to two explicit nulls. RBS side requests require
explicit `id`, `sequence`, `strand`, `anti_sd`, `temperature_c` and `host` (which
may be null). Promoter requires its existing explicit calibration and scan.

`settings.seconds_per_side` is required and finite in `(0,120]`. RBS additionally
requires an existing `profile`; Promoter rejects that setting. Both side requests
are retained. Candidate policies/positions may differ and are not coerced; they
belong to the independent candidate universes, not the numerical model identity.
Resource settings and deadline-induced failures remain visible separately.

A comparison's four separate SHA256 identities bind the complete model and
parameters, effective scoring settings, verified backend (or explicit no-backend
identity), and calibration/host configuration. For RBS, anti-SD and temperature
are effective settings, and profile is bound by the model/setting identity.
For Promoter, the complete resolved calibration including host is retained.
Request IDs, sequence hashes, candidate positions, output verbosity and genomic
projection do not make otherwise identical scoring settings incomparable.
Every such omitted field remains bound in the full pair/prediction identity.

For RBS, enumerate the complete explicit or standard scanned start roster before
executing the backend. Retain a requested but unreturned candidate as unavailable
rather than erasing it. For either calculator, an invalid request with an
unresolvable scan has an explicitly unknown roster, never an empty one. Opposite
candidates then have an unavailable-counterpart reason rather than an assertion
that the opposite candidate is absent. Malformed pair/sequence binding is an
atomic setup error; predictor-level invalid, unsupported, failed and no-candidate
records retain their original semantics and complete diagnostic results.

The initial portable export is JSON plus a flat CSV comparison view. The JSON
retains both full predictions, candidate rosters, four-part identities, mapped
features, coverage and scalar differences. Existing per-side GFF3 is available
through the original projected predictors; a difference row is not itself a
new biological feature. A single RBS comparison uses the explicitly supplied
strand on each side; callers request the other strand separately.

## Literal library result contract

`predict_pair(document: object, backend: RnaStructure | None = None) -> dict`
returns exactly these top-level keys:

```text
schema_version: "paired-regulatory-result-1"
pair_id: string
calculator: "rbs" | "promoter"
status: "complete" | "partial" | "incomparable" | "unavailable"
request_sha256: lowercase SHA256
prediction_sha256: lowercase SHA256
edit_map: complete paired-edit-map-1 object
settings: exact supplied wrapper settings
limits: wrapper limits plus predictors object described below
sides: {current: Side, recoded: Side}
comparisons: [Comparison, ...]
coverage: Coverage
warnings: [string, ...]
```

A `Side` has exactly `request`, `prediction`, `prediction_sha256`, `identities`,
`projection`, `roster_status`, and `candidates`. `request` is the full supplied
single-record request; `prediction` is the full original RBS result or full
single-record Promoter batch envelope, including original structures, model,
limits, host status, warnings, scientific claims and failure details. These
native results are neither stripped nor rewritten. `projection` is the resolved
side projection or null. `roster_status` is `known` or `unknown`; an empty known
roster has `candidates: []`, while an unknown roster also has an explicit null
expected count. No candidate absence is inferred from an unknown roster.
`identities` has exactly `model_sha256`, `settings_sha256`, `backend_sha256`, and
`calibration_sha256`.

A candidate has exactly `id`, `strand`, `anchor`, `codon_bases`, `status`,
`reason`, `site_index`, `scalars`, `features`, and `genomic`. The anchor is a
zero-based local forward-frame base, with strand `+` or `-`. `codon_bases` is
null for Promoter or the three RBS local bases in translation order. Status is
the native site status, or `unavailable` with
`reason: prediction_candidate_unavailable` when the expected site was not
returned. `site_index` is its zero-based index in the complete native `sites`
array, or null. Candidate order follows the native resolved roster (RBS sorted
oriented starts; Promoter declared strand/range or positions order). Candidates
have IDs `pcandidate1:<scope32>:<side>:<calculator>:<strand>:<anchor>`, where
`scope32` is the first 32 hex characters of the canonical hash of
`{request, identities, projection}`. IDs thus bind the full side request and
scientific/projection identities; they are not a cross-sequence join key.

Every scalar and delta has exactly `{value, unit, reason}`. `value` is finite or
null; `reason` is null for a present value. A legitimate zero remains zero.
RBS scalar names are the native energy field names:
`dG_mRNA`, `dG_mRNA_native_prediction`, `dG_cofold_native_prediction`,
`dG_cofold_search`, `dG_search_with_spacing`, `dG_complex`, `dG_spacing`,
`dG_start`, `dG_standby_signed`, `dG_accessible_complex`, `dG_total`,
`dG_standby`, `dG_distortion`, `dG_unfolding`, `dG_unfolding_raw`, `dG_sliding`,
and `dG_post_footprint`, each in `kcal/mol`. Missing profile-specific terms
remain null. `tir` uses `relative_initiation_score`; `log_tir` uses
`ln_relative_initiation_score`. Promoter terms `hex10`, `hex35`, `discriminator`,
`extended10`, `itr`, `up`, `spacer`, `intercept`, `total`, and `binding` use
`source_dG_units`, the model's learned source units, never physical kcal/mol.
`relative_transcription_score` and `log_relative_transcription_score` use the
same respective strings as their units, with the latter unit prefixed `ln_`
instead of `log_`. The native log is a natural logarithm. Missing values use
`value_unavailable`, or the native relative-score status for an unrepresentable
Promoter relative score. No term sum is recomputed by the wrapper.

A feature has exactly `{interval, strand, mapping, genomic, reason}`. `interval`
is an ascending half-open local pair `[start,end]`, or null with
`reason: feature_unavailable`; `mapping` and `genomic` are then null. Otherwise
`reason` is null and `mapping` is exactly the edit factory's
`{source_bases, mapped_bases, mapped_runs, unmatched_bases,
complete_base_mapping, contiguous_target_path}`. All bases are retained in
transcription order, including explicit null mappings. Circular runs may split
at the origin while retaining a contiguous circular path. Each `genomic` object
has exactly `{projection, strand, bases}` and projects the source bases using
that side's own resolved projection; it is null without a projection.
Candidate `genomic` uses the same shape with its one anchor base.

RBS features always name `start_codon`, `window`, `binding_interval`,
`standby_interval`, and `coding_footprint`. They use only intervals returned by
the predictor; unavailable intervals remain null. When present, the native
standby intervals add `standby.original_hairpin`, `standby.hairpin`,
`standby.distal`, `standby.proximal`, and
`standby.downstream_hairpins.<zero-based-index>`. Native pair arrays keep their
original window-relative coordinate space inside the full prediction, rather
than being presented as invented binding features. Promoter always names its
selected state's `UP`, `gap`, `hex35`, `spacer`, `extended10`, `hex10`,
`discriminator`, and `itr` intervals; all are null when no state was selected.
All-state verbosity does not duplicate every state's features in the wrapper.

A comparison has exactly `current_candidate_id`, `recoded_candidate_id`,
`status`, `reason`, `identity_mismatches`, `deltas`, and `feature_changes`.
Candidates match only by mapped local anchor, equal local strand and, for RBS,
exactly corresponding three-base codon paths. Rows visit current candidates in
order, followed by unpaired recoded candidates in order. The status is `paired`,
`unmatched`, or `unavailable`; an unavailable row specifically means the
opposite roster is unknown. One candidate ID is null for an unpaired row.
`identity_mismatches` lists differing identity key names in model, settings,
backend, calibration order, even on unpaired rows. Row reasons are:

- null for geometrically paired, successful candidates with compatible identities;
- `incompatible_identity` when paired scientific identities differ;
- `unsuccessful_candidate` when compatible paired candidates are not both `ok`;
- `counterpart_roster_unknown` when the opposite roster cannot be resolved;
- `unmapped_current_anchor` or `unmapped_recoded_anchor` for an unmatched base;
- `mapped_anchor_absent_from_recoded_roster` or
  `mapped_anchor_absent_from_current_roster` for a known absent counterpart;
- `interrupted_codon` on both unpaired rows when anchors correspond but the
  three RBS bases do not.

`deltas` has the same scalar keys and units as candidates. It is always
`recoded - current`; row reasons suppress all deltas. Per-value missingness uses
`value_unavailable`; finite operands whose subtraction overflows use
`nonfinite_delta`. Overflow does not replace the original finite scalar values.
`feature_changes` is empty on unpaired rows. Paired rows use the union of feature
names, each with exactly `{mapped_bases_equal, reason}`. Equality compares every
mapped current base to the recoded feature's source path and requires complete
mapping; missing features give null equality with `feature_unavailable`.
It does not classify biological gains or losses.

`Coverage` has `current` and `recoded` objects, each with exactly `expected`,
`returned`, `scored`, and `complete`. Expected is null for an unknown roster;
returned counts candidates with a native site index; scored counts `ok` sites.
Side completeness requires a known roster, every candidate returned, and a
native `ok` or `no_candidate` record. Native context completeness remains in
the full predictions. Coverage also has `paired`, `unmatched`, `comparable`,
`complete`, and `diagnostic_only`. `unmatched` counts all unpaired rows,
including unavailable ones. Comparable counts paired rows with null row reason;
it does not promise every optional scalar is available. Overall completeness
requires both side completeness flags, independently of identity compatibility.
Diagnostic-only is true when execution is incomplete.

Top-level status is `complete` for complete execution and equal scientific
identities, including empty rosters and geometrically unmatched candidates.
Complete execution with differing identities is `incomparable`. Incomplete
execution with at least one comparable candidate pair is `partial`; otherwise
it is `unavailable`. Thus partial-record successful differences remain
available as diagnostics and never yield full success. Warnings always include
`predicted_differences_are_not_measured_regulatory_effects`; incomplete execution
also includes `partial_predictions_are_diagnostic_only`. Native scientific
warnings remain independently present inside both complete predictions.

## Exact hashing and provisional bounds

Wrapper hashes use SHA256 of `json.dumps(value, sort_keys=True,
separators=(",", ":"), allow_nan=False)` encoded as ASCII (default JSON ASCII
escaping). `request_sha256` binds the full raw JSON request, including exact
sequence spellings, IDs, pair topology/edits, requests, verbosity, projections
and resource settings. Each side `prediction_sha256` binds its entire original
predictor output. Top-level `prediction_sha256` binds every result field except
itself, including both complete predictions, maps, comparison rows, warnings,
coverage and effective limits. There is no timestamp or elapsed-time field.
Deadline-dependent outcomes can differ and then produce different result hashes.
The factory's sequence hashes bind exact uppercase DNA UTF-8 bytes; its edit
hash binds compact sorted JSON of the complete edit list.

The model digest binds the full emitted model, including source pins, parameter
identities, implementation version and scientific flags. Backend binds the
complete verified backend identity (executable/table hashes and settings, never
the installation path), or `{kind: stdlib_no_folding_backend}` for Promoter.
RBS settings bind effective normalized `anti_sd` and numeric `temperature_c`;
the outer resolved profile is already bound by the full model. RBS calibration
binds `{host, host_calibration: not_calibrated}`. Invalid RBS requests retain
raw values for these diagnostics and cannot receive successful deltas.
Promoter settings bind `{selection: minimum_source_total_first_visited_exact_tie}`;
calibration binds its complete native resolved calibration, including host and
scientific warnings. Sequences, candidate policies, output settings, IDs,
projections and deadlines are excluded from these four compatibility hashes
but remain bound by full request/result hashes. Different valid scans or
verbosity never force a common request or change the scientific model.

| Enforced wrapper bound | Value |
| --- | --- |
| Compact canonical input bytes | 2,000,000 |
| Authoritative result bytes | 67,108,864 |
| Candidates per side | 512 |
| Edits | 1,000 |
| Pair bases per side | 10,000 |
| Conservative source feature-base budget across both sides | 2,000,000 |
| Seconds per side | finite `(0,120]` |
| JSON depth / nodes | 20 / 100,000 |

`result_bytes` is authoritative pretty JSON: sorted keys, indent 2, finite
numbers, ASCII escaping and exactly one trailing LF. Its full byte length,
including verbose native predictions and duplicated feature maps, must fit the
output cap. There is no silent clipping. Input validation and both roster caps
finish before either predictor runs. A conservative preflight feature budget
charges 2,000 bases per RBS candidate or 100 per Promoter candidate, covering
all selected source intervals including standby features. The 512-per-side cap
and feature budget both apply; two full 512-candidate RBS rosters exceed the
combined feature budget. Per-base target maps and independent genomic maps
remain included in the authoritative output-byte check.

`limits.predictors.promoter` exposes the complete installed `promoter_io.LIMITS`
(5,000 bases/record, 1,000 sites/record, 4,000 sites/batch, 100 all-state sites
and 2,000 all-state entries/record, 2,000 entries/batch, among its other limits).
Each side is its own one-record batch, with the same explicit seconds used as
record and batch budgets. `limits.predictors.rbs` exposes 10,000 normalized
bases/record, 1,000 explicit or scanned starts, and 120 seconds/record; backend
search limits remain in its full emitted identity. Wrapper limits only lower
these limits; they do not change or bypass native limits. The public ~230-site
both-strand Promoter long-pair cases fit without clipping.

Only finite JSON objects/lists/scalars with string keys are accepted. Cycles,
excessive nesting, tuples, nonfinite floats, unknown outer fields, stale pair
sequence/ID bindings, caller-constructed maps and malformed edit geometry raise
`PairError` before prediction. RBS explicit scientific fields are mandatory.
Promoter side envelopes (`records`/`defaults`) and unsupported outer side schema
versions are atomic setup errors: each side must be one native schema-1.0
record. Remaining predictor-level invalid/unsupported controls retain their
native per-record statuses. Genomic projection errors in the optional outer
RBS projections object are atomic; Promoter projection errors remain native
record errors. RBS projections require all six public projection fields.

These resource caps are provisional implementation limits, not measured
production admission. Parent measurement, CLI/schema/fresh-wheel verification,
independent exact-patch review and B's immutable-candidate comparison remain
separate gates. Focused paired tests exercise real synthetic RBS and Promoter
unchanged and changed inputs; they do not rerun or tune any frozen native cohort.

Focused verification (the existing shared backend fixture requires
`REGSITE_RNASTRUCTURE`; a skipped real-backend case is not release validation):

```sh
PYTHONPATH=src:. .venv/bin/python -m pytest -q tests/test_paired.py \
  --cov=regsite.paired --cov-report=term-missing --cov-fail-under=100
.venv/bin/ruff check src/regsite/paired.py tests/test_paired.py
.venv/bin/ruff format --check src/regsite/paired.py tests/test_paired.py
.venv/bin/mypy src/regsite/paired.py tests/test_paired.py
git diff --check
```

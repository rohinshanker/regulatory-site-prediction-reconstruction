# Joint binding and standby selection

- Purpose: Define a complete bounded selection objective before implementation/evaluation.
- Profile: `joint_standby`; model `joint-standby-rnastructure-6.6-reconstruction-1`.
- Result version: 1.3; input version remains 1.0.
- Specification date: 2026-10-17; no experimental outcomes used to choose this algorithm.

## Objective and preserved components

This is an original reconstruction extension, not a recovered production version.
It reuses the [standby equations and state geometry](rbs-standby.md), the 100/100-nt
context and 13-nt footprint, scalar parameters and fixed-state folding adapter.
Historical, footprint2017, context2017 and standby2014 retain their existing
selection, arithmetic, schemas and defaults. Learned weights remain unchanged.

Call cofold once. Keep the same interstrand-connected candidates, aligned-spacing
eligibility and energy <= lowest connected energy + 3 kcal/mol + 1e-9 filter as
standby2014. Enumerate eligible candidates in original backend order. For each:

1. Fold the prefix before its first bound mRNA base and the post-footprint suffix.
2. Assemble and evaluate the full complex with the candidate's intermolecular
   pairs, prefix and suffix. Do not substitute its preliminary cofold energy.
3. Evaluate the complete existing standby opening search for this complex.
4. Calculate `total = (complex + spacing) + start - unbound + standby`, using
   the existing signed-term arithmetic order internally. Complex is the original
   assembled state; the changed energy is not added a second time.

Select by (complete total energy, original enumeration index). The module/state
tie policy inside each candidate is unchanged. The greedy counterfactual uses
(cofold energy + spacing, original enumeration index) over the exact same set,
and reports its *complete* energy after its own standby optimization. Neither
score is fitted to experiments. Lower computed energy is not biological proof.

No cross-candidate deduplication is performed: duplicate tracebacks retain their
original indices and each must complete. Within a candidate, the standby search
evaluates each unique ancestor-closed pairing state once, as before. Candidate
identity combines its original index with SHA-256 of canonical JSON containing
the cofold sequence and complete pairing array. It identifies a returned cofold
state, not a biological regulatory element; the containing prediction identity
provides model/settings/input/backend context.

## Limits, failure and diagnostics

The backend's existing limit is 100 returned structures. Each standby candidate
permits at most 512 unique fixed opening states. The new profile permits at most
4,096 attempted bound fixed-state evaluations per site, counting each assembled
baseline and each opening. Prefix/suffix/unbound folds and cofold evaluations are
separate operations under the same record deadline, not hidden opening states.
All candidates share the default 60-second record budget (configurable through
the existing API/CLI up to 120 seconds); backend processes retain their 15-second
maximum. There is no approximate early winner or experimental-data-based pruning.

Before the 4,097th bound-state evaluation, return unsupported. Any eligible
candidate's backend error, numerical failure, timeout or per-candidate limit
halts the search, leaves the site score/energy/structures null, and records the
completed, failed and not-evaluated candidate counts. Do not silently skip it.
The search object retains individually completed candidate diagnostics, without
a selected winner or greedy counterfactual for an incomplete search. If only the
final score transformation overflows after a complete search, preserve complete
search diagnostics but leave the site score/energies null with failed status.

`joint_search` is null when candidate search never produced a list. Otherwise
it records returned/connected/eligible/evaluated/failed/not-evaluated counts,
attempted/evaluated bound-state counts, completion, per-candidate status/reason,
stable candidate ID and index, preliminary score, complete total and standby
cost, and selected/greedy identities with the greedy complete energy. An empty
eligible set is a complete empty search, with no selected or greedy candidate.
All counts describe actual work; incomplete states never become numeric zero
predictions. Any negative raw unfolding encountered in an evaluated candidate
is explicitly flagged; its clamped energy policy remains unchanged.

Schema 1.3 retains selected structures, module intervals, positive standby terms
and the same strand/origin conventions as 1.2, adding the search diagnostics.
Native JSON embeds the new version and projects its selected intervals. CSV
remains the documented compact selected-score/coordinate/identity summary;
full search provenance and structures are in JSON. GFF3 retains the established
features and does not invent boundaries for unselected alternatives.

## Verification and interpretation

Verify against independent synthetic fixed-state energies where the preliminary
winner is worse after standby, singleton equality, ties and duplicate tracebacks,
invalid/no-eligible inputs, all limit/error branches, nonfinite energies, partial
progress and both strands/circular projections. Complete successful searches
must satisfy selected total <= greedy total within numerical tolerance. Test
against real original/traceback-2 engines and preserve earlier-profile numerical
outputs. Measure work/time on synthetic and public development inputs before
freezing this profile for B; final outcomes cannot change limits or parameters.

The optimization is complete only over the declared filtered returned candidates
and their declared opening states. Native cofold enumeration is incomplete and
the energy band excludes other bindings. Refolding into new pairings, simultaneous
opening of multiple original modules, kinetics, stacking extensions, coupling and
ensemble population sums remain outside this model. Independent experimental
ranking, hosted agreement and structural correctness are separate questions.

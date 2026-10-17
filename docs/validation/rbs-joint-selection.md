# Joint binding and standby model card

- Purpose: Define a complete bounded selection objective before implementation/evaluation.
- Scope: Opt-in joint selection, runtime diagnostics and compatibility boundaries.
- Last verified: 2026-10-17
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
4. Calculate `total = complex + spacing + start - unbound + standby`, using
   `math.fsum` over the five signed terms. Complex is the original assembled
   state; the changed energy is not added a second time. Compensated summation
   reduces intermediate-addition rounding; binary terms still have finite precision.
   Earlier profiles keep
   their original arithmetic; singleton totals can differ in the last binary digits.

Find the global minimum complete energy, then select the lowest original index
among candidates at most 1e-9 kcal/mol above that minimum. This absolute numerical
tie tolerance is far below the folding table precision and prevents a few binary
rounding digits from choosing a different reported structure. The comparison is
anchored to the global minimum, not a nontransitive sequence of pairwise tests.
Scores/energies are not rounded; the selected energy can exceed the computed
minimum by at most this tolerance. This pre-final policy was checked against the
independent decimal/sliding tie, without experimental outcomes.

The exact-float module/state tie policy inside each candidate is unchanged.
The greedy counterfactual uses
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

Identical prefix/suffix sequences share a per-site folding cache. Bound-state
energies are not reused across binding candidates. Each candidate's opening
states are submitted in ordered batches of at most 100 structures of the same
sequence, using the same `efn2 --simple --ne` evaluator as single-state execution.
The assembled baseline is evaluated first. Batching changes process overhead,
not the declared geometry, state set or objective; individual/batched fixed-state
energies are required to agree on real-engine controls.

## Limits, failure and diagnostics

The backend's existing limit is 100 returned structures. Each standby candidate
permits at most 512 unique fixed opening states. The new profile permits at most
4,096 attempted bound fixed-state evaluations per site, counting each assembled
baseline and each opening. Prefix/suffix/unbound folds and cofold evaluations are
separate operations under the same record deadline, not hidden opening states.
All candidates share the default 60-second record budget (configurable through
the existing API/CLI up to 120 seconds); backend processes retain their 15-second
maximum. There is no approximate early winner or experimental-data-based pruning.
The wall-time limit is independent of the deterministic state ceiling and can
expire first on a slow or busy host. Neither limit promises that every allowed
state count will finish within the wall-time budget.

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
`failed` includes a candidate halted by an unsupported search limit as well as
a computation error. `state_attempts` counts structures submitted in each batch;
`states_evaluated` counts accepted finite energies from fully validated batches.
If a batch fails, its submitted states remain attempted and none are accepted.
The three candidate counts partition `eligible`; selected/greedy IDs and indices
must identify candidate rows. The schema enforces local types/bounds, complete
row statuses and empty-search semantics; these relational identities are also
checked by runtime tests. All counts describe actual work; incomplete states never become numeric zero
predictions. Any negative raw unfolding encountered in an evaluated candidate
is explicitly flagged; its clamped energy policy remains unchanged.

Schema 1.3 retains selected structures, module intervals, positive standby terms
and the same strand/origin conventions as 1.2, adding the search diagnostics.
Native JSON embeds the new version and projects its selected intervals. CSV
remains the documented compact selected-score/coordinate/identity summary;
full search provenance and structures are in JSON. GFF3 retains the established
features and does not invent boundaries for unselected alternatives.

## Verification and interpretation

This is a deterministic mechanistic reconstruction with no learned weights or
new fitted parameters. Published source parameters retain their notices in the
[standby](rbs-standby.md) and [runtime](rbs-runtime.md) contracts. Original Python
code and synthetic fixtures are GPL-3.0-or-later; separately installed folding
executables remain GPL-2.0-only. No hosted implementation or restrictive folding
library is required. A host name and an anti-SD sequence configure the request;
they do not establish species-specific calibration. The historical scalar
parameters are based on 37 C conditions and are not refitted at other temperatures.

The independent [finite-state fixture](../../benchmarks/rbs/joint-selection-fixtures.json)
checks a greedy loser, singleton and exact candidate/state ties. Its expected
values are derived with Decimal arithmetic independently of the runtime.
[The runtime bridge](../../tests/test_joint_reference.py) checks candidate
selection/total accounting and forward/reverse/circular projection against those
unchanged values, plus the independent reviewer's non-dyadic sliding-cost tie.
These abstract costs are not folding measurements: full
geometry, state enumeration, deadlines, missingness and real engines are checked
separately in the runtime tests. Compensated totals and the declared numerical
candidate-tie tolerance address representation error without changing the
historical profiles or rounding exported energies.

```sh
REGSITE_RNASTRUCTURE=/absolute/path/to/RNAstructure .venv/bin/python -m pytest tests/test_joint_runtime.py tests/test_joint_reference.py tests/benchmarks/test_joint_selection_oracle.py
```

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

The [independent Wave 4 protocol](rbs-wave4-evaluation.md) governs the new-study
comparison. No advancement or native-host accuracy claim follows from the
implementation tests. The public 2014 panel is development evidence, while
Cambray ordinary protein-output ranking is the reserved primary endpoint and
Kuo is exposed secondary. Neither endpoint directly measures absolute initiation
rate; neither supplies native cyanobacterial calibration. The protocol's final
candidate receipt and completed aggregate report are required before a new-study
performance claim.

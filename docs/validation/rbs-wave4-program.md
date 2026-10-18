# Wave 4 implementation and evaluation contract

- Purpose: Improve RBS candidate selection and reliability, then measure new-study performance independently.
- Scope: Two coordinated sessions; an optional fourteen-hour working horizon per session.
- Scientific baseline: `a04ca92837772e1bbe4c47e230235baadecfc099` (Wave 3 integration); scientific files unchanged from `75d127cc350bcc4dc54be5b980db893da3c41e92`.
- Planning baseline: The exact commit supplied in both launch messages; it must contain this document and both Wave 4 prompts and descend from the scientific baseline.
- Last verified: 2026-10-17

This verification covers the planning and repository state, not future implementation.

## Objective and ownership

Deliver a complete, separately identified RBS profile that chooses the binding
candidate using its full assembled initiation energy, including standby costs;
repair the remaining folding failure if a correct source fix can be established;
and execute one frozen independent evaluation. A negative or inconclusive
biological result is a valid completed experiment. Lower computed energy alone
does not establish better prediction.

| Session | Primary implementation | Additional deliverables | Exclusive writing scope |
| --- | --- | --- | --- |
| A | #26 ordinary-W/linker repair; #27 joint binding/standby selection | #6 release-ready RBS artifact, reviewed B integration; #4/#13 updates | Runtime, backend component/builds, schemas, runtime tests, packaging, locks, CI, README and shared runtime contracts |
| B | #28 independent Cambray evaluation and comparator admission | #29 executable Promoter reference and fixtures; broader #1/#12 evidence | Benchmark/evidence code, fixtures, manifests, benchmark tests, evidence contracts and aggregate results |

Each session updates only its ticket files and index rows in its own worktree.
A reconciles the shared indexes during integration. B may execute an immutable
A checkout but may not patch its runtime. A may inspect released aggregate
reports after the final freeze but may not access private outcomes, per-case
residuals, evaluator transcripts or source tables containing reserved labels.
Do not reuse the consumed Wave 2 final cohorts as untouched validation.

Canonical repository:
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/regulatory-site-prediction-reconstruction`

| Session | Branch | New worktree |
| --- | --- | --- |
| A | `wave4/rbs-joint-runtime` | `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-wave4-runtime` |
| B | `wave4/b-independent-evaluation` | `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-wave4-evaluation` |

Create from the same planning commit. Reuse an existing worktree only after
checking its branch, baseline, ownership and dirty state. Preserve newer work;
never reset it to satisfy this plan. Main is still the original planning checkout;
the implementation is in the stacked branches/PRs. Do not implement in main or
the cyano repository. New draft PRs should target `planning/wave4` while that
branch remains the shared parent; inspect ancestry before choosing a different
integration base. Do not rebase frozen candidates or force-push shared work.

## Why joint selection is the next model change

The existing `standby2014` scorer selects a cofold candidate using cofold energy
plus spacing, then assembles the full complex and optimizes standby only for
that candidate (`src/regsite/rbs.py`). Its result explicitly warns about this
ordering. A different candidate can have a worse preliminary score but a better
assembled complex/accessibility cost. This is an implementation-level hypothesis,
not a claim that the published or hosted model uses the proposed algorithm.

The new opt-in profile must evaluate every candidate in the **declared returned
and filtered candidate set**, assemble each candidate with the same context,
footprint, prefix/suffix rules and standby opening search, and select the minimum
complete total energy. Retain the current connectedness, spacing eligibility
and 3-kcal/mol filter initially. Preserve the historical, footprint, context and
Wave 3 standby profiles byte/numerically where their contracts require it.

Specify the total-energy equation, tie order, candidate identity, pair/state
deduplication and limits before implementation. Report returned, eligible,
evaluated and failed counts, selected identity, state counts, and the greedy
counterfactual. Do not label this globally exhaustive RNA folding: bifold already
misses valid tiny topologies and the 3-kcal/mol filter is a search restriction.
Do not introduce an ensemble/Boltzmann sum or kinetic term in this wave.

Every admitted candidate must complete under the declared search, or the site
must report an explicit incomplete/failed result with no definitive winning
score. Never skip an expensive, malformed or failed candidate and claim an
optimum over all candidates. Preserve per-record deadlines, deterministic ties
and null-score failure semantics. Select total-work limits on synthetic/public
development inputs before the final freeze, with a hard documented cap. The
initial engineering envelope is at most 100 returned candidates, 512 opening
states per candidate and 4,096 opening states per site; change it only with
pre-final resource evidence and a versioned contract. Existing profiles keep
their existing limits.

Meaningful tests include an independent finite-state oracle where the greedy
winner loses after standby, exact agreement when there is only one candidate,
ties/duplicate states, no viable candidate, unsupported starts, boundary contexts,
resource exhaustion, backend failures and both strands/circular projections.
For complete searches over shared states, selected total energy must be no worse
than the greedy counterfactual within the declared numerical tolerance. That
mathematical check does not guarantee a better measured expression estimate.

## Backend repair and freeze

#26 is a separate source task: derive why an ordinary-W fragment crossing the
intermolecular linker receives a finite fill value with no valid traceback.
Do not guess a W2 retag or discard the offending structure. Preserve the pinned
original and traceback-2 installations/receipts. An accepted source change needs
a new component identity, source/patch/build pins, separate GPL-2.0-only packaging,
independent source review, recurrence/structure/energy regressions, ordinary Fold
controls and real runtime/CI tests. Runtime receipts must admit the new version
explicitly. Never replace the implementation behind a frozen identity.

If source reasoning/review cannot establish a valid fix, retain traceback-2,
keep #26 open with its exact remaining invariant, and complete the independent
joint-selection/runtime work. Do not turn an unsuccessful repair into a release
claim. Backend readiness is decided using structural/software evidence, not
experimental final outcomes.

## Independent evaluation and decision rule

Read [new-data admission](rbs-new-evaluation-data.md) before any scoring. The
335 Cambray inputs (112 families, 56 seed blocks; 332 observed ordinary means)
are the fixed final panel. The 261 Kuo inputs (253 means) are exposed secondary.
Do not change panel membership, append missing reporter context or fit on any
part of the reserved Cambray study. Keep input coverage and measured-outcome
denominators separate. Ordinary Cambray protein production is the primary
endpoint; it is neither measured TIR nor RNA-normalized TE.

B implements/reviews the evaluation runner using synthetic labels first and
commits the complete protocol before joining any candidate predictions to real
outcomes. A supplies an immutable candidate receipt: commits, model/profile and
schema identities, code/weight/parameter hashes, engine/source/patch/binary/table
identities, input/split hashes, host/aSD/temperature, all limits, comparator
exposure declarations and the exact commands. B acknowledges the receipt before
the final run. Inputs alone may be shared with A; outcomes remain with B.

The roster is bounded, with no new model fitting in this wave:

- Historical, Wave 3 standby and the new joint profile on traceback-2.
- The same three profiles on a newly reviewed backend only if #26 is accepted
  before the freeze (six mechanistic configurations maximum).
- Pinned OSTIR, the existing public-reporter sequence model and rebeca as
  optional, separately labelled comparisons (nine learned/mechanistic entries
  maximum altogether). B checks every artifact and exposure claim anew against
  the existing manifests. Failed admission is recorded, not silently replaced
  with a different implementation. Optional restrictive comparator environments
  must never enter the required open runtime or distributed release.
- Simple sequence-only controls specified by B before outcomes, including a
  constant (whose rank correlation is undefined) and a fixed GC-content control.

The primary contrast is joint versus Wave 3 standby on the **same** admitted
backend: the newly reviewed version if ready at freeze, otherwise traceback-2.
Backend-2 versus new-backend results are secondary structural/coverage comparisons.
If the joint candidate is not review-ready, B may execute the predeclared fallback
contrast, standby versus historical on traceback-2, only after A explicitly
freezes that roster and acknowledges that the panel will then be consumed.
Do not run an early final test merely to fill waiting time.

Report tie-aware Spearman correlation, paired seed-block bootstrap uncertainty,
every failure category, all-case coverage, shared-success counts and runtime
distributions. Use 10,000 paired block draws with a committed seed; preserve
ties and report undefined draws, with a prespecified minimum usable-draw rule.
No final-set slope/intercept, arbitrary-unit fold error, final-set feature
selection, outlier trimming or result-driven subgroup creation. Kuo's unknown
log base prohibits log2/fold-error conversion; analyze its contexts separately.

The proposed advancement gate is: at least 95% prediction coverage, no lost
baseline-success cases, paired primary Spearman improvement at least 0.05 with
the 95% block interval above zero, and completed resource/software gates. The
0.05 is a prespecified engineering threshold for added complexity, not a universal
biological accuracy standard. B must check its statistical feasibility with
synthetic/surrogate data and freeze the exact usable-draw and subgroup rules
before outcomes; any justified pre-final amendment needs a visible protocol
commit and A's acknowledgement. No post-result amendment is permitted. All
other contrasts are descriptive unless separately multiplicity-controlled in
that pre-final protocol.

Passing can support a limited claim about ordinary protein-output ranking in
this one E. coli local-context study. It cannot promote native cyanobacterial
calibration, absolute TIR, current hosted parity or universal superiority. All
Cambray sequences share the upstream leader: UTR-only ML models may return a
constant. Detect feature degeneracy without labels and retain the undefined
rank result; do not invent CDS features for an unchanged upstream model. Known
Cambray-trained models and Kuo-trained rebeca are not independent tests on their
training sources. Facilitated Cambray conditions are optional secondary outcomes
only if separately declared before collection; no new coupling model is required.

After the freeze A makes no scoring, selection, backend, parameter or calibration
change against the consumed panel. A genuine scoring bug invalidates the affected
candidate result; preserve it, record the correction and distinguish any rerun
from an untouched evaluation. Never erase failed attempts or reuse the holdout
as development under its old label. B releases aggregate reports with denominators,
uncertainty, hashes and reproduction recipes; raw outcomes/residuals stay private.

## Promoter progress and the release boundary

B's #29 executes the already pinned historical/fork inference in an isolated
research environment and produces independent numeric/coordinate fixtures,
source/weight/dependency notices and mismatch classifications. This is reference
preparation for #7, not the project Promoter runtime. Extend the prior published-
column audit with actual inference checks; keep those two forms of evidence
distinct. Preserve original versus corrected coordinate expectations, especially
reverse `L-t` keys versus `L-1-t` base coordinates and the missing gap in
`scan_arbitrary`. Unknown-host fallback is a historical behavior to label, not
a host-calibration claim. Do not publish restricted measurement workbooks.

If time remains, B can resolve admission gaps for the reserved GSE144621 candidate
and exact native-cyanobacterial sequence/measurement panels. No benchmark labels
should be exposed to A to accelerate implementation. Newly proposed experimental
or paid collection stages remain proposals; no coins, purchases or wet-lab work.

A integrates a tested RBS release candidate under #6: source/wheel, hashes,
notices, installation/upgrade instructions, supported domains and failure limits,
model card, independent result and exact CI identity. A draft PR/local artifact
does **not** close the actual tag/publication milestone. Existing authorization
covers branches and draft PRs, not a main merge, package publication or new tag.
Make the release decision concrete and reviewable before seeking any separately
needed publication authorization. Do not reinterpret this planning document as
permission to publish or waive #7's RBS-release dependency. Promoter runtime,
Operon, Riboswitch and cyano integration remain later implementation work unless
the user explicitly changes that dependency/authorization.

## Coordination, budgets and acceptance

At startup exchange session identity, branch, baseline and ticket claims. Known
Agent Deck identities: A `baf5b738-1792172297`, B `9677689a-1792176763`.
Confirm they still identify the intended sessions. The prior session-send path
hung; use scoped GitHub issue handoffs if transport remains unavailable, without
launching replacement coordinators or repeating unchanged failed sends.
Handoffs include commit, changed paths, decisions, commands/results and remaining
gaps. Do not transmit credentials, raw final outcomes or private filesystem dumps.

Suggested fourteen-hour cadence (checkpoints, not permission by elapsed time):

1. Hours 0–1: claims, input/result handshake, joint-state specification and B's
   evaluation plan. Both start independent work immediately.
2. Hours 1–7: A runtime/backend implementation and reviews; B synthetic evaluator,
   comparator/feature admission, independent structural oracle and Promoter work.
3. Around hours 7–8: reviewed scientific freeze. Never bypass a missing review
   or receipt to meet a clock target. Agree the deterministic fallback if needed.
4. Hours 8–12: one independent evaluation, then aggregate handoff. Default maximum
   two scoring processes, 60 seconds per record and four hours total collection;
   benchmark tools must preserve timeout/not-run statuses and full denominators.
   A records package/CI gates while B owns experimental scoring. Change limits
   only before the freeze on development resource evidence.
5. Hours 12–14: reviewed evidence integration, final CI/fresh installs, model card
   and ticket cleanup. Stop when acceptance is met; the time allowance is not a
   requirement to use the full duration. If the global collection cap is reached,
   mark the report incomplete and do not promote from a success-only subset.

Narrow independent delegation is allowed. Keep A and B as the two coordinators;
never re-dispatch either assignment. Follow the current Multica-first runbooks
and verified model/effort matrix, separate worktrees and exact-patch review.
Each child receives the canonical repository, exact baseline/result target,
scope/ownership, permitted child work, held-out boundary and privilege rules.
At most one additional implementation worker per session; schedule cross-provider
review without competing builds or duplicating B's evidence work. Do not alter
shared agent settings or activate an unrequested coordinator.

Before new credentials, administrator access or macOS permissions, disclose the
exact action/resource/reason and await the user's decision. Never bypass a pending
or denied prompt. No website browser/keychain operations are part of this wave.

Wave acceptance is a real locally runnable joint scorer (or an explicitly
uncompleted ticket), independently reviewed backend disposition, a frozen
evaluation with honest completed/incomplete status, tested Promoter reference
artifacts, and a review-ready RBS release package. Require real backend tests,
all configured branches, fresh offline installs, four-platform CI, source/licence
integrity, clean owned worktrees and exact commit/command reporting. Leave broad
or unfinished tickets open; only each owner closes its own completed scopes.

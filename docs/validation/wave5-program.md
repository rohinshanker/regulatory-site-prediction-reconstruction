# Wave 5: open Promoter implementation and independent native validation

- Purpose: Deliver the next usable calculator and a defensible native benchmark while completing the cumulative RBS release handoff.
- Scope: Two coordinating sessions, Claude-first bounded workers, two phases.
- Starting integration: `9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923`.
- Last verified: 2026-10-18

## Decisions and boundaries

The owner requested this two-phase wave and explicitly prefers more delegation
to Claude because its allowance is less consumed. The cyano visualizer already
handles annotation discrepancies. Reuse its reviewed decisions, source pins and
mapping contracts read-only; do not repeat the same reconciliation or silently
replace it with a new nearest-name/nearest-coordinate mapping.

The most useful immediate scientific addition is the Promoter calculator. Its
open source, parameters and independently executed 212-state reference are ready.
Another RBS optimization against the consumed Cambray/PCC 6803 cohorts would not
produce a new independent accuracy result. Preserve those frozen models and
negative findings. RBS development in this wave is release integration and
explicit transcript-context diagnostics, not another fitted model.

The existing rule makes actual RBS release a prerequisite for Promoter runtime
implementation. A has asked the owner whether isolated Promoter development may
proceed in parallel with release preparation. Until that decision arrives or
the release dependency is actually met, do contracts, source/fixture admission,
benchmark tooling and release review only. Record any owner-approved dependency
change in this contract and the affected parent tickets; elapsed time is not
approval. Main merges, tags, package publication and cyano writes are separate
from branch implementation and are not authorized by this plan.

## Ownership and worktrees

Canonical repository:
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/regulatory-site-prediction-reconstruction`.
Do not write in canonical main or any earlier wave's checkout. All new worktrees
start from the exact shared planning commit supplied in the launch handoff,
which must descend from the starting integration above. Preserve newer work.

| Owner | Tickets and work | Branch | Worktree under `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/` |
| --- | --- | --- | --- |
| Session A `baf5b738-1792172297` | #32 cumulative RBS release handoff; #33 Promoter runtime; #6/#7 parent context and final integration | `wave5/promoter-runtime` | `reconstruction-wave5-runtime` |
| Session B `9677689a-1792176763` | #34 independent Promoter/native validation; #35 Operon/Riboswitch source admission; #1/#12 parent context | `wave5/promoter-evidence` | `reconstruction-wave5-evidence` |

A owns runtime, runtime tests, schemas, packaging/locks/CI, README, AGENTS and
shared runtime/release contracts. B owns benchmark/evidence tools and tests,
input/dataset manifests, protocols, independent source fixtures and aggregate
reports. Each owner edits only its own ticket files/index rows; A reconciles
shared indexes on integration. Do not close an unfinished parent ticket merely
because a scoped child is complete.

## Phase 1: establish the executable and evaluation boundaries

**A — release integration and runtime contract.** Review the complete cumulative
`main..9edb989` tree, including prior exact-patch reviews and final artifact/CI
receipts. Claude review DEM-517 is already running on that immutable candidate;
do not dispatch a duplicate. Address reproduced release blockers in a separate
branch without retuning scientific code. Prepare a single cumulative PR against
main with source/wheel identity, exact review evidence and explicit publication
steps. Keep the current 0.4 artifacts immutable. A new artifact needs a new
identity. Do not merge or publish without concrete authorization.

Specify the Promoter request/result interface before parallel writers begin.
Prefer the existing standard-library foundation if it faithfully implements the
admitted public equations; do not add the legacy scientific stack solely to
load one-hot encoders. Preserve all 343 coefficients and active utility tables,
with exact derivation and notices. The runtime may not import B's independent
oracle. Read `promoter-source-and-benchmarks.md` and
`promoter-executed-reference.md` before selecting this approach.

The contract must cover DNA normalization, explicit calibration/model identity,
sequence-relative forward/reverse TSS points, half-open feature intervals,
requested positions versus scanning, all finite states versus selected state,
deterministic ties, raw term sum, relative score/log-score, stable IDs and
invalid/unsupported/no-candidate/failed results. Correct genomic coordinates
are explicit; legacy `L-t` dictionary keys never become base coordinates. Preserve
the one-base UP/hex35 gap. Unknown host names must not silently imply native
calibration. A target host may accompany an explicitly extrapolated E. coli
profile with a warning; host metadata is not calibration. Sigma levels unused by
the source cannot be represented as an effective regulatory control. Source
`dG` fields are learned score terms, not newly established physical energies.

Define hard record/batch/candidate/output limits and deadlines on synthetic
inputs before freeze. Report truncation or incomplete work explicitly. Design
modes, genome-wide calibrated probabilities, alternate sigma models and new
coefficient fitting remain outside this scoped runtime.

**B — independent inputs, protocol and source admission.** Inspect the existing
visualizer's annotation-discrepancy artifacts and provenance read-only, including
its actual commit and dirty state. Pin the reviewed authority used by the
portable reconstruction pipeline; do not assume matching locus names imply
identical coordinates. Reuse the existing Tan extraction and source hashes.
Keep paper/current alternatives and unresolved mappings explicit. Source-level
Table S1 and condition-specific records take precedence over the documented
legacy pooled aggregation for new diagnostics. Preserve alternate transcripts;
raw counts are not calibrated transcript-mixture weights.

Prepare a protocol with four separate outputs:

1. Numerical/source and coordinate parity against frozen synthetic fixtures and
   separately executed historical/fork inference.
2. Native positive-TSS localization: queries/candidate windows defined by a
   genome grid or annotation-based rule before evaluating model scores, not
   centered on the answer. Report coverage, out-of-window positives, exact and
   predeclared tolerance recovery, conditional ranks and tie handling. Group
   repeated TSSs/conditions/loci; no genome-wide precision or PR-AUC from unlabelled
   sites treated as negatives. TSS truth does not label complete promoter bounds.
3. RBS transcript-context sensitivity using unchanged profiles and a deterministic
   bounded input panel: measured TSS boundary versus the declared genomic-flank
   assumption. Report coverage, energy/rank changes and unsupported leaderless
   cases as input sensitivity, never as demonstrated translation improvement.
4. Promoter strength replication/evaluation only where sequence, condition,
   measurement, rights and train/test exposure permit. Published supplied-column
   audits remain exposed historical replication. Review the existing reserved
   GSE144621 lead rather than launch another broad search. If it fails admission,
   produce the exact missing requirement and complete the other outputs; do not
   manufacture a new independent accuracy claim.

Test evaluator code on synthetic outcomes before final outcomes. Freeze the
input/label identities, source/annotation policy, metric definitions, baseline
roster, grouping, scale conversions, resource caps and interpretation rules.
Keep new evaluation outcomes and per-case residuals with B; A receives input-only
contracts and reviewed aggregates. Already public TSS locations remain public,
but neither session may choose windows/thresholds to improve the final result.

In parallel, a bounded Claude evidence worker should recover complete open
Operon/Riboswitch inference or component paths. Reuse the source map and prior
papers. A wrapper, `.pyc` or live form is not complete code. Pin terms/code/data,
run isolated permitted smoke cases where possible, and deliver precise missing
submodels/parameters plus an ordered implementation contract. Do not begin a
second large calculator implementation or website collection in this wave.

## Phase 2: implement, freeze, independently evaluate and integrate

After the Promoter development dependency is satisfied, A delegates the pure
scoring/scanning core to Claude and retains shared contracts/integration. Delegate
CLI/export work separately only once the core interface is frozen and writer
paths are disjoint. Deliver real single/batch both-strand inference, explicit
model/host transfer warnings, parameter provenance and supported interval exports.
Test boundary windows, ties, overlaps, ambiguous bases, invalid settings, numerical
limits, failures and strand conversions. Preserve every RBS profile and frozen
artifact. Source parity checks must use B's pre-existing fixtures, not expected
values copied from the new runtime.

Cross-provider exact-patch review follows each substantive Claude implementation.
A can perform a focused independent review itself; a reviewer is used for an
unresolved consequential boundary, not as a compulsory extra chain. After tests
and reviews pass, send B one immutable candidate/settings receipt. B acknowledges
the frozen protocol before final collection. Never repair a model against final
outcomes and call the rerun held out.

B executes the frozen numerical/native/strength stages, reports all denominators
and statuses, and has an independent reviewer verify aggregate arithmetic and
claims. Negative or limited results are valid deliverables. A integrates only
reviewed evidence commits, runs the changed scopes and one final full matrix,
and prepares a separate draft Promoter candidate/model card. RBS publication,
Promoter publication and downstream cyano admission remain distinct milestones.

## Delegation and efficiency

Use the current Multica role/runbook and verify authentication, runtime and
capacity before dispatch. Both coordinators keep their selected models. Default
workers: Claude Opus implementer for code, Claude Fable evidence analyst for
bounded source work, Claude Sonnet steward for documentation cleanup. Use Astra
for integration decisions and independent review of consequential Claude patches.
Do not change shared settings or infer Claude access from native Codex spawn.

Reserve one of the two Claude implementer slots for each session while both
have independent code work. Start at most two child tasks per session; replace
a completed worker with the next useful slice. Read-only reviews need no second
source checkout; every writer gets its own worktree with exact baseline and
owned files. Child handoffs forbid rerouting, new coordinators and unrequested
review chains. Check an ambiguous original dispatch before fallback/replacement.

Send concise handoffs: commit, scope, decisions, checks, unresolved findings and
next dependency. Prefer Agent Deck's durable queued send and confirm delivery;
if it fails, use the scoped GitHub issue, not a duplicate coordinator. Do not
read B's private evaluator transcript as a coordination shortcut.

Use hash-addressed input/folding caches whose identity covers full model/backend
settings; never reuse output solely because its filename matches. Reuse admitted
source/fixture artifacts. Use focused tests during edits, full gates at integration,
and do not rebuild/re-run unchanged RBS engines or consumed experiments merely
to occupy both sessions. Limit expensive folding to two processes total on this
machine and agree ownership before launching. Test coverage still applies to
every implemented branch. TypeSafe is for warranted bounded semantic judgments
only, with actual access verified; deterministic joins and arithmetic stay code.

## Acceptance and authorization

Phase 1 is concrete when contracts/protocols and reusable source decisions are
committed, worker assignments are known, and the cumulative RBS PR is reviewable.
Phase 2 is concrete when an actual local Promoter runtime passes source parity,
fresh offline examples, full tests/CI and independent evaluation with an honest
model card. Keep unfinished production/source/release parents open.

No website jobs, coins, purchases, browser/keychain operations or canonical cyano
edits. Before a new credential, administrator password, sudo or macOS permission,
name the exact action, resource and reason and await the user's decision; no
bypass. Public permitted source downloads and branch/PR work are authorized.
No main merge, tag or package publication is implied by a planning or worker
handoff. Report completed versus gated work explicitly.

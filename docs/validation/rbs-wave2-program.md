# Wave 2: native validation, model comparison and improved RBS prediction

- Purpose: Coordinate two long-running sessions toward tested RBS refinements and an evidence-based cyanobacterial improvement decision.
- Scope: Up to fourteen hours per session after the user starts the supplied prompts; this document does not launch work or promise a scientific breakthrough.
- Last verified: 2026-10-16

## Objective and boundaries

Advance the program from historical reconstruction toward the strongest fully
open predictor we can demonstrate on independent experimental data. Prioritize
cyanobacterial translation strength at supplied starts and separately evaluate
native start localization. UTEX 2973 is the desired deployment host; PCC 6803
data inform transfer rather than establish UTEX accuracy.

Maintain three distinct identities: frozen historical reconstruction, published/
hosted compatibility refinements, and experimentally improved profiles. An
improved model may disagree with the website. No “best available” claim without
dated comparator coverage and held-out evidence; no requirement to make such a
claim to complete a useful wave. Other calculators remain planned and source
recovery may continue only after the RBS critical path is served.

Read [native validation](rbs-native-validation.md),
[comparator landscape](rbs-comparator-landscape.md),
[existing experimental protocol](rbs-evaluation-protocol.md),
[runtime contract](rbs-runtime.md), [live-reference contract](rbs-live-reference.md)
and [reconstruction contract](reconstruction-contract.md).
The executable handoffs are [Session A](../prompts/wave2-session-a.md) and
[Session B](../prompts/wave2-session-b.md).

## Owners and file boundaries

| Stream | Session A: implementation and integration | Session B: independent evidence and evaluation |
| --- | --- | --- |
| Tickets | 04, 18, RBS slice of 13, release integration 06 | RBS slices of 01/05/12, new 16/17 |
| Writes | Runtime/model/training source, runtime unit/integration tests, schemas, package/locks/CI, README/AGENTS, reconstruction contract | Source-specific data extraction, datasets/manifests, benchmark/comparator runners and their tests, source/evidence/benchmark cards |
| Native boundary | Portable transcript-aware extraction/scoring/export after receiving an agreed record contract | Source-specific TSS/TIS/CDS associations, confidence and mapping fixtures; independent positional/strength evaluator |
| Improved models | Candidate feature/model implementation, reproducible training, development-only tuning and model cards | Audit training rights/exposure, choose/freeze splits and metrics, run contenders and final evaluation |
| Live site | No browser operation; may use already-authorized diagnostic exports for development | Sole browser owner, immutable jobs/coin ledger, costed additional-panel plan |
| Shared changes | Final cherry-pick/integration, reconcile index rows, package/CI modifications requested by B | Edit only owned tickets/index rows in B worktree; send exact commits and integration requirements |

A owns this program and native/comparator planning contracts until B explicitly
accepts transfer of the evidence documents in the startup handshake. B then owns
the native/comparator contracts; A proposes changes by handoff rather than editing
them concurrently. Neither session edits the cyano repository or canonical main.

Existing identities: A `baf5b738-1792172297` (`cyano-rbs-scraping`), B
`9677689a-1792176763` (`reg-site-reconstruction`). Verify identities/status before
sending. A user prompt is required to begin each wave; do not relaunch the other
session or forward its assignment to a coordinator. Use agent-deck messages when
available; if its durable submission marker rejects delivery, do not bypass or
clear it. Existing GitHub issue comments are an authorized coordination fallback.
Use concise handoffs with owner, scope, commit/base, decisions, tests and gaps.

## Starting point and separate worktrees

Canonical checkout:
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/regulatory-site-prediction-reconstruction`.
The planning branch is `wave1/rbs-runtime`, draft PR 15. It contains the Wave 1
runtime and B's completed live-panel commit `802335dba23f9e532f1cfb2182d952c0f54eb5bd`
integrated as `af2c36f` with formatting/conflict resolution. Confirm exact
current head, ancestry, worktree status and assignments before creating branches.

Both sessions use the same pinned planning baseline specified in their prompts.
Create or safely reuse separate worktrees; never reset or overwrite newer work:

- A: branch `wave2/rbs-models`, worktree
  `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-wave2-models`.
- B: branch `wave2/rbs-validation`, worktree
  `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-wave2-validation`.

If an assignment-owned worktree already exists, inspect its baseline/commits and
continue it. Coordinate conflicting ownership; do not create competing writers.
Do not merge PRs 14/15 or push main as an incidental setup step. New draft PRs
may target `wave1/rbs-runtime` while it remains unmerged; rebase/retarget only after
checking the actual GitHub state and preserving all prior work.

## Work sequence and practical time budget

Time boxes are checkpoints, not permission to stop at a plan or wait idly for a
peer. Stop earlier if the wave acceptance criteria are met. Keep long tools
pollable so the user can steer the work; checkpoint files/commits before context
compaction or ending a run. Fourteen hours of agent time cannot create new wet-lab
measurements or justify repeated final-test tuning.

| Approximate elapsed time | Session A | Session B |
| --- | --- | --- |
| 0–2 h | Verify baseline, run real backend gates, claim tickets, agree contracts; start term-level refined profile fixtures and coordinate adapter | Claim tickets; preserve old holdout, audit/admit Tan + one strength dataset; send early comparator/code/weight licence recommendation and data contract |
| 2–6 h | Implement footprint/context and supported standby refinements with ablations; build native adapter from immutable inputs | Freeze native partitions and outcomes; provide development records and independent mapping fixtures; smoke/run prioritized alternative models |
| 6–10 h | Finish real native batch scoring; fit a finite set of justified simple/hybrid/transfer candidates using development only; freeze candidate commits/weights/settings | Run task-matched baselines, independent comparator and live comparisons; audit power, uncertainty and domain overlap; prepare prospective UTEX proposal if needed |
| 10–12 h | Deliver frozen predictions/interfaces, review B's usable commits, resolve integration defects | Perform the predeclared final evaluation once candidates are frozen, send aggregate results and exact reproducible evidence artifacts |
| 12–14 h | Reserve this block for integration, independent exact-patch review where useful, full CI, fresh install, documentation and draft PR | Finish evidence tests/reports/handoff; review scientific claims and final evaluation integrity; leave incomplete suite scope open |

If no eligible pretrained model runs promptly, B records the bounded failure and
prioritizes another admissible comparator. A can still complete mechanistic
refinements and simple feature/calibration baselines; no architecture depends on
an unreviewed weight file. Do not silently replace another model under its name.
If native labels are too few, produce learning curves, honest baselines and a
measurement proposal instead of training a large network on correlated examples.

Before fitting, predeclare a finite candidate roster and tuning budget (default
at most six profiles, at most 24 configurations total, three fixed seeds for
selected stochastic finalists). B can approve a justified revised budget before
final outcomes are seen. Check available CPU/RAM/disk and share resource bounds;
do not launch competing full-scale jobs or multi-GB downloads blindly. No paid
GPU/cloud instance, coin purchase or wet-lab spending is authorized.

Final-test boundaries are recorded per candidate cohort. Choose the champion on
development validation and predeclare final contrasts/multiplicity treatment.
After seeing final results, revisions go to a new development cycle and require another untouched
evaluation; do not tune against B's final per-case errors. The exposed 12-case
live diagnostic panel is development evidence. Additional live acquisition needs
a frozen count, price/cap and stop conditions published before spending; use the
existing authorizations and ledger without inventing an extra purchase approval.

## Concrete Wave 2 deliverables

1. A usable later-mechanism RBS profile with primary-source parameter provenance,
   explainable output and term-level ablation against the unchanged historical
   profile. Every unimplemented mechanism remains explicit.
2. A portable native transcript-context batch example with verified genomic
   mappings and unsupported/ambiguous cases preserved; TSS evidence cannot become
   translation truth. At least one admitted native TE panel and one independent
   reporter/context panel with task-separated evaluator results.
3. A reproducible competitor matrix with actual predictions from eligible
   mechanistic/empirical and learned methods where usable, missingness and fair
   comparison settings. Ineligible methods stay in the matrix with reasons;
   an unmet executable-comparator criterion remains open work.
4. A frozen experimental comparison of plausible improvements or a quantified
   no-improvement/data-insufficiency finding. A superior profile is released only
   if its predeclared effect/uncertainty/subgroup/coverage gates pass.
5. Integrated source/evidence, branch coverage, fresh offline examples, passing
   CI, exact commits and draft PRs; a release candidate with model applicability
   limits. No automatic main merge, public package publication or cyano UI edit.

Broader TIS evidence admission, prospective measurements, other calculators and
suite-wide tickets may remain open. Report exactly what is concrete, measured,
unimplemented and blocked by new data rather than closing a broad ticket for a
partial slice. “Best in cyanobacteria” requires stronger evidence than finishing
these software deliverables.

## Handoff and access rules

Send early source/data/interface decisions without waiting for a complete survey.
Each handoff includes exact source/result commits, changed paths, tests and
counts, rights decisions, model/backend identities and remaining gaps. A reviews
and integrates B's usable commits; B retains blinded outcomes outside public Git.
No account identifiers, tokens, cookies, private exports or restricted data in
commits, issue comments, CLI logs or prompts.

The owner's Keychain login was verified; the local procedure is
`/Users/Rohin/docs/validation/denovodna-keychain-access.md`. B alone uses live access.
Before an action requiring a new credential, administrator password or macOS
permission, disclose the exact action, resource and reason; honor existing
authorization and wait for any required new decision. Never bypass a denied or
pending permission. Ordinary inference never depends on these credentials.

Do not spawn another coordinator or resubmit either assignment. Any worthwhile
narrow delegation must follow the user's current Multica/model-routing runbooks,
preserve file/holdout/browser ownership and disclose privilege requirements in
the handoff. Native fallback is allowed only for the documented concrete reason;
an exact-patch read-only review is preferable to duplicating implementation.

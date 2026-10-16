# O_13-ground-truth-model-improvements__20261016 — Open

- Scope: Implement and test scientifically justified improvements in experimental predictive accuracy, RBS first.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Improvement hypotheses are proposed; no improvement has been demonstrated or implemented.
- Verification: Acceptance protocol specified below; all improvement experiments and software checks are pending.
- Cleanup: Owning session records results including negative findings, distills reusable model/evaluation contracts, updates indexes and GitHub issue, then removes the resolved ticket.
- Priority: P1
- Owner: Unclaimed.
- Dependencies: Frozen data/splits and quality audit 12; relevant working calculator 03/06–09; 05 for optional production comparisons.

Preserve a compatibility profile while building a separately named improved
profile. The user wants the best open predictor, so website agreement must not
prevent a demonstrated improvement against experimental measurements.

## Work

- Prioritize RBS error decomposition: implementation errors, energy-engine
  settings, transcript context, host calibration, structural/kinetic assumptions
  and measurement mismatch. Diagnose on development data only.
- Select a finite set of falsifiable changes from ticket 12. Start with corrected
  parameters/context and interpretable mechanisms; compare simple calibration,
  mechanistic refinements and, only if justified, learned residual models.
- Apply analogous targeted analysis to Promoter host/sigma/context behavior,
  Operon submodel interaction/error propagation and Riboswitch concentration,
  affinity/constraint uncertainty. Avoid tuning unknown inputs to test outcomes.
- Predeclare metrics, minimum worthwhile gain, subgroup regression bounds,
  uncertainty analysis and stopping criteria. Choose sample sizes from variance
  and practical effect size; do not invent a universal accuracy threshold.
- Run ablations, grouped validation and a final untouched experimental test.
  Include failure coverage, noise ceiling/replicate variability, complexity and
  runtime costs. Keep live-site agreement a separate diagnostic.
- Release source, learned parameters/training recipe, data/split manifests and
  model cards for any successful improved profile under open terms. Retain the
  compatibility profile and label every intentional production divergence.

## Acceptance criteria

- Each attempted change has reproducible baseline/variant results and ablations;
  no cherry-picked panel, post-hoc test normalization or hidden outlier deletion.
- Promote an improved model only when its predeclared held-out criteria pass
  with uncertainty and acceptable subgroup behavior. Report a negative result
  honestly and retain the baseline when hypotheses fail.
- All implementation paths are tested; released improvements have fresh-install,
  offline, schema/coordinate and full regression checks. New required components
  remain fully open and public, with no paid prediction dependency.
- Evidence gaps yield concrete optional lab/coin-budget proposals, not invented
  biological validation. No purchase or wet-lab execution is authorized by this ticket.

## Verification to record

Exact code/data/model pins, evaluation commands, frozen test identities, full
error distributions and uncertainty, subgroup analysis, ablation outcomes,
runtime measurements and focused independent review before promotion.

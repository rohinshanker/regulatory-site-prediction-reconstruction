# A_13-ground-truth-model-improvements__20261016 — Active

- Scope: Pursue a leading fully open experimental predictor through falsifiable comparisons, prioritizing cyanobacterial RBS prediction while preserving compatibility.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-17
- Current State: Wave 2 cohort/weights remain frozen and native promotion unestablished. Joint binding/standby was implemented without fitting and frozen at a11cb5b. The one authorized Cambray-primary/Kuo-secondary collection is complete: 6,556 recorded attempts, no retries or artifact changes. B is auditing all receipts and independently recomputing aggregates before handoff. Cambray is now consumed for this experiment; no model/settings changes or new inference against it. No accuracy conclusion is claimed before the reviewed aggregate.
- Verification: Software/resource/fresh-install gates and four-platform CI 39080285855 pass. Public development inputs complete 136/136 with three non-greedy winners and identical v2/v3 site outputs. Input-only collector verification checked all 18,481 unique artifact pins and six exact mechanistic commands; no private outcomes accessed. No new-study rank gain or native calibration is claimed before the aggregate result.
- Cleanup: Owning session records results including negative findings, distills reusable model/evaluation contracts, updates indexes and GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/13
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: Frozen data/splits and audit 12/16; competitor/source decisions 01/17; transcript-aware runtime 18; relevant calculator 03/06–09; 05 for optional hosted comparisons.

Preserve a compatibility profile while building a separately named improved
profile. The user wants the best open predictor, so website agreement must not
prevent a demonstrated improvement against experimental measurements.

The expanded ambition is to outperform the strongest reproducible applicable
methods, with a cyanobacterial specialist as the first focused target. Read the
[comparison strategy](../../validation/rbs-comparator-landscape.md) and
[Wave 2 program](../../validation/rbs-wave2-program.md). Do not promise universal
superiority or conflate PCC 6803, UTEX 2973 and E. coli. Site localization and
strength prediction require independent endpoints and evidence.

## Work

- Prioritize RBS error decomposition: implementation errors, energy-engine
  settings, transcript context, host calibration, structural/kinetic assumptions
  and measurement mismatch. Diagnose on development data only.
- Select a finite set of falsifiable changes from ticket 12. Start with corrected
  parameters/context and interpretable mechanisms; compare simple calibration,
  mechanistic refinements and, only if justified, learned residual models.
- Compare simple regularized sequence/energy-feature models, a host-aware hybrid
  and eligible pretrained transfer learning as data permit. Measure learning
  curves and leave-context/study/host generalization. Keep pretraining exposure,
  inference information, computational budget and calibration fair. No large
  model trained only on 136 related constructs can establish broad superiority.
- Freeze the contender roster, primary endpoint, minimum worthwhile gain,
  subgroup/coverage tolerances and fit budget before final outcomes. If data
  cannot distinguish a winner, deliver the tested negative/inconclusive finding
  and ticket 16's costed prospective UTEX measurement proposal.
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

# A_11-design-modes-and-open-suite-release__20261016 — Active

- Scope: Complete design modes and release the fully usable open calculator suite.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-11-01
- Current State: A owns suite integration. Bounded RBS design, conditional concentration sweeps and conditional/termination/drafting CSV exports are implemented and independently accepted. C's bounded Promoter design at `87510bdf` is independently accepted after 42 A CLI checks and integrated at `ac6fc7e`; C retains #79 documentation closure. A's 0.15 entry point/package/README/CI integration is complete locally. A's bounded multi-target component RBS design at `953906a` is pending independent C review. Isolated branch `wave10/vector-package-candidate` has frozen provisional 0.16 source `7b4ae1e` and its entry point/package/CI without changing the 0.15 candidate. Complete Operon mechanisms, sequence-to-switch design, broader biological validation and public release remain unfinished.
- Verification: The [0.15 candidate](../../validation/engineering-0.15-candidate.md) passed 7,733 tests, 1,551 subtests, zero skips, full measured coverage and 69 fresh-installed outputs. All eight 0.15 platform jobs pass; independent review of A's packaging remains pending. The new #80 implementation passed 259 focused tests with full new coverage and artificial native strand comparisons; its exact review and final integration remain pending. The [provisional 0.16 package](../../validation/engineering-0.16-candidate.md) passes 7,992 local tests/1,551 subtests/zero skips, full coverage and all 74 fresh-installed outputs; all eight exact-head platform jobs, one 64-candidate/ten-target resource control and saved wire-schema checks also pass; independent implementation/package review and final integration remain pending. Prior [0.14rc2](../../validation/engineering-0.14rc2-candidate.md) independent review and all eight platform jobs pass. Completing these software searches does not establish experimentally improved designs.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/11
- Priority: P1
- Owner: Session A (baf5b738-1792172297), runtime and integration; B retains independent scientific evaluation and C owns its separately agreed component slices.
- Dependencies: Core 02, admitted predictors 06–09 and model-specific reference panels 05. Owner-authorized branch implementation may precede publication; scientific and publication acceptance remain separate.

Complete production-relevant design capabilities and release all four calculators as a coherent public, reproducible suite. The owner intends unrestricted public accessibility under open-source terms; ordinary use must not consume De Novo DNA coins or require its accounts.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.

- Inventory actual production prediction/design capabilities and prioritize remaining parity gaps. Implement RBS target-rate sequence design first, then promoter target-profile design, operon multi-cistron objectives and riboswitch switching-response design.
- Use the validated predictor as each design objective; implement explicit allowed edits, immutable regions, sequence/structure constraints, deterministic seeds, convergence/budget controls and honest infeasible outcomes. Re-score every returned candidate and verify all constraints independently.
- Evaluate achieved objectives and sequence diversity against published and coin-funded hosted examples. Do not require identical stochastic sequences to establish comparable objective quality; do not report predicted improvements as experimental success.
- Package all required source, parameters, examples, licences, notices, dependency lockfiles and benchmark manifests. Publish install/run documentation, model cards, stable schemas, release tags and reproducible build artifacts.
- Measure realistic single/batch/design workloads, resource caps and failure recovery. Specify supported platforms and optional container builds without adding an unnecessary hosted service. Document browser/HTTP deployment only if later requested.
- Produce a final capability/error matrix for every calculator against observed production modes; trace remaining differences to evidence and maintain actionable unresolved work.

## Acceptance criteria

- Anyone can obtain the public source, build and run all four predictors and their supported design modes without a private package, restrictive mandatory dependency, paid service or account.
- Every advertised mode has real end-to-end examples, tests for every new path, reproducible seeds/settings, constraint validation and clear infeasibility/failure behavior.
- Final scientific/live-reference reports state coverage, uncertainty and differences; production-level or exact-equivalence claims match evidence.
- A clean-install offline test and full CI pass on the supported matrix; third-party components retain notices and the complete required dependency path is open.
- All required functional gaps are implemented or explicitly rescoped by the owner. Discovery-only findings cannot close an unfinished implementation program.

## Verification to record

Full coverage/integration gates, installation from released artifacts, offline runs, finite performance benchmarks, per-mode constraint checks and focused independent review of the exact release candidate. Distill reusable operational guidance and close only owned, actually completed tickets.

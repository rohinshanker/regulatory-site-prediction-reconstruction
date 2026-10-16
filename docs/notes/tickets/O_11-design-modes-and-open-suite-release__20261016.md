# O_11-design-modes-and-open-suite-release__20261016 — Open

- Scope: Complete design modes and release the fully usable open calculator suite.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- Priority: P1
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: Core 02, released predictors 06–09 and model-specific reference panels 05; RBS design may begin immediately after 06.

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

# A_rbs-wave4-public-receipt__20261021 — Active

- Scope: Public Wave 4 RBS receipt identity/accounting checker under parent #12; no scientific metric recomputation.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: codex-implementer delivered the assigned deterministic checker, immutable manifest, focused tests and reusable validation contract from claim 83061b7129f945b1251af7110c22f695b1a6358a. Coordinator owns the pending finite exact-patch software review, integration and closure; keep this ticket active. Observed/unobserved count feasibility uses the coordinator's supplied formula. Its N100/O80/Sl80/Sr80/Pl60/Pr80/S70 example is infeasible for every M; tests reject it and retain valid neighboring examples without changing the formula.
- Verification: 172 focused tests pass without skips; 100% statement/branch coverage (391 statements, 126 branches, zero missing/partial) on Python 3.14.7 using the approved read-only environment. Ruff check/format, scope-local ticket/index checker and git diff check pass. Standalone CLI succeeds twice with identical bytes. All five exact public pins match both claim 83061b7 and accepted baseline 605d0c2; recovered original digest is dcf165f06a8e97d69bb9a087ed9cc85cade939b6917fd42a84382922edea2080. Public-read tests assert exactly five artifact reads plus the manifest. No private/source/scoring/folding/backend work or independent review was run.
- Cleanup: Distill the checker contract into docs/validation/rbs-wave4-public-receipt.md and its index row; after accepted completion resolve/delete only this child and remove its row. Parent #12 remains open.
- Owner: Session B cyano-calcs-B, 9677689a-1792176763.
- GitHub: [#61](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/61).

## Reserved paths and bounds

New benchmarks/rbs/wave4_public_receipt.py, benchmarks/rbs/wave4-public-receipt-manifest.json,
tests/benchmarks/test_wave4_public_receipt.py, docs/validation/rbs-wave4-public-receipt.md,
this child and its own index rows. No shared IO refactor or package/CI edits.
Exactly the public protocol, freeze, aggregate, review and Markdown report are
allowlisted; original bytes remain unchanged. Referenced private/external paths
stay opaque and unopened. Existing DEM-516 scientific review is reused, not
repeated. No scorer/evaluator/metric imports, predictions, fitting, bootstrap
execution, source retrieval, paid jobs, consumer changes or publication.

This is distinct from #58; DEM-612/613 remain stopped without retry/rerouting,
as do PV-R1 and DEM-577/568. One scoped implementer and one finite reviewer may
run sequentially with no child chain. One writer per tree; zero folding slots.
Before any new credential/admin/sudo/keychain/macOS action disclose exact
action/resource/reason and await owner decision; no bypass.

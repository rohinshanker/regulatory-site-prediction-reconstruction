# A_rbs-wave4-public-receipt__20261021 — Active

- Scope: Public Wave 4 RBS receipt identity/accounting checker under parent #12; no scientific metric recomputation.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: Root repaired DEM-620 findings F1–F7 after its exact 9a82195 review: identical incomplete cohorts, reference-subset block constraints, undefined-correlation propagation, quantile/max accounting, structured malformed-field errors, explicit subgroup threshold and stale queue count. Numeric zero runtime sums accept 0 and 0.0; count typing remains strict. Same-reviewer finite repair recheck pending. Original receipts and trust manifest are unchanged.
- Verification: 210 focused tests pass without skips at 100% statement/branch coverage (414 statements/134 branches). Tests include rehashed semantic negatives, sorted artificial runtime samples with independent stdlib median/Decimal percentile indexing, exact public pins, null/failure and CLI boundaries. No private/source/scoring/folding/backend work or scientific recomputation occurred. Final immutable recheck receipt precedes closure.
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

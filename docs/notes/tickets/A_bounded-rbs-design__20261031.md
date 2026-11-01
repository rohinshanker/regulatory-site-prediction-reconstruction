# A_bounded-rbs-design__20261031 — Active

- Scope: Original bounded local RBS target-score design around existing admitted prediction profiles; child of #11.
- Status: active
- Opened: 2026-10-31
- Updated: 2026-10-31
- Current State: A sole writer from ef46acd in reconstruction-rbs-design-20261031 on wave10/rbs-bounded-design. Contract-first implementation; no scientific model changes, private outcomes or biological claims. B owns #73 and C owns conditional CSV #75 independently.
- Verification: Existing historical designer inspected at pinned public source; native prediction and new design tests have not run. Required tests, offline artificial smoke and exact independent review precede acceptance.
- Cleanup: A alone closes this child after review and package gates, distills reusable contract, removes resolved ticket/index row; parents #6/#11 remain open.
- Owner: Session A, calculator integration role baf5b738-1792172297.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/74

Implement the [fixed design contract](../../validation/rbs-design.md). A owns new
design modules/tests/schemas/examples, the CLI entry point and later package gates.
Do not change rbs.py, profiles.py, backend.py, source parameters or frozen #73 files.
No native call while the #73 two-process reservation is occupied. Existing roots
only; all credential/provider/stopped-task and consumer/publication holds remain.

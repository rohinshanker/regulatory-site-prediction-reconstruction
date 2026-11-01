# A_conditional-concentration-sweep__20261031 — Active

- Scope: Bounded explicit ligand concentration response using the admitted supplied-energy conditional model; child of #9/#11.
- Status: active
- Opened: 2026-10-31
- Updated: 2026-10-31
- Current State: A sole writer in reconstruction-conditional-sweep-20261031, wave10/conditional-sweep, from d6efdab. Library/CLI/schemas complete; finite independent review pending. No core equation/parameter/backend/export or held runner changes. C independently reviews frozen RBS design #74; B owns frozen native evaluation #73.
- Verification: Existing component source/equation contract and pure validation/prediction interfaces inspected. 101 focused tests pass with 100% of 167 statements and 22 branches; offline six-point scalar CLI completes; Ruff/mypy pass. Independent review and package/platform gates pending.
- Cleanup: A owns closure after acceptance; distill reusable contract, remove resolved ticket and own index row. Scientific parents remain open.
- Owner: Session A baf5b738-1792172297.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/77

Implement the [concentration sweep contract](../../validation/conditional-concentration-sweep.md)
without new source retrieval, native processes, fitting, private outcomes or
consumer changes. A owns new sweep library/CLI/tests/schemas/example and one
entry point. Keep frozen #74 and other owners' paths unchanged. All existing
credential/provider/stopped-task/publication holds remain.

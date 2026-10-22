# A_termination-tabular-export__20261022 — Active

- Scope: C's local termination CSV continuation, [#71](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/71), under #8/#11.
- Status: active
- Opened: 2026-10-22
- Updated: 2026-10-22
- Current State: local implementation and checks complete; awaiting A's independent exact-patch review.
- Verification: 62 focused tests pass with 100% statement/branch coverage for exporter/CLI; Ruff and mypy pass; default/explicit JSON regression passes. One existing artificial native process produced the expected 3 CSV rows and candidate fields, exit 0.
- Cleanup: after A's review, distill the reusable contract, resolve/remove this ticket and its queue row, and close this child only.

Branch `wave8/termination-csv` starts at
`6e2affdde363b207769077400f46775bc527645b`. Owned paths are
`src/regsite/termination_export.py`, narrow `termination_cli.py`, export/CLI tests,
the [validation contract](../../validation/termination-tabular-export.md), and
the owning ticket/index rows. A owns integration, package/CI and other paths.

Preserve default JSON, original hashes, all failure/empty records and all retained
candidates. No scientific modules, source/data fixtures, backend discovery,
genomic mapping or inferred/calibrated values. The owner dispatch hold remains:
no Multica assignments/follow-ups, subagents, provider fallback or new reviewer.
A reviews the exact finished patch locally. No new credential/admin/keychain
access; exclude MULTICA_TOKEN/TYPESAFE_API_KEY from child-test environments and
never inspect or print credential values. All prior source/evaluation holds remain.

Handoff target: `/tmp/calculator-wave8-20261022/c-termination-csv-handoff.md`.
Keep this task active until A returns review acceptance; no automatic next slice.

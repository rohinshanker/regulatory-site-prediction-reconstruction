# A_conditional-tabular-export__20261031 — Active

- Scope: C-owned conditional-result CSV projection under #9/#11; standalone CLI only.
- Status: active
- Opened: 2026-10-31
- Updated: 2026-10-31
- Current State: Contract and implementation complete at base ef46acd69b16021d1d83c4de5c65a682ad37faad on wave10/conditional-csv; A's finite exact-patch review is pending. C owns exporter, narrow CLI/test additions and this guide/ticket/index scope. B retains #73.
- Verification: 70 focused tests pass with no warnings/skips and full 110-statement/26-branch exporter/CLI coverage. Ten artificial cases preserve default/explicit JSON byte-for-byte versus the frozen original CLI; CSV identities/rows/exits match. Ruff/format and scoped mypy pass. Native math/backend/parameter/schema files remain unchanged; zero native processes. Local contract/ticket/link/diff checks pass.
- Cleanup: After A accepts the exact patch, resolve/remove only this child and its queue row; distill reusable guidance into conditional-tabular-export.md. Parent #9/#11 remain open.
- Owner: Session C56abed60-1792619583; coordinator/reviewer A baf5b738-1792172297.
- GitHub: [#76](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/76).

Only conditional_export.py, the existing conditional_cli.py and focused tests,
the new validation guide and one row in each index are reserved. No model/math,
backend/source/schema, runner, package/version/dependency/CI or peer-ticket edits.
Default JSON, producer identities, units, statuses and all exit semantics remain
unchanged. The export binds omitted evidence to authoritative JSON bytes.

No child/provider dispatch, source retrieval, private outcomes, fitting, paid
jobs, canonical/consumer edits or publication. Exclude named credential variables
and PYTHONHOME from checks without displaying values. New credential/admin/sudo/
keychain/macOS access needs exact disclosure and owner decision; never bypass.

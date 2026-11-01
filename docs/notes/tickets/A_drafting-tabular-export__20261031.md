# A_drafting-tabular-export__20261031 — Active

- Scope: C-owned CSV projection for the supplied-rate stationary drafting result; child of #11.
- Status: active
- Opened: 2026-10-31
- Updated: 2026-10-31
- Current State: A accepted exact base d12a03feb83f579634df43bbce6203b222b88f70 and 42-column contract; C sole writer in reconstruction-drafting-csv-20261031, wave10/drafting-csv. Contract fixed before implementation; implementation pending.
- Verification: Native result/transport contract and existing CLI inspected. Targeted tests, frozen JSON byte comparison and A independent review pending.
- Cleanup: C owns closure after A acceptance; distill reusable contract, delete resolved ticket and remove only its index row. Parent #11 remains open.
- Owner: Session C56abed60-1792619583; A owns review/integration and package/platform gates.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/78

Implement the [tabular contract](../../validation/drafting-tabular-export.md)
only in the new exporter, narrow drafting CLI, owned tests and guide/index.
Preserve drafting math/IO, schemas, fixtures, native JSON and prediction hashes.
No backend/native process, new source/model, child dispatch, provider reroute,
private outcomes, consumer/peer writes, package/publication or privileged access.
Test children exclude incident credentials and PYTHONHOME without inspecting values.

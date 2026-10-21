# A_offline-calculator-jobs__20261021 — Active

- Scope: Bounded offline execution and verified resume for existing calculators; child of #6/#11.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: A accepted the same-reviewer final repair at 136d6ffbcdb741776992a462c6742d892395f063 and integrated it at cb5bd3d, preserving C's coupling entry point. All ten original findings plus the introduced cache-reader defect are resolved within the explicit cooperative deadline and best-effort persistence boundary. The first 0.10.0rc1 package passed local gates and installed examples, but Linux CI exposed a test assuming process group 1 was inaccessible. A corrected only that test to use a deterministic permission error and a test-owned reaped group; all 200 jobs tests pass with full coverage. The separate 0.10.0rc2 candidate is now in validation. C owns intrinsic-termination #62 and B its independent evidence dossier. No consumer admission.
- Verification: Exact package source 95e95e0db455df332df6bf7b12e6eb4f03c39cf5 passed 6,341 tests with no skips, 100% coverage of 16,623 statements/6,282 branches, Ruff/format/mypy and 18 fresh offline checks. All five command kinds, real folding-backed examples, unchanged-attempt resume and corruption/restoration checks passed; all 46 wheel runtime files match source. Independent review covers 136d6ff; no remaining finding. CI39694268202 is blocked by the Linux test-portability failure; its prior local results remain historical, not CI approval. Coupling's separate c74ff8f CI39689533173 passed all eight jobs; C owns its child closure. Runner #59 stays open for final CI and durable closure. The scratch build driver initially used the older system Python, which rejected its tarfile filter argument before building; the unchanged source passed with the locked Python3.14 driver.
- Cleanup: Distill accepted usage and integrity rules to validation, remove resolved ticket/queue row, and close only this owned child after final checks.
- Owner: cyano-calcs-A / baf5b738-1792172297.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/59

Run explicit caller-authored requests through fixed existing calculator commands,
preserving every raw output and native failure. Keep full artifacts in an explicit
external directory with atomic receipts and exact input/runtime/backend hashes.
Never widen native caps or split a biological request implicitly. Resume only
verified terminal jobs; retain missing/interrupted attempts honestly. Explicit bounds on inputs, calculator execution, captured output and job/attempt
counts are part of the public contract. Setup and identity checks use cooperative
deadlines with disclosed verifier overhead; output accounting is not an OS disk
quota and does not bound native scratch files. No invented success, silent fallback, new dependencies or model fitting.

Implementation paths: new src/regsite/jobs*.py, tests/test_jobs*.py,
schemas/calculator-job*.schema.json, examples/jobs-*, one console entry and a new
offline-calculator-jobs validation contract. Existing scientific APIs stay unchanged.
A owns packaging/CI integration; worker may edit only its explicitly assigned paths.

Continuation: A reviews completed C/B receipts and sends the next concrete unblocked
assignment. Peers may wake A with a completed receipt and a scoped continuation
request. Keep one owner per task, at most two children per coordinator and at most
two local folding processes total. No duplicate dispatch or empty ping loops.

Preserve PV-R1, stopped DEM-577/568 and refused #58 thesis audit. No consumer/canonical
edits, private-outcome tuning, new paid jobs, main merges, tags or publication. New
credential/admin/sudo/keychain/macOS access requires exact prior disclosure and
owner decision; never bypass a pending/denied approval.

# A_offline-calculator-jobs__20261021 — Active

- Scope: Bounded offline execution and verified resume for existing calculators; child of #6/#11.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: A coordinates from accepted 605d0c2. Claude implementer DEM-614 repaired ten independently reproduced findings at 57d2ec88d40cb884daf3c88d9dfcaf85421cfee4; the same DEM-621 reviewer is checking that exact repair. Runner code remains outside the integration branch. C's reviewed reinitiation component is integrated and its distinct 0.9.0rc1 package passes local gates; C now owns intrinsic-termination admission/runtime #62. B's reviewed public Wave4 receipt checker is integrated at f5e2240, and B is implementing a disjoint termination evidence dossier. No native scoring changes or consumer admission.
- Verification: Runner worker reports 188 tests with full coverage; independent repair acceptance, real-backend package checks and combined CI remain pending. Coupling at c74ff8fac2331ba1e1e1836d953ea69036133b85 passes 5,932 tests without skips, full coverage and eight fresh-package checks; receipt /Users/Rohin/.cache/regsite-wave7-integration-20261021/coupling-0.9/receipt.json. Exact CI 39689533173 is pending. The integrated B checker passes 210 focused tests with full coverage. None of these receipts implies runner acceptance.
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

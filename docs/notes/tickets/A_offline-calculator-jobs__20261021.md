# A_offline-calculator-jobs__20261021 — Active

- Scope: Bounded offline execution and verified resume for existing calculators; child of #6/#11.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: Reviewed runner 136d6ff is integrated and frozen in development package 0.10.0rc2 (source 51ca353). Two Linux-specific test/coverage assumptions were replaced by deterministic process-group tests at 2f9db86; runner and package runtime bytes remain unchanged. CI39697665315 is in progress. All ten original findings and the cache-reader defect are resolved within the cooperative deadline/best-effort persistence contract. No consumer admission.
- Verification: Frozen RC2 passed 6,342 local tests, zero skips, 100% of 16,623 statements/6,282 branches, Ruff/format/mypy and 18 fresh offline checks. All five kinds, real folding-backed examples, one-attempt resume and corruption/restoration pass; 46 installed runtime files match source. Corrected test head passes 202 focused runner tests with zero skips/full coverage; Linux3.14 CI now passes its full gate. Historical failed CI receipts remain explicit; #59 stays open for the final matrix and closure.
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

CI 39697665315 passed all four complete runtime suites; fresh installation then
refused the relative manifest paths in the workflow (`manifest_path`). The
workflow and README now pass absolute paths required by the unchanged contract.
The exact installed RC2 wheel reproduced the refusal and then passed the five
corrected CI run/verify/resume invocations, including the real folding backend.
Evidence remains external in A’s `ci-wheel-smoke` directory. Full replacement
CI is pending; this was a caller correction, not a runtime identity relaxation.

The remaining Linux/Python 3.11 job hit the 45-minute CI ceiling after its
full suite and final 3,202-test variant run passed. A raised only the whole-job
CI budget to 60 minutes for the next matrix; calculator, campaign, output and
resource-admission limits remain unchanged. The exact cancelled-job log is
retained with the CI evidence. No completed full matrix is claimed.

# A_original-backend-installer__20261019 — Active

- Scope: Resolve the cross-platform installer integration gate for #51; parent #6.
- Status: active
- Opened: 2026-10-19
- Updated: 2026-10-19
- Current State: Reopened after final CI at c16f2a5. Linux/Python 3.14 exposed an existing macOS prerequisite test that did not mock selector availability after the builder added a prerequisite probe. macOS/Python 3.14 separately reported process_start instead of record_deadline in an unchanged synthetic collector test; it passed in the original and traceback-2 suites of the same run. No underlying OSError was retained. All original build/installer gates and resource jobs passed; the publication hold remains.
- Verification: Mock the selector prerequisite explicitly, reproduce the prior failure under simulated Linux availability, run the focused installer/component tests, and obtain finite independent review of this test-only correction. Preserve the collector assertion and source; use only a bounded synthetic reproduction, no private evidence or new collection. Rerun exact-head CI after the deterministic fixture fix and retain both original failure records.
- Cleanup: Existing reusable builder instructions remain current. After acceptance remove this reopened child/index row; #6/#51 retain the CI/publication gates until the final run is green.

Session A owns the fix in `reconstruction-original-backend-integration-20261019`, branch `quality/original-backend-integration-20261019`. B's benchmark source/test ownership is unchanged; no competing writer or new agent is assigned there. The CI logs are in `/tmp/calculator-original-installer-20261019/ci-{macos314,linux314}-failed.log`. This is software validation of synthetic subprocesses, not biological inference or a retry of stopped DEM-577/568/PV-R1 work. No credentials, privileges, coins, main merge or publication.

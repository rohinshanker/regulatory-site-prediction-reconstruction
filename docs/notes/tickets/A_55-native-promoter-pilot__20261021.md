# A_55-native-promoter-pilot__20261021 — Active

- Scope: Producer-side checker that compares the reconstructed Promoter kernel with the original-source native localization pilot; no model fitting, source discovery or biological inference.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: `experiments/promoter/pilot_parity.py` implements the reusable checker. The [contract](../../validation/promoter-native-pilot-parity.md) covers the frozen schema, protocol and input pins, the complete denominators and four failure categories. Still pending: source execution (DEM-605), Session A's freeze and independent review of this commit, comparison against the actual reference, and integration into `wave6/promoter-native-pilot`. Do not close #55 or parents #7/#12 until then.
- Verification: The checker's 117 focused tests pass with 100% statement and branch coverage (372 statements, 86 branches). The independent success case is the frozen poly(A) fixture from `reference-fixtures.json`. Self-scored reports exercise only the plumbing. The 70 adjacent Promoter parity/core tests pass. Ruff check and format pass. A synthetic scale probe projects 37 MiB and about 83 s for a full 2,475-case report. Native outputs and Tan counts were not opened.
- Cleanup: Session A records the actual-reference parity result and unresolved findings, then resolves this ticket. Reusable guidance already lives in the validation contract; remove this ticket and its index row after resolution.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/55
- Priority: P1
- Owner: Session A (`baf5b738-1792172297`); checker implemented under Multica DEM-606.
- Dependencies: Consumer runner at `f808362` (read-only interface reference; no code copied); DEM-605 source execution.

## Constraints

- Tolerances (rel/abs `1e-12`; tie abs `1e-12`, rel 0) are predeclared. Never tune them on observed native results.
- A bounded cohort, or one with a `sample_limit` exclusion, is never reported as the full pilot.
- Session B owns the count-association benchmark (#12). This ticket does not touch those paths.

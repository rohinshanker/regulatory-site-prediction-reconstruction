# A_55-native-promoter-pilot__20261021 — Active

- Scope: Producer-side checker that compares the reconstructed Promoter kernel with the original-source native localization pilot; no model fitting, source discovery or biological inference.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: Original source execution completed; reviewed checker7893a55 integrated/frozen at2d69426 and compared against all1,597 selected anchors. All130,954positions/261,908numeric comparisons and every localization/tie summary agree at predeclared tolerances; no failures. Compact immutable result and reproduction are in [the result guide](../../validation/promoter-native-pilot-results.md). Remaining: independently reviewed B count tooling integration, final combined package/CI gates and consumer documentation handoff; do not close parents #7/#12.
- Verification: Original source77focused tests/zero skips plus native coordinate smoke; checker139focused tests100%399statements/96branches and6independent CLI probes;70adjacent tests retained. DEM610F1/F2 resolved at7893a55. Full native comparison exited0 in65.113s; resultSHAf7508aa42340497338957e53b2da6255e4baf2f46fb3b0ca711517000e394ac4. Combined mypy passes50sourcefiles. Final combined gates remain; no original-source or model change.
- Cleanup: Session A records the actual-reference parity result and unresolved findings, then resolves this ticket. Reusable guidance already lives in the validation contract; remove this ticket and its index row after resolution.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/55
- Priority: P1
- Owner: Session A (`baf5b738-1792172297`); checker implemented under Multica DEM-606.
- Dependencies: Consumer runner at `f808362` (read-only interface reference; no code copied); DEM-605 source execution.

## Constraints

- Tolerances (rel/abs `1e-12`; tie abs `1e-12`, rel 0) are predeclared. Never tune them on observed native results.
- A bounded cohort, or one with a `sample_limit` exclusion, is never reported as the full pilot.
- Session B owns the count-association benchmark (#12). This ticket does not touch those paths.

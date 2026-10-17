# A_27-rbs-joint-candidate-selection__20261017 — Active

- Scope: Implement a versioned RBS profile that selects binding and standby states using complete assembled initiation energy.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Opt-in joint_standby implementation and schema 1.3 are ready for exact-patch review. Complete candidate objective, stable identities, greedy counterfactual, partial-progress missingness and bounded work are implemented. B's independent synthetic fixtures/protocol are available for reviewed integration; no reserved outcomes accessed or final collection authorized.
- Verification: Traceback-2 full suite passes 1,506 tests and 234 subtests with 100% of 5,005 statements/2,084 branches. Two additional real-deadline/nonselected-warning checks bring focused joint tests to 27 passing. Ruff/mypy and scoped ticket/validation metadata checks pass. Resource measurements, independent review/oracle bridge, original-engine compatibility, fresh artifacts and four-platform CI remain before scientific freeze.
- Cleanup: Session A records exact validation and remaining gaps, distills the runtime/model contract, resolves/removes this scoped ticket and index row; broader #4/#13 remain open as needed.
- Owner: Session A (baf5b738-1792172297), wave4/rbs-joint-runtime; backend component may be assigned to one scoped worker.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/27
- Dependencies: Existing standby profile and backend contracts; B's #28 supplies independent fixtures/evaluation. #26 is a separate optional backend improvement, not a prerequisite to implement this profile.
- Parent: #4/#13; release integration #6.

Follow the [Wave 4 program](../../validation/rbs-wave4-program.md) and
[Session A prompt](../../prompts/wave4-session-a.md).

Implement an opt-in, explicitly named profile over the same declared eligible
cofold candidate set. For each candidate assemble the full complex, optimize the
declared standby states, include spacing/start/unbound terms, and select the
minimum complete energy. Preserve earlier profiles, source parameters and frozen
models. Do not call the bounded candidate set exhaustive RNA folding or assume
that lower energy improves measured accuracy.

Acceptance:

1. Versioned input/result semantics, complete objective, deterministic ties,
   candidate/state identity, counts, greedy counterfactual and explicit resource
   limits. Any uncompleted eligible candidate prevents a claimed complete winner.
2. Real single/batch/native JSON/CSV execution and valid strand/origin coordinates;
   no invented structures or silent failed-candidate filtering.
3. Independent finite-state oracle, singleton/tie/duplicate cases, whole-site
   limits/failures, every implemented branch and unchanged old-profile controls.
4. Source/specification and exact-patch review, pinned dependencies, fresh offline
   installation, full real-backend tests and four-platform CI.
5. Immutable candidate receipt delivered before B's final evaluation; aggregate
   result and model card retain failed/negative findings without post-test tuning.

No new training or final-set calibration; no coins/browser/keychain, main/cyano
changes, publication or resubmission of A/B assignments. Forward the shared
privilege-disclosure and private-outcome boundaries to scoped workers.

# A_27-rbs-joint-candidate-selection__20261017 — Active

- Scope: Implement a versioned RBS profile that selects binding and standby states using complete assembled initiation energy.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Opt-in joint_standby/schema 1.3 are complete and independently reviewed. Frozen scientific commit a11cb5b and candidate receipt c98d7626d703c31d1ad5c9b8038a763afb6499fac097c395870ca7b9d9738963 passed every software/resource gate. B acknowledged the exact 11-config collector receipt; A authorized one unchanged run in issue28 comment 6243651142. Aggregate evaluation/model-card integration remains before closure; no private outcomes accessed.
- Verification: Candidate passes 1,614 tests with 100% of 5,603 statements/2,314 branches; 35 three-engine checks; all four jobs in CI 39080285855; exact-patch review; fresh offline source/wheel examples. All 136 development searches complete on v2/v3 with identical full site outputs, three non-greedy winners and measured resource bounds. Collector receipt eba048f52132ebb1d52d812c49316de4397afb0502c39cfb895f0eaef6565591 verified input-only before GO.
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

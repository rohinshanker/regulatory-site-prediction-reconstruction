# A_27-rbs-joint-candidate-selection__20261017 — Active

- Scope: Implement a versioned RBS profile that selects binding and standby states using complete assembled initiation energy.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Opt-in joint_standby and schema 1.3 are implemented and independently reviewed. The finite search, 1e-9 candidate tie rule, batching/cache, exact internal-state tie policy and failure semantics are documented. Source/backend admission reviews are complete; the immutable a11cb5b checkout awaits final CI and the B receipt handshake. No reserved outcomes accessed.
- Verification: At a11cb5bd13d3c021eedc98cf451609eb4710bb6a, full linker-3 suite passes 1,614 tests with 100% of 5,603 statements/2,314 branches. All 136 public-development searches complete on v2/v3 with identical full site outputs; median times 0.823/0.870 s and three non-greedy winners. Earlier profiles are independently confirmed unchanged. Fresh wheel/source and complete offline examples pass. Thirty-five component checks pass; final CI 39080285855 is pending before B experimental collection.
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

# O_27-rbs-joint-candidate-selection__20261017 — Open

- Scope: Implement a versioned RBS profile that selects binding and standby states using complete assembled initiation energy.
- Status: open
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Planned for Session A in Wave 4. Existing standby scoring chooses its binding candidate before full complex/accessibility evaluation; no joint profile is implemented yet.
- Verification: Baseline source selection order inspected at a04ca92837772e1bbe4c47e230235baadecfc099; implementation and independent evaluation are pending.
- Cleanup: Session A records exact validation and remaining gaps, distills the runtime/model contract, resolves/removes this scoped ticket and index row; broader #4/#13 remain open as needed.
- Owner: Session A, reserved assignment; claim active when execution starts.
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

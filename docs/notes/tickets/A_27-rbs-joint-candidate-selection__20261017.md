# A_27-rbs-joint-candidate-selection__20261017 — Active

- Scope: Implement a versioned RBS profile that selects binding and standby states using complete assembled initiation energy.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Opt-in joint_standby and schema 1.3 are implemented in draft PR31. Independent review prompted an explicit 1e-9 numerical candidate-tie policy, batched fixed-state evaluation and per-site prefix/suffix caching, all before scientific freeze. B’s independently reviewed protocol/fixtures are integrated unchanged; the runtime bridge passes. Final candidate review, backend disposition and experimental evaluation remain pending; no reserved outcomes accessed.
- Verification: At cd6cb3a62cdd560b226f6cbae3d152f103afa606, traceback-2 full suite passes 1,544 tests plus 234 subtests with 100% of 5,185 statements / 2,156 branches. Static gates pass. 32 normalized complete legacy outputs match the original-engine baseline exactly. The formerly timed-out native example now completes both records (187/591 states) in 12.87 s; 4,096 real fixed-state evaluations take 11.71 s in 41 batches. Independent fix review and CI 39078711254 are active; public-development resource verification and final integration gates precede the receipt.
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

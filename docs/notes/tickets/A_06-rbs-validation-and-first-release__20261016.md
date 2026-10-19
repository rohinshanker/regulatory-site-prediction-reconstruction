# A_06-rbs-validation-and-first-release__20261016 — Active

- Scope: Validate and release the first fully usable open RBS calculator.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-19
- Current State: Cumulative draft PR37 against main contains the complete RBS candidate plus documentation-only release corrections at 73dfbab. DEM-517 accepted the exact 9edb989 archives and independently accepted the corrections/staged bundle. Main merge, tag and publication remain outside this slice and incomplete. Isolated subsequent-calculator development is already authorized; publication and consumer admission retain separate gates. No frozen model or archive was changed. Separate draft PR52 supplies the reviewed pinned original-backend installer and output-preserving Promoter validation reuse. Its code head `7fdfb6f` passed all eight CI jobs in run 39305475909; it does not alter this older release candidate or grant new binary/profile admission. The final documentation cleanup preserves those tested runtime bytes; consult PR52 for current merge checks.
- Verification: Exact archive-source CI39088709792 passed all four jobs; 1,624 integrated tests at 100% measured Python coverage and 35 three-engine checks remain the validated baseline. DEM-517 independently verified archive/wheel contents and six fresh offline outputs, then rechecked the corrected release body, unchanged archive hashes and SHA-preserving tag plan. Docs/index/link checks pass. New cumulative-PR CI is a separate run; consult its exact-head checks rather than assuming the prior green result applies to a different commit.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/6
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: 02–04; 05 for hosted claims; 12/16/17 independent evidence and comparisons; 18 for native-context exports. Scope claims to completed gates.

Deliver the first installable, documented RBS prediction release. The owner permits isolated implementation of subsequent calculators alongside this release preparation; source, scientific validation, publication and consumer-admission boundaries still apply.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.
- Apply [native task-specific gates](../../validation/rbs-native-validation.md):
  TSS context integrity, experimental TIS localization and translation-strength
  accuracy are separate. Include eligible ML/mechanistic contenders from 17,
  native TE/context challenges from 16 and full prediction coverage. Unsupported
  leaderless/native cases remain explicit; they cannot silently disappear from
  denominators. B owns final metrics and outcomes; A owns release integration.

- Assemble licensed experimental/reference datasets with exact sequences, host, construct context, measured quantity, conditions and model settings. Split by study/sequence family to prevent near-duplicate leakage.
- Evaluate equation correctness, hosted agreement and experimental predictive accuracy separately under the shared contract. Report site matching/coverage, per-term energy differences, log-rate errors, ranks, failures and uncertainty by domain.
- Predeclare acceptance tolerances and numerical regression criteria before held-out evaluation. Compare against the historical baseline, simple appropriate baselines and Jaymin's scorer where executable.
- Package a stable library/CLI, single/batch prediction, JSON/CSV and verified annotated export, examples, supported input limits, dependency pins and full source/parameter notices.
- Publish model identity, known deviations and applicability. Native cyanobacterial accuracy is not established by an E. coli fit or a host dropdown. The UTEX synthetic-RBS reporter paper has narrower scope than genome-wide calibration.

## Acceptance criteria

- A clean machine installs the release and runs complete offline examples with no account, private DNAc, required restrictive dependency or unavailable binary.
- All specified prediction paths and exports pass unit/integration/coordinate tests; every added branch is exercised. Runtime/memory limits and batch failure behavior are measured.
- Reproducible benchmark reports distinguish implementation correctness, production-reference agreement and biological accuracy, with complete denominators and unresolved gaps.
- Hosted testing can be pending for a clearly labeled provisional release, but claims of production equivalence and completion of the hosted-comparison work remain open until measured. Never fabricate reference fixtures.
- The release/tag, compatibility notes and consumer-ready schema are available; ticket 10 can integrate this first calculator independently of the others.

## Verification to record

Full CI/coverage, fresh-install and offline smoke tests, frozen benchmark rerun, licence/dependency inventory and an independent review of the exact release candidate. RBS design is completed under ticket 11 and must not be advertised before it works.

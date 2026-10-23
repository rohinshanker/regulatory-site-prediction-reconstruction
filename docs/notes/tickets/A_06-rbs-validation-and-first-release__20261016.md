# A_06-rbs-validation-and-first-release__20261016 — Active

- Scope: Validate and release the first fully usable open RBS calculator.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-22
- Current State: Cumulative draft PR37 against main contains the complete RBS candidate plus documentation-only release corrections at 73dfbab. DEM-517 accepted the exact 9edb989 archives and independently accepted the corrections/staged bundle. Main merge, tag and publication remain outside this slice and incomplete. Isolated subsequent-calculator development is already authorized; publication and consumer admission retain separate gates. No frozen model or archive was changed. Separate draft PR52 supplies the reviewed pinned original-backend installer and output-preserving Promoter validation reuse. Its code head `7fdfb6f` passed all eight CI jobs in run 39305475909; it does not alter this older release candidate or grant new binary/profile admission. The final documentation cleanup preserves those tested runtime bytes; consult PR52 for current merge checks.
- Verification: Exact archive-source CI39088709792 passed all four jobs; 1,624 integrated tests at 100% measured Python coverage and 35 three-engine checks remain the validated baseline. DEM-517 independently verified archive/wheel contents and six fresh offline outputs, then rechecked the corrected release body, unchanged archive hashes and SHA-preserving tag plan. Docs/index/link checks pass. New cumulative-PR CI is a separate run; consult its exact-head checks rather than assuming the prior green result applies to a different commit.
- Continued development: Draft PR63 preserves frozen 0.12 source356abc2 and its passing eight-job CI39703039920 at efe90fcb. Later CI39825830327 at349b40b passed seven jobs but failed macOS14/Python3.14's Wave4 descendant-deadline test (process_start versus record_deadline); its underlying errno is unknown. B's exact collector repair adde9430ae9ba2af445aed27d2856a1d34523712 passed C's original review plus F1 recheck and A's34focused tests/3subtests/full295statements110branches. A accepted and integrated it at7109956, preserving exact source/test/guide bytes and both sessions' index rows; Combined source97c21e35c1204c0424b3a3ad39aa723a506d1c8d passed7,119local tests with zero skips/full17,991statements6,662branches plus Ruff/format/mypy. All eight platform jobs passed in CI39839410653 at e787802cca9982ef44a0462d18e4ff9cc45e2575: each runtime job passed7,118tests/one declared original-conditional skip, full measured coverage and both3,013-test repaired-backend selections, followed by fresh installation. Local validation enables the skipped exact original backend. B closed #72 at6de02b87417eeee4939e3c91e29dce068906de5f; A integrated its three documentation/ticket paths at7f3b4f1 without changing accepted code or tests. Earlier #66 supplied-rate numerical validation and #71 termination CSV are accepted and integrated; the pre-repair combined source passed7,106local tests/zero skips/full17,891statements6,624branches. Source changes do not relabel frozen archives or establish biological accuracy. New Multica dispatch and the separate #68 package review remain on owner hold. See the [frozen package guide](../../validation/drafting-0.12-candidate.md) and [collector contract](../../validation/wave4-collector-process-cleanup.md); current-head checks remain distinct from immutable prior evidence.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/6
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: 02–04; 05 for hosted claims; 12/16/17 independent evidence and comparisons; 18 for native-context exports. Scope claims to completed gates.

Deliver the first installable, documented RBS prediction release. The owner permits isolated implementation of subsequent calculators alongside this release preparation; source, scientific validation, publication and consumer-admission boundaries still apply.

The [combined development package](../../validation/integrated-runtime-build.md)
adds the reviewed supplied-transcript component and independent native Promoter
pilot tooling. Source `2f68daa` has 5,658 passing local tests, no skips, full measured
statement/branch coverage and 22 fresh offline checks. Its archives are distinct
from the frozen release candidates; exact proposed-head CI, main/tag/package
publication and downstream admission are still separate. This integration does
not change the older RBS scientific results or close this release parent.

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

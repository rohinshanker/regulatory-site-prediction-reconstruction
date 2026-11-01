# A_06-rbs-validation-and-first-release__20261016 — Active

- Scope: Validate and release the first fully usable open RBS calculator.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-11-01
- Current State: A owns release integration. Original RBS publication remains separate. The accepted bounded RBS/Promoter and multi-target implementations are packaged in isolated 0.16rc2 source `d49dcaa`; local/fresh gates pass, replacement archive review and platform CI are pending. Original 0.16rc1 is preserved unreleased with its confirmation reporting defect; the independently accepted repair is present only in the replacement. The five-kind runner and frozen 0.12 scientific candidate remain unchanged; held #68 stays excluded.
- Verification: [Engineering 0.16rc2](../../validation/engineering-0.16rc2-candidate.md) passes 7,994 tests/1,551 subtests/zero skips, full measured coverage, static checks and 74 fresh-installed outputs. C accepted implementation repair `137585b` and the separate documentation attribution correction. Replacement CI41326470205 at `d49dcaa` and independent package review are pending; earlier green package/platform gates do not replace them.
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

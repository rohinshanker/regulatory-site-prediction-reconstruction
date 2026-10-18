# A_33-promoter-local-runtime__20261018 — Active

- Scope: Implement the admitted historical Promoter equations as a small open runtime with single/batch both-strand scanning, versioned contracts, term-level results and portable exports.
- Status: active
- Opened: 2026-10-18
- Updated: 2026-10-18
- Current State: Reviewed contract defines explicit local-reference scans, transcript-oriented genomic projection, every-site retention, term/log-score semantics, calibration and failure/limit rules. Result normalization/nulls, canonical hash payloads and all 20 effective-limit keys are specified for B's independent adapter; the candidate receipt must pin the complete emitted model and identity model. Valid empty scans finalize in preflight as no_candidate/empty_scan with complete zero coverage, unaffected by deadlines; validation still takes precedence. Literal sorted-key, indent-2 authoritative JSON plus LF fixes the result-size measure; adapters must check both received and authoritative bytes. The Draft 2020-12 request schema, two synthetic examples and 200 structural contract tests are implemented and reviewed. B Phase 1 adapter/metrics through 1295aff are reviewed and integrated by ancestry at ab29891. The owner authorized isolated implementation alongside release preparation on 2026-10-18; core and interface work now proceed. Candidate freeze and independent collection remain separate gates.
- Verification: A reproduced the combined 1,732-test suite with the real linker-3 engine at 100% measured coverage (7,230 statements/3,010 branches), plus 200 new schema tests separately; Ruff/format/mypy, ticket/link/diff checks pass. All four CI jobs pass at b8ef835 (run 39168056105). A reproduced the integrated seven-module synthetic benchmark checks: 154 tests pass, 100% of 2,209 statements/962 branches; the 200 request-schema tests also pass. New adapter/metrics hashes match B, and frozen inputs/runtime/dependencies are unchanged. B's four input-only examples validate against the schema, and projection algebra agrees with 53,508 small-contig interval cases. Documented hash payloads execute on artificial inputs and agree with the existing canonical helper, including Unicode escaping, numeric representation and identity sensitivity. Literal authoritative serialization also passes sorted-key/Unicode/LF checks and demonstrates compact-below/pretty-above-cap rejection on an independent synthetic object. Promoter scorer/source parity, resource measurements, fresh offline CLI, runtime CI and independent evaluation remain unexecuted requirements.
- Cleanup: The owning session alone resolves the scoped ticket, records unresolved findings, distills reusable contracts, removes the resolved file/index row and closes this issue with the exact result commit.

- Owner: Session A. Parent scope: #7.

Constraints: No promoter design, new fitting, silent host fallback or claim of hosted parity. Parent #7 retains unmet production/live/design scope.

Follow docs/validation/wave5-program.md and the assigned docs/prompts/wave5-session-a.md or wave5-session-b.md. Baseline science/integration is 9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923; the launch message supplies the exact shared planning commit.

Before any new credential, administrator password, sudo, keychain or macOS-permission action, disclose the exact action/resource/reason and await the user. No bypass; no main/cyano mutation or package publication is implied. Preserve private-outcome boundaries and one writer per worktree.

- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/33

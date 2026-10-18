# A_33-promoter-local-runtime__20261018 — Active

- Scope: Implement the admitted historical Promoter equations as a small open runtime with single/batch both-strand scanning, versioned contracts, term-level results and portable exports.
- Status: active
- Opened: 2026-10-18
- Updated: 2026-10-18
- Current State: Pure scoring core, independent parameter derivation, result schema and batch/CLI/CSV/GFF3 interface are integrated through 6f8c5e6. Parameters reproduce the pinned source arrays and tables. Provisional 0.5.0rc1 packaging and offline examples run. DEM-532 accepted the equations, parameters and export fixes through 1a87508. Its remaining first-error precedence note is fixed with regression tests. DEM-533 measured original resource ceilings; combined verbose batches exceeded the output cap, so provisional effective limits are now 1000 sites/record, 4000/batch and 2000 all-state entries/record and batch. Final cross-platform resource admission remains pending. Session B owns independent source-parity/native collection; no candidate receipt or collection authorization has been issued.
- Verification: A reproduced all 802 Promoter-only tests, including the 212 frozen source states, and the complete 2582-test/816-subtest suite with the real linker-3 backend: 100% of 8865 statements/3700 branches. The focused interface slice now has 128 tests at 100% of 443 statements/198 branches. Ruff/format/mypy pass. Fresh no-index/no-deps wheel installation runs single/batch/CSV/GFF3 examples, includes parameter data and original notice, excludes reference tools from the wheel, and imports no NumPy/SciPy/sklearn/Bio. Earlier B adapter verification remains 154 tests, 100% of 2209 statements/962 branches. Cross-platform CI, final resource receipt and independent source/native evaluation remain outstanding.
- Cleanup: The owning session alone resolves the scoped ticket, records unresolved findings, distills reusable contracts, removes the resolved file/index row and closes this issue with the exact result commit.

- Owner: Session A. Parent scope: #7.

Constraints: No promoter design, new fitting, silent host fallback or claim of hosted parity. Parent #7 retains unmet production/live/design scope.

Follow docs/validation/wave5-program.md and the assigned docs/prompts/wave5-session-a.md or wave5-session-b.md. Baseline science/integration is 9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923; the launch message supplies the exact shared planning commit.

Before any new credential, administrator password, sudo, keychain or macOS-permission action, disclose the exact action/resource/reason and await the user. No bypass; no main/cyano mutation or package publication is implied. Preserve private-outcome boundaries and one writer per worktree.

- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/33

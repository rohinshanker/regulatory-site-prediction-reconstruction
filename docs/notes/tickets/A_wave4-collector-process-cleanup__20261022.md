# A_wave4-collector-process-cleanup__20261022 — Active

- Scope: B local process/error-classification repair for Wave4 collector, parent #12; no scientific collection or model change.
- Status: active
- Opened: 2026-10-22
- Updated: 2026-10-22
- Current State: B implemented the reserved six-path repair from 6e2affdde363b207769077400f46775bc527645b on quality/wave4-collector-portability in reconstruction-wave4-collector-portability-20261022. CI39720882453's original errno remains unknown; artificial fault injection establishes classification/ownership defects. Exact-patch local review by A and platform CI rerun are pending. No worker or old collection rerun.
- Verification: Old-code artificial fault injection reproduces three post-start failures falsely reported as process_start, with lost exit information. Final 32 focused/adjacent tests pass, zero skips, full 286 statements/108 branches; Ruff/format/mypy, guide links, ticket checker and diff checks pass. Original timeout/descendant assertions remain intact. Historical frozen evidence remains immutable. Evidence: /tmp/calculator-wave8-20261022/b-wave4-collector/.
- Cleanup: Distill process/diagnostic contract into docs/validation/wave4-collector-process-cleanup.md, add only its validation-index row, then close/delete own child after acceptance. Parent #12 remains open.
- Owner: Session B 9677689a-1792176763; coordinator/reviewer A baf5b738-1792172297.
- GitHub: [#72](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/72).

Implementation retains an unreaped group anchor through teardown, captures both pipes concurrently, records phase/type/errno and actual command state, and halts new scheduling on uncertain cleanup with every unstarted record retained. The CI errno is unknown; this is a reproduced classification/ownership repair, not an asserted diagnosis of the runner's precise fault. No test deadline or descendant assertion was relaxed.

Exclusive paths are benchmarks/rbs/wave4_collect.py, tests/benchmarks/test_wave4_collect.py, the new guide, and own ticket/index rows. Canonical producer and peer trees stay untouched. No workflow, shared runtime, scoring, model, source, dataset or fixture edits. No drafting internals/private outcomes, new Multica/follow-up/fallback, paid jobs, native build/folding, consumer changes or publication. Existing stopped tasks remain stopped. New credentials/admin/sudo/keychain/macOS permissions require exact action/resource/reason disclosure and owner decision before access; no bypass.

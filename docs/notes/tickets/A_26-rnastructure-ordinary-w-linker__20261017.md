# A_26-rnastructure-ordinary-w-linker__20261017 — Active

- Scope: Diagnose and repair the remaining ordinary-W/intermolecular-linker traceback failure.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Linker-3 source repair, pinned build/runtime identity and missing-receipt integrity guard are implemented and independently reviewed. The original and traceback-2 engines remain unchanged. Scientific candidate a11cb5bd13d3c021eedc98cf451609eb4710bb6a is isolated in reconstruction-rbs-wave4-frozen; final four-platform CI is pending before evaluation admission.
- Verification: Independent source review DEM-513 approved aaa0532c/945436ed; runtime admission and receipt guard reviews confirmed 0a10d3b/a11cb5b. All 35 three-engine component tests passed in 686.956 s with Python 3.14.7, including source/energy panels, constraint controls and mutation-sensitive harnesses. Full candidate suite: 1,614 tests, 100% of 5,603 statements/2,314 branches. Repaired seed succeeds on both strands in context/standby/joint; original/v2 retain explicit null failures. CI 39080285855 is active.
- Cleanup: Resolve only after independently reviewed source repair or justified domain contract, real backend/CI checks and durable validation; remove resolved ticket/index row.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/26
- Owner: Session A (baf5b738-1792172297), wave4/rbs-joint-runtime; backend component may be assigned to one scoped worker.
- Dependencies: #4; scoped #21 source repair and its preserved version2 controls.

Independent review found a reproducible failure in RNAstructure's unchanged ordinary-W/linker path. Original RNAstructure 6.6 and traceback-2 both exit zero with traceback errors and no CT. This is an upstream limitation, not a regression introduced by the W2/WMB2 repair. Parent #4; follows the scoped #21 repair.

Reproduce with synthetic seed 484, index 17:

- Leader: `GGAGGGUAUAACAGUGAGUCACCUGAGGUGGUAAGGUUUGGAUAACUGCGUCUUAGCAGU`
- aSD: `ACCUCCUUU`
- bifold arguments: `--maximum 100 --percent 100 --window 0 --loop 30 --temperature 303.15 --alphabet rna`
- Source archive SHA-256: `1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`
- Traceback-2 patch SHA-256: `2d599e7fa9f6581b605350508163c4aa14458ebb8f444c096e5f923c8742d671`

Observed diagnosis: the wrapped V(43,90) ordinary multiloop coax/interbases traceback pushes W(61,88) with energy −154. It contains linker centre 62 for N=72. Five failures arise at W(62,88)=−154 twice, W(35,62)=−79 twice, and W(62,84)=−144. Why the fill assigns a finite ordinary-W value here remains unresolved. Do not guess a W2 retag or discard the candidate.

Acceptance:

1. Derive the fill/trace invariant and root cause from the pinned source; implement a separately identified GPL-2.0-only source repair. Preserve the original and frozen Wave 3 artifacts.
2. Add independent recurrence, energy and structure regressions; retain the 60-input/12-leader controls and add fresh synthetic cases, ordinary Fold checks and relevant constraint/boundary tests.
3. Run real runtime and four-platform gates. Report every remaining failure and energy discrepancy; structural repair alone does not establish biological accuracy.

Future owner: Session A or its narrowly scoped backend implementer, in a separate worktree. B retains independent fixtures/evaluation. The runtime/component checks must continue to return explicit failure until a valid repair is available.

No private final outcomes, coins, browser, main/cyano changes or hidden fallback. Before any new credential, administrator or macOS permission action, disclose the exact action, resource and reason and await the required user decision.

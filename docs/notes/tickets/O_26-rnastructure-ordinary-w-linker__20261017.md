# O_26-rnastructure-ordinary-w-linker__20261017 — Open

- Scope: Diagnose and repair the remaining ordinary-W/intermolecular-linker traceback failure.
- Status: open
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Independent source review confirms the same synthetic failure in original RNAstructure6.6 and traceback-2. The W2/WMB2 repair remains accepted; the ordinary-W finite fill value has no valid traced decomposition. Runtime and component checks preserve explicit failure.
- Verification: Four deterministic reproductions per original/traceback-1/traceback-2 build in independent review; exit0, stderr traceback errors, no CT. Coordinator's real runtime rejects the input with null scores/energies in context2017 and standby2014 on both strands.
- Cleanup: Resolve only after independently reviewed source repair or justified domain contract, real backend/CI checks and durable validation; remove resolved ticket/index row.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/26
- Owner: Future Session A backend scope; B retains independent evidence and evaluation.
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

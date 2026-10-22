# Supplied-rate drafting numerical results

- Purpose: Reproduce the frozen artificial arithmetic and public-contract check.
- Scope: Original 0.12.0rc1 candidate, supplied stationary rates only.
- Last verified: 2026-10-22

**All 30 frozen requests passed**, crediting all 198 expected result records.
The [compact receipt](../../benchmarks/rbs/drafting-numeric-summary.json) separates
semantic agreement from execution and binds the external evidence by byte count
and SHA-256. It is 6,538 bytes, SHA-256
`7abeaf2c00c862a0ccefc7dc546edcb5fbd0ea308932773083ad86d337502fe6`.
The [independent protocol](rbs-drafting-numeric-validation.md), fixture and checker
were frozen before execution and remain unchanged.

| Denominator | Result |
| --- | --- |
| Frozen requests | 30 attempted once; 30 passed; no failures, missing cases, unstarted cases or retries |
| Parseable submitted roster entries | 305, including rosters in invalid envelopes |
| Accepted result-roster records | 198/198 credited: 48 `ok`, 139 `invalid_input`, 11 `unsupported_domain` |
| Invalid-envelope/transport requests | 17/17 correctly refused, with empty result rosters |
| Quantities in successful records | 192 checked: 177 finite, 9 exact zero, 6 underflow |
| Envelope statuses and CLI exits | 11 complete/exit 0; 2 partial/exit 1; 17 invalid/exit 2 |

The mathematical check uses the frozen exact-rational expectations, relative
tolerance `1e-11`, natural-log absolute tolerance `1e-10`, and separate strict
representation rule. In particular the borderline occupied probability in
`finite-panel`, index 5, remained finite as required; a tolerance interval
touching zero did not excuse an underflow representation. Invalid or unsupported
records count as correct refusals, not successful biological predictions.

The original candidate is source
`356abc2d40198a95f807967a38126a14b0f3d0c9`, version `0.12.0rc1`, wheel SHA-256
`a95abeeca03360e94b2d79a469520c62cfb8d45ff505dc6395032d9aa2f6c11b`.
It was not replaced by the later package. DEM636's independent mathematics/checker
review is reused. A separately accepted exact local driver SHA-256
`f5c147cac19d9d3632b04e372e4cf4d3495ce135ce3a176355914abb78df657f`, reproduced
39 synthetic tests with full 204-statement/68-branch coverage, and checked an
additional dual-stream overflow probe before authorizing execution.

Execution was serial in fixture order, with unchanged argv, replacement
environment and 10-second/4,194,305-byte stdout/65,536-byte stderr limits. Every
exit matched, all 30 stdout files matched authoritative serialization exactly,
and all stderr files were empty. The maximum observed child elapsed time was
0.070112 seconds; their sum was 1.671029 seconds. These observations include
process cleanup, exclude identity work, and are not a performance benchmark.
Largest stdout was 42,947 bytes. No stop condition occurred.

All 145 opaque identities matched before, between and after execution: the 144
frozen inputs/runtime assets plus the driver itself. The inventory includes 54
installed source/data files and A's 50 verified bytecode files. B hashed their
bytes without inspecting predictor code or code objects. The separate audit
rehashed all 60 output files, checked complete capture, mode 0600, limits, exits,
formatting and original settings. It records a corrected postprocessing-only
status-name assertion; neither candidate output nor the semantic report changed.

## Rechecking saved evidence

The explicit external root is
`/Users/Rohin/.cache/regsite-drafting-numeric-20261021`. Its
`candidate-301cfe2/execution-receipts/execution.json` is 2,744,922 bytes, SHA-256
`08a8342bf3b10a57d72c3abc4dd859ac57b93a7d6e05e04a11d8f684159421db`.
`candidate-301cfe2/semantic-report.json` is 10,784 bytes, SHA-256
`9c1bb04f222b92132912da3dc3863af134a5bac800db9cee71678e1c9e9f49b4`.
The compact receipt lists exact pins for these and the settings, identity,
authorization, bytecode supplement, accepted driver, independent review evidence
and execution audit. Complete per-case outputs and identity observations remain
external; no private or empirical outcome was used.

Verify those hashes before checking saved outputs. The exact 30-case checker
argv and cwd are in `candidate-301cfe2/semantic-command.json`, also pinned in the
compact receipt. Replay only that checker command with a **new output path**;
the checker refuses collisions. It exits 0 for this saved panel. Its repeated
`--result ID=PATH` arguments include every frozen case. Do not invoke the
one-shot collection driver again. Relocation requires explicitly remapping
saved paths while preserving and checking their bytes; a local path is not a
portable data distribution or a fresh execution receipt.

## Interpretation limits

This finite check supports supplied-rate stationary arithmetic, extreme-number
representation, refusals and the public software interface. It does not prove
every binary64 input correct. The rates are artificial caller inputs; the test
does not infer them from sequence or measure folding kinetics, translation,
native-host transfer, recoding effects or hosted equivalence. The model's
stationary and memoryless assumptions remain. Source admission, arithmetic
agreement, biological validation and consumer/release admission are separate.

A independently reviewed the driver and the checker had independent review
before execution. The immutable compact receipt records B's handoff state before
A's outcome recheck. During integration, A verified all 17 artifact pins and
rehashed all 60 saved output files, then replayed the unchanged checker against
those outputs. It exited 0 with a byte-identical semantic report: 30 requests
and 198 credited records. No predictor was rerun. This accepts scoped #66
arithmetic/interface delivery; broader release and biological gates remain open.

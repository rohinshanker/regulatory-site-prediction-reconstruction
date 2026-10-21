# A_07-promoter-calculator-reconstruction__20261016 — Active

- Scope: Recover and implement the production-oriented Promoter Calculator.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-21
- Current State: Historical local runtime, unchanged-output optimization and native pilot are implemented and independently reviewed. The complete anchor-centered native/source comparison agrees across 130,954 positions; native best-position localization is 900/1,597 within five bases versus 398 shuffled controls. Separate frozen count analysis yields weak control-count Spearman 0.173 (95% interval 0.126–0.219). These exposed-cohort results establish historical fidelity, not native strength calibration, hosted parity or model improvement. See [pilot results](../../validation/promoter-native-pilot-results.md). Broader scientific, publication and consumer-admission scope stays open.
- Verification: Full combined local suite 5,658 passed/zero skips, 100% measured statements/branches; fresh installed package passes 22 offline checks across all seven commands. Source checker 139 tests and count evaluator 156 tests independently reviewed at full coverage. Frozen source fixtures and parameters remain unchanged. [Combined package identity](../../validation/integrated-runtime-build.md) distinguishes this build from earlier evaluated candidates; exact proposed-head remote CI remains a separate check.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/7
- Priority: P1
- Owner: Session A (`baf5b738-1792172297`); Session B owns independent source/benchmark work.
- Dependencies: Promoter slice of 01; 02; independent source/benchmark contracts. RBS milestone 06 remains a publication dependency, not a blocker for isolated implementation after the 2026-10-18 owner instruction.

Deliver a usable DNA-to-promoter/TSS predictor and a documented path to production parity. Reuse the public Salis model and the cyano compatibility work; do not mistake iDOG promoter parts/design machinery for an existing locator.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.

- Start at the pinned Promoter_Calculator directory and primary paper in the source map. Reuse verified preparation and coefficient-array pins after checking licences. Audit training/calibration assumptions and any later production changes.
- Implement forward/reverse scanning, candidate TSS positions, UP/-35/spacer/-10/discriminator/initial-transcribed-region features, raw transcription scores and energy breakdowns actually supported by the model.
- Explicitly identify RNAP/sigma-factor and E. coli calibration. Unknown hosts must not silently receive E. coli labels. Host transfer and any future cyano calibration are separate model profiles with evidence.
- Verify feature coordinate conventions with extracted-sequence round trips and live exports. Define candidate selection/thresholds independently of display choices.
- Compare to published construct data and held-out live profiles; separate strength prediction from positional detection. TSS data do not establish complete promoter boundaries, and repeated conditions at the same locus must not leak across splits.

## Acceptance criteria

- A standalone open library/CLI performs single/batch both-strand prediction with term-level outputs and verified intervals; all required arrays and dependencies are reproducible and licensed.
- Historical/public versus reconstructed/hosted identities and production feature gaps are explicit. Public-source recovery is tried before replacement modeling.
- Tests cover every implemented path, edge windows, overlaps, invalid input, candidate selection, output conversions and stable coefficients.
- Experimental and live benchmark reports include failure coverage and predeclared tolerances. A fresh install runs offline and emits the shared schema.

## Verification to record

Full suite gates, source/preparation hashes, coefficient preservation, coordinate fixtures and frozen benchmark results. Publish the calculator's own model card and release artifact; constrained design is completed under 11.

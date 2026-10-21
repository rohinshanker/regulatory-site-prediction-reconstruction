# A_operon-coupling-component__20261021 — Active

- Scope: Source-supported translational coupling for explicitly supplied adjacent CDSs; child of #8.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: Source/math review DEM-615 admits only supplied-energy reinitiation; its two documentation findings are reconciled at `a5b43c7`. Geometry, strict JSON, log-space runtime, schemas and single/batch CLI examples are implemented. No folding jobs or biological evaluation executed. Runtime review and final integration gates remain.
- Verification: Baseline `605d0c25066de937d124e69fe42be3c40bb2e749`; isolated worktree `reconstruction-operon-coupling-20261021`, branch `wave7/operon-coupling`. 271 focused tests pass with 100% new-module line/branch coverage; Ruff and mypy pass. Source/math review verified pinned paper bytes, all five synthetic controls and geometry identities independently.
- Cleanup: Session C alone closes this child after recording every finding and final validation, distilling reusable contracts, updating both indexes and the linked issue, then removing the resolved ticket. Broad #8 remains open.
- Owner: cyano-calcs-c / 56abed60-1792619583; A owns integration and B independent evaluation.
- Parent: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/8
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/60

## Constraints and acceptance

Own only new `coupling*` runtime/schema/test/example paths, `operon-coupling*`
validation documents, `benchmarks/operon-coupling/`, this ticket and its index
rows. Shared runtime, packaging, CI and README remain A's responsibility. Keep
source bundles in external storage; article rights, implementation terms and
measurement rights are separate. No fitting, sequence design, private outcomes,
consumer changes, publication or claims of complete Operon/UTEX calibration.

Before model code: pin equations, parameters, sign/scale conventions, geometry,
admitted mechanisms and explicit unsupported cases; freeze independent synthetic
fixtures and obtain source/math review. Then ship real offline single/batch
examples, strict schemas, full new-path branch coverage, numerical/budget/failure
tests and independent patch review. A handles common packaging and fresh install.
Coordinate before any folding execution; two local folding processes globally.

## Source intake

- Tian and Salis (2015), DOI `10.1093/nar/gkv635`, PMC4538824.
- Retrieval: 2026-10-21, public Europe PMC `fullTextXML` endpoint.
- XML SHA-256: `fcd1558c2ebab38782b48b11a2484c16aa73e24ac4299b9e26516e3cd6f1a089`.
- External cache: `/Users/Rohin/.cache/regsite-coupling-source-20261021`.
- Terms: article CC-BY-NC-4.0; no article/data redistribution admitted.
- Model equations appear as image graphics; text-only XML is insufficient to
  verify their exact algebra. No coefficients adopted yet.
- Direct Europe PMC PDF returned HTTP 403; no access control bypass attempted.

## Open findings

- C-SOURCE-1 resolved for the explicitly narrow component by DEM-615 and `a5b43c7`; other negative-distance law remains a documented full-model dependency.
- C-SOURCE-2 excluded from this component: sequence-derived energy decomposition/backend and unfolding formula conflict remain explicit broader #8 dependencies; no substitute or zero correction is supplied.
- C-REVIEW-1 resolved by DEM-615 and `a5b43c7`; Figure 1D conflict and host-locator corrections are incorporated.
- C-REVIEW-2 open: exact implementation review and final package tests.

## Active assignments

- DEM-615: GPT-6 Astra independent source/mathematical review of `deb3e2f`.
- DEM-616: GPT-6.1 Sol source-independent geometry validator only, separate
  `reconstruction-coupling-geometry-20261021` worktree; no model calculations.
- C retains runtime/contract integration. Initial source contract narrows the
  proposed admitted scope to reinitiation; printed Eqs. 4/5 have an unresolved
  unfolding/sign interpretation and negative-distance coefficients remain gated.

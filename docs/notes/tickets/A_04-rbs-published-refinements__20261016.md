# A_04-rbs-published-refinements__20261016 — Active

- Scope: Reconstruct later published RBS mechanisms and production behavior.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-17
- Current State: Wave 3 now isolates backend repair (#21) and complete standby reconstruction (#22); website collection is deferred. Historical science preserved; footprint/context profiles implemented and independently reviewed. All 136 reporter-development and 27 secondary 2017 inputs score. Native historical/footprint score 2,400/2,530 source cases; context scores 2,234 with 268 explicit backend failures. The 18-case 2017 TE challenge favors context over historical scoring, but is one partly exposed shared family. Live diagnostic candidate coverage agrees while numerical parity fails. Later standby/sliding/drafting/stacking and backend differences remain unresolved.
- Verification: Integrated code a3b46fa passes 1,383 tests with the real backend, 100% of 4,185 statements and 1,742 branches; Ruff/mypy pass. Scientific runtime/export is frozen at 7547778c508d4a31b4a4f95df370923ce8bd07c3. Later changes are evidence integration and documentation; final report links and exact release CI are recorded on issue #6.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/4
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), Wave 2 implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: 03 baseline; 05 supplies hosted evidence as available.

Extend the tested baseline toward the current production RBS Calculator using papers, supplementary equations/data and legitimate reference outputs. A version label or improved fit does not prove a faithful reconstruction.

## Work

- Build a mechanism-to-equation/parameter/test matrix for standby geometry, selective unfolding/sliding, coding-region footprint, sequence-specific stacking and any published folding-kinetic/ribosome-drafting correction relevant to the target.
- Read the 2014, 2016, 2017 and model-testing sources in the source map with their supplements. Separate mechanisms described in documentation from mechanisms proven implemented by the target hosted version.
- Implement documented mechanisms incrementally with explicit versioned profiles and unit fixtures. Preserve the historical baseline to expose which change explains each output difference.
- Test folding engine/energy parameters, cofold constraints, enumeration and optimization choices before changing fitted coefficients. Never turn unexplained website outputs into undocumented constants.
- Use development reference cases from 05 for diagnosis; keep the held-out set untouched until the final comparison. Record unidentifiable or unsupported mechanisms as precise gaps.
- Follow the [Wave 2 program](../../validation/rbs-wave2-program.md). The exposed
  live diagnostic panel is development evidence. Prioritize explicit footprint,
  transcript context and supported standby mechanisms; keep backend enumeration
  differences measurable. Compare independently runnable methods from 17 without
  importing restricted components or fitting hidden constants to website outputs.

## Acceptance criteria

- Every adopted refinement has primary evidence, parameter provenance, an implemented calculation, fixtures and an ablation comparison against the baseline.
- The current reconstructed profile runs locally with open dependencies, returns explainable energies/coordinates and retains deterministic behavior.
- A feature/parameter parity matrix distinguishes matched, measurably different, not observed and not implemented behavior; no silent heuristic substitute for a missing term.
- Failures and remaining numerical differences have reproducible examples. A major missing advertised capability remains open work rather than being hidden by a production-equivalent label.

## Verification to record

Full CI, term-level fixtures, independently checked paper examples, baseline/refinement regression and a frozen held-out hosted comparison when available. Report tuning separately from final evaluation.

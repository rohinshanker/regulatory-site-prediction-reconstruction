# A_04-rbs-published-refinements__20261016 — Active

- Scope: Reconstruct later published RBS mechanisms and production behavior.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-21
- Current State: Historical, footprint/context, standby2014 and joint profiles remain frozen; joint selection failed its independent advancement gate. B completed source/math admission #65. Separate supplied-rate stationary drafting #66 is independently reviewed at c75ca5d and packaged locally in 0.12; platform gates and B’s independent numerical tooling remain; it does not derive rates from sequence or modify existing profiles. Sequence-derived kinetics, production stacking, folding-search completeness and hosted parity remain open.
- Verification: Scientific a11cb5b and integration 1d4b622 passed four-platform CI; 1,624 integrated tests at 100% measured Python coverage and 35 three-engine component checks pass. Frozen Wave 4 review independently reproduces the negative advancement result. Runtime/model/source contracts retain bounded enumeration and energy discrepancies; no native or hosted equivalence is established.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/4
- Priority: P0
- Owner: Session A (`baf5b738-1792172297`), implementation/integration; suite-wide scope remains open where applicable.
- Dependencies: 03 baseline; 05 supplies hosted evidence as available.
- Current source dependency: [Admitted supplied-rate theory](../../validation/rbs-kinetics-source-admission.md) and six original rational fixtures are integrated unchanged from B abd9f286. [Child #66](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/66) owns implementation; B’s distinct independent numerical checker is reserved and awaiting session delivery. Sequence-to-rate timescales/calibration and the source energy-accounting ambiguity remain unadmitted. Held termination review #64 and native-host audit #58 stay separate.

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

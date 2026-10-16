# O_04-rbs-published-refinements__20261016 — Open

- Scope: Reconstruct later published RBS mechanisms and production behavior.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- Priority: P0
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: 03 baseline; 05 supplies hosted evidence as available.

Extend the tested baseline toward the current production RBS Calculator using papers, supplementary equations/data and legitimate reference outputs. A version label or improved fit does not prove a faithful reconstruction.

## Work

- Build a mechanism-to-equation/parameter/test matrix for standby geometry, selective unfolding/sliding, coding-region footprint, sequence-specific stacking and any published folding-kinetic/ribosome-drafting correction relevant to the target.
- Read the 2014, 2016, 2017 and model-testing sources in the source map with their supplements. Separate mechanisms described in documentation from mechanisms proven implemented by the target hosted version.
- Implement documented mechanisms incrementally with explicit versioned profiles and unit fixtures. Preserve the historical baseline to expose which change explains each output difference.
- Test folding engine/energy parameters, cofold constraints, enumeration and optimization choices before changing fitted coefficients. Never turn unexplained website outputs into undocumented constants.
- Use development reference cases from 05 for diagnosis; keep the held-out set untouched until the final comparison. Record unidentifiable or unsupported mechanisms as precise gaps.

## Acceptance criteria

- Every adopted refinement has primary evidence, parameter provenance, an implemented calculation, fixtures and an ablation comparison against the baseline.
- The current reconstructed profile runs locally with open dependencies, returns explainable energies/coordinates and retains deterministic behavior.
- A feature/parameter parity matrix distinguishes matched, measurably different, not observed and not implemented behavior; no silent heuristic substitute for a missing term.
- Failures and remaining numerical differences have reproducible examples. A major missing advertised capability remains open work rather than being hidden by a production-equivalent label.

## Verification to record

Full CI, term-level fixtures, independently checked paper examples, baseline/refinement regression and a frozen held-out hosted comparison when available. Report tuning separately from final evaluation.

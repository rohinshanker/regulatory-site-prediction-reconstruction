# O_09-riboswitch-calculator-reconstruction__20261016 — Open

- Scope: Recover and implement the conditional Riboswitch Calculator.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- Priority: P1
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: RBS milestone 06, core 02, Riboswitch slice 01 and live references 05.

Deliver an open predictor for a specified aptamer/ligand/structure in transcript context, matching the production calculator as closely as evidence permits. Aptamer discovery is a separate upstream task.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.

- Read original and extension papers/supplements and inspect current prediction/design inputs. Search linked code and releases for a complete implementation before reconstruction. Determine which ligand/protein-sensing modes the hosted target actually supports.
- Specify transcript, aptamer span, bound structure, ligand concentration/binding assumptions, temperature and host. Validate dot-bracket/sequence alignment, paired-base consistency, concentration units and supported constraints.
- Implement documented bound/unbound structural states, energetic coupling, occupancy/concentration response, translation-initiation predictions and regulation metrics. Reuse the versioned RBS core with explicit shared assumptions.
- Preserve equilibrium/kinetic assumptions and model domains. Do not invent affinities, bound structures or binding-site locations from a gene name or family hit.
- Provide inspectable state structures/energies and concentration-response output with correctly defined ratio direction, zero/boundary behavior and uncertainty/applicability warnings.

## Acceptance criteria

- The predictor runs fully locally from explicit inputs and reproduces permitted paper examples and a frozen hosted panel with declared tolerances or quantified discrepancies.
- Tests exercise concentration limits, occupancy/normalization, state-energy/rate calculations, malformed constraints, invalid units, unsupported ligand/protein modes, deterministic selection and all implemented error paths.
- Model/source/parameter identity, structure constraints, settings and outputs survive schema/export round trips; independent aptamer evidence remains distinguishable from conditional predictions.
- A fresh-install offline release has complete source and required parameters under open terms, examples and a model card. No generic genome-wide riboswitch-discovery claim is made.

## Verification to record

Full CI, analytic limiting cases, structural fixtures, primary-data comparison and live-reference discrepancies. Constrained switch design is delivered under 11; this prediction ticket remains open if essential state calculations are missing.

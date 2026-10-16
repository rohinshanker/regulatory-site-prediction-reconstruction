# O_03-rbs-historical-baseline__20261016 — Open

- Scope: Implement and validate the historical RBS scoring baseline.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- Priority: P0
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: RBS selection in 01; working foundation in 02.

Deliver the first real RBS prediction implementation using the public Salis v1 source and Jaymin/iDOG as pinned references. Establish which historical behaviors can be preserved with an entirely open runtime.

## Work

- Map each calculation to a paper equation/code symbol: unbound folding, candidate mRNA–rRNA binding, spacing, start-codon contribution, standby accessibility, residual folding, total energy and rate conversion.
- Port reusable source with provenance and notices. Audit iDOG optional/error branches and parsers before reuse. Verify suboptimal structure enumeration, selection/tie behavior, window sizes, footprint, dangles and temperature.
- Make anti-SD an explicit input. Keep ACCUCCUUA and vendor/annotated-boundary ACCUCCUUU scenarios distinct; do not claim the latter establishes mature UTEX processing or calibration.
- Provide supplied-start scoring and documented supported start scanning, term breakdown, structural output and validated candidate/SD/spacer/start/footprint coordinates where established by the model.
- Label open-backend deviations explicitly. A NUPACK-to-ViennaRNA substitution is not proven numerical equivalence. Preserve a named historical profile and a distinct reconstructed profile when necessary.

## Acceptance criteria

- A real local library/CLI scores public reference sequences singly and in batches, including alternatives/internal starts and no-viable-binding cases without fabricated results.
- Unit tests reproduce independently checkable energy terms and exponential conversion, and regression fixtures cover historic outputs where legitimately available.
- Boundary/strand/start-codon cases, invalid inputs, dependency failures, overflow and every implemented branch are exercised.
- A term-by-term comparison explains deviations between pinned Salis/iDOG/reference outputs; similarity of final rates alone is insufficient.
- Source/parameter/backend provenance is included in results and documentation; no private or research-only runtime is required.

## Verification to record

Run the full ticket-02 gates, paper/reference fixtures and fresh-install offline examples. Publish baseline coverage and limitations, preserving all unverified production-parity claims for tickets 04–06.

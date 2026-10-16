# O_08-operon-calculator-reconstruction__20261016 — Open

- Scope: Recover and implement the integrated Operon Calculator.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- Priority: P1
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: RBS milestone 06, Promoter 07, core 02, Operon source slice 01 and references 05.

Reconstruct the production Operon Calculator as an integrated, fully open local model. This includes its documented submodels and outputs, not merely concatenating RBS and promoter results.

## Work

- Use ticket 12 for the relevant benchmark-quality audit and frozen experimental splits. Keep any ticket-13 improved profile distinct from the compatibility profile; assess both against the same held-out data.

- Inspect the live prediction/design contract and cited primary sources/supplements. Build an explicit submodel dependency graph for transcription initiation, internal promoters, translation initiation/coupling where applicable, elongation, terminators/readthrough, RNA stability and any expression-combination model. Include the documented pause-site, repeat, transposon/phage insertion-site and synthesis-complexity features in the parity inventory; distinguish sequence-risk annotations from experimentally active sites.
- Recover openly licensed complete implementations first, including candidate mRNA stability and terminator tools; verify their actual role in the production model rather than treating similar function as equivalence.
- Specify inputs for supplied promoter, ordered RBS/CDS pairs, terminator, host and transcript context. Test the observed 1–10-pair domain and document any extension. Do not infer an operon solely from neighboring genes.
- Implement each necessary missing submodel from cited equations/parameters with independent fixtures. Validate interfaces and propagated units/uncertainty; multiplying unrelated scores is not a supported expression model.
- Return per-cistron quantities, internal elements, structures/stability where supported, submodel versions, warnings and a validated annotated GenBank export. Distinguish predicted RNA abundance, translation and protein expression scales.

## Acceptance criteria

- A clean local installation handles complete representative operons and reports every supported required submodel, with no private module or silent unavailable-score filler.
- Submodel/unit tests and integrated examples cover monocistronic/multicistronic inputs, internal elements, overlapping/short spacers, strand/context boundaries, invalid organizations and batch failures.
- A feature parity matrix and held-out live comparisons show which output classes agree, differ or remain unimplemented; each required unresolved submodel remains an explicit open item in this ticket.
- Source/licence/parameter provenance, units and coordinate exports are auditable; predictor release and examples run offline.

## Verification to record

Full CI, submodel ablations, end-to-end fixtures, real export round trips and live/experimental benchmarks with actual input assumptions. Ticket 11 adds constrained operon design and final suite parity; missing prediction submodels cannot be hidden by that later work.

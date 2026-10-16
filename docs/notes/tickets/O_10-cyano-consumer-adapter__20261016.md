# O_10-cyano-consumer-adapter__20261016 — Open

- Scope: Integrate released calculator outputs into the cyano consumer.
- Status: open
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Planned; implementation has not started. See the work and acceptance criteria below.
- Verification: Repository setup checked ticket H1/fields, queue membership and local links on 2026-10-16; implementation validation is specified below and has not run.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/10
- Priority: P1
- Owner: Unclaimed; the implementing session must claim this ticket before writing its scope.
- Dependencies: 02 schema and each relevant calculator release; RBS can ship after 06 without waiting for 07–09.

Provide a versioned producer/consumer interface and coordinate dependent ticket updates in isaacs-cyano-gene-selection. Calculator internals stay in this repository; native extraction, admission and UI stay in the consumer.

## Work

- Follow [the consumer boundary](../../validation/cyano-integration.md) and inspect current consumer instructions, model admission contracts and ticket ownership. Pin an actual release, not a mutable sibling path.
- Implement package/CLI adapters and fixtures that preserve exact input, assembly, strand/window, host, temperature, model/parameter versions, score semantics, warnings and evaluation status.
- Map only verified site intervals onto versioned replicons. Test positive/reverse strands, transcript windows, overlapping sites, boundary cases and supported circular-origin mapping.
- For recoding, compare original/active-scheme inputs under identical settings. Define candidate matching and added/lost/changed scoring before counting; keep not evaluated/no data distinct from zero changes.
- RBS and Promoter feed their existing consumer tickets. Future Operon layers require explicit organization; Riboswitch layers require independent aptamer evidence and specified structural/binding inputs. Neither is inferred from a gene name.
- Coordinate runtime placement with the optional compute-backend ticket only if selected workloads need it. Keep existing native RNA folding, Tan-TSS edit counts and Rfam work independent.

## Acceptance criteria

- RBS is integrated first through a version-pinned interface with end-to-end fixtures; later calculators can be admitted independently when ready.
- Consumer docs/tickets identify exact dependency releases and retained scientific/admission constraints. No duplicate model engine or hidden account dependency is introduced.
- Strand/coordinate, missingness, stale-cache/model-version and original/recoded comparison tests pass in both repositories as applicable.
- Any visible UI changes pass the consumer's rendered validation and full required gates. No consumer ticket is closed without its owning session and all acceptance criteria.

## Verification to record

Producer contract tests, consumer integration fixtures, exact result/package pins, consumer npm/pytest/contract checks and relevant rendered states. A successful reconstruction benchmark alone does not admit a viewer layer.

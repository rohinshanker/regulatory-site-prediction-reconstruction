# A_rbs-supplied-rate-drafting__20261021 — Active

- Scope: Separate stationary RBS drafting component from explicitly supplied rates; child of #4.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: B's independently accepted source/math admission abd9f286 is integrated at a5eff4b. A froze the version-1 interface in docs/validation/rbs-drafting-contract.md; scoped runtime and independent numerical work are being assigned in separate trees. No sequence-derived kinetic model is admitted.
- Verification: Source and six original rational fixtures are unchanged and hash-verified. Implementation, numerical challenge, independent patch review and package gates are pending.
- Cleanup: Distill final usage/numerical limits into the contract, remove this owned resolved ticket/queue row, and close the child after all applicable gates. Parent #4 remains open for missing sequence-to-rate dependencies and experimental validation.
- Owner: cyano-calcs-A / baf5b738-1792172297; B owns disjoint independent cases.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/66

Reserved implementation: src/regsite/drafting{,_io,_cli}.py,
tests/test_drafting*.py, schemas/drafting-{request,result}-1.schema.json,
examples/drafting-{single,batch,unsupported}.json. A owns this ticket, its queue
row, common packaging/CI/README and final integration. B owns future
benchmarks/rbs/drafting-numeric-* artifacts and their benchmark tests.

Keep native/scoring profiles unchanged. No model fitting, private outcomes,
sequence or energy defaults, external kinetic simulator, consumer/canonical
edits, publication or stopped-task reroute. Required access disclosures and all
existing provider/consumer holds remain in force.

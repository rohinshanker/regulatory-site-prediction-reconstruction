# A_rbs-supplied-rate-drafting__20261021 — Active

- Scope: Separate stationary RBS drafting component from explicitly supplied rates; child of #4.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: B’s independently accepted #65 source/math admission is integrated unchanged. DEM-627 implemented the frozen version-1 interface, then repaired two schema findings at c75ca5d24efdff2077c882b4edb495a2864c8c4a. DEM-629 independently accepted that exact patch; A integrated it at 10b35a367e4811c49f98dbf3d91b4e4f3a32d0ae. Version 0.12 package integration is underway. B’s distinct numerical checker scope is reserved and awaits session delivery; no replacement worker has been started.
- Verification: Independent recheck confirms 258 focused tests, zero skips, full coverage of 171 statements/44 branches plus Ruff/format/mypy. Six immutable source fixtures and extreme-rate/renewal/balance/schema/CLI cases pass. Source/fixture hashes are unchanged. Independent review also checked 100 artificial records, with maximum absolute log error 2.27e-13 against its Decimal reference. B’s separate numerical check, installed package and combined CI remain pending; these mathematical checks do not establish biological accuracy.
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

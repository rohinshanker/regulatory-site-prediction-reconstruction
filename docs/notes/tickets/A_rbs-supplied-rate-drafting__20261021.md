# A_rbs-supplied-rate-drafting__20261021 — Active

- Scope: Separate stationary RBS drafting component from explicitly supplied rates; child of #4.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: B’s independently accepted #65 source/math admission is integrated unchanged. DEM-627 implemented the frozen version-1 interface at 7c277da8ee44c3d881bceda220d4bd211b618251 in its isolated tree; DEM-629 is independently reviewing that exact patch. A owns package integration after review. B’s distinct numerical checker scope is reserved and awaits session delivery; no replacement worker has been started.
- Verification: Worker reports 160 focused tests, zero skips, full coverage of 171 statements/44 branches plus Ruff/format/mypy. Six immutable source fixtures and extreme-rate/renewal/balance/schema/CLI cases pass. Source/fixture hashes are unchanged. Independent review, B’s separate numerical check, installed package and combined CI remain pending.
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

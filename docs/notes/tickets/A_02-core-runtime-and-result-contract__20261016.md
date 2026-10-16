# A_02-core-runtime-and-result-contract__20261016 — Active

- Scope: Build the shared local runtime, result schema and test infrastructure.
- Status: active
- Opened: 2026-10-16
- Updated: 2026-10-16
- Current State: Active Wave 1 implementation in the isolated runtime worktree. Source/licence/backend evidence and independent benchmarks are owned by Session B; no production-parity claim is made.
- Verification: 125 runtime tests pass with 100% statement/branch coverage using the independently built RNAstructure 6.6 backend; Ruff and mypy pass. Fresh wheel single/batch JSON/CSV examples run offline. All four CI jobs passed at a27a76f; final connected-band/input-normalization fix d367d86 is in CI and focused review. B’s early source/backend evidence is integrated; its benchmark handoff is pending. Production equivalence is unverified.
- Cleanup: Owning session records final checks and unresolved findings, resolves the ticket, distills reusable guidance into docs/validation/, updates both indexes and linked GitHub issue, then removes the resolved ticket.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/2
- Priority: P0
- Owner: Session A / cyano-rbs-scraping (agent-deck baf5b738-1792172297), branch wave1/rbs-runtime.
- Dependencies: RBS slice of 01 for adopted dependencies; contract design can start immediately.

Create the smallest working package/CLI foundation needed by the first RBS engine. Prefer Python and reuse verified open scientific dependencies; choose another language only with a documented practical reason. No browser UI or hosted service is necessary for the first release.

## Work

- Establish package/build metadata, supported interpreter/platform versions, pinned dependencies, a lock/install process and CI. Select a licence-compatible open folding backend and capture its version/energy tables/settings.
- Implement typed inputs/results and real sequence/structure validation under [the reconstruction contract](../../validation/reconstruction-contract.md). Separate model math, folding adapter, IO and sequence-coordinate mapping.
- Define explicit single/batch result statuses, deterministic identities, warnings, score scales and JSON/CSV export semantics. Specify zero-based half-open internal coordinates, orientation, point features and conversions.
- Include configurable host/anti-SD, temperature, window policy and resource limits; reject unknown settings rather than silently switching to an E. coli default.
- Build real folding/normalization/coordinate functions with tests, not empty calculator classes. Integrate an actual RBS call during ticket 03; expose only implemented capabilities in the CLI.

## Acceptance criteria

- A clean supported environment installs the package, invokes the implemented utility/CLI paths and passes CI without private dependencies or credentials.
- Every new code path has tests, including ambiguous/invalid bases, bad structures, reverse complements, boundary windows, zero-length/no-hit/failed results and batch isolation.
- Folding calls have bounded resource handling, explicit errors and reproducible settings. Required inference is offline after installation.
- Exact lint/type/unit/integration/coverage commands and support matrix are documented for later tickets; schemas include examples and a compatibility policy.

## Verification to record

Fresh-install smoke test, backend fixture comparisons, schema round trips, branch coverage, and the full established CI commands. Keep unsupported calculator commands absent until implemented.

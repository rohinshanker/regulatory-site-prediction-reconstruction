# A_intrinsic-termination-component__20261021 — Active

- Scope: Implement and verify a bounded intrinsic-termination candidate scorer using the admitted external TransTermHP engine; child of #8.
- Status: active
- Opened: 2026-10-21
- Updated: 2026-10-21
- Current State: C implementation is independently admitted at `6113b54a467af3f90a9a70b20a77c2247983a91c`; source/runtime reviews and repair rechecks close every material finding. A common package/full-suite/CI gates remain before C closes #62.
- Verification: 370 focused tests pass with zero skips and full 712-statement/188-branch coverage, using the actual offline builder output. CI-scoped Ruff/format/mypy, ticket validation and diff checks pass. Source/math and exact runtime acceptance are independently complete; combined integration is pending.
- Cleanup: C alone resolves after review, repairs and required integration evidence; rename/H1/status to resolved, retain reusable contracts, update indexes, delete resolved ticket and close linked issue. #8 remains open.
- Owner: cyano-calcs-c / 56abed60-1792619583; A owns common integration, B independent experimental/source evaluation.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/62
- Parent: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/8

## Ownership and next gate

Canonical checkout is read-only. C writes only in
`reconstruction-intrinsic-termination-20261021` on `wave7/intrinsic-termination`
from `605d0c25066de937d124e69fe42be3c40bb2e749`. A accepted the five termination
runtime modules, offline builder, three schemas, three examples, eight test files,
termination source/runtime docs and fixtures, and C's ticket/index rows. Shared
package/entry-point/version/CI/README changes belong to A. B exclusively owns
`benchmarks/termination/evaluation-sources.json` and
`docs/validation/termination-benchmark-admission.md`.

DEM623's isolated backend/parser/builder implementation is integrated at c7f7864.
C added API/IO/CLI/schema integration and fixed Make compiler-path metacharacters
at 989031d. Runtime review completed on a separate clean snapshot at 2276af4; no duplicate
source review, writer or reviewer is authorized. DEM619 run
`01a160d2-aefe-7eab-a7f3-d7a19430b4c4` completed with four bounded findings.
Same-reviewer repair run `01a160e2-2352-769f-bd3d-c49c6be93d27` accepted the main
repairs; final run `01a160e6-9420-7606-8d01-6765ae4a2936` closed residual R1 with
no regression. Final code is 6113b54. No further review is pending within C scope.

A reserves C one sequential native/compiler slot within the global cap of two.
The completed reviewer used three frozen tiny-input executions and released
that slot. C used it serially for the complete post-repair native suite. The
unchanged external source-built engine needs no rebuild.

## Contracts and evidence

The [source contract](../../validation/intrinsic-termination-source.md) records
all admitted numerical, licensing and boundary decisions. The
[runtime contract](../../validation/intrinsic-termination-runtime.md) specifies
strict input/output, process handling, missingness and reproduction commands.
Source admission does not imply biological accuracy or full Operon reconstruction.

The actual external builder output is
`/Users/Rohin/.cache/regsite-termination-adapter-20261021/backend.json`;
its executable SHA256 is
`b01d8d864eb6f41d36cdbf4d0e46255ce3f702c463c838afdaf21770d3d7cb4d`.
The [adapter receipt](../../../benchmarks/termination/adapter-build-manifest.json)
pins that build, focused checks and complete CLI captures. Original scalar,
11-case native, non-saturated tie and 12-case corrected-build fixtures remain
immutable. No original fixture or empirical outcome is retuned.

## Constraints

Candidate motif/background scores are not termination efficiency, readthrough,
expression, native calibration or De Novo DNA equivalence. Preserve complete
rosters, coordinates, failure states and withheld boundary confidence. External
engine source, table, executable and notices remain outside the Python package.

No private/consumed outcomes, fitting, large scans, paid jobs, canonical/peer or
consumer writes, main merge or publication. PV-R1, DEM577/568 and refused
DEM612/613/#58 remain stopped. Before any new credential/admin/sudo/keychain/macOS
permission, disclose the exact action, resource and reason and wait for the
owner; no bypass. No child may reroute or duplicate its assignment.

## Exact runtime finding disposition

- F1: distinct `native_candidate_limit`, null roster, and explicit sequence-dependent candidate/output/time limits within the input-length cap. No long-fragment completeness claim or new density experiment.
- F2: execute private mode0700 copy of verified bytes; replacement-race and copy-failure cleanup tests pass.
- F3/F4: both confidence fields null at the ambiguous boundary; schema enforces boundary geometry/status/context implications and rejects invalid mutations.
- F5/F6: final pre-launch deadline check; document `attempted` as backend invocation and distinguish unavailable capture/return status from process launch.
- F7: support native calls from a single-threaded Python process; `preexec_fn` caveat is explicit. Separate processes may provide concurrency under resource reservations.
- F8: strict regex end assertions reject final newlines consistently, including schema-only checks.
- F9: retain disclosed caller-asserted toolchain provenance; no new attestation or toolchain surface.
- F10: reject G after the left gene-end row, consistent with pinned map/scan events. Do not impose an unproved 11-base extent minimum: the source admission already distinguishes the genomic-right-arm check from gapped opposite-arm length. No scoring-code change.

R1 from the completed repair recheck is fixed by bounded total/G/F counters and
complete validation of rows/trailer/counts after retention stops. Five negative
cases cover missing trailer, trailing garbage, nonconsecutive IDs and both
context-count mismatches. The final independent R1 check is complete with no regression. No new source,
engine build or empirical input.

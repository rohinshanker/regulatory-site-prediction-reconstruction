# Intrinsic-termination 0.11.0rc1 development candidate

- Purpose: Bind the reviewed optional native adapter to a locally installed package.
- Scope: Retained intrinsic motif candidates and software verification; platform matrix pending; integration review accepted after a workflow repair.
- Last verified: 2026-10-21

The [package receipt](../../models/termination/0.11.0rc1/package.json) binds exact
source `a00cdb59714d431aeb226d9af7473a3a7327fc16`. The five termination modules
and external builder match independently reviewed
`6113b54a467af3f90a9a70b20a77c2247983a91c`. Source and numerical admission,
runtime repair review, and package integration are distinct checks. No earlier
source or validation receipt has been relabelled as this package.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 184,159 | `8946e857f67ccfdfb0090bd2d6e9f884a56d2b3dfa12d47f518483bda47bc88f` |
| Source distribution | 5,222,049 | `c55452c35788cde4e1463043bd904178b55e21e0d58058603af7ac086f3cdfc6` |

The execution-host artifact root is
`/Users/Rohin/.cache/regsite-wave7-integration-20261021/termination-0.11-installed`.
Preserve `dist/`, `receipt.json` and `installed-byte-check.json` when relocating
them. All 51 installed runtime files match source; the wheel contains no native
executable or background table. The source archive includes the builder, schemas
and examples. Compressed rebuild byte identity is not claimed.

## Reproduction and interpretation

Build/install the exact source using locked development tools and an external
virtual environment, following the
[offline package procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction).
The [termination runtime guide](intrinsic-termination-runtime.md) specifies the
separate pinned source ZIP, patch, compiler and background-table installation.
No source download, compiler installation or backend discovery is implicit.

```sh
/external/runtime/bin/regsite-termination /source/examples/termination-single.json --backend-manifest /external/termination/backend.json
/external/runtime/bin/regsite-termination /source/examples/termination-batch.json --backend-manifest /external/termination/backend.json
/external/runtime/bin/regsite-termination /source/examples/termination-unsupported.json --backend-manifest /external/termination/backend.json
```

The last example intentionally exits 1 and preserves unsupported records with
null candidates. A successful empty search has an empty list instead. Boundary
score ambiguity retains candidate geometry but nulls both structured confidence
fields. Native confidence is a fixed random-background motif score, not
termination efficiency, readthrough or a biological probability. The
[source guide](intrinsic-termination-source.md) explains the historical
archive/banner version discrepancy and separate GPL-2.0-only component boundary.

The adapter requires POSIX and a single-threaded calling process; use separate
worker processes for concurrency. Maximum input size does not guarantee success
within candidate/output/time limits. The job runner retains its five existing
command kinds; termination has its own explicit CLI/backend manifest.

## Verified boundary

At the exact source, 6,714 local tests passed with zero skips and nine warnings;
all 17,335 measured statements and 6,470 branches were covered. Ruff, formatting
and mypy passed. Original RNAstructure, the separately admitted conditional
original backend, and a fresh source-built TransTermHP installation were enabled.

The fresh installed package passed 24 checks: existing coupling and five-kind
job cases, termination single/batch/unsupported, repeated stdin execution,
absent backend and duplicate-key rejection. Prediction identity is stable across
native timing differences; the separate full-result hash binds each raw capture.
The artificial table-boundary control reproduces hairpin `[70,86)`, forward
strand, costs `-11.8` and `-3.87583`, and confidence 78. These are original software
controls, not experimental observations.

Independent source/runtime reviews are reused. Separate package integration review
accepted the unchanged package after workflow-only repair `950b833`: the backend
variable now uses a supported step-level context, and installed smoke assertions
pin the exact score, geometry, empty roster and unsupported reasons. The same
reviewer reproduced positive and mutation controls with no remaining finding.
The unchanged termination component subsequently passed all four native-platform
jobs in the [0.12 integration matrix](drafting-0.12-candidate.md#verification-boundary)
at `efe90fcb`. This is a development candidate; no hosted equivalence, cyanobacterial calibration,
empirical benchmark admission, consumer release or publication is claimed.

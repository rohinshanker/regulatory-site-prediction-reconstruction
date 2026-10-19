# A_calculator-artifact-manifests__20261019 — Active

- Scope: Producer-side offline manifest creation and integrity checking for explicitly selected calculator artifacts; child of #6/#10.
- Status: active
- Opened: 2026-10-19
- Updated: 2026-10-19
- Current State: Implementation delivered from exact baseline `d3d0e76f3eadfc2e10b0526948bc704d3d3103dd` on `quality/calculator-artifact-manifests-20261019`; reviewed runtime ancestor remains `920215602a837b0fd2fed403512f3b3ed59bfda2`. Explicit create/verify library and CLI, schema, artificial-byte tests and [storage contract](../../validation/calculator-artifact-storage.md) are ready for Session A integration and finite independent review. No predictions, consumer or runtime changes.
- Verification: Python 3.14.7/macOS: `PYTHONPATH=src:. python -m pytest tests/test_calculator_artifacts.py --cov=tools.calculator_artifacts --cov-report=term-missing` passed 125 tests, 245/245 statements and 40/40 branches (100%). Existing shared `reconstruction-rbs-wave4-runtime/.venv/bin` tools used read-only; no installs. `ruff check src tests experiments tools`, `ruff format --check src tests experiments tools` (137 files), and `mypy src/regsite experiments tools` (40 source files) passed. Focused tests check the new Draft 2020-12 schema, strict inputs, exact limits, relocation, streamed bytes, mutation, links/special files and IO/CLI failures. Local changed-document links, ticket/index fields and `git diff --check` pass. Home ticket checker reports four pre-existing errors solely in untouched `O_claude-doctor-cleanup__20261016.md`; this repository is outside its automatic scope and was checked directly. Session A integrated the CI coverage target and reproduced the focused gates, fresh stdlib-only execution and large-file/relocation/corruption checks. DEM-596 found no false-complete defect; its low-severity collision finding is repaired, permission/output-mode/diagnostic limits are explicit, and exact repair review remains pending. The repair passes127 focused tests at100% of250 statements/40 branches. Remote CI remains pending; no folding/model suite requested locally for this independent tool.
- Cleanup: Keep large artifacts outside Git, leave original files untouched, distill reusable commands and boundaries into the validation guide, then remove this child ticket and index row after acceptance. Parent release/consumer tickets remain open.

## Scope and acceptance

Implement a standard-library CLI/library at `tools/calculator_artifacts.py`, its
tests, a versioned public manifest schema, and a reusable validation guide.
Record exact producer commit, explicit artifact roles, root-relative paths,
SHA-256 and byte counts. Hash only explicit regular files in bounded chunks;
never discover directories, follow links, retrieve URLs, invoke a scorer, parse
biological payloads or alter any source artifact. A deterministic verification
report must distinguish matching, missing, unreadable, changed and invalid
artifacts and return a failing exit status whenever verification is incomplete.
Do not call byte integrity scientific validation or producer/consumer admission.

The calculator repository owns code, parameter/source manifests, schemas,
benchmark tooling and small redistributable fixtures. Bulky generated outputs,
raw data, backend installations and non-redistributable references stay in
explicit external storage with permitted small manifests. The visualizer keeps
its own admission and UI boundaries. Moving files does not reduce the size of a
JSON document parsed by a browser.

## Boundaries

No runtime equation, source model, package version, dependency, private
outcome, scoring, genome sweep, consumer/browser or publication change. The only
CI change adds this module to the existing required coverage target. This is
not a response to or workaround for the held PV-R1 import-cap task; DEM-577/568
remain stopped and no previously rejected task may be routed to another provider.
Session B exclusively owns the public Promoter evaluation receipt checker under
#12, using its four public artifacts, with no overlap in file ownership.

Before any new credential, administrator, sudo, keychain or macOS-permission
requirement, disclose the exact action, resource and reason and await the owner.

# A_calculator-artifact-manifests__20261019 — Active

- Scope: Producer-side offline manifest creation and integrity checking for explicitly selected calculator artifacts; child of #6/#10.
- Status: active
- Opened: 2026-10-19
- Updated: 2026-10-19
- Current State: Session A owns integration. Implementation starts from reviewed paired candidate `920215602a837b0fd2fed403512f3b3ed59bfda2` in isolated branch `quality/calculator-artifact-manifests-20261019`. The owner resumed technical calculator work and requested keeping implementation and bulky data off the consumer repository.
- Verification: Required deterministic manifest, unchanged byte preservation, streaming hashes, strict path/input handling, complete focused coverage, schema/lint checks, and finite independent review of the exact patch. No new predictions are needed.
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

No runtime equation, source model, package version, dependency, CI, private
outcome, scoring, genome sweep, consumer/browser or publication change. This is
not a response to or workaround for the held PV-R1 import-cap task; DEM-577/568
remain stopped and no previously rejected task may be routed to another provider.
Session B exclusively owns the public Promoter evaluation receipt checker under
#12, using its four public artifacts, with no overlap in file ownership.

Before any new credential, administrator, sudo, keychain or macOS-permission
requirement, disclose the exact action, resource and reason and await the owner.

# Explicit offline artifact storage

- Purpose: Register complete opaque local files and independently check declared byte identities.
- Scope: Producer-side standard-library manifest tool; no scoring, consumer admission or publication.
- Last verified: 2026-10-19

Keep bulky request, result, benchmark, report and parameter files in a
caller-selected external storage directory. Select every file explicitly; the
tool neither discovers files nor copies, links, moves, deletes or decodes their
contents. It reads only the selected files and the manifest. It has no network,
source retrieval, subprocess, calculator, browser or third-party runtime dependency.
Use complete files: no reduced result projection is produced. Only small,
permitted manifests belong in Git; check paths and redistribution terms before
committing one. Artifact IDs and filenames can themselves disclose information.

This checks declared bytes, not scientific validity, origin authenticity,
licence, native accuracy or result-schema admission. The fixed producer repository
identity and supplied full producer commit are caller declarations. The tool
does not inspect Git, prove that a commit exists, or establish which code produced
a file. There are no signatures or cryptographic-authenticity guarantees. SHA-256
and byte counts bind only the bytes read. An attacker able to replace both the
manifest and files can replace those declarations together.

External storage does not reduce the size of a JSON document loaded by a browser,
fix browser node caps, or establish consumer readiness or release admission.
The [reconstruction contract](reconstruction-contract.md) and
[consumer boundary](cyano-integration.md) retain their separate gates.

## CLI and library

Run from a source checkout with Python 3.11 or newer on a POSIX system supporting
`dir_fd`, `O_DIRECTORY` and `O_NOFOLLOW` (macOS/Linux). Windows is unsupported.
Every ancestor directory needs read and search permission; search-only directories
are unsupported by this implementation. Output parents also need write permission.
The tool does not change permissions. These commands assume
the named external files already exist; they do not run predictions or create
artifact directories. Replace the example absolute paths and commit with your
explicit locations and declared producer revision:

```sh
python3 tools/calculator_artifacts.py create \
  --root /Users/you/calculator-storage/run-01 \
  --producer-commit d3d0e76f3eadfc2e10b0526948bc704d3d3103dd \
  --entry input request requests/full.json \
  --entry prediction result results/full.json \
  --entry settings parameter parameters.json \
  --entry evaluation benchmark benchmark.json \
  --entry summary report report.json \
  --output /Users/you/calculator-manifests/run-01.json

python3 tools/calculator_artifacts.py verify \
  --root /Users/you/calculator-storage/run-01 \
  --manifest /Users/you/calculator-manifests/run-01.json \
  --output /Users/you/calculator-manifests/run-01-check.json
```

`create` requires `--root`, `--producer-commit`, one or more repeated
`--entry ID ROLE RELATIVE_PATH`, and `--output`. `verify` requires `--root` and
`--manifest`; its `--output` is optional. Both print deterministic, sorted-key JSON
with a trailing newline to stdout. Verification returns entries sorted by ID even
if the stored roster is reordered. No root, machine path, timestamp or raw OS
error is included in emitted JSON. No implicit working-directory root is accepted.
After caller-managed storage relocation, pass the new root with the same manifest.

`tools.calculator_artifacts` exposes `create_manifest(root, producer_commit,
entries, output)`, `validate_manifest(value)` and
`verify_manifest(root, manifest_path, output=None)`. Creation entries are a list
of dictionaries with exactly `id`, `role`, `path`; the returned manifest adds
`sha256` and `bytes` to each. Functions return ordinary dictionaries and raise
`ArtifactError` for invalid declarations or file-check failures; setup/publication
IO errors may raise `OSError`. Verification retains file failures within its
returned report once the manifest has passed structural validation.

## Manifest format and limits

The public [schema](../../schemas/calculator-artifact-manifest-1.0.schema.json)
defines exactly `schema_version`, `producer_repository`, `producer_commit` and
`artifacts`. The version is `calculator-artifact-manifest-1.0`; the repository is
`https://github.com/rohinshanker/regulatory-site-prediction-reconstruction`.
Each artifact has exactly `id`, `role`, `path`, `sha256`, `bytes`.

| Field/resource | Rule |
| --- | --- |
| Producer commit | Exactly 40 lowercase hexadecimal characters; declared, unverified |
| SHA-256 | Exactly 64 lowercase hexadecimal characters |
| Byte count | Nonnegative integer; booleans, strings and float syntax are rejected |
| Roster | 1–256 entries; IDs and relative paths must each be unique |
| ID | 1–128 ASCII characters; starts alphanumeric, followed by alphanumeric, `.`, `_`, `-` |
| Role | Exactly `request`, `result`, `benchmark`, `report` or `parameter` |
| Artifact path | 1–1024 ASCII characters; `/`-separated components of 1–255 alphanumeric, `.`, `_`, `-` characters |
| Manifest input/output | At most 1,048,576 encoded UTF-8 bytes; input limit includes whitespace |
| Read chunk | At most 65,536 bytes per read, including manifests |
| Artifact size | No configured byte ceiling; streamed without payload decoding |

Artifact paths cannot be absolute, empty, repeated-separator, trailing-separator,
`.` or `..` components, backslash, URL, drive-prefixed or control-character paths.
Portable artifact names deliberately exclude spaces and non-ASCII characters.
OS path/file limits still apply. Root, manifest and output arguments must be
absolute local POSIX paths without empty, `.` or `..` components, colons,
backslashes or NULs. `/` is accepted as an explicitly supplied root only.

Manifest decoding rejects malformed UTF-8/JSON, a BOM, duplicate object keys at
any depth, nonfinite numbers, float syntax and unknown/missing keys. JSON Schema
describes decoded structure; runtime checks additionally enforce byte limits,
unique IDs/paths, JSON syntax and filesystem rules. Standard JSON Schema treats
`1.0` as an integer mathematically; this loader requires integer JSON syntax and
the library requires Python `int`, excluding `bool`. Do not substitute a schema
check alone for the tool's validator/loader. Structural limits bound metadata
memory; artifact memory usage is independent of total artifact size. The manifest
is small and decoded in memory; artifact payloads are never parsed as JSON.

## File safety, publication and mutation

Each root and parent component is opened relative to a directory descriptor with
symlink following disabled. Selected leaf files must be regular files both before
and after opening. FIFOs, sockets, directories and symlinks, including dangling
and intermediate links, are rejected. Duplicate selected file identities (device,
inode), including hardlink aliases, are rejected; a verified manifest cannot
refer to itself or its hardlink alias. Unselected files are never enumerated.

Outputs cannot coincide with selected input paths, including missing inputs, or
the verification manifest, or replace any of their parent directories with a file.
Path comparisons conservatively normalize Unicode to NFC and ignore case,
including on filesystems that distinguish those names. Existing destinations of
any kind are never overwritten. Only the generated manifest/report uses a private
mode-0600 temporary file beside the destination; after writing, flushing and
fsync, an exclusive atomic link publishes its complete bytes. The temporary name
is then removed. The published file retains mode 0600; sharing it requires a
separate, deliberate permission decision by its owner. No input artifact is
linked or changed. Publication requires a
filesystem supporting same-directory hardlinks; there is no unsafe fallback.
Failed writes do not publish truncated destination files. A process crash can
leave a private temporary file; cleanup failure can leave a temporary name beside
an already complete output. This is atomic publication, not a power-loss durability
or transactional snapshot guarantee. Avoid concurrent changes to storage.

Hashing records the initial inode/device, size, nanosecond modification/change
times, streamed byte count, final descriptor metadata and reopened path metadata.
Detected growth, truncation, rewrites, disappearance or replacement fail as
`changed`/`mutated_during_read`. Reads stop if bytes exceed the initial size, so
continual append cannot extend a single hash indefinitely. Manifest reads also
check size and metadata before decoding. Checks are observations, not locks:
changes after the final check, hostile directory/mount changes and mutations
invisible to filesystem metadata are not guaranteed detectable. A set of entries
is not hashed as one filesystem snapshot. Keep originals immutable independently
when a stronger storage guarantee is required.

## Verification outcomes and exit codes

A valid manifest produces `calculator-artifact-verification-1.0` with the same
declared producer metadata and **every entry**, retaining all original fields.
Each entry adds `status`, `observed` (hash/count or null) and `error` (stable code
or null). Ordinary byte/size mismatches retain observed bytes with `changed`;
mutation failures have no trustworthy observed hash. Permission and IO failures
do not become missing files or matching empty files.

| Entry status | Meaning |
| --- | --- |
| `matching` | Both observed hash and byte count equal the declaration |
| `missing` | Selected file or parent was not found |
| `unreadable` | Access or other IO failure prevented complete checking |
| `changed` | Hash/size differs, or mutation was detected while reading |
| `invalid` | Link, special file, non-directory parent, or selected identity alias |

A filesystem-level missing/unreadable/unsafe root yields that failure for every entry. The report
status is `complete` only when every entry matches; otherwise `incomplete`.
Malformed or structurally invalid manifests have no trusted roster and fail the
command as a whole. CLI declaration, manifest and output-publication failures
emit a deterministic `{"status":"invalid","error":"stable_code"}` envelope.
Argument-parser usage errors go to stderr. Callers must check process exit status,
including stdout/write failures, before accepting any command as complete.
IO codes are deliberately coarse: `not_found` can identify either a missing
input or an output parent, and `io_error` includes an existing output destination.
The tool never overwrites that destination or attempts a permission change.

| Exit | Meaning |
| --- | --- |
| 0 | Manifest created, or all verification entries match |
| 1 | Valid manifest checked with at least one incomplete/inconsistent entry |
| 2 | Invalid arguments/declarations/manifest, setup IO or publication failure |

## Development checks

Use the repository's existing locked development environment, without installing
new dependencies. This independent tool needs no folding backend or prediction
suite. From the checkout with that environment's Python/commands on PATH:

```sh
PYTHONPATH=src:. python -m pytest tests/test_calculator_artifacts.py \
  --cov=tools.calculator_artifacts --cov-report=term-missing
ruff check tools/calculator_artifacts.py tests/test_calculator_artifacts.py
ruff format --check tools/calculator_artifacts.py tests/test_calculator_artifacts.py
mypy tools/calculator_artifacts.py
git diff --check
```

Tests use artificial temporary bytes only, covering exact metadata limits,
schema structure, relocation/order, corruption, missing/unreadable/unsafe files,
streaming, detectable mutations, exclusive publication and CLI failures. Review
local Markdown links and ticket/index fields when editing this guide.

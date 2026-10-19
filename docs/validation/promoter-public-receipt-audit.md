# Public Promoter receipt consistency

- Purpose: Verify frozen public receipt bytes and their structured arithmetic.
- Scope: Consumed Wave 5 positive-TSS localization for candidate `2dff23cb5697507281f7ffa73fc617d56989b40c`.
- Last verified: 2026-10-19

Run from the repository with Python 3.11 or later on a POSIX platform supporting
`dir_fd`, `O_NOFOLLOW` and directory descriptors:

```sh
python -m benchmarks.promoter.native_public_receipt --root . \
  --manifest benchmarks/promoter/native-public-receipt-manifest.json
```

The explicit manifest is a trust input. Obtain it from the reviewed commit;
never rebuild its expected digests from the files being tested. The checker has
no manifest-generation mode. Its scope fields explicitly retain consumed-cohort,
positive-TSS-localization and public-consistency status. They do not infer claims
from prose. Success does not independently recompute biological outcomes or
approve release, host calibration, or the current paired package.

## Reading and trust boundaries

The only artifact reads are the supplied manifest and these four fixed relative
paths under `--root`:

| Artifact | Treatment |
| --- | --- |
| `docs/validation/promoter-wave5-results.md` | Immutable SHA-256 only; Markdown semantics are not validated. |
| `benchmarks/promoter/wave5-native-evaluation-freeze.json` | Frozen identity, metric and uncertainty settings, input references. |
| `benchmarks/promoter/wave5-collection-ack.json` | Candidate, collection settings, totals, public freeze binding. |
| `benchmarks/promoter/wave5-native-aggregates.json` | Public cross-file bindings, counts, statuses, endpoint summaries and intervals. |

Every component of these paths, including the root and manifest ancestors, must
be a real directory or regular file. Symlinks are refused without following
them. Inputs are capped at 2,000,000 bytes each; nonregular files, missing inputs,
I/O errors, malformed UTF-8/JSON, duplicate object keys, nonfinite numbers,
unsupported schema versions/keys, invalid count types and excessive nesting fail.
No network, predictor, fitting, folding, scorer import, filesystem search, or
private evidence access occurs. On macOS, use `/private/tmp` rather than the
`/tmp` symlink if explicitly supplying a temporary root or manifest.

The manifest pins the candidate and all four byte hashes, and explicitly defines
exact frozen metadata contracts for the freeze and acknowledgement. These
contracts include their settings, receipts, collection identities and policy
fields. The acknowledgement's freeze hash is checked against actual public bytes
rather than copied into its metadata contract. Unsupported manifest schemas and
extra allowlist paths fail. A substituted manifest changes the trust decision;
this tool is a consistency check, not an authenticity/signature service.

## Reconciled public evidence

Candidate identities agree across the three JSON files and the manifest. The
acknowledgement and aggregate bind the checked freeze bytes; the aggregate also
binds the checked acknowledgement bytes. All structurally published SHA-256
references are inventoried with their JSON locations and compared to the explicit
manifest inventory. Repeated input, score, tool, metric-settings and
uncertainty-settings references are reconciled. Settings digests use sorted-key,
compact UTF-8 JSON followed by one LF. No private metric document or bootstrap
sufficient statistics are reconstructed from these settings.

Batch/request/candidate status rosters and totals reconcile with acknowledgement
counts and collection coverage. Label counts retain all-label, in-window,
out-of-window, complete-query and successful-own-candidate denominators.
Recovery and exact-rank tie endpoint rosters, fractions, bounds and rank
sum/mean relationships are checked for the overall report and every subgroup.
Replicons partition labels, rank totals and both endpoint scopes. Source-category
memberships may overlap; they are checked separately and never summed as a
partition. Conditional-successful endpoints retain their own denominator and
cannot replace all-case results. Bootstrap summaries reconcile endpoint rosters,
point estimates, eligible/zero-denominator group counts, resample counts and
interval bounds with frozen settings; intervals are not recomputed.

The frozen public receipts report 92 batches, 366 requests, 364,416 candidates,
4,808 source-positive labels, 292 in-window labels and 4,516 out-of-window labels.
These are public consistency checks on existing evidence, not a new evaluation.

## Unchecked dependencies and output

`checked_bytes` contains only the four public file digests.
`referenced_only.status` is always `not_checked`, and its `artifacts` inventory
retains 12 freeze, 10 acknowledgement and 37 aggregate hash occurrences. This
includes candidate preparation/input manifests, query/label/group documents,
source/tool/protocol files, collector/executable identity, admission/candidate/CI/
installation/plan/transport receipts, wheel, collection, execution receipt,
journal, and native/control score, metric and uncertainty artifacts. Published
paths and filenames are opaque strings: they are never opened or resolved, even
when locally present. Matching repeated hashes verifies public reference
agreement, never those external artifact bytes. Unpublished raw per-case outputs
and group sufficient statistics remain outside this check.

The library `check(root, manifest_path)` returns a result or raises
`ReceiptError`. The CLI writes one deterministic, sorted-key compact JSON line
to stdout and writes no files. Exit 0 means `status: consistent`; exit 1 means a
JSON failure report; invalid CLI arguments use argparse diagnostics and exit 2.
The result includes candidate, scope, manifest byte digest, checked-byte digests
and the unchecked inventory. There are no timestamps or machine-local paths in
the report. Redirect stdout only to a separately chosen evidence location.

Synthetic regression fixtures construct their own reports and trust inputs.
Semantic-negative mutations update synthetic byte pins and public digest chains
so they reach numerical/schema validation. A separate exact-public-pin test
checks the immutable shipped inputs and asserts the five-read boundary. The
focused gate requires branch coverage and Ruff on the two checker/test files;
no runtime benchmark or biological experiment is needed for this checker.

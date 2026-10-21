# Public Wave 4 RBS receipt consistency

- Purpose: Verify public byte identities, repeated references and feasible aggregate accounting.
- Scope: Consumed one-study Wave 4 receipts for candidate `a11cb5bd13d3c021eedc98cf451609eb4710bb6a`; no new scientific evaluation or release approval.
- Last verified: 2026-10-21

Run with Python 3.11 or later on POSIX with `dir_fd`, directory descriptors and
`O_NOFOLLOW` support:

```sh
python -m benchmarks.rbs.wave4_public_receipt --root . \
  --manifest benchmarks/rbs/wave4-public-receipt-manifest.json
```

Obtain the explicit manifest from the reviewed commit. It is a trust input, not
a signature or authenticity proof. There is no shipped regeneration mode.
Changing that manifest changes the trust decision. Exact frozen metadata and
reference inventories are explicit; dynamic metrics are validated by rules,
not copied into the manifest as expected answers.

## File and parsing boundary

Only the supplied manifest and these five fixed relative artifact paths are read:

| Path | Checked evidence |
| --- | --- |
| `docs/validation/rbs-wave4-results.md` | SHA-256 only; opaque Markdown, without semantic interpretation. |
| `benchmarks/rbs/wave4-protocol.json` | Frozen settings, denominator contract and identity references. |
| `benchmarks/rbs/results/wave4-freeze.json` | Candidate, exact configuration metadata, roster and scheduled accounting. |
| `benchmarks/rbs/results/wave4-aggregate.json` | Cross-file identities, counts, runtime, comparison states and advancement. |
| `benchmarks/rbs/results/wave4-review.json` | Public artifact bindings and consistency of reported review totals. |

Every file, including the manifest, is bounded to 2,000,000 bytes. Each path
component is opened with descriptors and without following symlinks; files must
be regular. Missing files, parent traversal, nonregular files and I/O failures
fail closed. On macOS, temporary test roots use `/private/tmp`, since `/tmp` is
a symlink. JSON requires strict UTF-8, unique keys and finite numbers; malformed
numbers, unpaired Unicode surrogates, trees deeper than 64 or larger than 100,000
value nodes fail. Count fields require nonnegative bounded integers, excluding
Booleans and floats. Unsupported schemas, rosters and metric keys fail.

Embedded paths, commands, working directories, binary names, URLs and source
references remain opaque. They are never resolved, executed or read, even when
locally present. The checker imports no scorer, evaluator or metric module and
uses no subprocess, network, source retrieval, case-level data or bootstrap run.

## Identity and accounting rules

The candidate agrees across the manifest, freeze, frozen software gates and
review. The public protocol hash agrees with the freeze and aggregate. Published
input, envelope, split, outcome, receipt and code references agree where repeated;
this verifies string agreement, not external bytes. The review binds the actual
public report and aggregate bytes. Its third document hash remains unchecked.

The original evaluator encoding is recovered by removing only
`publication_context`, preserving parsed insertion order, and using
`json.dumps(indent=2, ensure_ascii=False, allow_nan=False)` plus one LF. Its
SHA-256 agrees with the publication metadata and review. No historical private
aggregate is opened. A sorted-key encoding would produce a different identity.

The exact roster has 11 configurations, including nine external configurations
and two controls. Per configuration, 335 primary and three 87-input secondary
contexts give 596 requests: 6,556 scheduled, 5,364 external and 1,192 control jobs.
Primary observations and blocks remain 332 and 56; secondary observations total
253. Status entries are positive counts from the published vocabulary; totals,
OK successes, failure reasons, coverage and measured-success bounds reconcile.
Null correlations stay distinct from zero, with finite values bounded to [-1,1].

For population N, observed population O, successes Sl/Sr, measured successes
Pl/Pr, shared successes S and shared measured successes M, let Ul=Sl-Pl and
Ur=Sr-Pr. In addition to ordinary intersection bounds, the checker requires:

```text
max(0, Pl+Pr-O, S-min(Ul,Ur)) <= M
M <= min(Pl, Pr, S-max(0,Ul+Ur-(N-O)))
lost_reference_successes = Sl-S
```

These are feasibility bounds, not inferred case identities. Correlation
subtraction is checked only when both summaries cover every observed input.
Equal marginal counts alone do not establish the same cohort. GC and secondary
point comparisons keep their own scopes; no pooled secondary endpoint is added.
GC strata partition primary counts, statuses, failure counts and runtime sums;
correlations, medians and quantiles are not additive.

Runtime execution count equals inputs minus `not_run`; unsuccessful executions
still contribute time. Zero executions require sum zero and null quantiles.
Positive execution times are finite and nonnegative, with ordered median/p95/max
and feasible sum bounds; one/two-execution cases retain their estimator rules.
A complete collection cannot contain unexecuted requests.

## Comparison states and advancement

Shared blocks cannot exceed either total blocks or shared measured rows; zero
shared blocks and zero shared measured rows imply each other. Frozen support
requires 30 measured rows and 10 blocks. Requested draws stay 10,000, separately
from attempted, usable and undefined draws. Insufficient support and undefined
points have null gain/interval and zero attempted draws. A finite supported
point attempts every requested draw; fewer than 9,900 usable draws gives a null
interval. Otherwise the finite ordered interval lies in [-2,2]. A percentile
interval need not contain the point estimate. Small GC groups retain counts
and null contrasts; secondary/GC point summaries never gain an interval.

The advancement conjunction retains its ordered reasons: collection/integrity,
software readiness, coverage at least 0.95, no lost reference successes, gain at
least 0.05, and an interval lower endpoint strictly above zero. Thresholds remain
fixed. Review job/draw totals and advancement reconcile with public output.
Reported numerical-match counts and maximum numerical difference are type/range
checked but are not independently reverified; existing DEM-516 review remains
distinct from this software consistency check.

## Output and regression checks

`check(root, manifest_path)` returns a JSON-compatible result or raises
`ReceiptError`. The CLI writes exactly one sorted-key compact JSON line: exit 0
for `consistent`, exit 1 for a structured failure, or argparse exit 2 for invalid
arguments. It writes no files and reports no timestamps or local input paths.
The result carries candidate, explicit consumed-stage scope, manifest hash, five
`checked_bytes` hashes and `recovered_original_digest`.

`referenced_only.status` is `not_checked`. Its inventory contains 4 protocol,
53 freeze, 8 aggregate and 4 review digest occurrences, including nested binary
hash maps and the learned artifact digest stored positionally in an opaque
command. Public byte bindings are excluded from that unchecked inventory.
Recovered original identity does not imply a read of historical private bytes.
Success grants no current-model, biological-accuracy, calibration or publication
approval and makes no claim about Markdown semantics.

Tests separately assert immutable actual public pins and the exact five-artifact
read boundary. Synthetic metrics are independently constructed; semantic
mutations refresh synthetic pins, recovered encoding, review bindings and trust
inventories before exercising their intended invariants. Focused verification
requires full line/branch coverage and Ruff check/format on the checker and test
files. No runtime backend or full scientific suite is needed.

```sh
PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=/chosen/scratch/.coverage \
  python -m pytest tests/benchmarks/test_wave4_public_receipt.py \
  --cov=benchmarks.rbs.wave4_public_receipt --cov-branch \
  --cov-report=term-missing --cov-fail-under=100
python -m ruff check benchmarks/rbs/wave4_public_receipt.py \
  tests/benchmarks/test_wave4_public_receipt.py
python -m ruff format --check benchmarks/rbs/wave4_public_receipt.py \
  tests/benchmarks/test_wave4_public_receipt.py
```

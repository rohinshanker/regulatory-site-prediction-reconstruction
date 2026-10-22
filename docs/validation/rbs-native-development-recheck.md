# Native RBS development recheck

- Purpose: Describe coverage and rank association for four fixed configurations on existing public PCC 6803 development-validation inputs.
- Scope: Consumed-study exploratory analysis; no fitting, promotion, final outcomes or new experimental planning.
- Last verified: 2026-10-22
- State: Local tooling and artificial verification implemented; finite C/A review and final execution freeze remain pending. No native prediction has run for this task.

The [protocol](../../benchmarks/rbs/native-development-recheck-protocol.json)
fixes the cohort, candidate, configurations, packing, resources and endpoints
before implementation or collection. A owns candidate preparation, execution and
integration. B owns requests, independent admission/evaluation and this guide;
the existing C root provides finite independent review. The candidate identity
review admits preparation only, not this protocol or collection.

## Public inputs and scientific limits

Only `karlsen2018-development.json` and `native-splits.json` are data inputs.
Their protocol hashes are mandatory trust pins, not regenerated expectations.
Selection retains all 479 `development_validation` records in 423 frozen
homology groups, sorted by original ID. Every record has a 200-base context,
start 100, PCC 6803 host metadata, 30 C and anti-SD `ACCUCCUUU`. No label or
prediction affects selection, ordering, deduplication, trimming or packing.
The selected ordered-ID SHA256 is
`e0e879ba551b8aabb9b8a9a3d1f3231f69c778a9963af52dc2b6d6fa0fd23dec`
under sorted-key compact finite JSON without a trailing newline.

The [data card](rbs-native-data-card.md) supplies source rights, measurement
normalization, current-annotation and transcript-context limitations. HC TE is a
stored relative ribosome-footprint/RNA proxy, not an isolated initiation rate or
protein-output measurement. Reuse the stored values without fitted scale,
outlier removal, pseudocounts or library renormalization. The released training
records are not evaluation rows. Private final/LC/plasmid outcomes and source
workbooks are not inputs and must not be opened. This consumed development study
cannot establish UTEX accuracy, general host transfer or recoding effects.

## Fixed execution boundary

The reviewed original 0.12.0rc1 package at source
`356abc2d40198a95f807967a38126a14b0f3d0c9` supplies four configurations:
historical/original RNAstructure 6.6, historical/linker-3, context2017/linker-3
and standby2014/linker-3. The complete model/backend objects are bound through
A's pinned preparation receipt and final freeze, never inferred from a name.

Prepare standard RBS JSON arrays with unchanged sequence and ID, explicit
`start_positions: [100]`, local `strand: "+"`, host, anti-SD and temperature.
Do not include labels, groups or outcome-ordered source-row metadata in requests.
Use 29 batches of 16 and one of 15 per configuration: 120 jobs and 1,916 planned
record predictions. Original and repaired backends have separate campaigns.
The repaired campaign visits batches in ID order, cycling the fixed three
profiles within each batch; rotate their order by batch index modulo three.
This outcome-independent schedule avoids always placing one profile last.

Reuse the [five-kind installed job runner](offline-calculator-jobs.md), with
60 seconds per record, 1,100 seconds per job, campaign limits of 3,600 and
10,800 seconds, at most two global folding processes, 64 MiB stdout and 1 MiB
stderr per job, and 1 GiB captured streams per campaign. The runner reserves
both per-job stream caps before admission; its budget stop is retained even if
prior jobs emitted less. Filesystem/identity checks have cooperative deadlines,
not a hard wall-time guarantee. No resume, retry, replacement run or repacking
is permitted after outcomes. Raw requests/results/receipts remain external.

Execution feasibility is supported by the public CLI/runner contracts and the
reviewed empty-scan identity controls, not by a timing prediction. Actual
coverage under these finite budgets is an endpoint; no test run on native inputs
is needed to decide the protocol. Existing package/interface identities remain
unchanged. The code branch baseline is intentionally newer than the installed
candidate and does not substitute a new runtime.

## Admission, missingness and metrics

Before a public-label join, bind protocol/plan/candidate pins, exact selected
roster, both campaign manifests, installed runtime/backend identities, and
verified attempt receipts and raw bytes. Require zero or one attempt per job.
Reject identity, roster or schema substitutions. Ordinary genuine native
failures remain records; they are not grounds for removing a case.

The installed runner's read-only `verify` checks campaign layout, request copies,
receipt consistency and stream hashes without executing a prediction. The
proposed separation has A run and pin those two verification summaries, while B
binds them and verifies every consumed receipt/output byte before semantics.
This avoids importing scorer modules through the runner library in B tooling.
The artifact interface below implements this proposed separation for finite A/C
review. Final acceptance and execution acknowledgement remain required; the
interface does not weaken the installed runner verification requirement.

A complete valid exit-1 JSON batch may retain successful rows beside explicit
native failures. Timed-out, truncated, refused, abnormal, interrupted or unstarted
jobs contribute explicit missing predictions for every assigned record; no
successful-looking prefix is salvaged. Preserve original bytes and reason codes.
An `ok` score must satisfy its native schema (finite, strictly positive TIR);
missing/failed values remain null, never zero. A native `invalid_input` record
with null input/prediction identity and no sites remains unsuccessful: its
assigned request is still bound by the runner request-copy hash. All other
records require exact normalized input/settings and a prediction identity.

Report each configuration's all-479 coverage, status/failure counts and
successful-measured Spearman correlation with denominators. Use the tested
average-tie [rank helpers](../../benchmarks/rbs/wave4_metrics.py). Three paired
contrasts compare repaired versus original historical, context versus repaired
historical, and standby versus repaired historical. Each uses exactly its common
successful measured rows, with lost-reference successes and group counts shown.
Do not subtract correlations from different successful subsets.

Resample all 423 input groups with replacement for 2,000 draws using seed
20261022; preserve repeated member rows and filter successes after sampling.
Rerank each draw. Use the existing paired helper's floor/ceil 95% percentile
convention. At least two usable rows and two represented groups are required;
an interval additionally requires 1,800 defined draws. Otherwise show explicit
nulls and undefined/support counts. These are descriptive within-study group
intervals, not biological-replicate uncertainty or a superiority test. No fitted
calibration, log/fold error, promotion threshold or additional model is admitted.

The CLI supplies no per-record elapsed value. Runtime diagnostics therefore
retain each job's attempted/terminal/unstarted state and actual elapsed time,
including failures; do not divide batch time into invented per-record timings.

## Review and execution gates

Implement and test request construction, strict artifact/result admission,
full-roster failure accounting and deterministic metric sanity with artificial
inputs only. Cover every new path and retain unchanged public input hashes.
Return the immutable code/protocol to existing C/A for one finite review.
Final collection requires their accepted tooling and a separate acknowledged
execution freeze. The provisional preparation receipt is not authorization.
No worker dispatch, scoring import, predictor call, new source, private outcome,
consumer change or publication belongs to B's tooling step.


## Offline preparation and evaluation interface

Run the benchmark module from the reviewed producer tree using the existing
locked development environment (`jsonschema`/`referencing` are already present;
no runtime package dependency is added). It imports no `regsite` or scorer
module, spawns no process and makes no network call. Committed schemas use only
local references; an empty reference registry prevents external resolution.

```sh
python -m benchmarks.rbs.native_development_recheck prepare \
  --candidate "$CANDIDATE_RECEIPT" --output "$NEW_PREPARED_DIRECTORY"
python -m benchmarks.rbs.native_development_recheck evaluate \
  --candidate "$CANDIDATE_RECEIPT" --plan "$PREPARED_PLAN" \
  --freeze "$EXECUTION_FREEZE" --freeze-sha256 "$FREEZE_SHA256" \
  --acquisition "$ACQUISITION_RECEIPT" --acquisition-sha256 "$ACQUISITION_SHA256" \
  --output "$NEW_EVALUATION_DIRECTORY"
```

`prepare` writes outcome-free requests, two runner manifests, the protocol and
`plan.json` last. The plan binds full model/backend objects, input/packing
identities and hashes of this tool, reused helpers and committed schemas.
A must review/acknowledge those exact bytes before execution. The
`execution_authorized: false` field in the protocol means the protocol itself
grants no execution permission; a separate pre-execution acknowledgement is
required. Never substitute the current installed package for frozen 0.12.

A supplies two external trust documents. The evaluator requires their independently
communicated SHA256 values, not hashes silently computed to admit arbitrary files:

- `native-rbs-development-freeze-1`: `execution_authorized: true`,
  `protocol_sha256`, `candidate_receipt_sha256`, `plan_sha256`, and the complete
  `runtime` object from the reviewed installed runner. Runtime version,
  executable hash and 54-file code fingerprint must match the pinned candidate.
  Additional review/resource/pre-post identity receipts may be retained as opaque
  fields; this checker does not resolve their paths.
- `native-rbs-development-acquisition-1`: `freeze_sha256` and exactly two
  `campaigns`, `original` and `linker3`. Each contains an absolute `root` and a
  `files` map from explicit relative paths to exactly `{bytes, sha256}`. This
  is A's post-run attestation binding installed-runner verification to preserved
  bytes, not cryptographic proof of who generated them.

Each acquisition root is an external **evidence directory**, with the original
runner output beneath `campaign/`. Its siblings `run-summary.json` and
`verification.json` contain the complete returned run and read-only verify JSON.
Do not put these siblings inside the runner campaign or alter its layout.
The file map contains exactly the consumed files:

- `campaign/campaign.json`, `campaign/manifest.json`, both sibling summaries;
- `campaign/jobs/<fixed-job-id>/request.json` for every planned job;
- for each one-attempt job with a receipt,
  `campaign/jobs/<fixed-job-id>/attempt-0001/{receipt.json,stdout,stderr}`;
- an existing `launch.json` may be included and is hashed as opaque runner-verified
  evidence; a receipt-less abandoned attempt may include either/both captured
  streams and that launch file. Absent partial streams remain absent.

The evaluator follows only these derived paths; unconsumed map entries reject.
It rejects symlinks, traversal, duplicate/nonfinite/malformed JSON, unsupported
schemas, substitutions, retries, inconsistent counts, incompatible result
identities and mismatched raw bytes. All planned request copies are checked,
including unstarted jobs. Valid abandoned/unfinished attempts retain all assigned
cases as missing; complete transport failures never contribute score prefixes.
The runner's original run stop reason is retained separately from verify status.
Run and verify roster/state/accounting must agree. If the runner cannot verify a
corrupted campaign, no scientific report is produced; preserve the evidence and
return the concrete admission failure, without rerunning jobs.

All native-result schemas and input/coordinate/identity checks precede extraction
of successful TIR. Both campaigns must pass before measurement fields are joined.
The report preserves job state/attempt/elapsed/exit diagnostics, raw artifact
hashes and fixed aggregate endpoints. It contains no per-record measurements or
predicted scores. Positive/negative values are not scientific approval: rank
association and coverage remain separate descriptive endpoints.

Outputs use deterministic sorted-key, two-space, ASCII-escaped finite JSON with
one trailing LF. New output directories are exclusive, outside repositories,
mode 0700; atomically published files are mode 0600. Existing files/directories
are never overwritten. A preparation write failure preserves its incomplete
new directory; `plan.json` is published last. A failed evaluation admits no report.
Successful CLI operations return 0 with a small summary; validation/I/O failures
return 2 with a diagnostic. No resume or retry is provided. The local filesystem
must remain owner-controlled: checks do not lock all ancestors against a
concurrent path replacement. Keep original external artifacts immutable.

## Focused verification

The focused test uses artificial requests, schema-valid synthetic native records
and runner receipts, plus a separate exact-public-input pin check. It verifies
packing/no label leakage, all four profiles, strict identity/coordinate/null
semantics, ordinary failures/abandonment, every-case denominators, deterministic
ranks and group intervals, consistently rehashed semantic mutations, output
collision/failure behavior and no scorer imports. Synthetic fixtures test
contracts; they do not establish producer fidelity or biological accuracy.

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_cov \
  --confcutdir=tests/benchmarks \
  tests/benchmarks/test_native_development_recheck.py \
  tests/benchmarks/test_wave4_metrics.py tests/benchmarks/test_metrics.py \
  --cov=benchmarks.rbs.native_development_recheck --cov-branch \
  --cov-report=term-missing --cov-fail-under=100
python -m ruff check benchmarks/rbs/native_development_recheck.py \
  tests/benchmarks/test_native_development_recheck.py
python -m mypy --follow-imports=silent --ignore-missing-imports \
  benchmarks/rbs/native_development_recheck.py
```

These checks reuse the existing independently reviewed rank helpers. They do not
repeat a native collection or the full runtime suite. A/C review of the immutable
patch and A's execution acknowledgement remain separate gates.

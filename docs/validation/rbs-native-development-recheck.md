# Native RBS development recheck

- Purpose: Describe coverage and rank association for four fixed configurations on existing public PCC 6803 development-validation inputs.
- Scope: Consumed-study exploratory analysis; no fitting, promotion, final outcomes or new experimental planning.
- Last verified: 2026-11-01
- State: Frozen acquisition admitted and evaluated once with unchanged reviewed tooling. Public aggregates/report await finite independent review; this is consumed-study exploratory evidence.

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

## Frozen 0.12 results

All 120 runner jobs completed and verified, returning all 1,916 requested
record/configuration outcomes. Successful prediction coverage differs by profile:
the two historical configurations each return 449 scores and 30 explicit
`no_candidate` outcomes; context and standby each return 479 scores. The reason
for all historical missing scores is `no_interstrand_candidate_in_bounded_search`.
Runner success therefore does not imply successful scoring of every record.

| Fixed configuration | Successful / all inputs | Coverage | Successful measured groups / all groups | Spearman rho | Descriptive 95% group interval |
| --- | ---: | ---: | ---: | ---: | --- |
| historical / original | 449 / 479 | 93.74% | 400 / 423 | 0.188643 | [0.102247, 0.276528] |
| historical / linker-3 | 449 / 479 | 93.74% | 400 / 423 | 0.188643 | [0.102247, 0.276528] |
| context2017 / linker-3 | 479 / 479 | 100% | 423 / 423 | 0.127502 | [0.037675, 0.217512] |
| standby2014 / linker-3 | 479 / 479 | 100% | 423 / 423 | 0.111376 | [0.020518, 0.206013] |

These per-profile correlations use different successful subsets. The frozen
paired comparisons below instead use the same 449 successful measured records
and 400 represented groups for both sides of each comparison. All 423 input
groups, including groups without successful predictions, remain in the bootstrap
sampling universe. Each contrast retains all 479 inputs for coverage accounting;
none loses a reference success.

| Contender minus reference | Common successful measured records | Change in Spearman rho | Descriptive 95% paired group interval |
| --- | ---: | ---: | --- |
| historical/linker-3 minus historical/original | 449 | 0.000000 | [0.000000, 0.000000] |
| context2017/linker-3 minus historical/linker-3 | 449 | -0.066713 | [-0.137833, 0.005412] |
| standby2014/linker-3 minus historical/linker-3 | 449 | -0.086302 | [-0.161770, -0.010781] |

All seven interval calculations retained 2,000 usable draws and zero undefined
draws under the fixed seed and percentile convention. The two historical
backends give identical coverage and ranking endpoints on this cohort; that is
not an energy-level equivalence or current-hosted-equivalence test. Context and
standby recover the 30 historical no-candidate records. Neither shows a ranking
gain on the common successful subset. Standby's paired interval lies below zero
in this consumed study; context's interval includes zero. These are descriptive
findings, not a model-promotion decision or confirmatory superiority test.

The observed associations are weak. They concern the stored HC relative
footprint/RNA proxy at assumed annotation starts and genomic flanks. They do not
measure isolated initiation, completed protein output, site discovery, native
transcript boundaries, UTEX performance or effects of original-versus-recoded
sequences. Absolute-rate calibration, fold-error endpoints, experimental-replicate
uncertainty and untouched-cohort confirmation are unavailable in this protocol.
No fitting, normalization change, new exclusion or threshold was introduced.

The sum of job-reported elapsed seconds was 419.003 for historical/original,
401.762 for historical/linker-3, 597.609 for context2017 and 1,773.623 for standby.
Each profile attempted all 30 jobs. These are batch-job diagnostics including
execution overhead, not per-record timings or a controlled speed comparison.
All jobs are retained, including batches containing explicit no-candidate rows.

The [compact public summary](../../benchmarks/rbs/native-development-recheck-summary.json)
copies complete-precision configuration and contrast aggregates from the original
external report. No per-record measurements, predictions or raw native streams
are included. The evaluated package is **0.12.0rc1**, source
`356abc2d40198a95f807967a38126a14b0f3d0c9`; newer engineering packages do not inherit
this result. Acquisition SHA256 is
`9778a53ee4483a6fed3805349eaeeace6cabc9f0eafeceb8460599b76ed953c1`.
The unchanged evaluator admitted all 608 mapped acquisition files before the
public-label join and exited 0 after one invocation. It ran no predictor.

The authoritative report is 158,784 bytes, SHA256
`10822eddc7736d2d58114c58fef85c249a19d25fc7f4ccfaad97155a2d4f980a`,
at external `regsite-wave10-20261031/b-evaluation-01/report.json`.
The execution receipt in sibling `b-evaluation-execution-01/receipt.json` binds
the pre-execution command, 18 before/after input pins, exit, stdout, timing log
and report; SHA256
`a4dd46ec586bee5dd3c5602ad282d6bfcf91924053271acd672d8585ae4d8827`.
Reported metric values and interpretation remain pending the finite independent
aggregate/report review; prior tooling acceptance is not that review.

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
The artifact interface below implements the accepted separation. B's independent
freeze acknowledgement precedes A's one-attempt acquisition; the interface does
not weaken the installed runner verification requirement.

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

The exact repair `d8c9a43b0157234e3cca18404cbb13f6ade0fc3a` has no remaining
finding in the bounded A/C recheck. A checked all 120 planned argv lists against
the frozen formatter; C checked failure accounting, prediction identity and
window geometry using eight focused tests and 20 independent artificial controls.
The existing 51-test coverage receipt is reused, not represented as a new
independent full-suite run. Review evidence remains external under
`regsite-wave10-20261031/c-recheck/`; its receipt SHA256 is
`30d89a7370897d1641ec2431603a5040aab8324ce43f363678d11b34dc8e89ef`.
This acceptance is about admission tooling, not biological accuracy or permission
to collect. Preserve the original code/protocol/plan pins in the execution freeze.

The separate execution freeze is SHA256
`7b8b435310949f86870993e4e754ef5952d0d487cfa7b762e67f3182f2b41e56`;
B's acknowledgement is SHA256
`3d55a599a4eefb055965968eabc3787ca72dfcb4b7f007f9a5b60612c7ae4c12`.
Both remain external under `regsite-wave10-20261031/`. They authorize only A's
exact original-0.12 one-attempt commands and preserve every frozen limit. An
acknowledgement is not a completed run or an admitted acquisition; B still
requires independently communicated acquisition pins before scientific analysis.


## Frozen producer wire and result semantics

Receipt argv is derived from each frozen manifest job's options, not a formatted
copy of a higher-level budget. Match the installed runner's sorted option names,
underscore-to-hyphen flag spelling, unchanged strings and `repr` for numeric
values. In particular, a manifest float `60.0` requires wire argument `"60.0"`;
an integer `60` requires `"60"`. These spellings are not interchangeable identities.

A singleton site outcome has a null enclosing record reason. Its site status
must equal the record status; successful sites have a null site reason, while
failed/unsupported/no-candidate sites carry the failure reason used in aggregate
accounting. Genuine record-level failed or invalid-input cases have empty sites
and a nonempty record reason. Do not reject ordinary completed site failures or
replace their reason with a fabricated record-level reason. Complete exit-1
batches retain successful rows; completed unsupported/no-candidate batches have
exit 0 and still contribute unsuccessful records.

For every non-invalid record, independently recompute `prediction_id` from the
validated full input, model and backend plus the floating-point declared budget:

```python
payload = {"input": record["input"], "model": record["model"],
           "backend": record["backend"], "budget_seconds": float(declared_budget)}
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("utf-8")
expected_prediction_id = hashlib.sha256(encoded).hexdigest()
```

There is no trailing LF in this hash encoding. Null identity is accepted only
for legitimate invalid-input records with null input and no sites. An unrelated,
stale or wrong-budget hash fails even if receipt/output hashes were refreshed.

Every retained site's complete `window` must match the frozen model's
`upstream_nt`/`downstream_nt` parameters: start `max(0, start-upstream_nt)`, end
`min(sequence_length, start+downstream_nt)`, with the identical `+` input interval.
For these fixed inputs, historical is `[65,135)` and context2017/standby2014 are
`[0,200)`. These checks apply to unsuccessful sites too; reversed, out-of-bounds,
wrong-strand and wrong-profile windows fail admission without folding or
re-evaluating energies.

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
semantics, literal integer/float wire identities, source-shaped singleton failure
reasons, full prediction hashes, profile windows, ordinary failures/abandonment,
every-case denominators, deterministic
ranks and group intervals, consistently rehashed semantic mutations, output
collision/failure behavior and no scorer imports. Synthetic fixtures test
contracts; they do not establish producer fidelity or biological accuracy.
Complete synthetic campaigns refresh every affected stream, receipt and summary
pin before semantic-negative checks. Mixed exit-1/exit-0 unsuccessful campaigns
verify failure accounting; a bad result in the second campaign prevents the
public-label join and report publication.

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

# Native RBS development recheck

- Purpose: Describe coverage and rank association for four fixed configurations on existing public PCC 6803 development-validation inputs.
- Scope: Consumed-study exploratory analysis; no fitting, promotion, final outcomes or new experimental planning.
- Last verified: 2026-10-22
- State: Initial protocol/feasibility proposal; tooling, independent review and execution freeze remain pending. No native prediction has run for this task.

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
A must confirm this separation before its dependent implementation; it does not
weaken the requirement for the existing runner's complete verification.

A complete valid exit-1 JSON batch may retain successful rows beside explicit
native failures. Timed-out, truncated, refused, abnormal, interrupted or unstarted
jobs contribute explicit missing predictions for every assigned record; no
successful-looking prefix is salvaged. Preserve original bytes and reason codes.
An `ok` score must be finite; missing/failed values remain null, never zero.

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

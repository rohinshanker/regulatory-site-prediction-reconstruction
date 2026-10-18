# RBS transcript-context paired metrics

- Purpose: Summarize measured-TSS versus genomic-flank input sensitivity of unchanged RBS profiles.
- Scope: Session B, Wave 5 output 3; aggregate tooling only, no collection or scoring.
- Last verified: 2026-10-18

This implements the paired summary declared in
[promoter-wave5-evaluation](promoter-wave5-evaluation.md#3-unchanged-rbs-transcript-context-sensitivity).
[`benchmarks/rbs/context_metrics.py`](../../benchmarks/rbs/context_metrics.py)
reads one hash-pinned `native-rbs-evidence-1` panel from
[`context_panel`](../../benchmarks/rbs/context_panel.py) and one hash-pinned
`rbs-context-collection-1` document. It imports no runtime scoring code, runs no
prediction and writes aggregates only. Results are descriptive input sensitivity,
never translation accuracy or improvement.

## Collection interface

```json
{
  "schema_version": "rbs-context-collection-1",
  "panel_sha256": "<64-hex SHA-256 of the exact panel file>",
  "candidate_commit": "<40-hex frozen candidate commit>",
  "settings": {
    "mode": "supplied_start",
    "execution": {
      "implementation_version": "<package version>",
      "backend": {"<complete backend identity object>": "..."},
      "seconds_per_record": 60,
      "seconds_per_batch": 3600
    }
  },
  "runs": {
    "historical": {
      "expected_model_id": "<historical model ID>",
      "status": "completed",
      "reason": null,
      "output": {
        "schema_version": "native-rbs-result-1",
        "batch_id": "<64-hex>",
        "mode": "supplied_start",
        "model_id": "<historical model ID>",
        "execution": {"<identical to settings.execution>": "..."},
        "coordinate_space": "zero-based half-open reference segments in transcript order",
        "task_scope": "supplied start strength",
        "results": ["<one unchanged native row per panel scenario>"]
      }
    },
    "context2017": {
      "expected_model_id": "<context2017 model ID>",
      "status": "not_run",
      "reason": "<nonempty reason, e.g. folding slot unavailable>",
      "output": null
    }
  }
}
```

Every object has exactly these keys. `runs` holds exactly the panel's declared
profiles. `completed` requires a null reason and the complete, unedited native
output. `failed` and `not_run` require null output and a nonempty reason; their
requested scenarios remain in every denominator as `not_collected`. Budgets are
positive non-boolean numbers within the native limits of 120 s per record and
3,600 s per batch.

The candidate commit and settings are caller assertions recorded in the report.
The tool verifies hashes and per-result consistency, not that a clean checkout
actually executed. The CLI requires the expected commit and both model IDs
separately, so a collection cannot redefine them.

## Verification

Panel: the file hash, genome sequence hashes and unique IDs; panel schema, source
and tool hash format; settings equal to the builder's declared settings and their
hash. Every scenario has `source_record_id`, a `current`/`historical` anchor and a
`measured_tss`/`genomic_flank` context, an ID of `source:anchor:context`, a panel
genome, aSD `ACCUCCUUU`, 37°C and 100/100-nt limits. Each selected source has
exactly four scenarios. Selected loci are in stratum/key order, recompute their
selection keys, list sorted unique record IDs matching the scenarios' locus/genome,
and cover all scenarios exactly. Stratum selections equal `min(per_stratum,
available)`; all derived counts reconcile. At most 4,096 scenarios are accepted.

Completed outputs: exact top-level keys, schema, `supplied_start` mode, expected
model ID, execution exactly equal to the frozen settings, coordinate space, task
scope and batch hash format. Every panel scenario appears exactly once with
evidence equal to its panel record. Every prepared context has an RNA sequence
matching its hash, an in-range start and the panel genome identity.

Each profile has a declared result schema, following [rbs-runtime](rbs-runtime.md):
`historical` emits 1.0 and `context2017` emits 1.1 (adding `dG_post_footprint`).
Every successful prediction must use its profile's schema. The report keeps the
expected schema separate from the observed one, which is null when a run has no
success. The expected term roster applies to all-failed and uncollected profiles.

A successful row needs a prepared context and a prediction whose `id`, `status`,
`model.id`, `model.implementation_version` and `backend` agree with the run's
model ID and `execution`. Its public core request (`input`) must restate the
prepared context and scenario. `oriented_sequence` (T read as U) equals the
context sequence, with `oriented_sha256` its hash. `strand` is `+`, and
`start_positions` is exactly `[context.start]`. `temperature_c` and `anti_sd`
equal the panel scenario. Field names follow the public `native_predictions`
check in [`prediction_io`](../../benchmarks/rbs/prediction_io.py). The row has
exactly one core and one genomic site, both `ok` at the context start. It needs a
finite `log_tir` and the schema's complete energy set in kcal/mol, with finite
required terms and finite-or-null `dG_mRNA_native_prediction` and
`dG_cofold_native_prediction`.

A non-ok row may not carry an `ok` prediction. A non-null core request on it gets
the same check, and needs a prepared context. Absent predictions or requests are
not invented. Status, reason and context presence are retained, never converted
to a missing row or zero. This tool does not re-extract genomic contexts; B's
independent input-expectation checks cover that before collection.

Accepted numbers have magnitude at most 1e9. JSON is strict UTF-8 with duplicate
keys and non-finite numbers rejected. Inputs are bounded: 64 MiB per panel and
256 MiB per collection. The report is written exclusively with mode 0600.

## Metrics

Pairs exist only within one profile, anchor and `source_record_id`, with both
scenarios `ok`. For `log_tir` and each required energy term, change is measured
minus flank. Each summary reports `n`, `min`, `q25`, `median`, `q75`, `max` and
`changed` (absolute change greater than 1e-12). Quantiles use ascending linear
interpolation at `(n-1)*p`, with no outlier removal. Audit fields use only pairs
with both values finite and report `missing_pairs`. Empty sets give `n: 0`,
`changed: 0` and null statistics.

Ranks place higher `log_tir` first, with exact-tie midranks within the fixed
eligible pair set of each profile/anchor. Rank change is measured rank minus
flank rank, so a negative value ranks the measured context higher.

Each profile/anchor/context reports status and prepared-context counts, plus
counts by status and `reason_sha256`. That hash covers the exact UTF-8 reason, and
is null when no reason is given. Whole-profile run reasons appear only as
`run_reason_sha256`. Raw reasons can name cases, sequences or values, so they stay
in the private collection. The tool neither redacts nor classifies their prose.
Any public interpretation of error categories needs a separately reviewed claim
from the private raw evidence. Pair accounting lists eligible and ineligible pairs, status
combinations and pairs with identical prepared contexts. Prepared contexts are
grouped by RNA hash, start, aSD, temperature, model ID and execution identity,
never by filename. The report omits per-case IDs, scores and residuals. Source
associations and repeated loci are not independent samples. The tool runs no
significance test or bootstrap, and it does not compare profiles on one scale.

## Reproduction

```sh
python -m benchmarks.rbs.context_metrics PANEL.json COLLECTION.json REPORT.json \
  --panel-sha256 PANEL_SHA256 --collection-sha256 COLLECTION_SHA256 \
  --candidate-commit CANDIDATE_COMMIT \
  --historical-model-id HISTORICAL_MODEL_ID \
  --context2017-model-id CONTEXT2017_MODEL_ID
python -m coverage run --branch --source=benchmarks.rbs.context_metrics \
  -m pytest tests/benchmarks/test_context_metrics.py
python -m coverage report -m
```

Run from the repository root with `PYTHONPATH=src:.`. Exit 1 means a rejected
input or an existing output; the previous report is never overwritten.
[rbs-native-runtime](rbs-native-runtime.md) states that extracted-context hashes
are over RNA. One feasibility check remains before final collection: that each
core prediction's `backend` equals the output's `execution.backend`. Confirm it
with A's interface/example receipt or a synthetic candidate smoke run; this tool
runs no folding.

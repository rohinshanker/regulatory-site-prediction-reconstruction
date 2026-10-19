# Frozen Promoter collection

- Purpose: Execute a reviewed immutable request plan once, retaining exact private evidence.
- Scope: Independent selected-state native evaluation; no labels, fitting or model selection.
- Last verified: 2026-10-18

## Prerequisites and identities

Follow the [scientific protocol](promoter-wave5-evaluation.md) and
[adapter contract](promoter-runtime-adapter.md). The collector does not decide
whether a candidate is scientifically admitted. The operator first verifies the
immutable candidate/wheel, installed package files, source-parity result, complete
resource/CI receipt, frozen inputs/settings and recorded protocol acknowledgement.
The admission JSON is an opaque, nonempty, hash-pinned object; the explicit CLI
acknowledgement records that prior review, not an inferred approval.

Use Python ≥3.11 on POSIX. The standard-library collector sets a file-size limit
only in its child process; no administrator access or shared setting change is
needed. The reviewed public Promoter CLI launches no child processes. Its installed
entrypoint hash does not by itself prove package identity; bind the wheel and
installed-file verification separately. Clear `PYTHONPATH` and `PYTHONHOME` for
collection and its inherited child environment, disable user site packages, and
verify that the executable's interpreter resolves `regsite` inside the verified
installation. A development `PYTHONPATH=src:.` can otherwise shadow the admitted
wheel. Run the collector from this repository root; its imports need no runtime
source path.

Plans must use the adapter's canonical JSON encoding. A pretty archival copy can
be retained, but execution uses the already-frozen canonical document identity.
Do not change requests, batch membership, calibration, host metadata or settings
when serializing this copy. The collector validates every request, byte hash,
record order, packing limit and public identity before any process starts.

For candidate `2dff23cb5697507281f7ffa73fc617d56989b40c`, input admission additionally
requires strict UTF-8, no CR bytes and raw input at most 4,000,000 bytes, passed as
an explicit file path. The frozen CLI uses text-mode input handling and cannot be
claimed to enforce the raw-byte cap on arbitrary CRLF or inherited-encoding stdin.
The 92 frozen native requests satisfy the narrowed conditions; no stdin is used.
This limitation does not change any input hash or model equation.

## One-attempt execution

```sh
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 \
  /absolute/path/to/verified-venv/bin/python -m benchmarks.promoter.collect \
  PLAN.canonical.json /absolute/path/to/regsite-promoter ADMISSION.json PRIVATE_NEW_DIR \
  --plan-sha256 PLAN_SHA --executable-sha256 EXECUTABLE_SHA \
  --admission-sha256 ADMISSION_SHA --acknowledge-reviewed-admission \
  --stage-seconds 3600.0 --process-grace-seconds 30.0
```

Record and batch deadlines come literally from the frozen manifest; CLI calibration
and state defaults are added only when non-null there. Each batch is launched once,
in declared order, with its exact request bytes and no shell. Process timeout is
the smaller of the remaining stage time and batch deadline plus the explicit grace
allowance for serialization/exit. Recheck the absolute stage deadline after the
last prelaunch persistence operation; an expired budget cancels the launch.
There is no retry, resume, adaptive repacking or settings adjustment. All unstarted
batches remain in the declared roster.

A new output directory is required (mode 0700); files use exclusive creation and
mode 0600. Keep raw stdout/stderr, requests and execution receipts outside Git.
Do not print raw outcomes, failure text or per-case identifiers into shared reports.
The collector supports at most 64 MiB per diagnostic stream, with stricter runtime
wire and authoritative JSON caps checked by the adapter before acceptance.

Exit 0 or 1 from the runtime produces completed raw evidence. The complete public
result and exit/status agreement must then validate. Exit 2 is a setup failure;
other exits are execution failures, with null result identities in the adapter
collection. Timeout and launch errors use documented synthetic nonzero codes.
Malformed or mismatched completed output is an explicit collector validation
failure, not an invented missing score. It stops further execution and prevents
successful downstream adaptation. Failed raw diagnostics remain private.

A collector exit of zero means its ledger was saved; it does not mean every
prediction succeeded. Inspect the execution receipt and use the adapter's complete
roster checks. Filesystem failures remain explicit and must not trigger a rerun of
the final cohort. Raw failure messages and per-case outcomes stay with B.

## Durable attempt evidence

Before launching a process, the collector saves the complete plan and identity
roster in `execution-journal.jsonl` (`promoter-execution-journal-2`). Version 1 is
rejected rather than reinterpreted or resumed. Each canonical JSONL event is flushed and
fsynced. The ordered events record initialization, the exact argv and timeout
ceiling before launch, the observed process return and actual timeout, completed
output validation, and final receipt hashes. The actual timeout is computed after
prelaunch persistence, so a slow sync cannot grant extra process time. A cancelled
launch is recorded explicitly without an invented exit. Output streams are
flushed and fsynced before their final hashes are recorded. Directory synchronization
preserves newly created entries. The journal is bounded to 1 GiB. Any persistence
failure stops collection; it never triggers a retry.

The read-only `benchmarks.promoter.collect.recover(output_directory)` API retains
all planned batches. An unmatched launch intent is `interrupted_unknown`, with null
actual exit and actual timeout; a recorded return without completed validation remains distinct
from validated output. Never-started batches remain `not_run`. Timeout and launch
failure codes are explicitly synthetic, separate from actual observed exits.
Recovery does not launch processes or invent a replacement collection.

A final unterminated JSONL fragment is flagged as truncated; preceding complete
events are retained. A malformed complete event or invalid event order rejects
recovery. Unfinished journals, missing or mismatched final artifacts, truncation,
or collector validation failures block normal adaptation. Even a finalized valid
journal does not replace the adapter's validation of the complete raw results.

## Evaluation and review

The adapter consumes the exact collection and completed stdout bytes, rebuilds
the frozen plan, and verifies every identity, coordinate, state and status before
emitting private scores. Apply the separate frozen metric and uncertainty settings;
all-case endpoints give incomplete requests no recovery credit. Successful-position
diagnostics and the constant-score control remain separate outputs.

An independent reviewer checks the collected artifacts, arithmetic and proposed
public claims. Publish only reviewed aggregates and reproducible artifact hashes.
No positive-TSS result establishes specificity, translation strength, native-host
calibration or equivalence to the hosted calculator.

```sh
PYTHONPATH=src:. python -m coverage run --branch \
  --source=benchmarks.promoter.collect \
  -m pytest -q tests/benchmarks/test_promoter_collect.py
python -m coverage report --fail-under=100
```

Tests use artificial plans/results and tiny fake executables. They do not execute
the scientific runtime or read native labels/outcomes.

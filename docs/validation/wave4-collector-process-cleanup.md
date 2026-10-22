# Wave4 collector process cleanup

- Purpose: Preserve process ownership, failure phase and raw evidence in prospective collections.
- Scope: Offline engineering checks with artificial commands; no historical collection rerun or scoring change.
- Last verified: 2026-10-22

The [collector](../../benchmarks/rbs/wave4_collect.py) previously caught launch,
communication and cleanup `OSError` exceptions in one handler. Consequently
`process_start` did not establish that launch failed. Artificial injected read
errors and first/final group-signal denials reproduce that false label, loss of
an already observed exit and, in the first-stop case, loss of partial output.
CI run 39720882453 reported this label in a descendant timeout test but retained
no original exception/errno. The specific CI fault therefore remains unknown;
neither timeout flakiness nor a particular permission error is established.

## Ownership and capture

Each external command gets a dedicated stdlib anchor process in its own POSIX
process group. The command joins that group. The anchor is neither polled nor
waited while group signaling remains possible: its unreaped PID prevents reuse
of the numeric group ID. This follows the existing offline job runner's ownership
pattern without importing a runtime or scorer. `stop_process` rejects an already
reaped anchor before any signal. It sends at most one group kill during the
attempt; no signal is sent after releasing the anchor.

Both output pipes and request input use concurrent nonblocking I/O. Captured
prefixes stay available if an OS error interrupts communication. Teardown drains
remaining pipe bytes where possible, retains the command's actual observed exit,
then closes pipes and reaps the anchor. A successful parent cannot release the
group while its silent descendants remain. A descendant keeping an inherited
output pipe open still reaches the original deadline; a parent exit code of zero
does not turn that timeout into success.

The command, request bytes, cwd, explicit environment, scientific parameters and
worker-slot count are unchanged. One additional lightweight anchor process is
used per active command. The execution deadline includes setup. Cleanup permits
one second each for draining, command wait and anchor wait; these are bounded
OS operations after the execution deadline, not new prediction attempts.
File writes and OS scheduling are not hard real-time guarantees. This collector
still retains complete raw output in memory and has no newly introduced output
cap. It is intended for admitted commands; detached sessions or external reapers
are outside its process ownership contract.

## Receipts and failure classification

Every external attempt adds a `process` diagnostic object:

- `started`, `pid`, `pgid` distinguish command launch from anchor setup.
- `primary_event` preserves completion, timeout or I/O/start failure before
  cleanup; `timeout_reason` distinguishes record and collection deadlines.
- `errors` retains each phase, exception type and errno. Exception text and
  inherited environment values are not recorded.
- `stdout_complete` and `stderr_complete` require observed EOF; retained prefixes
  are not described as complete streams.
- `cleanup_complete` is false on any teardown error or exhausted cleanup wait.

`process_start` now means the command did not start; the diagnostic phase
distinguishes capture setup, anchor startup and command startup. Post-start pipe
errors produce `process_io`. Teardown failures produce `process_cleanup`, with
null predicted value even when valid output and exit zero were observed. The
primary event, actual exit, all captured bytes and SHA-256 values remain visible.
A signal denial is recorded as failure, not suppressed or retried through another
mechanism. There is no privilege probe or fallback.

Cleanup uncertainty halts scheduling. Already active jobs finish their owned
teardown, while the remaining full roster is stored as `not_run` with reason
`collection_cleanup_failure`. The collection has `complete: false` and
`cleanup_complete: false`. No failed attempt is retried. Controls and unstarted
records have `process: null`.

The historical evaluator still accepts ordinary successful/failed/timeout
records and rejects the new I/O/cleanup classifications rather than silently
crediting them. No evaluator admission is added here. Any future collection needs
a new explicit collector hash and admission; old frozen receipts, model/input
bytes and published conclusions remain unchanged. The original collector is
available by its historical commit, not silently replaced in old evidence.

## Focused verification

Run with the existing project Python 3.11+ environment, without a native backend:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_cov \
  --confcutdir=tests/benchmarks \
  tests/benchmarks/test_wave4_collect.py tests/benchmarks/test_wave4_evaluate.py \
  --cov=benchmarks.rbs.wave4_collect --cov-branch \
  --cov-report=term-missing --cov-fail-under=100
python -m ruff check benchmarks/rbs/wave4_collect.py tests/benchmarks/test_wave4_collect.py
python -m ruff format --check benchmarks/rbs/wave4_collect.py tests/benchmarks/test_wave4_collect.py
python -m mypy --follow-imports=silent benchmarks/rbs/wave4_collect.py
```

Tests preserve the original real-child timeout and descendant-marker assertions.
Additional artificial cases exercise large bidirectional streams, startup
resource exhaustion, nonblocking readiness races, early stdin closure, retained
prefixes after read failure, cleanup denials, wait/close failures, stale ownership
refusal and complete failed/unstarted accounting. Faults that simulate signal
denial first terminate the actual test group, so the injected error does not leak
test descendants. No fixture requires a prediction, fold or empirical outcome.

Local checks do not certify the GitHub macOS 14 runner. Independent exact-patch
review and the platform rerun belong to A; preserve their explicit pending status
until receipts exist. This engineering repair gives no new biological evidence.

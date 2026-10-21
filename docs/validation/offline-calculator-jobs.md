# Offline calculator jobs

- Purpose: Run explicit caller-authored requests through the fixed installed calculators with bounded resources, atomic external receipts and verified resume.
- Scope: Standard-library job runner `regsite-jobs`; no new model, scoring change, request generation, consumer admission or publication.
- Last verified: 2026-10-21

`regsite-jobs` executes each manifest job as one invocation of an existing
calculator entry point and stores the request bytes and complete native outputs
as opaque artifacts. It does not generate sequences, discover genes, split or
merge requests, parse native results, widen native caps or change scoring. A
native result keeps its own JSON, statuses and exit code. Stored artifacts and
receipts bind bytes and declared identities; they do not validate predictions,
prove origin or authenticate anything. Anyone able to rewrite the output
directory can rewrite receipts and artifacts together.

## Commands and exit codes

```sh
regsite-jobs run    --manifest /abs/manifest.json --output-dir /abs/new-dir [--backend-root /abs/rnastructure]
regsite-jobs resume --manifest /abs/manifest.json --output-dir /abs/existing-dir [--backend-root /abs/rnastructure]
regsite-jobs verify --manifest /abs/manifest.json --output-dir /abs/existing-dir
```

`run` creates a new output directory; it refuses an existing path. `resume`
continues a campaign created by `run` with the same manifest bytes, runtime and
backend. `verify` is read-only: it checks the manifest, layout, request copies,
receipts and artifact bytes, but not the current runtime or backend. `run` and
`resume` refuse an output directory inside a Git working tree (an ancestor with
a `.git` entry) unless `--allow-repository-output` is given. Keep outputs out of
browser-served directories; the runner cannot detect them.

Every command prints one sorted-key JSON document with a trailing newline. A
summary (`calculator-job-summary-1`) is printed when a trusted campaign roster
exists; otherwise an envelope `{"schema_version": "calculator-job-summary-1",
"status": "invalid", "error": "<stable code>"}`. Argument-parser usage errors
go to stderr with exit 2. If stdout cannot be written, a fixed line goes to
stderr and the exit is 2; `summary.json` and receipts remain authoritative.

| Exit | Meaning |
| --- | --- |
| 0 | Every job has a verified terminal receipt with outcome `succeeded` |
| 1 | Every job is terminal; at least one terminal outcome is not `succeeded` |
| 2 | Invalid arguments/manifest/inputs, identity mismatch, lock held, corrupted campaign, orphan risk, setup or stdout failure |
| 3 | Stopped with unfinished, unstarted or attempt-exhausted jobs, or the summary could not be stored; `stop_reason` says why |

## Manifest `calculator-job-manifest-1`

[Schema](../../schemas/calculator-job-manifest-1.schema.json). Exactly
`schema_version`, `limits` and `jobs`. Each job has exactly `id`, `kind`,
`request` (`path`, `sha256`), `backend` and `options`. Request paths are
relative to the manifest's directory. An [example](../../examples/jobs-synthetic/manifest.json)
runs the bundled artificial Promoter and supplied-energy conditional requests.

| Field/resource | Rule |
| --- | --- |
| Manifest | ≤1,048,576 bytes; strict UTF-8 JSON, no BOM, duplicate keys, NaN/Infinity or overflowing numbers |
| Jobs | 1–256; IDs 1–64 ASCII characters `[A-Za-z0-9][A-Za-z0-9._-]*`, unique after Unicode NFC casefolding |
| Kind | `rbs`, `promoter`, `compare`, `transcript` or `conditional` |
| Request path | Registrar path syntax: `/`-separated `[A-Za-z0-9._-]` components, no `.`/`..`, ≤1024 characters |
| Request bytes | ≤4,000,000 bytes; SHA-256 must equal the lowercase declaration |
| `seconds_per_job` | Finite number, 0 < x ≤ 3,600 |
| `seconds_total` | Finite number, 0 < x ≤ 86,400; wall time for one `run`/`resume` invocation, including setup |
| `stdout_bytes_per_job` | Integer 1–134,217,728 |
| `stderr_bytes_per_job` | Integer 1–1,048,576 |
| `output_bytes_total` | Integer up to 17,179,869,184 and ≥ the two per-job caps; stdout+stderr bytes over all attempts |

Booleans are not numbers and byte limits require integer syntax. Options are
whitelisted per kind and become explicit flags; omitted options keep the native
default. Every kind except `conditional` also receives `--format json`.

| Kind | Fixed entry point | `backend` | Options |
| --- | --- | --- | --- |
| `rbs` | `python -m regsite` | must be `true` | `profile` (native RBS profile name), `seconds_per_record` |
| `promoter` | `regsite.promoter_cli.main` via a fixed `-c` call (the module has no main guard) | must be `false` | `calibration` (`ecoli_mg1655`, `in_vitro`), `states` (`selected`, `all`), `seconds_per_record`, `seconds_per_batch` |
| `compare` | `python -m regsite.paired_cli` | optional | none |
| `transcript` | `python -m regsite.transcript_cli` | optional | none |
| `conditional` | `python -m regsite.conditional_cli` | optional | none |

Option seconds must be finite positive numbers; native range rules still apply
and a native refusal is a terminal `refused` outcome. `--backend-root` is
required (absolute) when any job has `backend: true` and refused otherwise. It comes only
from the command line, never from the manifest, and is passed to the jobs that
request it. There is no environment fallback: the child never sees
`REGSITE_RNASTRUCTURE`.

## Execution policy

Jobs run sequentially in manifest order: at most one calculator process and its
folding engine at a time. Each calculator runs as `sys.executable -P -s` plus its
fixed entry point, `-` (request on stdin from the stored request copy) and its
flags; no shell or manifest-supplied command text. It joins a new process group
led by a runner-owned anchor (`sys.executable -I -S -c "import os; os.read(0, 1)"`),
which blocks on a pipe held by the runner and exits on EOF if the runner dies.
The runner reaps the anchor only after its final group kill, so the group ID
stays owned (alive or unreaped) whenever the runner signals it, on every
supported platform and without non-reaping exit probes. The calculator has
working directory `/` and only this environment:
`PATH=/bin:/usr/bin`, `PYTHONPATH` set to the directory containing the running
`regsite` package, `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`,
`PYTHONUTF8=1`, `OMP_NUM_THREADS=1` and `TMPDIR` equal to the runner's temporary
directory. Receipts record argv with `{python}` and `{backend_root}` placeholders.

Before each job the runner requires campaign time and enough unused output
budget for both full per-job caps; otherwise it stops with `campaign_deadline`
or `output_budget` and the job stays unstarted. The job deadline is the earlier
of `seconds_per_job` and the campaign deadline. Output is streamed into the
attempt's `stdout`/`stderr` files; bytes beyond a cap are discarded. On a
deadline, output cap or signal the runner sends SIGTERM to the process group,
waits 2 seconds, then sends SIGKILL. When the calculator exits, the runner sends
SIGKILL to the group, so no folding child is left behind; existing backend
processes inherit the calculator's group. A descendant that creates its own
session or group is outside this guarantee. On macOS a group holding only the
unreaped anchor answers `EPERM`; the runner treats that as no live member.

SIGINT, SIGTERM and SIGHUP set a flag checked every 50 ms; the running job is
stopped and recorded as `interrupted`, no further job starts, and the summary
reports `stop_reason: "signal"` with exit 3. The library must run in the main
thread. A runner killed by SIGKILL or power loss cannot clean up: its child loses
its stdout pipe and native deadlines bound it. `resume` refuses with
`orphan_process` while the recorded process group of an unreceipted attempt
still exists (a reused group ID also refuses; that errs on the safe side).

After each job the runtime and backend identities are recomputed. A change makes
that attempt `runtime_changed` and stops the campaign.

## Output directory and identity

```text
<output-dir>/
  lock                       exclusive flock while run/resume executes
  manifest.json              exact manifest bytes
  campaign.json              calculator-job-campaign-1, written last at creation
  summary.json               latest summary, atomically replaced
  jobs/<id>/request.json     exact verified request bytes
  jobs/<id>/attempt-0001/    stdout, stderr, launch.json, receipt.json
```

The output parent must exist; the directory is created with mode 0700 and files
with mode 0600. Every path component is opened without following symlinks
(on macOS pass `/private/tmp`, not `/tmp`). The output directory cannot equal or
contain the manifest or a request path (NFC casefold comparison). Unknown
entries make the layout invalid; `.tmp-*` names are ignored leftovers of
interrupted publication. Nothing outside the output directory is written and
existing receipts, artifacts and copies are never overwritten. Only
`summary.json` is replaced.

[`campaign.json`](../../schemas/calculator-job-campaign-1.schema.json) binds the
manifest SHA-256/bytes, the runtime and the backend. Runtime identity is the
`regsite` version, a SHA-256 over every regular file in the installed package
directory except `__pycache__` (relative path plus content hash; any other file
type refuses), and Python implementation, `sys.version`, cache tag, platform,
machine and the resolved interpreter executable's SHA-256 (not the standard
library tree). Backend identity reuses unchanged verifiers:
`RnaStructure.open(...).identity` for `rbs`/`compare`/`transcript` jobs with a
backend, and the conditional exact-original `verify_backend` identity for
conditional jobs with a backend. Their admission rules are unchanged, so a
patched RNAstructure root cannot satisfy a conditional backend job. Paths are
not part of identity; the bytes are.

A [receipt](../../schemas/calculator-job-receipt-1.schema.json) is published only
after both output files are complete and fsynced, by exclusive hard-link of a
fsynced temporary file. A [launch record](../../schemas/calculator-job-launch-1.schema.json)
stores the calculator `pid` and the anchor-owned `pgid`. Publication is atomic,
not a power-loss guarantee.

| Outcome | Terminal | Meaning |
| --- | --- | --- |
| `succeeded` | yes | Calculator command exited 0 within all limits |
| `partial` | yes | Exit 1: native record failure, partial or unavailable result |
| `refused` | yes | Exit 2: native input/setup refusal or usage error |
| `abnormal_exit` | yes | Any other exit status or a signal the runner did not send |
| `timed_out` | yes | `seconds_per_job` expired; stopped by the runner |
| `output_limit` | yes | stdout or stderr exceeded its cap; first cap bytes kept, `truncated: true` |
| `interrupted` | no | Runner received a signal |
| `campaign_deadline` | no | Campaign time ran out before the job deadline |
| `launch_failed` | no | The interpreter could not be started |
| `storage_error` | no | An output write failed; the child was stopped |
| `runtime_changed` | no | Code, interpreter or backend identity changed during the job |

`succeeded` states only that the command exited 0. It does not check that stdout
is valid JSON, that native result statuses are `ok`, or anything scientific;
outputs stay opaque. Native stdout is never replaced: a timed-out or stopped job
keeps exactly the bytes it emitted, possibly none. Exit 0 alone never makes a
receipt valid: verification also needs the bound bytes and identities.

## Resume and verification

Resume and verify load the supplied manifest and require its bytes to equal
`manifest.json` and the bound SHA-256. They check the layout, re-hash every
request copy and every receipt's stdout/stderr, and check each receipt's
campaign hash, job, kind, attempt, request identity, argv, outcome/exit
consistency and truncation flag. Attempts must be numbered contiguously from 1,
at most 8 per job (receipted or not); only the last attempt may be terminal.
A job is then:

| Job state | Meaning |
| --- | --- |
| terminal outcome | Last attempt has a verified terminal receipt |
| `attempts_exhausted` | 8 attempts exist and none is terminal; never started again |
| `unfinished` | Fewer than 8 attempts exist and none is terminal (receipted non-terminal or unreceipted/abandoned) |
| `unstarted` | No attempt |
| `corrupted` | Missing/changed request copy or artifact, invalid receipt/launch record, gap, more than 8 attempts or misplaced terminal attempt |

Verify reports corrupted jobs with exit 2. Resume refuses (exit 2) any corrupted
job, unknown layout entry, changed original request, manifest/runtime/backend
mismatch, held lock or live orphan group. It then re-runs only unfinished and
unstarted jobs, each with a new attempt number; earlier attempts are kept and
count toward `output_bytes_total`. Attempt-exhausted jobs are skipped while
later jobs still run; the invocation then reports `stop_reason:
"attempt_limit"` (exit 3) unless another stop occurred first. The attempt cap
bounds receipts, launch records and verification work even when output bytes
stay small. Verified terminal jobs, including `partial`,
`refused` and resource outcomes, are never re-run; to change limits, run a new
campaign in a new directory. `seconds_total` restarts for each invocation.

`stop_reason` is null or one of `signal`, `campaign_deadline`, `output_budget`,
`launch_failed`, `storage_error`, `runtime_changed` and `attempt_limit`; verify
always reports null. The summary lists counts for every state, total and
abandoned attempts, used output bytes and, per job, its state, attempt count, receipt path, exit code,
stdout reference/hash/bytes and corruption code. It does not embed native
results. Its paths and job IDs fit the [artifact registrar](calculator-artifact-storage.md)
syntax, so `tools/calculator_artifacts.py create --root <output-dir>` can register
selected files from a source checkout. The installed runner does not need it,
and registration checks bytes, not predictions.

## Disk and process bounds

Disk use is at most the manifest, the request copies (≤256 × 4,000,000 bytes),
`output_bytes_total`, and at most 8 small receipt/launch pairs per job plus the
summary. Each running job adds one idle anchor interpreter process. A killed calculator can leave
`regsite-*` scratch directories in `TMPDIR`. Windows is unsupported (POSIX
`dir_fd`, `O_NOFOLLOW`, `flock` and process groups are required).

## Development checks

From the checkout with the locked development tools:

```sh
PYTHONPATH=src python -m pytest tests/test_jobs.py --cov=regsite.jobs \
  --cov-report=term-missing
ruff check src/regsite/jobs.py tests/test_jobs.py
ruff format --check src/regsite/jobs.py tests/test_jobs.py
mypy src/regsite/jobs.py
git diff --check
```

The tests use synthetic child processes for launch, timeout, output-cap,
signal, orphan, storage and corruption cases, plus real Promoter and
supplied-energy conditional jobs, which need no folding backend. Real RBS,
paired and transcript jobs need the separately installed backend.

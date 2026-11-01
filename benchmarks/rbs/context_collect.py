"""One-attempt, POSIX context collection; imports no scientific runtime.

``make_plan`` binds local files and caller-reviewed receipts; freeze its canonical
bytes before ``collect``. Candidate receipts expose candidate_commit,
mode, execution and complete_models (profile -> complete prediction.model).
Other receipt fields are retained unchanged. Backend artifacts expose binaries
(Fold/bifold/efn2), build_receipt, table_manifest and tables as path/sha256 specs.
Root verifies installation, CI, process-group inheritance and admission;
this tool checks bytes, never infers those facts from receipt strings.

Recovery is read-only. Only ready=True permits metrics. A durable intent without
an observation means interrupted_unknown, even when no child actually started.
Use from the main thread: collection temporarily handles SIGINT/SIGTERM and uses
child-only RLIMIT_FSIZE. No retry, resume, scoring or model selection API exists.
"""

import contextlib
import hashlib
import math
import os
import resource
import signal
import stat
import subprocess
import time
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    canonical_bytes,
    checked_hash,
    document_sha256,
    strict_json,
)
from benchmarks.rbs import context_metrics as metrics
from benchmarks.rbs.datasets import digest

PROFILES = ("historical", "context2017")
MAX_STREAM = 64 * 1024 * 1024
MAX_COLLECTION = 256 * 1024 * 1024
MAX_PANEL = 40_000_000
MAX_RECEIPT = 8 * 1024 * 1024
MAX_JOURNAL = 32 * 1024 * 1024
THREAD_ENV = dict.fromkeys(
    (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ),
    "1",
)
VALIDATION_ERRORS = (
    ValueError,
    UnicodeError,
    RecursionError,
    KeyError,
    TypeError,
    IndexError,
    OverflowError,
)


def _seconds(value, maximum):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 < value <= maximum
    ):
        raise ValueError("Budget must be finite, positive and within its cap")
    return float(value)


def _read(path, limit):
    """Reject links/devices/FIFOs; bound reads even if the file grows."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("Expected a regular file")
    with os.fdopen(descriptor, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("File exceeds byte cap")
    return raw


def _hash_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("Expected a regular artifact")
    with os.fdopen(descriptor, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _pin(path, expected, limit):
    raw = _read(path, limit)
    if digest(raw) != checked_hash(expected):
        raise ValueError("Pinned file changed")
    return raw


def _spec(spec):
    metrics._exact_keys(spec, ("path", "sha256"), "artifact")
    path = Path(spec["path"])
    if not path.is_absolute() or _hash_file(path) != checked_hash(spec["sha256"]):
        raise ValueError("Artifact path or SHA-256 mismatch")


def _settings(candidate):
    return dict(mode=candidate["mode"], execution=candidate["execution"])


def _candidate(value):
    if not isinstance(value, dict) or not metrics.COMMIT.fullmatch(
        value.get("candidate_commit", "")
    ):
        raise ValueError("Candidate requires a full commit")
    settings = metrics._settings(_settings(value))
    models = value["complete_models"]
    metrics._exact_keys(models, PROFILES, "complete models")
    for model in models.values():
        metrics._exact_keys(
            model,
            ("id", "source_commit", "parameters", "implementation_version"),
            "complete model",
        )
        if (
            not isinstance(model["source_commit"], str)
            or not metrics.COMMIT.fullmatch(model["source_commit"])
            or not isinstance(model["parameters"], dict)
        ):
            raise ValueError("Complete candidate models required")
        metrics._text(model.get("id"), "model ID")
        if (
            model.get("implementation_version")
            != settings["execution"]["implementation_version"]
        ):
            raise ValueError("Candidate model version mismatch")
    return settings, models


def _artifacts(artifacts, backend, root):
    metrics._exact_keys(
        artifacts,
        ("binaries", "build_receipt", "table_manifest", "tables"),
        "backend artifacts",
    )
    metrics._exact_keys(artifacts["binaries"], ("Fold", "bifold", "efn2"), "binaries")
    if not isinstance(artifacts["tables"], dict) or not artifacts["tables"]:
        raise ValueError("Explicit table artifacts required")
    for name, spec in artifacts["binaries"].items():
        if Path(spec["path"]) != root / "exe" / name:
            raise ValueError("Binary path differs from explicit backend root")
        _spec(spec)
        if spec["sha256"] != backend["binary_sha256"][name]:
            raise ValueError("Binary differs from candidate backend")
    _spec(artifacts["build_receipt"])
    if artifacts["build_receipt"]["sha256"] != backend["build_receipt_sha256"]:
        raise ValueError("Build receipt differs from candidate backend")
    manifest = artifacts["table_manifest"]
    _spec(manifest)
    if manifest["sha256"] != checked_hash(backend["table_manifest_sha256"]):
        raise ValueError("Table manifest differs from candidate backend")
    tables = strict_json(_pin(manifest["path"], manifest["sha256"], MAX_RECEIPT))
    if tables != {name: spec["sha256"] for name, spec in artifacts["tables"].items()}:
        raise ValueError("Table roster differs from the pinned manifest")
    for name, spec in artifacts["tables"].items():
        if Path(name).name != name or Path(spec["path"]) != root / "data_tables" / name:
            raise ValueError("Table path differs from explicit backend root")
        _spec(spec)


def _argv(executable, request, profile, settings):
    execution = settings["execution"]
    return [
        str(executable),
        str(request),
        "--profile",
        profile,
        "--mode",
        "supplied_start",
        "--format",
        "json",
        "--seconds-per-record",
        str(float(execution["seconds_per_record"])),
        "--seconds-per-batch",
        str(float(execution["seconds_per_batch"])),
    ]


def make_plan(
    panel_path,
    panel_sha256,
    candidate_path,
    candidate_sha256,
    executable,
    executable_sha256,
    admission_path,
    admission_sha256,
    backend_root,
    backend_artifacts,
    acknowledgement,
    *,
    output,
    seconds_per_record=60.0,
    seconds_per_batch=3600.0,
    stage_seconds=7200.0,
    grace_seconds=30.0,
    stream_bytes=MAX_STREAM,
):
    """Outcome-free preflight. Positive smaller budgets/caps support synthetic tests.

    Candidate settings must equal the requested budgets. Acknowledgement is a
    nonempty root-reviewed string, not an authorization discovered by this tool.
    Paths are made absolute; output-directory-specific argv is frozen in intent.
    """
    for value, cap in (
        (seconds_per_record, 60),
        (seconds_per_batch, 3600),
        (stage_seconds, 7200),
        (grace_seconds, 30),
    ):
        _seconds(value, cap)
    if type(stream_bytes) is not int or not 1 <= stream_bytes <= MAX_STREAM:
        raise ValueError("Invalid stream cap")
    metrics._text(acknowledgement, "root acknowledgement", 4096)
    paths = [
        Path(p).absolute()
        for p in (panel_path, candidate_path, executable, admission_path, backend_root)
    ]
    panel_path, candidate_path, executable, admission_path, backend_root = paths
    panel_raw = _pin(panel_path, panel_sha256, MAX_PANEL)
    if b"\r" in panel_raw:
        raise ValueError("Panel must be strict UTF-8 LF-only")
    panel = metrics.load_panel(panel_raw, panel_sha256)
    candidate_raw = _pin(candidate_path, candidate_sha256, MAX_RECEIPT)
    candidate = strict_json(candidate_raw)
    settings, _ = _candidate(candidate)
    if (
        settings["execution"]["seconds_per_record"],
        settings["execution"]["seconds_per_batch"],
    ) != (seconds_per_record, seconds_per_batch):
        raise ValueError("Budgets differ from candidate settings")
    admission_raw = _pin(admission_path, admission_sha256, MAX_RECEIPT)
    admission = strict_json(admission_raw)
    if (
        not isinstance(admission, dict)
        or admission.get("candidate_commit") != candidate["candidate_commit"]
        or admission.get("bound_receipts", {}).get(
            "rbs-context-preparation/candidate.json"
        )
        != candidate_sha256
    ):
        raise ValueError(
            "Final admission must bind this exact candidate receipt and commit"
        )
    _spec(dict(path=str(executable), sha256=executable_sha256))
    if not os.access(executable, os.X_OK) or not backend_root.is_dir():
        raise ValueError("Executable and explicit backend root required")
    _artifacts(backend_artifacts, settings["execution"]["backend"], backend_root)
    plan = dict(
        schema_version="rbs-context-plan-1",
        output=str(Path(output).absolute()),
        panel=dict(path=str(panel_path), sha256=panel_sha256, bytes=len(panel_raw)),
        candidate=dict(
            path=str(candidate_path), sha256=candidate_sha256, receipt=candidate
        ),
        executable=dict(path=str(executable), sha256=executable_sha256),
        admission=dict(path=str(admission_path), sha256=admission_sha256),
        backend_root=str(backend_root),
        backend_artifacts=backend_artifacts,
        acknowledgement=acknowledgement,
        stage_seconds=float(stage_seconds),
        grace_seconds=float(grace_seconds),
        stream_bytes=stream_bytes,
        collector_sha256=_hash_file(__file__),
        jobs=[
            dict(
                profile=p,
                record_ids=[r["id"] for r in panel["records"]],
                argv=_argv(
                    executable, Path(output).absolute() / "panel.json", p, settings
                ),
            )
            for p in PROFILES
        ],
    )
    # Round trip detaches all caller-owned mutable objects.
    return strict_json(canonical_bytes(plan))


def preflight(
    plan,
    expected_plan_sha256,
    expected_candidate_sha256,
    expected_admission_sha256,
    acknowledgement,
):
    """Rebuild every binding before creating output or starting a process."""
    if document_sha256(plan) != checked_hash(expected_plan_sha256):
        raise ValueError("Plan SHA-256 mismatch")
    if (
        plan["candidate"]["sha256"] != checked_hash(expected_candidate_sha256)
        or plan["admission"]["sha256"] != checked_hash(expected_admission_sha256)
        or plan["acknowledgement"] != acknowledgement
    ):
        raise ValueError("Explicit receipt bindings or acknowledgement mismatch")
    candidate = plan["candidate"]["receipt"]
    execution = candidate["execution"]
    rebuilt = make_plan(
        plan["panel"]["path"],
        plan["panel"]["sha256"],
        plan["candidate"]["path"],
        expected_candidate_sha256,
        plan["executable"]["path"],
        plan["executable"]["sha256"],
        plan["admission"]["path"],
        expected_admission_sha256,
        plan["backend_root"],
        plan["backend_artifacts"],
        acknowledgement,
        seconds_per_record=execution["seconds_per_record"],
        seconds_per_batch=execution["seconds_per_batch"],
        stage_seconds=plan["stage_seconds"],
        grace_seconds=plan["grace_seconds"],
        stream_bytes=plan["stream_bytes"],
        output=plan["output"],
    )
    if not _same(plan, rebuilt):
        raise ValueError("Plan differs from preflight")
    return plan


def _sync(stream):
    stream.flush()
    os.fsync(stream.fileno())


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def _save(path, raw):
    with _private(path) as stream:
        stream.write(raw)
        _sync(stream)


def _event(journal, **event):
    raw = canonical_bytes(event)
    if journal.tell() + len(raw) > MAX_JOURNAL:
        raise ValueError("Journal exceeds cap")
    journal.write(raw)
    _sync(journal)


def _limit(cap):
    _, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    bound = cap if hard == resource.RLIM_INFINITY else min(cap, hard)
    resource.setrlimit(resource.RLIMIT_FSIZE, (bound, hard))


def _group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill_wait(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        return False
    return not _group_exists(process.pid)


@contextlib.contextmanager
def _signals(*, defer=False):
    """Defer startup cancellation until Popen has returned an owned handle.

    A construction error remains a launch error. On success, a pending signal
    becomes KeyboardInterrupt only after the caller has assigned the process.
    The child inherits no blocked signal mask; caught handlers reset at exec.
    """
    pending = False

    def cancel(signum, frame):
        nonlocal pending
        if not defer:
            raise KeyboardInterrupt
        pending = True

    previous = {s: signal.signal(s, cancel) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if pending:
        raise KeyboardInterrupt


def _attempt(argv, timeout, stdout, stderr, env, cap):
    began = time.monotonic()
    process = None
    try:
        try:
            with _signals(defer=True):
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=env,
                    shell=False,
                    start_new_session=True,
                    preexec_fn=lambda: _limit(cap),
                )
        except (OSError, subprocess.SubprocessError):
            return dict(
                actual_exit_code=None, reason="launch_error", cleanup_confirmed=True
            )
        process.wait(timeout=max(0.0, timeout - (time.monotonic() - began)))
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        if process is None:
            raise
        clean = _kill_wait(process)
        return dict(
            actual_exit_code=process.returncode,
            reason="timeout"
            if isinstance(error, subprocess.TimeoutExpired)
            else "cancelled",
            cleanup_confirmed=clean,
        )
    except BaseException:
        if process is not None:
            _kill_wait(process)
        raise
    # A leader can exit while its descendants are still writing. Stop the stage.
    if _group_exists(process.pid):
        clean = _kill_wait(process)
        return dict(
            actual_exit_code=process.returncode,
            reason="descendants_remaining",
            cleanup_confirmed=clean,
        )
    return dict(
        actual_exit_code=process.returncode, reason=None, cleanup_confirmed=True
    )


def _same(left, right):
    """Compare complete JSON evidence without bool/int/float coercion."""
    return canonical_bytes(left) == canonical_bytes(right)


def _observation(value):
    metrics._exact_keys(
        value,
        ("actual_exit_code", "reason", "cleanup_confirmed"),
        "process observation",
    )
    code, reason = value["actual_exit_code"], value["reason"]
    if (
        type(value["cleanup_confirmed"]) is not bool
        or reason
        not in (None, "timeout", "cancelled", "launch_error", "descendants_remaining")
        or (code is not None and type(code) is not int)
        or (reason == "launch_error" and code is not None)
        or (
            code is None
            and reason != "launch_error"
            and not (
                reason in ("timeout", "cancelled") and not value["cleanup_confirmed"]
            )
        )
        or (reason is None and not value["cleanup_confirmed"])
    ):
        raise ValueError("Invalid process observation")
    return value


def _validate(raw, code, profile, plan, panel):
    native = strict_json(raw)
    candidate = plan["candidate"]["receipt"]
    model = candidate["complete_models"][profile]
    metrics._output_rows(native, profile, model["id"], _settings(candidate), panel)
    for row in native["results"]:
        prediction = row["prediction"]
        if prediction is not None and (
            not _same(prediction.get("model"), model)
            or not _same(prediction.get("backend"), candidate["execution"]["backend"])
        ):
            raise ValueError("Complete model/backend differs from candidate")
    failed = any(
        row["status"] in ("failed", "invalid_input") for row in native["results"]
    )
    if code != int(failed):
        raise ValueError("Actual exit disagrees with native statuses")
    return native


def _collection(plan):
    candidate = plan["candidate"]["receipt"]
    return dict(
        schema_version=metrics.COLLECTION_SCHEMA,
        panel_sha256=plan["panel"]["sha256"],
        candidate_commit=candidate["candidate_commit"],
        settings=_settings(candidate),
        runs={
            p: dict(
                expected_model_id=candidate["complete_models"][p]["id"],
                status="not_run",
                reason="not_started",
                output=None,
            )
            for p in PROFILES
        },
    )


def collect(
    plan,
    output,
    *,
    expected_plan_sha256,
    expected_candidate_sha256,
    expected_admission_sha256,
    acknowledgement,
):
    """Execute exactly once. Raises on persistence errors; never starts another job.

    An existing output directory is always an error. Returns a private receipt;
    recover(output)['ready'] is required before adapting its collection to metrics.
    """
    preflight(
        plan,
        expected_plan_sha256,
        expected_candidate_sha256,
        expected_admission_sha256,
        acknowledgement,
    )
    output = Path(output).absolute()
    if str(output) != plan["output"]:
        raise ValueError("Output directory differs from frozen plan")
    output.mkdir(mode=0o700)
    collection = _collection(plan)
    began = time.monotonic()
    deadline = began + plan["stage_seconds"]
    jobs = []
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(
        THREAD_ENV, PYTHONNOUSERSITE="1", REGSITE_RNASTRUCTURE=plan["backend_root"]
    )
    with _signals(), _private(output / "journal.jsonl") as journal:
        _event(journal, event="initialized", plan=plan)
        _sync_dir(output)
        _sync_dir(output.parent)
        _save(output / "plan.json", canonical_bytes(plan))
        for key, filename, limit in (
            ("panel", "panel.json", MAX_PANEL),
            ("candidate", "candidate.json", MAX_RECEIPT),
            ("admission", "admission.json", MAX_RECEIPT),
        ):
            _save(
                output / filename, _pin(plan[key]["path"], plan[key]["sha256"], limit)
            )
        panel = metrics.load_panel(
            _read(output / "panel.json", MAX_PANEL), plan["panel"]["sha256"]
        )
        for profile in PROFILES:
            # Detect changed files again between profiles, before any child exists.
            preflight(
                plan,
                expected_plan_sha256,
                expected_candidate_sha256,
                expected_admission_sha256,
                acknowledgement,
            )
            ceiling = min(
                deadline - time.monotonic(),
                plan["candidate"]["receipt"]["execution"]["seconds_per_batch"]
                + plan["grace_seconds"],
            )
            if ceiling <= 0:
                _event(journal, event="cancelled", profile=profile, launched=False)
                break
            argv = _argv(
                plan["executable"]["path"],
                output / "panel.json",
                profile,
                collection["settings"],
            )
            with (
                _private(output / f"{profile}.stdout") as stdout,
                _private(output / f"{profile}.stderr") as stderr,
            ):
                _event(
                    journal,
                    event="intent",
                    profile=profile,
                    argv=argv,
                    timeout_ceiling=ceiling,
                )
                _sync_dir(output)
                _pin(output / "panel.json", plan["panel"]["sha256"], MAX_PANEL)
                timeout = min(ceiling, deadline - time.monotonic())
                if timeout <= 0:
                    _event(journal, event="cancelled", profile=profile, launched=False)
                    break
                observation = _attempt(
                    argv, timeout, stdout, stderr, env, plan["stream_bytes"]
                )
                # First durable action after wait: never parse before observing.
                _event(
                    journal,
                    event="observed",
                    profile=profile,
                    timeout_seconds=timeout,
                    **observation,
                )
                _sync(stdout)
                _sync(stderr)
            streams = {
                name: dict(
                    sha256=_hash_file(output / f"{profile}.{name}"),
                    bytes=(output / f"{profile}.{name}").stat().st_size,
                )
                for name in ("stdout", "stderr")
            }
            reason = observation["reason"]
            native = None
            code = observation["actual_exit_code"]
            if max(s["bytes"] for s in streams.values()) > plan["stream_bytes"]:
                reason = "output_cap"
            elif reason is None:
                if code not in (0, 1):
                    reason = "process_exit"
                else:
                    try:
                        native = _validate(
                            _read(output / f"{profile}.stdout", plan["stream_bytes"]),
                            code,
                            profile,
                            plan,
                            panel,
                        )
                    except VALIDATION_ERRORS:
                        reason = "invalid_native_output"
            entry = collection["runs"][profile]
            entry.update(
                status="completed" if reason is None else "failed",
                reason=reason,
                output=native,
            )
            detail = dict(
                profile=profile,
                observation=observation,
                timeout_seconds=timeout,
                streams=streams,
                status=entry["status"],
                reason=reason,
            )
            _event(journal, event="finished", **detail)
            _sync_dir(output)
            jobs.append(detail)
            if reason is not None:
                break
        raw = canonical_bytes(collection)
        if len(raw) > MAX_COLLECTION:
            raise ValueError("Collection exceeds byte cap")
        receipt = dict(
            schema_version="rbs-context-receipt-1",
            plan_sha256=expected_plan_sha256,
            candidate_sha256=expected_candidate_sha256,
            admission_sha256=expected_admission_sha256,
            acknowledgement=acknowledgement,
            collector_sha256=plan["collector_sha256"],
            collection_sha256=digest(raw),
            jobs=jobs,
        )
        _save(output / "collection.json", raw)
        _save(output / "receipt.json", canonical_bytes(receipt))
        _sync_dir(output)
        _event(
            journal,
            event="finalized",
            collection_sha256=digest(raw),
            receipt_sha256=document_sha256(receipt),
        )
    return receipt


def recover(output, *, expected_plan_sha256):
    """Reconcile saved bytes/events without writing, launching or resuming.

    Malformed complete events raise ValueError. A truncated last line, unknown
    intent, missing artifacts or failed profile always blocks readiness.
    """
    output = Path(output).absolute()
    raw = _read(output / "journal.jsonl", MAX_JOURNAL)
    lines = raw.splitlines(keepends=True)
    truncated = bool(lines and not lines[-1].endswith(b"\n"))
    if truncated:
        lines.pop()
    events = [strict_json(line) for line in lines]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Journal events must be objects")
    if (
        not events
        or set(events[0]) != {"event", "plan"}
        or events[0]["event"] != "initialized"
    ):
        raise ValueError("Missing initial plan/roster")
    plan = events[0]["plan"]
    if document_sha256(plan) != checked_hash(expected_plan_sha256):
        raise ValueError("Recovery plan SHA-256 mismatch")
    jobs = {
        p: dict(state="not_run", intended=False, observed=False, validated=False)
        for p in PROFILES
    }
    index, phase, stop, final = 0, "new", False, None
    details = []
    for event in events[1:]:
        kind = event.get("event")
        if final is not None:
            raise ValueError("Event follows finalization")
        if kind == "finalized":
            metrics._exact_keys(
                event, ("event", "collection_sha256", "receipt_sha256"), "final event"
            )
            if phase not in ("new", "finished", "cancelled"):
                raise ValueError("Unobserved/unvalidated finalization")
            final = event
            continue
        if stop or index >= len(PROFILES) or event.get("profile") != PROFILES[index]:
            raise ValueError("Event violates profile order or stop")
        profile = PROFILES[index]
        job = jobs[profile]
        if kind == "intent" and phase in ("new", "finished"):
            metrics._exact_keys(
                event, ("event", "profile", "argv", "timeout_ceiling"), "intent"
            )
            ceiling = _seconds(
                event["timeout_ceiling"],
                min(
                    plan["stage_seconds"],
                    plan["candidate"]["receipt"]["execution"]["seconds_per_batch"]
                    + plan["grace_seconds"],
                ),
            )
            if event["argv"] != _argv(
                plan["executable"]["path"],
                output / "panel.json",
                profile,
                _settings(plan["candidate"]["receipt"]),
            ):
                raise ValueError("Intent argv mismatch")
            job.update(state="interrupted_unknown", intended=True)
            phase = "intent"
        elif kind == "cancelled" and phase in ("new", "finished", "intent"):
            if not _same(
                event, dict(event="cancelled", profile=profile, launched=False)
            ):
                raise ValueError("Invalid cancellation")
            job.update(state="cancelled_not_launched")
            phase, stop = "cancelled", True
        elif kind == "observed" and phase == "intent":
            metrics._exact_keys(
                event,
                (
                    "event",
                    "profile",
                    "timeout_seconds",
                    "actual_exit_code",
                    "reason",
                    "cleanup_confirmed",
                ),
                "observation",
            )
            _seconds(event["timeout_seconds"], ceiling)
            observation = _observation(
                {
                    k: event[k]
                    for k in ("actual_exit_code", "reason", "cleanup_confirmed")
                }
            )
            timeout = event["timeout_seconds"]
            job.update(
                state="observed_unvalidated", observed=True, observation=observation
            )
            phase = "observed"
        elif kind == "finished" and phase == "observed":
            metrics._exact_keys(
                event,
                (
                    "event",
                    "profile",
                    "observation",
                    "timeout_seconds",
                    "streams",
                    "status",
                    "reason",
                ),
                "finish",
            )
            if not _same(_observation(event["observation"]), observation) or not _same(
                event["timeout_seconds"], timeout
            ):
                raise ValueError("Finish observation mismatch")
            if event["status"] not in ("completed", "failed") or (
                event["reason"] is None
            ) != (event["status"] == "completed"):
                raise ValueError("Invalid finish status")
            detail = {k: v for k, v in event.items() if k != "event"}
            details.append(detail)
            job.update(state=event["status"], validated=event["status"] == "completed")
            phase, stop = "finished", event["status"] == "failed"
            index += 1
        else:
            raise ValueError("Invalid event order")
    result = dict(
        ready=False,
        truncated=truncated,
        finalized=final is not None,
        jobs=jobs,
        artifact_error=None,
    )
    if final is None or truncated:
        return result
    try:
        saved_plan = strict_json(_read(output / "plan.json", MAX_JOURNAL))
        if not _same(saved_plan, plan):
            raise ValueError("Archived plan mismatch")
        candidate_raw = _pin(
            output / "candidate.json", plan["candidate"]["sha256"], MAX_RECEIPT
        )
        if not _same(strict_json(candidate_raw), plan["candidate"]["receipt"]):
            raise ValueError("Archived candidate mismatch")
        _candidate(plan["candidate"]["receipt"])
        _pin(output / "admission.json", plan["admission"]["sha256"], MAX_RECEIPT)
        panel = metrics.load_panel(
            _pin(output / "panel.json", plan["panel"]["sha256"], MAX_PANEL),
            plan["panel"]["sha256"],
        )
        if plan["jobs"] != [
            dict(
                profile=p,
                record_ids=[r["id"] for r in panel["records"]],
                argv=_argv(
                    plan["executable"]["path"],
                    str(Path(plan["output"]) / "panel.json"),
                    p,
                    _settings(plan["candidate"]["receipt"]),
                ),
            )
            for p in PROFILES
        ] or not _same(
            len(_read(output / "panel.json", MAX_PANEL)), plan["panel"]["bytes"]
        ):
            raise ValueError("Archived roster mismatch")
        expected = _collection(plan)
        for detail in details:
            profile = detail["profile"]
            streams = detail["streams"]
            metrics._exact_keys(streams, ("stdout", "stderr"), "streams")
            for name, spec in streams.items():
                raw_stream = _pin(
                    output / f"{profile}.{name}", spec["sha256"], plan["stream_bytes"]
                )
                if not _same(len(raw_stream), spec["bytes"]):
                    raise ValueError("Stream size mismatch")
            native = None
            if detail["status"] == "completed":
                if detail["observation"]["reason"] is not None:
                    raise ValueError("Failed observation marked completed")
                native = _validate(
                    _read(output / f"{profile}.stdout", plan["stream_bytes"]),
                    detail["observation"]["actual_exit_code"],
                    profile,
                    plan,
                    panel,
                )
            expected["runs"][profile].update(
                status=detail["status"], reason=detail["reason"], output=native
            )
        collection_raw = _pin(
            output / "collection.json", final["collection_sha256"], MAX_COLLECTION
        )
        if not _same(strict_json(collection_raw), expected):
            raise ValueError("Collection does not reconcile")
        receipt = strict_json(
            _pin(output / "receipt.json", final["receipt_sha256"], MAX_RECEIPT)
        )
        wanted = dict(
            schema_version="rbs-context-receipt-1",
            plan_sha256=document_sha256(plan),
            candidate_sha256=plan["candidate"]["sha256"],
            admission_sha256=plan["admission"]["sha256"],
            acknowledgement=plan["acknowledgement"],
            collector_sha256=plan["collector_sha256"],
            collection_sha256=digest(collection_raw),
            jobs=details,
        )
        if not _same(receipt, wanted):
            raise ValueError("Receipt does not reconcile")
        result["ready"] = all(job["validated"] for job in jobs.values())
    except (OSError, *VALIDATION_ERRORS):
        result["artifact_error"] = "unreconciled_artifacts"
    return result

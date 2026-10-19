"""Private, once-only execution of the frozen 36 paired requests.

No scientific runtime is imported. Root owns package/CI installation admission,
full native schemas/input/model/backend validity and the reserved folding slot.
Receipt pins verify bytes only. ``ready`` means all wrapper audits reconcile;
it does not admit native predictions. Recovery never writes, retries or resumes.
Use from the main thread; the shared POSIX process helper owns group cleanup.
"""

import os
import time
from pathlib import Path

from benchmarks.promoter.native_inputs import checked_hash, strict_json
from benchmarks.rbs import context_collect as io
from benchmarks.rbs.datasets import digest
from benchmarks.recoding import runtime_check as checker

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models/paired/0.6.0rc1"
PREPARATION = ROOT / "benchmarks/recoding/wave5-paired-preparation.json"
PREPARATION_SHA256 = "e79fa42cb04a0f2c5e31cdd1b10c3e469a5626fdb37b15bedf8a558a3b918b08"
MAX_DOCUMENT = io.MAX_RECEIPT
MAX_STREAM = io.MAX_STREAM
ERRORS = io.VALIDATION_ERRORS
# Bind reused planning/checking/IO code and its local imports, plus contracts.
SOURCES = (
    "benchmarks/recoding/collect.py",
    "benchmarks/recoding/runtime_check.py",
    "benchmarks/recoding/edit_maps.py",
    "benchmarks/recoding/codon_pairs.py",
    "benchmarks/recoding/runtime-pair-fixtures.json",
    "benchmarks/rbs/context_collect.py",
    "benchmarks/rbs/context_metrics.py",
    "benchmarks/rbs/context_panel.py",
    "benchmarks/rbs/metrics.py",
    "benchmarks/rbs/datasets.py",
    "benchmarks/rbs/native.py",
    "benchmarks/promoter/native_inputs.py",
    "docs/validation/paired-regulatory-runtime.md",
    "schemas/paired-regulatory-request-1.schema.json",
    "schemas/paired-regulatory-result-1.schema.json",
)


def _keys(value, names):
    checker._keys(value, names)


def _snapshot(path, expected=None):
    path = Path(path).absolute()
    raw = io._read(path, MAX_DOCUMENT)
    sha = digest(raw)
    if expected is not None and sha != checked_hash(expected):
        raise ValueError("Input SHA-256 mismatch")
    return dict(path=str(path), sha256=sha), raw


def _inputs(preparation_path, candidate_path, admission_path, backend_candidate_path):
    prep_spec, raw = _snapshot(preparation_path, PREPARATION_SHA256)
    preparation = strict_json(raw)
    candidate_spec, raw = _snapshot(
        candidate_path, preparation["candidate_receipt_sha256"]
    )
    candidate = strict_json(raw)
    admission_spec, raw = _snapshot(admission_path, preparation["ci_admission_sha256"])
    admission = strict_json(raw)
    backend_spec, raw = _snapshot(
        backend_candidate_path,
        admission["bound_receipts"]["rbs-context-preparation/candidate.json"],
    )
    backend_candidate = strict_json(raw)
    if (
        preparation["schema_version"] != "paired-b-evaluation-preparation-1"
        or candidate["schema_version"] != "paired-runtime-candidate-1"
        or candidate["candidate_commit"] != preparation["candidate_commit"]
        or admission["candidate_commit"] != preparation["candidate_commit"]
        or backend_candidate["candidate_commit"] != preparation["candidate_commit"]
        or admission["bound_receipts"]["candidate.json"] != candidate_spec["sha256"]
    ):
        raise ValueError("Candidate/admission binding mismatch")
    _keys(candidate["limits"], (*checker.LIMIT_CEILINGS, "predictors"))
    for name, ceiling in checker.LIMIT_CEILINGS.items():
        checker._integer(candidate["limits"][name], 1, ceiling)
    _keys(candidate["limits"]["predictors"], ("promoter", "rbs"))
    return (
        dict(
            preparation=prep_spec,
            candidate=candidate_spec,
            admission=admission_spec,
            backend_candidate=backend_spec,
        ),
        preparation,
        candidate,
        backend_candidate,
    )


def _jobs(output, preparation, limits):
    requests, manifest = checker.build_requests()
    checker._same(
        manifest, preparation["request_manifest"], "Frozen request manifest mismatch"
    )
    if len(requests) != 36:
        raise ValueError("Frozen full request roster mismatch")
    jobs = []
    for index, request in enumerate(requests):
        checker._tree(request, limits)
        if len(checker.canonical_bytes(request)) > limits["max_input_json_bytes"]:
            raise ValueError("Request byte cap")
        jobs.append(
            dict(
                index=index,
                request=request,
                manifest=manifest["jobs"][index],
                request_path=str(Path(output) / f"{index:02d}.request.json"),
            )
        )
    return jobs


def make_plan(
    executable,
    executable_sha256,
    backend_root,
    backend_artifacts,
    acknowledgement,
    *,
    output,
    preparation_path=PREPARATION,
    candidate_path=MODEL / "candidate.json",
    admission_path=MODEL / "ci-admission.json",
    backend_candidate_path=MODEL / "rbs-context-preparation/candidate.json",
):
    """Build an outcome-free plan; root must review/freeze its canonical SHA256.

    All four receipt paths can be explicit. Artifact specs use context_collect's
    binaries/build_receipt/table_manifest/tables contract. No process is started.
    Preserve original parsed numbers in every document hash.
    """
    if (
        not isinstance(acknowledgement, str)
        or not 0 < len(acknowledgement.strip()) <= 4096
    ):
        raise ValueError("Explicit root acknowledgement required")
    inputs, preparation, candidate, backend_candidate = _inputs(
        preparation_path, candidate_path, admission_path, backend_candidate_path
    )
    executable = dict(path=str(Path(executable).absolute()), sha256=executable_sha256)
    io._spec(executable)
    backend_root = Path(backend_root).absolute()
    if not os.access(executable["path"], os.X_OK) or not backend_root.is_dir():
        raise ValueError("Executable and explicit backend root required")
    io._artifacts(
        backend_artifacts, backend_candidate["execution"]["backend"], backend_root
    )
    output = str(Path(output).absolute())
    sources = {name: _snapshot(ROOT / name)[0] for name in SOURCES}
    for name, expected in (
        ("benchmarks/recoding/runtime_check.py", preparation["checker_sha256"]),
        (
            "benchmarks/recoding/runtime-pair-fixtures.json",
            preparation["request_manifest"]["fixture_sha256"],
        ),
        (
            "docs/validation/paired-regulatory-runtime.md",
            candidate["runtime_contract_sha256"],
        ),
        (
            "schemas/paired-regulatory-request-1.schema.json",
            candidate["request_schema_sha256"],
        ),
        (
            "schemas/paired-regulatory-result-1.schema.json",
            candidate["result_schema_sha256"],
        ),
    ):
        if sources[name]["sha256"] != checked_hash(expected):
            raise ValueError("Checker, fixture or public contract pin mismatch")
    plan = dict(
        schema_version="paired-b-plan-1",
        output=output,
        inputs=inputs,
        sources=sources,
        executable=executable,
        backend_root=str(backend_root),
        backend_artifacts=backend_artifacts,
        acknowledgement=acknowledgement,
        stage_seconds=preparation["stage_seconds"],
        grace_seconds=preparation["process_exit_grace_seconds"],
        stream_bytes=MAX_STREAM,
        limits=candidate["limits"],
        jobs=_jobs(output, preparation, candidate["limits"]),
    )
    return strict_json(checker.canonical_bytes(plan))


def plan_sha256(plan):
    """Hash the compact ASCII plan, without a trailing LF."""
    return checker.sha256(plan)


def preflight(plan, expected_plan_sha256, expected_admission_sha256, acknowledgement):
    """Reproduce all inputs/helper/executable/artifact bindings before launch."""
    if plan_sha256(plan) != checked_hash(expected_plan_sha256):
        raise ValueError("Plan SHA-256 mismatch")
    if (
        plan["inputs"]["admission"]["sha256"] != checked_hash(expected_admission_sha256)
        or plan["acknowledgement"] != acknowledgement
    ):
        raise ValueError("Admission or acknowledgement mismatch")
    rebuilt = make_plan(
        plan["executable"]["path"],
        plan["executable"]["sha256"],
        plan["backend_root"],
        plan["backend_artifacts"],
        acknowledgement,
        output=plan["output"],
        **{f"{key}_path": spec["path"] for key, spec in plan["inputs"].items()},
    )
    if checker.canonical_bytes(rebuilt) != checker.canonical_bytes(plan):
        raise ValueError("Plan differs from preflight")


def _argv(plan, index):
    return [
        plan["executable"]["path"],
        plan["jobs"][index]["request_path"],
        "--format",
        "json",
    ]


def _validate(plan, index, raw, code):
    audit = checker.check_result(plan["jobs"][index]["request"], raw, plan["limits"])
    if type(code) is not int or code != int(
        audit["status"] in ("partial", "unavailable")
    ):
        raise ValueError("Actual exit disagrees with paired status")
    return audit


def _finish(output, plan, index, observation, timeout):
    streams, raw = {}, None
    for name in ("stdout", "stderr"):
        wire = io._read(output / f"{index:02d}.{name}", plan["stream_bytes"] + 1)
        streams[name] = dict(sha256=digest(wire), bytes=len(wire))
        if name == "stdout":
            raw = wire
    reason, audit = observation["reason"], None
    if any(spec["bytes"] > plan["stream_bytes"] for spec in streams.values()):
        reason = "output_cap"
    if reason is None:
        if observation["actual_exit_code"] not in (0, 1):
            reason = "process_exit"
        else:
            try:
                audit = _validate(plan, index, raw, observation["actual_exit_code"])
            except ERRORS:
                reason = "invalid_paired_output"
    return dict(
        index=index,
        state="validated" if reason is None else "failed",
        observation=observation,
        timeout_seconds=timeout,
        streams=streams,
        reason=reason,
        audit=audit,
    )


def _receipt(plan, jobs):
    return dict(
        schema_version="paired-b-receipt-1",
        plan_sha256=plan_sha256(plan),
        admission_sha256=plan["inputs"]["admission"]["sha256"],
        acknowledgement=plan["acknowledgement"],
        sources=plan["sources"],
        native_prediction_admitted=False,
        jobs=jobs,
    )


def collect(plan, *, expected_plan_sha256, expected_admission_sha256, acknowledgement):
    """Persist inputs and serial intent/observation/audit/finish; never reuse a dir.

    Persistence errors propagate immediately, leaving a non-ready private ledger.
    No next launch occurs until the previous finish and its directory are synced.
    """
    preflight(plan, expected_plan_sha256, expected_admission_sha256, acknowledgement)
    output = Path(plan["output"])
    output.mkdir(mode=0o700)
    deadline = time.monotonic() + plan["stage_seconds"]
    jobs = [dict(index=j["index"], state="not_run") for j in plan["jobs"]]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(
        io.THREAD_ENV, PYTHONNOUSERSITE="1", REGSITE_RNASTRUCTURE=plan["backend_root"]
    )
    with io._signals(), io._private(output / "journal.jsonl") as journal:
        io._event(journal, event="initialized", plan=plan)
        io._sync_dir(output)
        io._sync_dir(output.parent)
        io._save(output / "plan.json", checker.canonical_bytes(plan))
        for key, spec in {**plan["inputs"], **plan["sources"]}.items():
            # Archive every bounded planning input under an unambiguous flat name.
            io._save(
                output / (key.replace("/", "_") + ".input"),
                io._pin(spec["path"], spec["sha256"], MAX_DOCUMENT),
            )
        for job in plan["jobs"]:
            io._save(Path(job["request_path"]), checker.canonical_bytes(job["request"]))
        io._sync_dir(output)
        for index, job in enumerate(plan["jobs"]):
            preflight(
                plan, expected_plan_sha256, expected_admission_sha256, acknowledgement
            )
            ceiling = min(
                deadline - time.monotonic(),
                2 * job["request"]["settings"]["seconds_per_side"]
                + plan["grace_seconds"],
            )
            if ceiling <= 0:
                io._event(journal, event="cancelled", index=index, launched=False)
                jobs[index] = dict(index=index, state="cancelled_not_launched")
                break
            with (
                io._private(output / f"{index:02d}.stdout") as stdout,
                io._private(output / f"{index:02d}.stderr") as stderr,
            ):
                io._event(
                    journal,
                    event="intent",
                    index=index,
                    argv=_argv(plan, index),
                    timeout_ceiling=ceiling,
                )
                try:
                    io._sync_dir(output)
                    io._pin(
                        job["request_path"],
                        job["manifest"]["request_sha256"],
                        plan["limits"]["max_input_json_bytes"],
                    )
                    timeout = min(ceiling, deadline - time.monotonic())
                except KeyboardInterrupt:
                    timeout = 0
                if timeout <= 0:
                    io._event(journal, event="cancelled", index=index, launched=False)
                    jobs[index] = dict(index=index, state="cancelled_not_launched")
                    break
                observation = io._attempt(
                    _argv(plan, index),
                    timeout,
                    stdout,
                    stderr,
                    env,
                    plan["stream_bytes"],
                )
                # First durable action after wait, before any parsing or raw sync.
                io._event(
                    journal,
                    event="observed",
                    index=index,
                    timeout_seconds=timeout,
                    **observation,
                )
                io._sync(stdout)
                io._sync(stderr)
            detail = _finish(output, plan, index, observation, timeout)
            io._save(
                output / f"{index:02d}.audit.json",
                checker.canonical_bytes(detail["audit"]),
            )
            io._event(journal, event="finished", **detail)
            io._sync_dir(output)
            jobs[index] = detail
            if detail["state"] == "failed":
                break
        receipt = _receipt(plan, jobs)
        raw = checker.canonical_bytes(receipt)
        io._save(output / "receipt.json", raw)
        io._sync_dir(output)
        io._event(journal, event="finalized", receipt_sha256=digest(raw))
    return receipt


def _observation(event, ceiling):
    _keys(
        event,
        (
            "event",
            "index",
            "timeout_seconds",
            "actual_exit_code",
            "reason",
            "cleanup_confirmed",
        ),
    )
    io._seconds(event["timeout_seconds"], ceiling)
    code, reason, clean = (
        event["actual_exit_code"],
        event["reason"],
        event["cleanup_confirmed"],
    )
    if (
        type(clean) is not bool
        or reason
        not in (None, "launch_error", "timeout", "cancelled", "descendants_remaining")
        or (code is not None and type(code) is not int)
        or (reason == "launch_error" and code is not None)
        or (
            code is None
            and reason != "launch_error"
            and not (reason in ("timeout", "cancelled") and not clean)
        )
        or (reason is None and not clean)
    ):
        raise ValueError("Invalid process observation")
    return dict(actual_exit_code=code, reason=reason, cleanup_confirmed=clean)


def recover(output, *, expected_plan_sha256):
    """Read-only reconciliation; every job remains visible, including unknown intents.

    Invalid complete journal events raise. Missing/corrupted archived artifacts or
    incomplete/truncated journals never become ready. External installations and
    scientific/native admission are not re-verified or claimed by recovery.
    """
    output = Path(output).absolute()
    raw = io._read(output / "journal.jsonl", io.MAX_JOURNAL)
    lines = raw.splitlines(keepends=True)
    truncated = bool(lines and not lines[-1].endswith(b"\n"))
    if truncated:
        lines.pop()
    events = [strict_json(line) for line in lines]
    if (
        not events
        or not isinstance(events[0], dict)
        or set(events[0]) != {"event", "plan"}
        or events[0]["event"] != "initialized"
    ):
        raise ValueError("Missing initial plan/roster")
    plan = events[0]["plan"]
    if plan_sha256(plan) != checked_hash(expected_plan_sha256):
        raise ValueError("Recovery plan SHA-256 mismatch")
    if (
        plan["schema_version"] != "paired-b-plan-1"
        or plan["output"] != str(output)
        or len(plan["jobs"]) != 36
    ):
        raise ValueError("Invalid archived plan")
    jobs = [dict(index=i, state="not_run") for i in range(36)]
    index, phase, stopped, final = 0, "new", False, None
    for event in events[1:]:
        if not isinstance(event, dict) or final is not None:
            raise ValueError("Invalid event after finalization")
        kind = event.get("event")
        if kind == "finalized":
            _keys(event, ("event", "receipt_sha256"))
            if phase not in ("new", "finished", "cancelled") or not (
                stopped or index == 36
            ):
                raise ValueError("Premature finalization")
            final = event
            continue
        if (
            stopped
            or index >= 36
            or type(event.get("index")) is not int
            or event["index"] != index
        ):
            raise ValueError("Event violates job order or stop")
        if kind == "intent" and phase in ("new", "finished"):
            _keys(event, ("event", "index", "argv", "timeout_ceiling"))
            ceiling = io._seconds(
                event["timeout_ceiling"],
                min(
                    plan["stage_seconds"],
                    2 * plan["jobs"][index]["request"]["settings"]["seconds_per_side"]
                    + plan["grace_seconds"],
                ),
            )
            checker._same(event["argv"], _argv(plan, index), "Intent argv mismatch")
            jobs[index] = dict(index=index, state="interrupted_unknown")
            phase = "intent"
        elif kind == "cancelled" and phase in ("new", "finished", "intent"):
            checker._same(
                event,
                dict(event="cancelled", index=index, launched=False),
                "Invalid cancellation",
            )
            jobs[index] = dict(index=index, state="cancelled_not_launched")
            phase, stopped = "cancelled", True
        elif kind == "observed" and phase == "intent":
            observation = _observation(event, ceiling)
            timeout = event["timeout_seconds"]
            jobs[index] = dict(
                index=index, state="observed_unvalidated", observation=observation
            )
            phase = "observed"
        elif kind == "finished" and phase == "observed":
            _keys(
                event,
                (
                    "event",
                    "index",
                    "state",
                    "observation",
                    "timeout_seconds",
                    "streams",
                    "reason",
                    "audit",
                ),
            )
            detail = {k: v for k, v in event.items() if k != "event"}
            checker._same(
                event["observation"], observation, "Finish observation mismatch"
            )
            checker._same(event["timeout_seconds"], timeout, "Finish timeout mismatch")
            if event["state"] not in ("validated", "failed") or (
                event["reason"] is None
            ) != (event["state"] == "validated"):
                raise ValueError("Finish status mismatch")
            _keys(event["streams"], ("stdout", "stderr"))
            for spec in event["streams"].values():
                _keys(spec, ("sha256", "bytes"))
                checked_hash(spec["sha256"])
                checker._integer(spec["bytes"], 0, plan["stream_bytes"] + 1)
            if event["state"] == "validated":
                if (
                    not isinstance(event["audit"], dict)
                    or event["audit"].get("native_prediction_admitted") is not False
                ):
                    raise ValueError("Invalid wrapper audit")
            else:
                checker._same(
                    event["audit"], None, "Failed job cannot have a passing audit"
                )
            jobs[index] = detail
            phase, stopped = "finished", event["state"] == "failed"
            index += 1
        else:
            raise ValueError("Invalid event order")
    result = dict(
        ready=False,
        truncated=truncated,
        finalized=final is not None,
        jobs=jobs,
        artifact_error=None,
        native_prediction_admitted=False,
    )
    if final is None or truncated:
        return result
    try:
        io._pin(output / "plan.json", expected_plan_sha256, io.MAX_JOURNAL)
        for key, spec in {**plan["inputs"], **plan["sources"]}.items():
            io._pin(
                output / (key.replace("/", "_") + ".input"),
                spec["sha256"],
                MAX_DOCUMENT,
            )
        preparation = strict_json(io._read(output / "preparation.input", MAX_DOCUMENT))
        if checker.canonical_bytes(
            _jobs(str(output), preparation, plan["limits"])
        ) != checker.canonical_bytes(plan["jobs"]):
            raise ValueError("Archived request roster mismatch")
        for job in plan["jobs"]:
            io._pin(
                job["request_path"],
                job["manifest"]["request_sha256"],
                plan["limits"]["max_input_json_bytes"],
            )
        for job in jobs:
            if job["state"] in ("validated", "failed"):
                i = job["index"]
                expected = _finish(
                    output, plan, i, job["observation"], job["timeout_seconds"]
                )
                if checker.canonical_bytes(job) != checker.canonical_bytes(expected):
                    raise ValueError("Raw result/audit mismatch")
                io._pin(
                    output / f"{i:02d}.audit.json",
                    checker.sha256(job["audit"]),
                    MAX_DOCUMENT,
                )
        receipt = io._pin(
            output / "receipt.json", final["receipt_sha256"], MAX_DOCUMENT
        )
        if receipt != checker.canonical_bytes(_receipt(plan, jobs)):
            raise ValueError("Final receipt mismatch")
        result["ready"] = all(job["state"] == "validated" for job in jobs)
    except (OSError, *ERRORS):
        result["artifact_error"] = "unreconciled_artifacts"
    return result

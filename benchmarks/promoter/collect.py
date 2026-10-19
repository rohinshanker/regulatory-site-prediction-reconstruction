"""Serial, one-attempt collection of an admitted frozen public-interface plan.

Admission is an opaque, hash-pinned, nonempty JSON object acknowledged by the
operator. Package/wheel consistency and CI review are the root reviewer's
responsibility, not inferred here. No labels or scientific calculations enter.
POSIX child file-size limits bound each diagnostic stream to 64 MiB; subprocess
timeout cleanup suffices for the reviewed CLI, which launches no children.
Synthetic exit codes: -1 for launch errors and -9 for subprocess timeouts.
Malformed completed outputs remain completed raw evidence in collection.json;
the separate receipt records validation failure and the command exits 1.
The fsynced append-only execution-journal.jsonl is primary attempt evidence.
recover() is read-only: unmatched starts have unknown actual exits, returned
processes remain unvalidated until their finished event, and incomplete journals
or finalization block adaptation. It never creates a replacement collection.
"""

import argparse
import hashlib
import math
import os
import resource
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.promoter import runtime_adapter as adapter
from benchmarks.promoter.native_inputs import (
    canonical_bytes,
    checked_hash,
    document_sha256,
    read_bounded,
    strict_json,
    write_exclusive,
)
from benchmarks.rbs.datasets import digest

MAX_ADMISSION_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_JOURNAL_BYTES = 2 * adapter.MAX_PLAN_BYTES
JOURNAL_NAME = "execution-journal.jsonl"
JOURNAL_SCHEMA = "promoter-execution-journal-1"
PLAN_KEYS = (
    "schema_version scope tool_sha256 query_document_sha256 query_source "
    "query_settings_sha256 queries_sha256 manifest manifest_sha256 identity_sha256 "
    "settings_sha256 public_contract_commit request_contract expected_calibration "
    "totals batches"
).split()
BATCH_KEYS = (
    "batch_index request_sha256 request_bytes batch_id n_records n_bases n_sites "
    "records request"
).split()


def _pinned(path, expected, limit, name):
    raw = read_bounded(path, limit)
    if digest(raw) != checked_hash(expected):
        raise ValueError(f"{name} SHA-256 mismatch")
    return raw


def _check_request_record(record, row, index, manifest):
    """Validate request shape using the adapter constructor and primitive checks."""
    settings = manifest["settings"]
    fields = "id sequence calibration scan projection output model".split()
    if settings["host"] is not None:
        fields.append("host")
    adapter._exact_keys(record, fields, "request record")
    adapter._same(record["id"], f"q{index:06d}", "record order")
    adapter._same(row["request_id"], record["id"], "request ID")
    runtime = settings["runtime_limits"]
    adapter._text(record["id"], "record ID", runtime["max_id_chars"])
    projection = record["projection"]
    adapter._exact_keys(
        projection,
        (
            "contig",
            "origin",
            "contig_length",
            "sequence_strand",
            "topology",
            "origin_crossing",
        ),
        "projection",
    )
    adapter._text(projection["contig"], "contig", runtime["max_contig_chars"])
    size = adapter._int(
        projection["contig_length"],
        "contig length",
        1,
        adapter.MAX_GENOME_LENGTH,
    )
    adapter._int(projection["origin"], "origin", 0, size - 1)
    if (
        projection["sequence_strand"] not in ("+", "-")
        or projection["topology"] not in ("linear", "circular")
        or type(projection["origin_crossing"]) is not bool
    ):
        raise ValueError("Invalid projection fields")
    sequence, scan = record["sequence"], record["scan"]
    if not isinstance(sequence, str) or not sequence or set(sequence) - set("ACGT"):
        raise ValueError("Invalid request sequence")
    adapter._exact_keys(scan, ("mode", "strands", "range"), "scan")
    lower, upper = adapter._pair(scan["range"], "scan range", 0, len(sequence))
    adapter._same(scan, dict(mode="scan", strands=["+"], range=[lower, upper]), "scan")
    # Reuse the adapter's record constructor; no sequence or score changes.
    expected = adapter.request_record(
        index,
        dict(sequence=sequence, candidate_local_range=[lower, upper]),
        record["projection"],
        manifest,
    )
    adapter._same(record, expected, "request record")
    return record, len(sequence), upper - lower


def _check_plan(raw):
    plan = strict_json(raw)
    adapter._exact_keys(plan, PLAN_KEYS, "plan")
    if raw != canonical_bytes(plan) or plan["schema_version"] != adapter.PLAN_SCHEMA:
        raise ValueError("Plan must be canonical with the adapter plan schema")
    adapter._same(plan["tool_sha256"], adapter.tool_sha256(), "adapter tool")
    manifest = adapter.check_manifest(plan["manifest"])
    settings, identity = manifest["settings"], manifest["identity"]
    for key, document in (
        ("manifest_sha256", manifest),
        ("identity_sha256", identity),
        ("settings_sha256", settings),
    ):
        adapter._same(plan[key], document_sha256(document), key)
    for key in ("query_document_sha256", "query_settings_sha256", "queries_sha256"):
        checked_hash(plan[key])
    adapter._same(
        plan["public_contract_commit"], identity["public_contract_commit"], "contract"
    )
    adapter._same(
        plan["request_contract"],
        dict(
            request_schema_version=adapter.CONTRACT_VERSION,
            result_schema_version=adapter.CONTRACT_VERSION,
            scan_strands=adapter.SCAN_STRANDS,
            output=adapter.OUTPUT_OPTIONS,
        ),
        "request contract",
    )
    adapter._same(
        plan["expected_calibration"],
        adapter.expected_calibration(settings["calibration"], settings["host"]),
        "calibration",
    )
    batches = plan["batches"]
    if not isinstance(batches, list) or not batches:
        raise ValueError("Plan needs a nonempty batch roster")
    requests, entries, query_ids = [], [], set()
    totals = dict(n_requests=0, n_batches=len(batches), n_bases=0, n_sites=0)
    for index, batch in enumerate(batches):
        adapter._exact_keys(batch, BATCH_KEYS, "batch")
        adapter._same(batch["batch_index"], index, "batch order")
        request = batch["request"]
        adapter._exact_keys(
            request, ("defaults", "records", "schema_version"), "request"
        )
        adapter._same(request["defaults"], {}, "request defaults")
        adapter._same(
            request["schema_version"], adapter.CONTRACT_VERSION, "request schema"
        )
        records, roster = request["records"], batch["records"]
        if (
            not isinstance(records, list)
            or not records
            or not isinstance(roster, list)
            or len(records) != len(roster)
        ):
            raise ValueError("Batch needs a nonempty matching record roster")
        bases = sites = 0
        for record, row in zip(records, roster, strict=True):
            adapter._exact_keys(row, ("request_id", "query_id"), "record roster")
            query_id = row["query_id"]
            if not isinstance(query_id, str) or not query_id or query_id in query_ids:
                raise ValueError("Invalid or duplicate query ID")
            query_ids.add(query_id)
            entry = _check_request_record(record, row, totals["n_requests"], manifest)
            _, length, count = entry
            entries.append(entry)
            totals["n_requests"] += 1
            bases += length
            sites += count
        raw_request = adapter.plan_request_bytes(plan, index)
        adapter._same(
            [
                batch[key]
                for key in ("request_bytes", "n_records", "n_bases", "n_sites")
            ],
            [len(raw_request), len(records), bases, sites],
            "batch counts",
        )
        adapter._same(
            batch["batch_id"], adapter.batch_id(request, settings, identity), "batch"
        )
        totals["n_bases"] += bases
        totals["n_sites"] += sites
        requests.append(raw_request)
    # Reuse packing validation and require the frozen deterministic membership.
    packed = adapter.pack(entries, settings["limits"])
    adapter._same(
        [group["records"] for group in packed],
        [batch["request"]["records"] for batch in batches],
        "batch membership",
    )
    adapter._same(plan["totals"], totals, "plan totals")
    return plan, requests


def check_plan(raw):
    """Check canonical identity and execution roster without rebuilding queries."""
    try:
        return _check_plan(raw)
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("Malformed plan structure") from error


def _seconds(value, maximum, zero=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value > maximum
        or value < 0
        or (not zero and value == 0)
    ):
        raise ValueError("Invalid stage or process grace seconds")


def _executable(path, expected):
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Executable must be an installed executable file")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != checked_hash(expected):
        raise ValueError("Executable SHA-256 mismatch")


def _open_private(path):
    return os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600), "wb"
    )


def _limit_output():
    """Child-only POSIX limit; preserve an already stricter hard limit."""
    _, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    bound = (
        MAX_OUTPUT_BYTES
        if hard == resource.RLIM_INFINITY
        else min(MAX_OUTPUT_BYTES, hard)
    )
    resource.setrlimit(resource.RLIMIT_FSIZE, (bound, hard))


def _diagnostic(path):
    size = path.stat().st_size
    # Never read an oversized artifact, including one from an injected runner.
    return dict(
        path=path.name,
        bytes=size,
        sha256=digest(read_bounded(path, MAX_OUTPUT_BYTES))
        if size <= MAX_OUTPUT_BYTES
        else None,
    )


def _attempt(argv, timeout, stdout, stderr, runner):
    try:
        process = runner(
            argv,
            stdout=stdout,
            stderr=stderr,
            timeout=timeout,
            check=False,
            shell=False,
            preexec_fn=_limit_output,
        )
        return process.returncode, None
    except subprocess.TimeoutExpired:
        return -9, "timeout"
    except (OSError, subprocess.SubprocessError):
        return -1, "launch_error"


def _process_status(code):
    return (
        "completed"
        if code in (0, 1)
        else "setup_failed"
        if code == 2
        else "execution_failed"
    )


def _process_reason(code):
    if code == 0:
        return None
    return (
        "record_failure"
        if code == 1
        else "setup_failed"
        if code == 2
        else "process_signal"
        if code < 0
        else "process_exit"
    )


def _validate_output(code, stdout, stderr, batch, plan, output):
    if (
        max(stdout["bytes"], stderr["bytes"]) > MAX_OUTPUT_BYTES
        or code == -signal.SIGXFSZ
    ):
        raise ValueError("Diagnostic output exceeds the collector byte cap")
    if code in (0, 1):
        outcomes = adapter.check_result(
            read_bounded(output / stdout["path"], MAX_OUTPUT_BYTES), batch, plan
        )
        failed = any(row["status"] in ("failed", "invalid_input") for row in outcomes)
        if code != int(failed):
            raise ValueError("Result statuses disagree with process exit code")


def _sync_file(stream):
    stream.flush()
    os.fsync(stream.fileno())


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _append_event(journal, event):
    raw = canonical_bytes(event)
    if journal.tell() + len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError("Journal exceeds its byte cap; execution must stop")
    journal.write(raw)
    _sync_file(journal)


def _durable_document(path, document):
    write_exclusive(path, document, 0o600)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _ledgers(
    plan,
    plan_sha256,
    executable_sha256,
    admission_sha256,
    stage_seconds,
    process_grace_seconds,
    collector_sha256,
    diagnostic_byte_cap,
):
    """Initial complete roster and private metadata, also used by recovery."""
    collection = dict(
        schema_version=adapter.COLLECTION_SCHEMA,
        plan_sha256=plan_sha256,
        batches=[
            dict(
                batch_index=index,
                request_sha256=batch["request_sha256"],
                status="not_run",
                exit_code=None,
                result_sha256=None,
            )
            for index, batch in enumerate(plan["batches"])
        ],
    )
    receipt = dict(
        schema_version="promoter-execution-receipt-1",
        plan_sha256=plan_sha256,
        admission_sha256=admission_sha256,
        acknowledged_reviewed_admission=True,
        executable_sha256=executable_sha256,
        adapter_tool_sha256=adapter.tool_sha256(),
        collector_tool_sha256=collector_sha256,
        manifest_sha256=plan["manifest_sha256"],
        package_consistency="root-reviewed admission responsibility; not verified here",
        stage_seconds=stage_seconds,
        process_grace_seconds=process_grace_seconds,
        diagnostic_byte_cap=diagnostic_byte_cap,
        stop_reason=None,
        validation_failure=None,
        batches=[
            dict(
                entry,
                argv=None,
                duration_seconds=None,
                timeout_seconds=None,
                reason="not_started",
                stdout=None,
                stderr=None,
            )
            for entry in collection["batches"]
        ],
    )
    return collection, receipt


def _argv(executable, request_path, settings):
    argv = [
        str(executable),
        str(request_path),
        "--format",
        "json",
        "--seconds-per-record",
        str(settings["seconds_per_record"]),
        "--seconds-per-batch",
        str(settings["seconds_per_batch"]),
    ]
    for key, option in (
        ("cli_calibration", "--calibration"),
        ("cli_states", "--states"),
    ):
        if settings[key] is not None:
            argv.extend((option, settings[key]))
    return argv


def collect(
    plan_path,
    plan_sha256,
    executable,
    executable_sha256,
    admission_path,
    admission_sha256,
    acknowledge_reviewed_admission,
    stage_seconds,
    process_grace_seconds,
    output,
    *,
    clock=time.monotonic,
    runner=subprocess.run,
):
    """Execute a prevalidated plan once; return false on collector validation failure.

    Process failures retain diagnostics and may continue. Timeout, launch error,
    malformed output and stage expiry stop execution. The complete planned roster
    is always saved after execution; filesystem errors propagate without retries.
    """
    if acknowledge_reviewed_admission is not True:
        raise ValueError("Explicit reviewed admission acknowledgement is required")
    _seconds(stage_seconds, 3600)
    _seconds(process_grace_seconds, 60, zero=True)
    plan, requests = check_plan(
        _pinned(plan_path, plan_sha256, adapter.MAX_PLAN_BYTES, "Plan")
    )
    admission = strict_json(
        _pinned(admission_path, admission_sha256, MAX_ADMISSION_BYTES, "Admission")
    )
    if not isinstance(admission, dict) or not admission:
        raise ValueError("Admission must be a nonempty JSON object")
    executable = Path(executable).absolute()
    _executable(executable, executable_sha256)
    output = Path(output).absolute()
    output.mkdir(mode=0o700)  # Exclusive directory creation: no resume or reuse.
    os.chmod(output, stat.S_IRWXU)
    settings = plan["manifest"]["settings"]
    collection, receipt = _ledgers(
        plan,
        plan_sha256,
        executable_sha256,
        admission_sha256,
        stage_seconds,
        process_grace_seconds,
        digest(Path(__file__).read_bytes()),
        MAX_OUTPUT_BYTES,
    )
    with _open_private(output / JOURNAL_NAME) as journal:
        _append_event(
            journal,
            dict(
                event="initialized",
                schema_version=JOURNAL_SCHEMA,
                plan=plan,
                receipt=receipt,
                executable=str(executable),
                output=str(output),
            ),
        )
        _sync_directory(output)
        _sync_directory(output.parent)
        start = clock()
        for index, (batch, raw) in enumerate(
            zip(plan["batches"], requests, strict=True)
        ):
            entry, detail = collection["batches"][index], receipt["batches"][index]
            request_path = output / f"request-{index:06d}.json"
            with _open_private(request_path) as stream:
                stream.write(raw)
                _sync_file(stream)
            argv = _argv(executable, request_path, settings)
            remaining = stage_seconds - (clock() - start)
            if remaining <= 0:
                receipt["stop_reason"] = "stage_expired"
                break
            timeout = min(
                remaining, settings["seconds_per_batch"] + process_grace_seconds
            )
            stdout_path, stderr_path = (
                output / f"{name}-{index:06d}.bin" for name in ("stdout", "stderr")
            )
            detail.update(argv=argv, timeout_seconds=timeout)
            before = clock()
            with (
                _open_private(stdout_path) as stdout,
                _open_private(stderr_path) as stderr,
            ):
                _append_event(
                    journal,
                    dict(
                        event="started",
                        batch_index=index,
                        argv=argv,
                        timeout_seconds=timeout,
                    ),
                )
                _sync_directory(output)
                code, reason = _attempt(argv, timeout, stdout, stderr, runner)
                detail["duration_seconds"] = clock() - before
                _append_event(
                    journal,
                    dict(
                        event="observed",
                        batch_index=index,
                        actual_exit_code=code if reason is None else None,
                        synthetic_exit_code=code if reason is not None else None,
                        reason=reason,
                        duration_seconds=detail["duration_seconds"],
                    ),
                )
                _sync_file(stdout)
                _sync_file(stderr)
            entry.update(
                status=_process_status(code),
                exit_code=code,
            )
            detail.update(
                stdout=_diagnostic(stdout_path), stderr=_diagnostic(stderr_path)
            )
            if code in (0, 1):
                entry["result_sha256"] = detail["stdout"]["sha256"]
            try:
                _validate_output(
                    code, detail["stdout"], detail["stderr"], batch, plan, output
                )
            except (
                ValueError,
                UnicodeError,
                RecursionError,
                KeyError,
                TypeError,
                IndexError,
                OverflowError,
            ) as error:
                reason = "collector_validation_failed"
                receipt["validation_failure"] = str(error)
            detail.update(entry, reason=reason or _process_reason(code))
            _append_event(
                journal,
                dict(
                    event="finished",
                    batch_index=index,
                    detail=detail,
                    validation_failure=receipt["validation_failure"],
                ),
            )
            if reason is not None:
                receipt["stop_reason"] = reason
                break
        receipt["duration_seconds"] = clock() - start
        receipt["collection_sha256"] = document_sha256(collection)
        _durable_document(output / "collection.json", collection)
        _durable_document(output / "execution-receipt.json", receipt)
        _sync_directory(output)
        _append_event(
            journal,
            dict(
                event="finalized",
                collection_sha256=document_sha256(collection),
                receipt_sha256=document_sha256(receipt),
                duration_seconds=receipt["duration_seconds"],
                stop_reason=receipt["stop_reason"],
                validation_failure=receipt["validation_failure"],
            ),
        )
        return receipt["validation_failure"] is None


def _journal_header(header):
    adapter._exact_keys(
        header,
        (
            "event",
            "schema_version",
            "plan",
            "receipt",
            "executable",
            "output",
        ),
        "journal initialization",
    )
    adapter._same(
        [header["event"], header["schema_version"]],
        ["initialized", JOURNAL_SCHEMA],
        "journal schema",
    )
    plan, _ = check_plan(canonical_bytes(header["plan"]))
    receipt = header["receipt"]
    for key in (
        "plan_sha256",
        "executable_sha256",
        "admission_sha256",
        "collector_tool_sha256",
    ):
        checked_hash(receipt[key])
    adapter._same(receipt["plan_sha256"], document_sha256(plan), "journal plan")
    _seconds(receipt["stage_seconds"], 3600)
    _seconds(receipt["process_grace_seconds"], 60, zero=True)
    adapter._int(
        receipt["diagnostic_byte_cap"], "diagnostic cap", 1, adapter.MAX_RESULT_BYTES
    )
    collection, expected = _ledgers(
        plan,
        receipt["plan_sha256"],
        receipt["executable_sha256"],
        receipt["admission_sha256"],
        receipt["stage_seconds"],
        receipt["process_grace_seconds"],
        receipt["collector_tool_sha256"],
        receipt["diagnostic_byte_cap"],
    )
    adapter._same(receipt, expected, "initial receipt")
    for key in ("executable", "output"):
        if not isinstance(header[key], str) or not Path(header[key]).is_absolute():
            raise ValueError("Journal paths must be absolute")
    return plan, collection, receipt


def _observed(event):
    adapter._exact_keys(
        event,
        (
            "event",
            "batch_index",
            "actual_exit_code",
            "synthetic_exit_code",
            "reason",
            "duration_seconds",
        ),
        "observed event",
    )
    actual, synthetic, reason = (
        event[key]
        for key in (
            "actual_exit_code",
            "synthetic_exit_code",
            "reason",
        )
    )
    if reason is None:
        if type(actual) is not int or synthetic is not None:
            raise ValueError("Observed process return requires its actual exit code")
        code = actual
    else:
        expected = {"timeout": -9, "launch_error": -1}
        if reason not in expected or actual is not None or type(synthetic) is not int:
            raise ValueError("Invalid synthetic process observation")
        adapter._same(synthetic, expected[reason], "synthetic exit")
        code = synthetic
    _seconds(event["duration_seconds"], math.inf, zero=True)
    return code


def _finished(event, row, initial, cap):
    adapter._exact_keys(
        event,
        ("event", "batch_index", "detail", "validation_failure"),
        "finished event",
    )
    detail, failure = event["detail"], event["validation_failure"]
    adapter._exact_keys(detail, initial, "finished detail")
    if failure is not None and (not isinstance(failure, str) or not failure):
        raise ValueError("Invalid collector validation failure")
    code = row["exit_code"]
    for key in (
        "batch_index",
        "request_sha256",
        "argv",
        "timeout_seconds",
        "duration_seconds",
        "exit_code",
    ):
        adapter._same(detail[key], row[key], "finished " + key)
    adapter._same(detail["status"], _process_status(code), "process status")
    for name in ("stdout", "stderr"):
        diagnostic = detail[name]
        adapter._exact_keys(diagnostic, ("path", "bytes", "sha256"), "diagnostic")
        adapter._same(
            diagnostic["path"],
            f"{name}-{row['batch_index']:06d}.bin",
            "diagnostic path",
        )
        adapter._int(diagnostic["bytes"], "diagnostic bytes", 0, MAX_JOURNAL_BYTES)
        if diagnostic["bytes"] > cap:
            adapter._same(diagnostic["sha256"], None, "oversize diagnostic hash")
            if failure is None:
                raise ValueError("Oversize diagnostics require validation failure")
        else:
            checked_hash(diagnostic["sha256"])
    adapter._same(
        detail["result_sha256"],
        detail["stdout"]["sha256"] if code in (0, 1) else None,
        "finished result hash",
    )
    reason = (
        "collector_validation_failed"
        if failure is not None
        else (row["reason"] or _process_reason(code))
    )
    adapter._same(detail["reason"], reason, "finished reason")
    return detail, failure


def _final_artifacts(output, event):
    try:
        return all(
            digest(read_bounded(output / name, MAX_JOURNAL_BYTES)) == event[key]
            for name, key in (
                ("collection.json", "collection_sha256"),
                ("execution-receipt.json", "receipt_sha256"),
            )
        )
    except (OSError, ValueError):
        return False


def _recover(events, truncated, output):
    header = events[0]
    plan, collection, receipt = _journal_header(header)
    rows = [
        dict(
            detail,
            actual_exit_code=None,
            synthetic_exit_code=None,
            validation_state="not_started",
            process_status="not_run",
        )
        for detail in receipt["batches"]
    ]
    phase, index, stop, failure, artifacts = "idle", 0, None, None, False
    settings = plan["manifest"]["settings"]
    for event in events[1:]:
        kind = event["event"]
        if kind == "finalized":
            adapter._exact_keys(
                event,
                (
                    "event",
                    "collection_sha256",
                    "receipt_sha256",
                    "duration_seconds",
                    "stop_reason",
                    "validation_failure",
                ),
                "finalized event",
            )
            if phase not in ("idle", "finished"):
                raise ValueError(
                    "Finalization before a finished attempt or after finalization"
                )
            expected_stop = stop or ("stage_expired" if index < len(rows) else None)
            adapter._same(
                [event["stop_reason"], event["validation_failure"]],
                [expected_stop, failure],
                "final stop",
            )
            _seconds(event["duration_seconds"], math.inf, zero=True)
            receipt.update(
                duration_seconds=event["duration_seconds"],
                collection_sha256=document_sha256(collection),
                stop_reason=expected_stop,
                validation_failure=failure,
            )
            adapter._same(
                event["collection_sha256"],
                document_sha256(collection),
                "final collection",
            )
            adapter._same(
                event["receipt_sha256"], document_sha256(receipt), "final receipt"
            )
            artifacts = _final_artifacts(output, event)
            phase = "finalized"
            continue
        if index >= len(rows) or phase == "finalized":
            raise ValueError("Event after the final planned batch or finalization")
        adapter._same(event["batch_index"], index, "journal batch order")
        row = rows[index]
        if kind == "started":
            adapter._exact_keys(
                event,
                ("event", "batch_index", "argv", "timeout_seconds"),
                "started event",
            )
            if phase not in ("idle", "finished") or stop is not None:
                raise ValueError("Attempt started out of order or after a stop")
            adapter._same(
                event["argv"],
                _argv(
                    header["executable"],
                    Path(header["output"]) / f"request-{index:06d}.json",
                    settings,
                ),
                "started argv",
            )
            _seconds(
                event["timeout_seconds"],
                min(
                    receipt["stage_seconds"],
                    settings["seconds_per_batch"] + receipt["process_grace_seconds"],
                ),
            )
            row.update(
                argv=event["argv"],
                timeout_seconds=event["timeout_seconds"],
                status="interrupted_unknown",
                process_status="interrupted_unknown",
                validation_state="unfinished",
                reason="unmatched_start",
            )
            phase = "started"
        elif kind == "observed":
            if phase != "started":
                raise ValueError("Observation without an unmatched start")
            code = _observed(event)
            status = "returned_unvalidated" if code in (0, 1) else _process_status(code)
            row.update(
                actual_exit_code=event["actual_exit_code"],
                synthetic_exit_code=event["synthetic_exit_code"],
                exit_code=code,
                status=status,
                process_status=_process_status(code),
                reason=event["reason"],
                duration_seconds=event["duration_seconds"],
            )
            phase = "observed"
        elif kind == "finished":
            if phase != "observed":
                raise ValueError("Finished validation without an observed process")
            detail, failure = _finished(
                event, row, receipt["batches"][index], receipt["diagnostic_byte_cap"]
            )
            row.update(detail, validation_state="rejected" if failure else "validated")
            if failure is not None:
                row["status"] = "validation_failed"
            receipt["batches"][index] = detail
            collection["batches"][index] = {
                key: detail[key] for key in adapter.COLLECTED_BATCH_KEYS
            }
            if detail["reason"] in (
                "timeout",
                "launch_error",
                "collector_validation_failed",
            ):
                stop = detail["reason"]
            index += 1
            phase = "finished"
        else:
            raise ValueError("Unknown journal event")
    finalized = phase == "finalized"
    ready = finalized and artifacts and not truncated and failure is None
    return dict(
        schema_version="promoter-execution-recovery-1",
        plan_sha256=receipt["plan_sha256"],
        identities={
            key: value for key, value in header["receipt"].items() if key != "batches"
        },
        planned_batches=[
            {key: value for key, value in batch.items() if key != "request"}
            for batch in plan["batches"]
        ],
        batches=rows,
        truncated=truncated,
        finalized=finalized,
        adaptation_ready=ready,
        normal_adaptation_blocked=not ready,
        blocking_reason=(
            "truncated_journal"
            if truncated
            else "unfinished_journal"
            if not finalized
            else "final_artifacts_missing_or_mismatched"
            if not artifacts
            else "collector_validation_failed"
            if failure is not None
            else None
        ),
    )


def recover(output):
    """Read journal evidence only; never resume, launch or synthesize a collection.

    Unknown actual exits stay null. Complete returned observations are distinct
    from finished validation. A missing finalization, missing/mismatched final
    artifact, validation failure or truncated tail blocks normal adaptation.
    A complete malformed entry rejects recovery; only an unterminated last line
    is ignored and explicitly flagged. Adapter validation of raw result files
    remains required even when the journal permits adaptation.
    """
    raw = read_bounded(Path(output) / JOURNAL_NAME, MAX_JOURNAL_BYTES)
    lines = raw.split(b"\n")
    events = []
    for line in lines[:-1]:
        event = strict_json(line)
        if canonical_bytes(event) != line + b"\n":
            raise ValueError("Journal entries must be canonical JSONL")
        events.append(event)
    if not events:
        raise ValueError(
            "No complete journal initialization; no attempt was authorized"
        )
    try:
        return _recover(events, bool(lines[-1]), Path(output))
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("Malformed journal structure") from error


def main(argv=None):
    """Collect privately; stdout never contains process outcomes or metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("admission", type=Path)
    parser.add_argument("output", type=Path)
    for field in ("plan", "executable", "admission"):
        parser.add_argument(f"--{field}-sha256", required=True)
    parser.add_argument(
        "--acknowledge-reviewed-admission", action="store_true", required=True
    )
    parser.add_argument("--stage-seconds", type=float, required=True)
    parser.add_argument("--process-grace-seconds", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        valid = collect(
            args.plan,
            args.plan_sha256,
            args.executable,
            args.executable_sha256,
            args.admission,
            args.admission_sha256,
            args.acknowledge_reviewed_admission,
            args.stage_seconds,
            args.process_grace_seconds,
            args.output,
        )
    except OSError as error:
        print(
            f"Collection refused: I/O failed (errno {error.errno}); "
            "journal may be incomplete.",
            file=sys.stderr,
        )
        return 1
    except (ValueError, UnicodeError, RecursionError):
        print(
            "Collection refused; check private inputs and output permissions.",
            file=sys.stderr,
        )
        return 1
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

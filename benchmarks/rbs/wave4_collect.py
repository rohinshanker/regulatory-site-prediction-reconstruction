"""Bounded input-only inference collection with exclusive private receipts.

Commands consume one JSON request on stdin and emit one normalized JSON result.
This module never reads experimental measurements or imports a scoring model.
"""

import argparse
import concurrent.futures as futures
import errno
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.new_data import public_split
from benchmarks.rbs.wave4_metrics import STATUSES, indexed

THREAD_ENV = {
    name: "1"
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
}


def encoded(value):
    """Canonical finite JSON bytes for request/configuration identity."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def checked_bytes(spec):
    """Check exact bytes without parsing or printing artifact contents."""
    raw = Path(spec["path"]).read_bytes()
    if digest(raw) != spec["sha256"]:
        raise ValueError("Artifact hash mismatch")
    return raw


def private_bytes(path, raw):
    """Create once with0600, without a permissive intermediate file."""
    with os.fdopen(
        os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
    ) as stream:
        stream.write(raw)


def verify(receipt):
    """Require acknowledged freezes and bind input, split, config and artifacts."""
    if (
        receipt["schema_version"] != "rbs-wave4-receipt-1"
        or receipt["evaluation_authorized"] is not True
    ):
        raise ValueError("Evaluation is not authorized by a frozen receipt")
    if any(
        not isinstance(receipt["acknowledgements"][who], str)
        or not receipt["acknowledgements"][who]
        for who in ("A_protocol", "B_candidate")
    ):
        raise ValueError("Both protocol/candidate acknowledgements are required")
    if receipt["collector_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("Collector implementation differs from freeze")
    checked_bytes(receipt["candidate_receipt"])
    protocol = json.loads(checked_bytes(receipt["protocol"]))
    raw = checked_bytes(receipt["inputs"])
    inputs = json.loads(raw)
    split = json.loads(checked_bytes(receipt["split"]))
    if (
        digest(raw) != protocol["input_file_sha256"]
        or receipt["split"]["sha256"] != protocol["split_file_sha256"]
        or public_split(inputs) != split
    ):
        raise ValueError("Input/selection split differs from protocol")
    rows = list(indexed(inputs["records"]).values())
    for row in rows:
        if (
            row["study"] not in {"Cambray2018", "Kuo2020"}
            or digest(row["sequence"]) != row["sequence_sha256"]
        ):
            raise ValueError("Unknown study or changed sequence")
    configs = list(indexed(receipt["configurations"]).values())
    kinds = {"mechanistic", "ostir", "rebeca", "learned", "constant", "gc_content"}
    if (
        not configs
        or sum(c["kind"] not in {"constant", "gc_content"} for c in configs)
        > protocol["collection"]["roster_max_excluding_controls"]
    ):
        raise ValueError("Configuration roster is empty or exceeds cap")
    for config in configs:
        if config["kind"] not in kinds:
            raise ValueError("Unknown configuration kind")
        if config["kind"] not in {"constant", "gc_content"}:
            if (
                not config["command"]
                or not all(isinstance(x, str) and x for x in config["command"])
                or not config["artifacts"]
            ):
                raise ValueError("External command and artifact pins required")
            if any(
                k not in {*THREAD_ENV, "PYTHONPATH", "REGSITE_RNASTRUCTURE"}
                for k in config["environment"]
            ):
                raise ValueError("Undeclared execution environment key")
            for artifact in config["artifacts"]:
                checked_bytes(artifact)
    primary = receipt["primary"]
    named = {c["id"]: c for c in configs}
    if (
        primary["reference"] == primary["contender"]
        or not {primary["reference"], primary["contender"]} <= named.keys()
    ):
        raise ValueError("Primary contrast identities are missing or equal")
    reference, contender = named[primary["reference"]], named[primary["contender"]]
    backend = receipt["new_backend"]
    selected_backend = "rnastructure-6.6-traceback-2"
    if backend is not None:
        if backend["accepted_before_freeze"] is not True:
            raise ValueError("New backend lacks pre-final admission")
        selected_backend = backend["id"]
    profiles = ("standby2014", "joint_standby")
    if primary["mode"] == "fallback":
        if not primary["fallback_consumption_acknowledgement"]:
            raise ValueError("Fallback consumption requires explicit acknowledgement")
        profiles = ("historical", "standby2014")
        selected_backend = "rnastructure-6.6-traceback-2"
    elif primary["mode"] != "joint":
        raise ValueError("Unknown primary contrast mode")
    if any(
        c["kind"] != "mechanistic"
        or c["profile"] != p
        or c["backend"] != selected_backend
        for c, p in zip((reference, contender), profiles, strict=True)
    ):
        raise ValueError("Primary profile/backend contract changed")
    limits = protocol["collection"]
    if (
        type(limits["max_processes"]) is not int
        or not 1 <= limits["max_processes"] <= 2
        or any(
            not finite_number(limits[k]) or limits[k] <= 0
            for k in ("seconds_per_record", "total_seconds")
        )
    ):
        raise ValueError("Invalid collection limits")
    return protocol, rows, configs


def request(row):
    """Use explicit supplied starts and configuration-only host metadata."""
    return {
        "id": row["id"],
        "sequence": row["sequence"],
        "start_positions": [row["start"]],
        "strand": "+",
        "anti_sd": "ACCUCCUUA",
        "temperature_c": 37,
        "host": "Escherichia coli MDS42 delta-recA (configuration only)"
        if row["study"] == "Cambray2018"
        else "Escherichia coli MG1655 (configuration only)",
    }


def schedule(rows, configs):
    """Deterministic complete record-major roster with rotated model priority."""
    ordered = sorted(configs, key=lambda c: c["id"])
    jobs: list = []
    for study in ("Cambray2018", "Kuo2020"):
        selected = sorted(
            (r for r in rows if r["study"] == study), key=lambda r: r["id"]
        )
        for index, row in enumerate(selected):
            offset = index % len(ordered)
            jobs.extend((row, c) for c in ordered[offset:] + ordered[:offset])
    return jobs


def normalized(raw, packet):
    """Require exact request echo and null failure scores; ignore no failures."""
    result = json.loads(raw)
    status, score = result["status"], result["predicted"]
    if (
        result["id"] != json.loads(packet)["id"]
        or result["input_sha256"] != digest(packet)
        or status not in STATUSES - {"timeout", "not_run"}
        or (not finite_number(score) if status == "ok" else score is not None)
        or not isinstance(result["reason"], str)
    ):
        raise ValueError("Invalid normalized inference result")
    return {"status": status, "predicted": score, "reason": result["reason"]}


def stop_process(anchor):
    """Signal only a group whose dedicated anchor has not been reaped.

    Never poll/wait the anchor before this call: its unreaped PID prevents group
    ID reuse even when the command and all its descendants have exited.
    """
    if anchor.returncode is not None:
        raise ChildProcessError(errno.ECHILD, "Process group ownership released")
    try:
        os.killpg(anchor.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def pump(process, selector, capture, deadline):
    """Exchange input/output without losing captured prefixes on an OS error."""
    while selector.get_map() or process.poll() is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "timeout"
        for key, _ in selector.select(min(remaining, 0.05)):
            label = key.data
            try:
                if label == "stdin":
                    try:
                        count = os.write(key.fd, capture["stdin"][:4096])
                        del capture["stdin"][:count]
                    except BrokenPipeError:
                        capture["stdin"].clear()
                    if not capture["stdin"]:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    chunk = os.read(key.fd, 65_536)
                    capture[label].extend(chunk)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        capture[label + "_complete"] = True
            except BlockingIOError:
                continue
    return "completed"


def run_process(config, packet, deadline):
    """Keep an unreaped group anchor through capture, teardown and diagnostics.

    One extra stdlib process holds the group identity. No model is imported;
    the command, cwd and environment remain explicit. Cleanup gets a bounded
    one-second drain/wait allowance per operation, separate from execution.
    """
    capture: dict = {
        "stdin": bytearray(packet),
        "stdout": bytearray(),
        "stderr": bytearray(),
    }
    capture.update(stdout_complete=False, stderr_complete=False)
    details: dict = {"started": False, "pid": None, "pgid": None, "errors": []}
    anchor = process = selector = None
    event, phase = "process_start", "capture_setup"

    def error(where, exc):
        details["errors"].append(
            {
                "phase": where,
                "type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
            }
        )

    def close(stream, where):
        try:
            stream.close()
        except OSError as exc:
            error(where, exc)

    env = {"PATH": os.defpath, "LANG": "C.UTF-8", **config["environment"], **THREAD_ENV}
    try:
        selector = selectors.DefaultSelector()
        phase = "anchor_start"
        anchor = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", "import sys;sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=config["cwd"],
            process_group=0,
        )
        details["pgid"] = anchor.pid
        phase = "process_start"
        process = subprocess.Popen(
            config["command"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=config["cwd"],
            process_group=anchor.pid,
        )
        details.update(started=True, pid=process.pid)
        event, phase = "process_io", "pipe_setup"
        for label in ("stdout", "stderr", "stdin"):
            stream = getattr(process, label)
            os.set_blocking(stream.fileno(), False)
            selector.register(
                stream,
                selectors.EVENT_WRITE if label == "stdin" else selectors.EVENT_READ,
                label,
            )
        phase = "communication"
        event = pump(process, selector, capture, deadline)
    except (OSError, ValueError) as exc:
        error(phase, exc)
    finally:
        details["primary_event"] = event
        initial_errors = len(details["errors"])
        if anchor is not None:
            try:
                stop_process(anchor)
            except OSError as exc:
                error("cleanup_signal", exc)
        if process is not None:
            try:
                if pump(process, selector, capture, time.monotonic() + 1) == "timeout":
                    error(
                        "cleanup_drain", subprocess.TimeoutExpired(config["command"], 1)
                    )
            except (OSError, ValueError) as exc:
                error("cleanup_drain", exc)
            try:
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired) as exc:
                error("cleanup_wait", exc)
            for stream in (process.stdin, process.stdout, process.stderr):
                close(stream, "cleanup_pipe_close")
        if selector is not None:
            close(selector, "cleanup_selector_close")
        if anchor is not None:
            close(anchor.stdin, "cleanup_anchor_close")
            try:
                anchor.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired) as exc:
                error("cleanup_anchor_wait", exc)
        details["cleanup_complete"] = len(details["errors"]) == initial_errors
    details.update(
        stdout_complete=capture["stdout_complete"],
        stderr_complete=capture["stderr_complete"],
    )
    if not details["cleanup_complete"]:
        event = "process_cleanup"
    return (
        event,
        None if process is None else process.returncode,
        bytes(capture["stdout"]),
        bytes(capture["stderr"]),
        details,
    )


def control_score(row, kind):
    """Fixed outcome-independent controls, also rechecked during evidence audit."""
    seq = row["sequence"][max(0, row["start"] - 35) : row["start"] + 70]
    return 1.0 if kind == "constant" else sum(b in "GC" for b in seq) / len(seq)


def execute(
    row,
    config,
    seconds,
    deadline,
    directory,
    number,
    not_run_reason="collection_deadline",
):
    """Run one input, preserve raw evidence and never retry a failed prediction."""
    began = time.monotonic()
    remaining = deadline - began
    packet = encoded(request(row))
    result = {
        "id": row["id"],
        "input_sha256": digest(packet),
        "configuration_sha256": digest(encoded(config)),
        "status": "not_run",
        "predicted": None,
        "reason": not_run_reason,
        "seconds": 0,
        "execution": "not_run",
        "exit_code": None,
        "process": None,
    }
    stdout, stderr = b"", b""
    if remaining > 0:
        if config["kind"] in {"constant", "gc_content"}:
            result.update(
                status="ok",
                predicted=control_score(row, config["kind"]),
                reason="",
                execution="control",
            )
        else:
            event, code, stdout, stderr, details = run_process(
                config, packet, min(began + seconds, deadline)
            )
            details["timeout_reason"] = (
                ("record_deadline" if seconds < remaining else "collection_deadline")
                if details["primary_event"] == "timeout"
                else None
            )
            result.update(exit_code=code, process=details)
            if event == "timeout":
                result.update(
                    status="timeout",
                    execution="timeout",
                    reason="record_deadline"
                    if seconds < remaining
                    else "collection_deadline",
                )
            elif event != "completed":
                result.update(status="failed", reason=event, execution=event)
            elif code:
                result.update(
                    status="failed", reason="process_exit", execution="process_exit"
                )
            else:
                try:
                    result.update(normalized(stdout, packet))
                    result["execution"] = "returned"
                except (ValueError, KeyError, TypeError, OverflowError):
                    result.update(
                        status="failed",
                        reason="invalid_output",
                        execution="invalid_output",
                    )
        result["seconds"] = time.monotonic() - began
    result.update(stdout_sha256=digest(stdout), stderr_sha256=digest(stderr))
    stem = directory / f"job-{number:06d}"
    private_bytes(stem.with_suffix(".stdout"), stdout)
    private_bytes(stem.with_suffix(".stderr"), stderr)
    private_bytes(stem.with_suffix(".json"), encoded(result))
    return result


def collect(receipt_path, directory):
    """Collect every configuration before any label join; preserve incomplete work."""
    raw_receipt = receipt_path.read_bytes()
    receipt = json.loads(raw_receipt)
    protocol, rows, configs = verify(receipt)
    directory.mkdir(mode=0o700)
    private_bytes(directory / "freeze.json", raw_receipt)
    private_bytes(directory / "protocol.json", checked_bytes(receipt["protocol"]))
    began = time.monotonic()
    started = datetime.now(UTC).isoformat()
    limits = protocol["collection"]
    deadline = began + limits["total_seconds"]
    jobs = schedule(rows, configs)
    results = {}
    cursor = 0
    cleanup_failed = False
    with futures.ThreadPoolExecutor(max_workers=limits["max_processes"]) as pool:
        active: dict = {}
        while cursor < len(jobs) or active:
            while (
                cursor < len(jobs)
                and not cleanup_failed
                and len(active) < limits["max_processes"]
                and time.monotonic() < deadline
            ):
                row, config = jobs[cursor]
                active[
                    pool.submit(
                        execute,
                        row,
                        config,
                        limits["seconds_per_record"],
                        deadline,
                        directory,
                        cursor,
                    )
                ] = cursor
                cursor += 1
            if not active:
                break
            done, _ = futures.wait(active, return_when=futures.FIRST_COMPLETED)
            for future in done:
                number = active.pop(future)
                results[number] = future.result()
                details = results[number].get("process")
                if details is not None and not details["cleanup_complete"]:
                    cleanup_failed = True
    for number in range(cursor, len(jobs)):
        row, config = jobs[number]
        results[number] = execute(
            row,
            config,
            limits["seconds_per_record"],
            float("-inf"),
            directory,
            number,
            "collection_cleanup_failure" if cleanup_failed else "collection_deadline",
        )
    # A changed file invalidates collection; it is never silently relabelled.
    valid = True
    try:
        verify(receipt)
        if receipt_path.read_bytes() != raw_receipt:
            valid = False
    except (OSError, ValueError):
        valid = False
    model_records: dict = {c["id"]: [] for c in configs}
    for number, (_, config) in enumerate(jobs):
        model_records[config["id"]].append(results[number])
    complete = (
        valid
        and not cleanup_failed
        and not any(r["reason"] == "collection_deadline" for r in results.values())
    )
    payload = {
        "schema_version": "rbs-wave4-collection-1",
        "complete": complete,
        "artifacts_unchanged": valid,
        "cleanup_complete": not cleanup_failed,
        "freeze_sha256": digest(raw_receipt),
        "protocol_sha256": receipt["protocol"]["sha256"],
        "input_sha256": receipt["inputs"]["sha256"],
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "started_utc": started,
        "elapsed_seconds": time.monotonic() - began,
        "records_by_configuration": model_records,
    }
    private_bytes(directory / "collection.json", encoded(payload))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("new_private_directory", type=Path)
    args = parser.parse_args(argv)
    result = collect(args.receipt, args.new_private_directory)
    print(
        json.dumps(
            {
                "complete": result["complete"],
                "collection_sha256": digest(
                    (args.new_private_directory / "collection.json").read_bytes()
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

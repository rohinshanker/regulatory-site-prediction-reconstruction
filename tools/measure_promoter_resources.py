"""Measure synthetic Promoter requests through the public API, without tuning it.

Development tool; stdlib only. Run with PYTHONPATH=src:. and the locked Python.
Each measurement uses a fresh interpreter. Parent wall time includes startup,
imports, input decoding, prediction, authoritative serialization and metric
transfer; parent generation/preflight is outside per-child wall time. API time
includes parameter loading and the runtime's own size check;
serialization time measures the additional authoritative encoding used here.
Darwin ru_maxrss is bytes; Linux ru_maxrss is KiB (getrusage(2)). Other platforms
retain the raw value but deliberately do not guess a byte conversion. A killed
child has no RSS/result measurements; null never means zero. Failed API size
checks return no authoritative object, so its byte/count metrics stay null.

Only generated A/C/G/T and fixed-seed GC draws are used. No fixtures, benchmark
outcomes, network, folding process or runtime-limit mutation is involved. Finite
samples cannot establish a worst-case output bound or multi-platform admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from regsite import promoter
from regsite import promoter_io as pio

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = "synthetic-promoter-resources-1"
SEED = 1729
MAX_SECONDS = 1800.0


def digest(data: bytes) -> str:
    """Hash literal bytes, including any authoritative trailing LF."""
    return hashlib.sha256(data).hexdigest()


def scenarios(limits: dict) -> dict[str, dict]:
    """Prespecify ceiling probes and a smaller grid from the same generator.

    Ceiling probes never silently shrink when runtime limits change. An extra
    effective probe adapts to revised site/length limits, retaining both settings
    and the full effective limits in the receipt.
    """
    specs: dict[str, dict] = {}

    def add(name, lengths, counts, *, dna="gc50", states="selected", verbose=False):
        specs[name] = {
            "lengths": lengths,
            "sites": counts,
            "dna": dna,
            "states": states,
            "verbose": verbose,
            "seed": SEED,
            "edge_tss": None,
        }

    for dna in ("A", "C", "G", "T", "gc20", "gc50", "gc80"):
        add(f"record-{dna}", [5000], [5000], dna=dna)
    add("batch-records-bases", [1000] * 100, [2] * 100)
    for total in (2000, 4000, 8000, 20000):
        add(f"verbose-{total}", [5000] * 4, [total // 4] * 4, verbose=True)
    add("all-record", [5000], [100], states="all", verbose=True)
    add("all-batch", [5000] * 4, [100, 100, 100, 34], states="all", verbose=True)
    # 333 full sites * 30 + one partial site * 10 == 10,000 states.
    specs["all-batch"]["edge_tss"] = 61
    length = min(5000, int(limits["max_normalized_bases_per_record"]))
    count = min(5000, int(limits["max_planned_sites_per_record"]), 2 * length)
    add("effective-record", [length], [count], verbose=True)
    return specs


def sequence(kind: str, length: int, seed: int) -> str:
    """Use Random.random with explicit thresholds, independent of choice internals."""
    if kind in ("A", "C", "G", "T"):
        return kind * length
    gc = {"gc20": 0.2, "gc50": 0.5, "gc80": 0.8}[kind]
    rng = random.Random(seed)
    result = []
    for _ in range(length):
        draw = rng.random()
        result.append(
            "C"
            if draw < gc / 2
            else "G"
            if draw < gc
            else "A"
            if draw < (1 + gc) / 2
            else "T"
        )
    return "".join(result)


def generate(spec: dict, limits: dict) -> dict:
    """Generate both-strand sites; all-state sites have full context except edge."""
    records = []
    for index, (length, count) in enumerate(
        zip(spec["lengths"], spec["sites"], strict=True)
    ):
        dna = sequence(spec["dna"], length, spec["seed"] + index)
        if spec["states"] == "all":
            points = [(s, f) for f in range(67, length - 67) for s in ("+", "-")]
        else:
            # Centered range includes both strands, exactly count entries.
            start = (length - math.ceil(count / 2)) // 2
            points = [
                (s, f)
                for f in range(start, start + math.ceil(count / 2))
                for s in ("+", "-")
            ]
        points = points[:count]
        if spec["edge_tss"] is not None and index == len(spec["sites"]) - 1:
            points[-1] = ("+", spec["edge_tss"])
        record: dict[str, Any] = {
            "id": f"synthetic-{index}",
            "sequence": dna,
            "calibration": "in_vitro",
            "scan": {
                "mode": "positions",
                "positions": [{"strand": s, "tss": f} for s, f in points],
            },
            "output": {
                "states": spec["states"],
                "elements": True,
                "legacy_keys": spec["verbose"],
            },
        }
        if spec["verbose"]:
            record["id"] += "x" * max(
                0, int(limits["max_id_chars"]) - len(record["id"])
            )
            record["host"] = {"name": "\u754c" * int(limits["max_host_name_chars"])}
            record["metadata"] = {
                "text": "x"
                * max(
                    0,
                    int(limits["max_metadata_json_bytes"])
                    - len(pio.canonical_bytes({"text": ""})),
                )
            }
            record["projection"] = {
                "contig": "\u754c" * int(limits["max_contig_chars"]),
                "origin": 0,
                "contig_length": length,
                "topology": "linear",
                "origin_crossing": False,
                "sequence_strand": "+",
            }
        records.append(record)
    return {"schema_version": "1.0", "records": records}


def preflight(request: dict, limits: dict) -> dict:
    """Independently count requested sites/states and exact ceiling equalities.

    This checks generated resource dimensions, not general runtime validation.
    The public API remains authoritative for admission and record statuses.
    """
    observed: dict[str, int] = {
        "max_input_json_bytes": len(pio.canonical_bytes(request)),
        "max_records_per_batch": len(request["records"]),
    }
    equalities: set[str] = set()
    violations = []
    manifests = []
    total_bases = total_sites = total_states = 0

    def check(key, count):
        observed[key] = max(observed.get(key, 0), count)
        if count == limits[key]:
            equalities.add(key)
        if count > limits[key]:
            violations.append({"limit": key, "observed": count, "maximum": limits[key]})

    for key, value in list(observed.items()):
        check(key, value)
    for record in request["records"]:
        dna = record["sequence"]
        points = record["scan"]["positions"]
        states = sum(
            len(
                promoter.eligible_states(
                    len(dna),
                    p["tss"] if p["strand"] == "+" else len(dna) - 1 - p["tss"],
                )
            )
            for p in points
        )
        total_bases += len(dna)
        total_sites += len(points)
        all_states = states if record["output"]["states"] == "all" else 0
        total_states += all_states
        for key, count in (
            ("max_normalized_bases_per_record", len(dna)),
            ("max_raw_sequence_chars_per_record", len(dna)),
            ("max_planned_sites_per_record", len(points)),
        ):
            check(key, count)
        if record["output"]["states"] == "all":
            check("max_all_state_sites_per_record", len(points))
            check("max_all_states_per_record", states)
        manifests.append(
            {
                "id": record["id"],
                "normalized_sha256": digest(dna.encode()),
                "normalized_bases": len(dna),
                "planned_sites": len(points),
                "eligible_states": states,
                "planned_emitted_states": all_states,
            }
        )
    check("max_normalized_bases_per_batch", total_bases)
    check("max_planned_sites_per_batch", total_sites)
    check("max_all_states_per_batch", total_states)
    return {
        "observed": observed,
        "equalities": sorted(equalities),
        "violations": violations,
        "admitted_dimensions": not violations,
        "records": manifests,
        "planned_sites": total_sites,
        "planned_emitted_states": total_states,
    }


def runtime_identity() -> dict:
    """Pin source files as well as git HEAD: dirty runtime changes remain visible."""
    model, identity = pio.model_identity(promoter.load_parameters())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    paths = [
        "src/regsite/promoter.py",
        "src/regsite/promoter_io.py",
        "src/regsite/data/promoter-parameters-1.json",
        "tools/measure_promoter_resources.py",
    ]
    return {
        "git_head": head,
        "model": model,
        "identity_model": identity,
        "source_sha256": {p: digest((ROOT / p).read_bytes()) for p in paths},
        "limits": dict(pio.LIMITS),
        "api_call": {
            "function": "regsite.promoter_io.predict_batch",
            "seconds_per_record": pio.LIMITS["default_seconds_per_record"],
            "seconds_per_batch": pio.LIMITS["default_seconds_per_batch"],
            "cli_calibration": None,
            "cli_states": None,
            "output_format": "json",
        },
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
    }


def peak_rss() -> dict:
    """Keep the platform unit explicit and include interpreter/import overhead."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multiplier = {"Darwin": 1, "Linux": 1024}.get(platform.system())
    return {
        "raw": raw,
        "unit": {"Darwin": "bytes", "Linux": "KiB"}.get(
            platform.system(), "platform-dependent"
        ),
        "bytes": None if multiplier is None else raw * multiplier,
        "source": "resource.getrusage(RUSAGE_SELF).ru_maxrss",
    }


def measure(request: dict) -> dict:
    """Retain size-cap/setup exceptions instead of inventing lost result metrics."""
    started = time.perf_counter()
    metrics: dict = {
        "status": "setup_error",
        "error": None,
        "authoritative_bytes": None,
        "coverage": None,
        "api_seconds": None,
        "serialization_seconds": None,
    }
    try:
        result = pio.predict_batch(request)
        metrics["api_seconds"] = time.perf_counter() - started
        encoded_at = time.perf_counter()
        encoded = pio.result_bytes(result)
        metrics["serialization_seconds"] = time.perf_counter() - encoded_at
        records = result["results"]
        coverage = {
            key: sum((r["coverage"] or {}).get(key, 0) for r in records)
            for key in (
                "planned_sites",
                "scored_sites",
                "failed_sites",
                "unattempted_sites",
                "insufficient_context_sites",
            )
        }
        complete = result["batch"]["complete"] and all(
            r["status"] in ("ok", "no_candidate")
            and (r["coverage"] or {}).get("complete", False)
            for r in records
        )
        metrics.update(
            status="ok" if complete else "incomplete",
            authoritative_bytes=len(encoded),
            authoritative_sha256=digest(encoded),
            coverage=coverage,
            complete=complete,
            batch=result["batch"],
            record_statuses=[r["status"] for r in records],
            record_reasons=[r["reasons"] for r in records],
            emitted_states=sum(
                len(s.get("states", [])) for r in records for s in r["sites"]
            ),
        )
    except (
        Exception
    ) as exc:  # A measurement failure is a result, not a lost repetition.
        metrics.update(
            error={"type": type(exc).__name__, "message": str(exc)}, complete=False
        )
    metrics["worker_seconds"] = time.perf_counter() - started
    metrics["peak_rss"] = peak_rss()
    return metrics


def run_child(payload: dict, timeout: float) -> dict:
    """One foreground child per repetition, killed and reaped on timeout."""
    command = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    started = time.perf_counter()
    try:
        child = subprocess.run(
            command,
            input=pio.canonical_bytes(payload),
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=ROOT,
        )
        if child.returncode:
            metrics = {
                "status": "process_error",
                "returncode": child.returncode,
                "stderr": child.stderr.decode(errors="replace")[-4000:],
            }
        else:
            metrics = json.loads(child.stdout)
    except subprocess.TimeoutExpired:
        metrics = {"status": "process_timeout", "error": "run budget exhausted"}
    except (OSError, ValueError) as exc:
        metrics = {"status": "execution_error", "error": str(exc)}
    return {
        "authoritative_bytes": None,
        "coverage": None,
        "peak_rss": None,
        "complete": False,
        **metrics,
        "wall_seconds": time.perf_counter() - started,
        "command": command,
    }


def recommend(measurements: list[dict], limits: dict) -> dict:
    """Conservative sampled candidates only; all observed failures remain visible."""
    costs: dict[str, list[float]] = {"selected": [], "all": []}
    bytes_per_site: dict[str, list[float]] = {"selected": [], "all": []}
    for row in measurements:
        count = row["preflight"]["planned_sites"]
        if row["status"] == "ok" and count:
            mode = row["settings"]["states"]
            costs[mode].append(row["wall_seconds"] / count)
            bytes_per_site[mode].append(row["authoritative_bytes"] / count)
    candidates: dict[str, dict | None] = {}
    for mode in costs:
        if not costs[mode]:
            candidates[mode] = None
            continue
        c, b = max(costs[mode]), max(bytes_per_site[mode])
        byte_sites = math.floor(
            min(64 * 1024**2, limits["max_result_json_bytes"]) / 2 / b
        )
        record = min(
            int(limits["max_planned_sites_per_record"]),
            byte_sites,
            math.floor(limits["default_seconds_per_record"] / 2 / c),
        )
        batch = min(
            int(limits["max_planned_sites_per_batch"]),
            byte_sites,
            math.floor(limits["default_seconds_per_batch"] / 2 / c),
        )
        if mode == "all":
            record = min(
                record,
                int(limits["max_all_state_sites_per_record"]),
                int(limits["max_all_states_per_record"]) // 30,
            )
            batch = min(batch, int(limits["max_all_states_per_batch"]) // 30)
        candidates[mode] = {
            "worst_measured_wall_seconds_per_site": c,
            "worst_measured_authoritative_bytes_per_site": b,
            "candidate_sites_per_record": record,
            "candidate_sites_per_batch": batch,
        }
    return {
        "candidates": candidates,
        "caveats": [
            "Finite synthetic samples do not bound all inputs; "
            "no exhaustive maximum claim.",
            "Includes process and serialization overhead; "
            "only this platform/Python measured.",
            "Rejected/failed runs cannot certify capacity. "
            "Candidates require a new measured receipt.",
            "Independent evaluator and coordinator choose final limits; "
            "runtime is never modified.",
        ],
    }


def collect(names: list[str], repetitions: int, budget: float) -> dict:
    """Bound all runs by one monotonic deadline, retaining skipped repetitions."""
    started = time.monotonic()
    identity = runtime_identity()
    specs = scenarios(identity["limits"])
    rows = []
    for name in names:
        spec = specs[name]
        request = generate(spec, identity["limits"])
        plan = preflight(request, identity["limits"])
        payload = {
            "request": request,
            "limits": identity["limits"],
            "identity_model": identity["identity_model"],
        }
        for repetition in range(1, repetitions + 1):
            remaining = budget - (time.monotonic() - started)
            metrics = (
                {"status": "budget_exhausted", "complete": False}
                if remaining <= 0
                else run_child(payload, remaining)
            )
            rows.append(
                {
                    "scenario": name,
                    "repetition": repetition,
                    "settings": spec,
                    "input_sha256": pio.canonical_hash(request),
                    "preflight": plan,
                    **metrics,
                }
            )
    return {
        "receipt_version": 1,
        "generator": GENERATOR,
        "runtime": identity,
        "invocation": sys.argv,
        "repetitions": repetitions,
        "budget_seconds": budget,
        "elapsed_seconds": time.monotonic() - started,
        "measurements": rows,
        "recommendations": recommend(rows, identity["limits"]),
    }


def main(argv: list[str] | None = None) -> int:
    """Write reusable receipts only inside the ignored repository .cache tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--scenario", action="append", choices=list(scenarios(pio.LIMITS))
    )
    parser.add_argument("--budget-seconds", type=float, default=MAX_SECONDS)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".cache/promoter-resources/receipt.json"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        payload = json.load(sys.stdin)
        if (
            payload["limits"] != pio.LIMITS
            or payload["identity_model"]
            != pio.model_identity(promoter.load_parameters())[1]
        ):
            raise ValueError("worker runtime identity differs from parent")
        print(json.dumps(measure(payload["request"]), allow_nan=False))
        return 0
    if not 1 <= args.repetitions <= 10 or not 0 < args.budget_seconds <= MAX_SECONDS:
        parser.error("repetitions must be 1..10 and budget must be finite in (0,1800]")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".cache").resolve()):
        parser.error("receipt output must be inside repository .cache")
    receipt = collect(
        args.scenario or list(scenarios(pio.LIMITS)),
        args.repetitions,
        args.budget_seconds,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pio.result_bytes(receipt))
    print(f"receipt={output} sha256={digest(output.read_bytes())}")
    for row in receipt["measurements"]:
        print(
            f"{row['scenario']} #{row['repetition']}: {row['status']} "
            f"wall={row.get('wall_seconds')} bytes={row.get('authoritative_bytes')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

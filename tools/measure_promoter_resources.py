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

Candidate capacity: --suite candidate --repetitions 3 --budget-seconds 1200 --admit.
Diagnostics: --scenario tight-deadline (expected incomplete, separate receipt),
or --suite diagnostic (immutable original ceilings, often rejected by new caps).
Recheck an existing artifact with --check-receipt PATH; exit 1 means admission
failed. Generation/measurement and the public check_receipt gate are separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import re
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from regsite import promoter
from regsite import promoter_io as pio

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = "synthetic-promoter-resources-3"
SEED = 1729
MAX_SECONDS = 1800.0
SOURCE_PATHS = (
    "src/regsite/promoter.py",
    "src/regsite/promoter_io.py",
    "src/regsite/data/promoter-parameters-1.json",
    "tools/measure_promoter_resources.py",
)
CANDIDATE_SCENARIOS = (
    *(
        f"effective-record-{dna}"
        for dna in ("A", "C", "G", "T", "gc20", "gc50", "gc80")
    ),
    "effective-scan",
    "batch-records-bases",
    "effective-selected-batch",
    "all-2000",
    "mixed-4000-2000",
    "effective-all-sites",
    "effective-mixed",
)
ORIGINAL_SCENARIOS = (
    *(f"record-{dna}" for dna in ("A", "C", "G", "T", "gc20", "gc50", "gc80")),
    "batch-records-bases",
    *(f"verbose-{n}" for n in (2000, 4000, 8000, 20000)),
    "all-record",
    "all-batch",
    "scan-record",
    "mixed-ceiling",
    *(f"all-{n}" for n in (1000, 2000, 3000)),
    *(f"mixed-4000-{n}" for n in (1000, 2000, 3000)),
)


def api_call(limits: dict, **deadlines: float) -> dict:
    """Explicit public API options, including resolved actual deadlines."""
    return {
        "function": "regsite.promoter_io.predict_batch",
        "seconds_per_record": limits["default_seconds_per_record"],
        "seconds_per_batch": limits["default_seconds_per_batch"],
        "cli_calibration": None,
        "cli_states": None,
        "output_format": "json",
        **deadlines,
    }


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
    add("scan-record", [5000], [5000], verbose=True)
    specs["scan-record"]["scan_mode"] = "scan"
    add(
        "mixed-ceiling",
        [1000] * 100,
        [204 + (i < 82) for i in range(96)] + [100, 100, 100, 34],
        states="mixed",
        verbose=True,
    )
    specs["mixed-ceiling"].update(
        output_modes=["selected"] * 96 + ["all"] * 4, edge_tss=61
    )
    for states, edge in ((1000, 61), (2000, 63), (3000, None)):
        all_sites = math.ceil(states / 30)
        add(f"all-{states}", [5000], [all_sites], states="all", verbose=True)
        specs[f"all-{states}"]["edge_tss"] = edge
        selected, extra = divmod(4000 - all_sites, 99)
        add(
            f"mixed-4000-{states}",
            [1000] * 100,
            [selected + (i < extra) for i in range(99)] + [all_sites],
            states="mixed",
            verbose=True,
        )
        specs[f"mixed-4000-{states}"].update(
            output_modes=["selected"] * 99 + ["all"], edge_tss=edge
        )
    length = min(5000, int(limits["max_normalized_bases_per_record"]))
    count = min(5000, int(limits["max_planned_sites_per_record"]), 2 * length)
    add("effective-record", [length], [count], verbose=True)
    for dna in ("A", "C", "G", "T", "gc20", "gc50", "gc80"):
        add(f"effective-record-{dna}", [length], [count], dna=dna, verbose=True)
    # A symmetric scan cannot represent an odd number of sites: expose that
    # count explicitly, never change the effective runtime limit identity.
    add("effective-scan", [length], [count - count % 2], verbose=True)
    specs["effective-scan"]["scan_mode"] = "scan"
    total = int(limits["max_planned_sites_per_batch"])
    per_record = int(limits["max_planned_sites_per_record"])
    selected_counts = [min(per_record, total - i) for i in range(0, total, per_record)]
    add(
        "effective-selected-batch",
        [length] * len(selected_counts),
        selected_counts,
        verbose=True,
    )
    state_budget = min(
        int(limits["max_all_states_per_record"]),
        int(limits["max_all_states_per_batch"]),
        30 * int(limits["max_all_state_sites_per_record"]),
    )
    full, remainder = divmod(state_budget, 30)
    # Greedy partial states at distinct left-edge TSSs; all remaining sites
    # have full context. Settings preserve requested budget and actual positions.
    partial = []
    for t in range(66, 57, -1):
        size = len(promoter.eligible_states(length, t))
        for strand in ("+", "-"):
            if size and size <= remainder:
                partial.append(
                    {"strand": strand, "tss": t if strand == "+" else length - 1 - t}
                )
                remainder -= size
    all_count = full + len(partial)
    add("effective-all-sites", [length], [all_count], states="all", verbose=True)
    specs["effective-all-sites"].update(
        partial_positions=partial,
        extra_empty_sites=max(
            0, int(limits["max_all_state_sites_per_record"]) - all_count
        ),
        requested_state_budget=state_budget,
    )
    mixed_total = total - all_count
    mixed_counts = [
        min(per_record, mixed_total - i) for i in range(0, mixed_total, per_record)
    ]
    add(
        "effective-mixed",
        [length] * (len(mixed_counts) + 1),
        mixed_counts + [all_count],
        states="mixed",
        verbose=True,
    )
    specs["effective-mixed"].update(
        output_modes=["selected"] * len(mixed_counts) + ["all"],
        partial_positions=partial,
        requested_state_budget=state_budget,
    )
    add("tight-deadline", [length], [count], verbose=True)
    specs["tight-deadline"]["deadlines"] = {
        "seconds_per_record": 1e-9,
        "seconds_per_batch": 1e-9,
    }
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
        mode = spec.get("output_modes", [spec["states"]] * len(spec["sites"]))[index]
        if mode == "all":
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
        if mode == "all" and "partial_positions" in spec:
            partial = [(p["strand"], p["tss"]) for p in spec["partial_positions"]]
            points = points[: count - len(partial)] + partial
            points += [
                (s, f)
                for f in range(length)
                for s in ("+", "-")
                if not promoter.eligible_states(
                    length, f if s == "+" else length - 1 - f
                )
            ][: spec.get("extra_empty_sites", 0)]
        record: dict[str, Any] = {
            "id": f"synthetic-{index}",
            "sequence": dna,
            "calibration": "in_vitro",
            "scan": {
                "mode": "positions",
                "positions": [{"strand": s, "tss": f} for s, f in points],
            },
            "output": {
                "states": mode,
                "elements": True,
                "legacy_keys": spec["verbose"],
            },
        }
        if spec.get("scan_mode") == "scan":
            record["scan"] = {
                "mode": "scan",
                "range": [start, start + count // 2],
                "strands": ["+", "-"],
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
        scan = record["scan"]
        points = (
            scan["positions"]
            if scan["mode"] == "positions"
            else [
                {"strand": strand, "tss": f}
                for strand in scan["strands"]
                for f in range(*scan["range"])
            ]
        )
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
    return {
        "git_head": head,
        "model": model,
        "identity_model": identity,
        "source_sha256": {p: digest((ROOT / p).read_bytes()) for p in SOURCE_PATHS},
        "limits": dict(pio.LIMITS),
        "api_call": api_call(pio.LIMITS),
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


def measure(request: dict, **deadlines: float) -> dict:
    """Retain size-cap/setup exceptions instead of inventing lost result metrics."""
    started = time.perf_counter()
    call = api_call(pio.LIMITS, **deadlines)
    metrics: dict = {
        "api_call": call,
        "status": "setup_error",
        "error": None,
        "authoritative_bytes": None,
        "coverage": None,
        "api_seconds": None,
        "serialization_seconds": None,
    }
    try:
        result = pio.predict_batch(
            request,
            seconds_per_record=call["seconds_per_record"],
            seconds_per_batch=call["seconds_per_batch"],
        )
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
        overrun = metrics["api_seconds"] > call["seconds_per_batch"] or (
            len(records) == 1 and metrics["api_seconds"] > call["seconds_per_record"]
        )
        metrics.update(
            status="elapsed_overrun"
            if complete and overrun
            else "ok"
            if complete
            else "incomplete",
            elapsed_overrun=overrun,
            model=result["model"],
            authoritative_bytes=len(encoded),
            authoritative_sha256=digest(encoded),
            coverage=coverage,
            complete=complete and not overrun,
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
        if row["status"] == "ok" and count and row["settings"]["states"] != "mixed":
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
        "joint_samples": [
            {
                "scenario": row["scenario"],
                "repetition": row["repetition"],
                "planned_sites": row["preflight"]["planned_sites"],
                "planned_emitted_states": row["preflight"]["planned_emitted_states"],
                "half_output_compliant": row["status"] == "ok"
                and row["authoritative_bytes"]
                <= min(64 * 1024**2, limits["max_result_json_bytes"]) / 2,
            }
            for row in measurements
            if row["settings"]["states"] == "mixed"
        ],
        "caveats": [
            "Independent selected/all candidates cannot be combined without a mixed "
            "batch receipt: both consume the same output budget.",
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
            "deadlines": spec.get("deadlines", {}),
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


def positive(value: object) -> bool:
    """A finite positive JSON number, excluding booleans."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def check_receipt(
    receipt: object,
    *,
    repetitions: int = 3,
    required_scenarios: tuple[str, ...] = CANDIDATE_SCENARIOS,
    expected_runtime: dict | None = None,
) -> dict:
    """Check measured evidence without running/generating inputs or lowering caps.

    Returns concrete failures and global N*c safety arithmetic. Every included
    sample must be admitted and complete, with measured RSS and default actual
    deadlines. Tight-deadline/old-ceiling failures belong in separate diagnostic
    receipts. Required names and exact repetition IDs prevent partial suites from
    being admitted. expected_runtime optionally binds the evidence to a build;
    Python/platform/executable remain the measured platform's identity.

    This is an evidence consistency gate, not authentication of timing claims or
    a proof that finite synthetic samples bound every possible request.
    """
    failures: list[str] = []
    costs: list[float] = []
    safety: dict = {}
    try:
        if not isinstance(receipt, dict):
            raise ValueError("receipt must be an object")
        identity = receipt["runtime"]
        limits = identity["limits"]
        if set(limits) != set(pio.LIMITS) or any(
            not positive(v)
            or (
                not k.startswith(("default_seconds_", "max_seconds_"))
                and type(v) is not int
            )
            for k, v in limits.items()
        ):
            raise ValueError("runtime must pin all 20 finite positive effective limits")
        if set(identity["model"]) != {
            "id",
            "implementation_version",
            "kind",
            "source",
            "licence",
            "parameters",
            "term_source_names",
            "terms_unit",
            "terms_semantics",
            "source_quirks",
            "not_modeled",
            "claims",
        }:
            failures.append("complete emitted model fields are missing/unknown")
        if (
            not positive(receipt["budget_seconds"])
            or not positive(receipt["elapsed_seconds"])
            or receipt["elapsed_seconds"] > receipt["budget_seconds"]
        ):
            failures.append("measurement elapsed time exceeds budget or is unmeasured")
        expected_identity = {
            "id": identity["model"]["id"],
            "implementation_version": identity["model"]["implementation_version"],
            "source_commit": identity["model"]["source"]["commit"],
            "parameter_json_sha256": identity["model"]["parameters"][
                "parameter_json_sha256"
            ],
            "coefficient_array_sha256": identity["model"]["parameters"]["array_sha256"][
                "coefficients"
            ],
            "intercept_array_sha256": identity["model"]["parameters"]["array_sha256"][
                "intercept"
            ],
        }
        if identity["identity_model"] != expected_identity:
            failures.append("six-key identity does not match complete emitted model")
        if identity["api_call"] != api_call(limits):
            failures.append(
                "runtime actual API options must pin the effective defaults"
            )
        hashes = identity["source_sha256"]
        if set(hashes) != set(SOURCE_PATHS) or any(
            not isinstance(v, str) or re.fullmatch("[0-9a-f]{64}", v) is None
            for v in hashes.values()
        ):
            failures.append("missing/invalid runtime or tool source SHA256")
        for key in ("git_head", "python", "platform", "executable"):
            if not isinstance(identity[key], str) or not identity[key]:
                failures.append(f"missing runtime {key}")
        if expected_runtime is not None:
            for key in (
                "limits",
                "model",
                "identity_model",
                "source_sha256",
                "api_call",
            ):
                if identity[key] != expected_runtime[key]:
                    failures.append(f"runtime {key} differs from expected build")
        if (
            type(receipt["repetitions"]) is not int
            or receipt["repetitions"] != repetitions
        ):
            failures.append(f"receipt repetitions must equal {repetitions}")
        rows = receipt["measurements"]
        groups: dict[str, list] = {}
        for row in rows:
            name, repetition = row["scenario"], row["repetition"]
            label = f"{name} #{repetition}"
            groups.setdefault(name, []).append(repetition)
            plan = row["preflight"]
            planned = plan["planned_sites"]
            if (
                not plan["admitted_dimensions"]
                or plan["violations"]
                or type(planned) is not int
                or planned <= 0
            ):
                failures.append(f"{label}: preflight rejected dimensions")
            coverage = row.get("coverage") or {}
            complete = (
                row.get("status") == "ok"
                and row.get("complete") is True
                and not row.get("elapsed_overrun", False)
                and coverage.get("planned_sites") == planned
                and coverage.get("failed_sites") == 0
                and coverage.get("unattempted_sites") == 0
                and coverage.get("scored_sites", 0)
                + coverage.get("insufficient_context_sites", 0)
                == planned
            )
            if not complete:
                failures.append(
                    f"{label}: incomplete/rejected sample ({row.get('status')})"
                )
            rss = row.get("peak_rss") or {}
            factor = {"bytes": 1, "KiB": 1024}.get(rss.get("unit", ""))
            if (
                not positive(rss.get("bytes"))
                or not positive(rss.get("raw"))
                or factor is None
                or rss["bytes"] != rss["raw"] * factor
            ):
                failures.append(f"{label}: RSS not measured with a known matching unit")
            size = row.get("authoritative_bytes")
            if (
                type(size) is not int
                or not 0
                < size
                <= min(64 * 1024**2, limits["max_result_json_bytes"]) / 2
            ):
                failures.append(
                    f"{label}: authoritative bytes missing or exceed "
                    f"half output cap ({size})"
                )
            wall = row.get("wall_seconds")
            valid_wall = positive(wall)
            if not valid_wall:
                failures.append(f"{label}: missing/nonfinite wall time")
            call = row.get("api_call")
            if call != identity["api_call"]:
                failures.append(
                    f"{label}: actual API deadlines/options differ from defaults"
                )
            batch = row.get("batch") or {}
            if (
                row.get("model") != identity["model"]
                or batch.get("limits") != limits
                or batch.get("seconds_per_record")
                != identity["api_call"]["seconds_per_record"]
                or batch.get("seconds_per_batch")
                != identity["api_call"]["seconds_per_batch"]
            ):
                failures.append(f"{label}: emitted runtime identity/deadlines differ")
            if (
                row.get("emitted_states") != plan["planned_emitted_states"]
                or any(
                    s not in ("ok", "no_candidate")
                    for s in row.get("record_statuses", [])
                )
                or len(row.get("record_statuses", [])) != len(plan["records"])
                or batch.get("record_count") != len(plan["records"])
                or batch.get("complete") is not True
            ):
                failures.append(
                    f"{label}: rejected records or missing planned result counts"
                )
            if valid_wall and (
                wall > limits["default_seconds_per_batch"]
                or (
                    len(plan["records"]) == 1
                    and wall > limits["default_seconds_per_record"]
                )
            ):
                failures.append(
                    f"{label}: elapsed wall time exceeds actual default deadline"
                )
            if (
                complete
                and valid_wall
                and positive(planned)
                and row["settings"]["states"] != "mixed"
            ):
                costs.append(wall / planned)
        for name in required_scenarios:
            if name not in groups:
                failures.append(f"missing required scenario: {name}")
        for name, ids in groups.items():
            if any(type(i) is not int for i in ids) or sorted(ids) != list(
                range(1, repetitions + 1)
            ):
                failures.append(
                    f"{name}: repetitions must be exactly 1..{repetitions}, once each"
                )
        if not costs:
            failures.append("no complete nonmixed samples for per-site wall cost")
        else:
            c = max(costs)
            safety["worst_complete_nonmixed_wall_seconds_per_site"] = c
            for scope, key in (
                ("record", "max_planned_sites_per_record"),
                ("batch", "max_planned_sites_per_batch"),
            ):
                scaled, half = (
                    limits[key] * c,
                    limits[f"default_seconds_per_{scope}"] / 2,
                )
                safety[scope] = {
                    "sites": limits[key],
                    "scaled_seconds": scaled,
                    "half_deadline_seconds": half,
                }
                if scaled > half:
                    failures.append(
                        f"{scope}: N*c={scaled} exceeds half deadline {half}"
                    )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        failures.append(f"malformed receipt: {type(exc).__name__}: {exc}")
    return {
        "passed": not failures,
        "failures": failures,
        "time_safety": safety,
        "caveat": "Finite synthetic samples do not prove "
        "worst possible input capacity.",
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
    parser.add_argument(
        "--suite", choices=("all", "candidate", "diagnostic"), default="all"
    )
    parser.add_argument(
        "--admit",
        action="store_true",
        help="Fail unless the candidate receipt passes admission",
    )
    parser.add_argument(
        "--check-receipt", type=Path, help="Check a saved receipt without measuring"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check_receipt:
        gate = check_receipt(
            json.loads(args.check_receipt.read_bytes()),
            expected_runtime=runtime_identity(),
        )
        print(json.dumps(gate, sort_keys=True))
        return 0 if gate["passed"] else 1
    if args.worker:
        payload = json.load(sys.stdin)
        if (
            payload["limits"] != pio.LIMITS
            or payload["identity_model"]
            != pio.model_identity(promoter.load_parameters())[1]
        ):
            raise ValueError("worker runtime identity differs from parent")
        print(
            json.dumps(
                measure(payload["request"], **payload.get("deadlines", {})),
                allow_nan=False,
            )
        )
        return 0
    if not 1 <= args.repetitions <= 10 or not 0 < args.budget_seconds <= MAX_SECONDS:
        parser.error("repetitions must be 1..10 and budget must be finite in (0,1800]")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".cache").resolve()):
        parser.error("receipt output must be inside repository .cache")
    suites = {
        "all": list(scenarios(pio.LIMITS)),
        "candidate": list(CANDIDATE_SCENARIOS),
        "diagnostic": [*ORIGINAL_SCENARIOS, "tight-deadline"],
    }
    receipt = collect(
        args.scenario or suites[args.suite],
        args.repetitions,
        args.budget_seconds,
    )
    if args.admit:
        receipt["admission"] = check_receipt(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pio.result_bytes(receipt))
    print(f"receipt={output} sha256={digest(output.read_bytes())}")
    for row in receipt["measurements"]:
        print(
            f"{row['scenario']} #{row['repetition']}: {row['status']} "
            f"wall={row.get('wall_seconds')} bytes={row.get('authoritative_bytes')}"
        )
    if args.admit:
        print(json.dumps(receipt["admission"], sort_keys=True))
        return 0 if receipt["admission"]["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

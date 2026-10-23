"""Frozen public-development requests and rank diagnostics; no scorer imports."""

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry

from benchmarks.promoter.count_association import (
    canonical,
    digest,
    parse_json,
    publish,
    read_bytes,
    require,
    same,
)
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.wave4_metrics import STATUSES, indexed, paired, rho

PROTOCOL = Path(__file__).with_name("native-development-recheck-protocol.json")
ROOT = Path(__file__).resolve().parents[2]
INPUT_PINS = {
    "development": {
        "path": "benchmarks/rbs/karlsen2018-development.json",
        "sha256": "53ba87998de7e3d423fb7d6818db48a1bf93ede98bdb46bb6137b0119cfa39a4",
    },
    "split": {
        "path": "benchmarks/rbs/native-splits.json",
        "sha256": "d989341afcb3e463112e85134a322086d968a4cea6ad4b9cb4fa8cc893312409",
    },
}
INPUT_FIELDS = (
    "id",
    "group",
    "sequence",
    "sequence_sha256",
    "start",
    "host",
    "temperature_celsius",
    "anti_sd",
)
CODE_FILES = (
    "benchmarks/rbs/native_development_recheck.py",
    "benchmarks/rbs/metrics.py",
    "benchmarks/rbs/wave4_metrics.py",
    "benchmarks/promoter/count_association.py",
    "schemas/rbs-result-1.0.schema.json",
    "schemas/rbs-result-1.1.schema.json",
    "schemas/rbs-result-1.2.schema.json",
    "schemas/calculator-job-campaign-1.schema.json",
    "schemas/calculator-job-summary-1.schema.json",
    "schemas/calculator-job-receipt-1.schema.json",
)


def compact_hash(value):
    """Hash explicit finite JSON without whitespace or a trailing newline."""
    return digest(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )


def checked_json(path, expected_hash, limit):
    """Verify bounded input bytes before parsing; never discover other files."""
    raw = read_bytes(path, limit)
    require(digest(raw) == expected_hash, "Input hash mismatch")
    return parse_json(raw)


def select_inputs(development, split, cohort):
    """Select every fixed validation member; return no measurement fields."""
    require(
        development["schema_version"] == "native-rbs-development-1",
        "Development schema",
    )
    require(split["schema_version"] == "native-rbs-splits-1", "Split schema")
    same(
        development["input_envelope_sha256"],
        split["input_envelope_sha256"],
        "Source envelope",
    )
    released, assigned = indexed(development["records"]), indexed(split["records"])
    require(
        all(
            r["partition"] in {"development_train", "development_validation"}
            for r in released.values()
        ),
        "Non-development record in released input",
    )
    expected = {
        key
        for key, row in assigned.items()
        if row["partition"] == cohort["partition"] and row["primary_eligible"] is True
    }
    selected = {
        key for key, row in released.items() if row["partition"] == cohort["partition"]
    }
    require(selected == expected, "Validation roster mismatch")
    rows = []
    for identity in sorted(selected):
        row, assignment = released[identity], assigned[identity]
        for field in ("group", "partition", "sequence_sha256"):
            same(row[field], assignment[field], field)
        require(isinstance(row["group"], str) and bool(row["group"]), "Group identity")
        sequence = row["sequence"]
        require(
            isinstance(sequence, str)
            and len(sequence) == cohort["sequence_length"]
            and set(sequence) <= set("ACGT"),
            "Sequence context",
        )
        same(digest(sequence), row["sequence_sha256"], "Sequence hash")
        for field, expected_value in (
            ("start", cohort["start"]),
            ("host", cohort["host"]),
            ("temperature_celsius", cohort["temperature_c"]),
            ("anti_sd", cohort["anti_sd"]),
            ("condition", cohort["condition"]),
            ("quantity", cohort["source_quantity"]),
        ):
            same(row[field], expected_value, field)
        require(
            type(row["start"]) is int and 0 <= row["start"] <= len(sequence) - 3,
            "Supplied start",
        )
        require(
            sequence[row["start"] : row["start"] + 3] in {"ATG", "GTG", "TTG"},
            "Source start codon",
        )
        rows.append({key: row[key] for key in INPUT_FIELDS})
    require(len(rows) == cohort["records"], "Validation count")
    require(len({r["group"] for r in rows}) == cohort["homology_groups"], "Group count")
    same(
        compact_hash([r["id"] for r in rows]),
        cohort["ordered_ids_sha256"],
        "Ordered IDs",
    )
    same(
        compact_hash(
            [
                {key: r[key] for key in ("id", "group", "sequence_sha256", "start")}
                for r in rows
            ]
        ),
        cohort["ordered_id_group_sequence_start_sha256"],
        "Ordered input identities",
    )
    return rows


def load_inputs(protocol):
    """Read only the two immutable, already-public data artifacts."""
    same(protocol["inputs"], INPUT_PINS, "Public input pins")
    docs = {
        key: checked_json(ROOT / pin["path"], pin["sha256"], 8 * 1024**2)
        for key, pin in INPUT_PINS.items()
    }
    same(
        docs["development"]["split_sha256"],
        INPUT_PINS["split"]["sha256"],
        "Split reference",
    )
    return select_inputs(docs["development"], docs["split"], protocol["cohort"])


def request(row):
    """Explicit supplied-start request with no label/group/source-row leakage."""
    return {
        "schema_version": "1.0",
        "id": row["id"],
        "host": row["host"],
        "sequence": row["sequence"],
        "anti_sd": row["anti_sd"],
        "temperature_c": row["temperature_celsius"],
        "strand": "+",
        "start_positions": [row["start"]],
    }


def build_plan(protocol, candidate, rows):
    """Prepare immutable packing and expected identities, without executing jobs."""
    require(
        candidate["schema_version"] == "native-rbs-recheck-candidate-provisional-1",
        "Candidate schema",
    )
    same(
        candidate["candidate_source"],
        protocol["candidate"]["source_commit"],
        "Candidate source",
    )
    same(
        candidate["package_version"],
        protocol["candidate"]["version"],
        "Package version",
    )
    require(
        protocol["candidate"]["wheel_sha256"]
        in {item["sha256"] for item in candidate["archives"]},
        "Wheel identity",
    )
    settings = protocol["execution"]
    configurations = indexed(protocol["configurations"])
    batches = [
        rows[i : i + settings["batch_records"]]
        for i in range(0, len(rows), settings["batch_records"])
    ]
    require(len(batches) == settings["batches_per_configuration"], "Batch count")
    require(len(batches[-1]) == settings["last_batch_records"], "Last batch count")
    requests = {
        f"requests/batch-{number:03d}.json": [request(row) for row in batch]
        for number, batch in enumerate(batches)
    }
    expected = {}
    for identity, config in configurations.items():
        backend = candidate["backends"][config["backend"]]
        profile = backend["profiles"][config["profile"]]
        same(
            profile["schema_version"], config["result_schema_version"], "Result version"
        )
        expected[identity] = {
            "schema_version": profile["schema_version"],
            "model": profile["model"],
            "backend": backend["backend"],
        }
    campaigns: dict = {}
    for name, campaign in settings["campaigns"].items():
        jobs, roster = [], []
        for number, batch in enumerate(batches):
            order = campaign["configurations"]
            rotation = number % len(order)
            for identity in order[rotation:] + order[:rotation]:
                config = configurations[identity]
                same(config["backend"], name, "Campaign backend")
                path = f"requests/batch-{number:03d}.json"
                job_id = f"{identity}-{number:03d}"
                jobs.append(
                    {
                        "id": job_id,
                        "kind": "rbs",
                        "backend": True,
                        "request": {
                            "path": path,
                            "sha256": digest(canonical(requests[path])),
                        },
                        "options": {
                            "profile": config["profile"],
                            "seconds_per_record": settings["seconds_per_record"],
                        },
                    }
                )
                roster.append(
                    {
                        "id": job_id,
                        "configuration": identity,
                        "record_ids": [row["id"] for row in batch],
                    }
                )
        require(len(jobs) == campaign["jobs"], "Campaign job count")
        campaigns[name] = {
            "manifest": {
                "schema_version": "calculator-job-manifest-1",
                "limits": {
                    "seconds_per_job": settings["seconds_per_job"],
                    "seconds_total": campaign["seconds_total"],
                    "stdout_bytes_per_job": settings["stdout_bytes_per_job"],
                    "stderr_bytes_per_job": settings["stderr_bytes_per_job"],
                    "output_bytes_total": settings["output_bytes_total_per_campaign"],
                },
                "jobs": jobs,
            },
            "job_roster": roster,
        }
    require(
        sum(len(c["job_roster"]) for c in campaigns.values()) == settings["jobs"],
        "Total job count",
    )
    require(
        sum(len(j["record_ids"]) for c in campaigns.values() for j in c["job_roster"])
        == settings["record_predictions"],
        "Prediction count",
    )
    return {
        "schema_version": "native-rbs-development-plan-1",
        "stage": protocol["stage"],
        "protocol_sha256": digest(canonical(protocol)),
        "input_pins": protocol["inputs"],
        "candidate_receipt_sha256": protocol["candidate"]["provisional_receipt_sha256"],
        "rows": rows,
        "expected": expected,
        "campaigns": campaigns,
        "requests": requests,
    }


def rank_interval(rows, settings):
    """Group-resample all input groups, retaining failures in the draw universe."""
    groups: dict = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(row)
    keys = sorted(groups)

    def estimate(sample):
        usable = [row for row in sample if row["status"] == "ok"]
        return rho([r["observed"] for r in usable], [r["predicted"] for r in usable])

    usable = [r for r in rows if r["status"] == "ok"]
    point = estimate(rows)
    result = {
        "n_inputs": len(rows),
        "n_successful_measured": len(usable),
        "n_groups": len(keys),
        "n_successful_groups": len({r["group"] for r in usable}),
        "spearman_rho": point,
        "requested_draws": settings["draws"],
        "attempted_draws": 0,
        "usable_draws": 0,
        "undefined_draws": 0,
        "interval95": None,
        "interval_status": "insufficient_support",
    }
    if (
        len(usable) < settings["minimum_common_rows"]
        or result["n_successful_groups"] < settings["minimum_common_blocks"]
    ):
        result["spearman_rho"] = None
        return result
    if point is None:
        result["interval_status"] = "undefined_point_correlation"
        return result
    rng, estimates = random.Random(settings["seed"]), []
    for _ in range(settings["draws"]):
        value = estimate([r for _ in keys for r in groups[rng.choice(keys)]])
        if value is not None:
            estimates.append(value)
    result.update(
        attempted_draws=settings["draws"],
        usable_draws=len(estimates),
        undefined_draws=settings["draws"] - len(estimates),
    )
    if len(estimates) < settings["minimum_usable_draws"]:
        result["interval_status"] = "insufficient_usable_draws"
        return result
    estimates.sort()
    result.update(
        interval_status="ok",
        interval95=[
            estimates[math.floor(0.025 * (len(estimates) - 1))],
            estimates[math.ceil(0.975 * (len(estimates) - 1))],
        ],
    )
    return result


def analyze(rows, labels, predictions, protocol):
    """Report fixed rank endpoints after complete identity/status admission."""
    inputs = indexed(rows)
    require(set(labels) == set(inputs), "Label roster")
    require(all(finite_number(v) and v > 0 for v in labels.values()), "HC label value")
    expected = indexed(protocol["configurations"])
    require(set(predictions) == set(expected), "Configuration roster")
    joined, summaries = {}, {}
    for name in expected:
        scores = indexed(predictions[name])
        require(scores.keys() == inputs.keys(), "Prediction roster")
        records = []
        for identity, row in inputs.items():
            score = scores[identity]
            require(score["status"] in STATUSES, "Prediction status")
            require(isinstance(score["reason"], str), "Prediction reason")
            require(
                finite_number(score["predicted"]) and score["predicted"] >= 0
                if score["status"] == "ok"
                else score["predicted"] is None,
                "Prediction status/value mismatch",
            )
            records.append(
                {
                    "id": identity,
                    "group": row["group"],
                    "observed": labels[identity],
                    "status": score["status"],
                    "predicted": score["predicted"],
                    "reason": score["reason"],
                }
            )
        joined[name] = records
        success = sum(r["status"] == "ok" for r in records)
        summaries[name] = {
            "n_inputs": len(records),
            "n_observed": len(records),
            "n_success": success,
            "coverage": success / len(records) if records else None,
            "status_counts": dict(
                sorted(Counter(r["status"] for r in records).items())
            ),
            "failure_reasons": dict(
                sorted(
                    Counter(r["reason"] for r in records if r["status"] != "ok").items()
                )
            ),
            "rank": rank_interval(records, protocol["uncertainty"]),
        }
    contrasts = []
    for pair in protocol["endpoints"]["contrasts"]:
        reference, contender = pair["reference"], pair["contender"]
        contrasts.append(
            {
                **pair,
                **paired(joined[reference], joined[contender], protocol["uncertainty"]),
            }
        )
    return {
        "stage": protocol["stage"],
        "configurations": summaries,
        "contrasts": contrasts,
    }


def validate_schema(value, name):
    """Use committed local schemas; an empty registry forbids network resolution."""
    schema = parse_json(read_bytes(ROOT / f"schemas/{name}.schema.json", 262144))
    error = next(
        Draft202012Validator(schema, registry=Registry()).iter_errors(value), None
    )
    require(error is None, f"Invalid {name} document")


def native_scores(raw, rows, expected, exit_code, *, budget_seconds):
    """Admit complete native JSON before extracting supplied-start scores."""
    result = parse_json(raw)
    validate_schema(result, f"rbs-result-{expected['schema_version']}")
    same(
        [r["id"] for r in result["results"]],
        [r["id"] for r in rows],
        "Native roster/order",
    )
    scores = []
    for result_row, row in zip(result["results"], rows, strict=True):
        for field in ("schema_version", "model", "backend"):
            same(result_row[field], expected[field], f"Native {field}")
        sequence = row["sequence"].replace("T", "U")
        echo = {
            "id": row["id"],
            "host": row["host"],
            "sequence": sequence,
            "oriented_sequence": sequence,
            "input_sha256": row["sequence_sha256"],
            "normalized_sha256": digest(sequence),
            "oriented_sha256": digest(sequence),
            "start_positions": [row["start"]],
            "strand": "+",
            "anti_sd": row["anti_sd"],
            "temperature_c": float(row["temperature_celsius"]),
        }
        if result_row["status"] == "invalid_input":
            require(
                result_row["input"] is None
                and result_row["prediction_id"] is None
                and not result_row["sites"],
                "Invalid-input provenance",
            )
        else:
            same(result_row["input"], echo, "Native input/settings")
            same(
                result_row["prediction_id"],
                compact_hash(
                    {
                        "input": result_row["input"],
                        "model": result_row["model"],
                        "backend": result_row["backend"],
                        "budget_seconds": float(budget_seconds),
                    }
                ),
                "Native prediction identity",
            )
        sites = result_row["sites"]
        require(
            len(sites) == 1
            or (not sites and result_row["status"] in {"failed", "invalid_input"}),
            "Supplied-start roster",
        )
        predicted: Any = None
        reason = result_row["reason"]
        if sites:
            site = sites[0]
            require(reason is None, "Native record reason for site outcome")
            reason = site["reason"]
            same(site["oriented_start"], row["start"], "Oriented start")
            same(
                site["start_codon"],
                {"start": row["start"], "end": row["start"] + 3, "strand": "+"},
                "Start interval",
            )
            same(
                site["codon"], sequence[row["start"] : row["start"] + 3], "Start codon"
            )
            same(site["status"], result_row["status"], "Singleton status")
            parameters = expected["model"]["parameters"]
            begin = max(0, row["start"] - parameters["upstream_nt"])
            end = min(len(sequence), row["start"] + parameters["downstream_nt"])
            same(
                site["window"],
                {
                    "oriented_start": begin,
                    "oriented_end": end,
                    "input_interval": {"start": begin, "end": end, "strand": "+"},
                },
                "Native scoring window",
            )
            predicted = site["tir"]
        status = result_row["status"]
        require(
            (finite_number(predicted) and predicted >= 0)
            if status == "ok"
            else predicted is None,
            "Native score/status",
        )
        require(
            reason is None if status == "ok" else bool(reason),
            "Native reason/status",
        )
        scores.append(
            {
                "id": row["id"],
                "status": status,
                "reason": reason or "",
                "predicted": predicted,
            }
        )
    expected_exit = int(any(r["status"] in {"failed", "invalid_input"} for r in scores))
    same(exit_code, expected_exit, "Native exit/status")
    return scores


def rbs_argv(options):
    """Mirror the frozen runner's wire spelling, without importing its module."""
    argv = [
        "{python}",
        "-P",
        "-s",
        "-m",
        "regsite",
        "-",
        "--format",
        "json",
        "--backend-root",
        "{backend_root}",
    ]
    for name in sorted(options):
        value = options[name]
        argv.extend(
            [
                "--" + name.replace("_", "-"),
                value if isinstance(value, str) else repr(value),
            ]
        )
    return argv


class Artifacts:
    """Read only explicitly requested pinned files beneath one campaign root.

    This binds A's runner-verification attestation to consumed bytes, not a second
    campaign verifier. Ancestor/path replacement by another local writer is not
    locked; use immutable owner-controlled directories.
    """

    def __init__(self, root, pins):
        self.root, self.pins, self.used = Path(root), pins, {}
        require(self.root.is_absolute(), "Campaign root must be absolute")

    def read(self, name, limit):
        require(
            isinstance(name, str)
            and bool(name)
            and str(Path(name)) == name
            and not Path(name).is_absolute()
            and ".." not in Path(name).parts,
            "Unsafe artifact path",
        )
        path = self.root / name
        require(
            not any(p.is_symlink() for p in (path, *path.parents)), "Artifact symlink"
        )
        pin = self.pins[name]
        require(
            set(pin) == {"bytes", "sha256"}
            and type(pin["bytes"]) is int
            and 0 <= pin["bytes"] <= limit,
            "Artifact size pin",
        )
        raw = read_bytes(path, limit)
        require(
            len(raw) == pin["bytes"] and digest(raw) == pin["sha256"],
            "Artifact bytes/hash",
        )
        self.used[name] = pin
        return raw

    def json(self, name):
        return parse_json(self.read(name, 1048576))


def admit_campaign(plan, name, acquisition, runtime, protocol):
    """Bind trusted installed-runner verification and all consumed output bytes."""
    artifacts = Artifacts(acquisition["root"], acquisition["files"])
    campaign = artifacts.json("campaign/campaign.json")
    validate_schema(campaign, "calculator-job-campaign-1")
    same(campaign["runtime"], runtime, "Campaign runtime")
    expected_campaign = plan["campaigns"][name]
    expected_manifest = canonical(expected_campaign["manifest"])
    require(
        artifacts.read("campaign/manifest.json", 1048576) == expected_manifest,
        "Campaign manifest bytes",
    )
    same(
        campaign["manifest"],
        {
            "path": "manifest.json",
            "sha256": digest(expected_manifest),
            "bytes": len(expected_manifest),
        },
        "Campaign manifest identity",
    )
    first_config = expected_campaign["job_roster"][0]["configuration"]
    same(
        campaign["backend"],
        {
            "rnastructure": plan["expected"][first_config]["backend"],
            "conditional_original": None,
        },
        "Campaign backend",
    )
    verified = artifacts.json("verification.json")
    run = artifacts.json("run-summary.json")
    for summary, command in ((verified, "verify"), (run, "run")):
        validate_schema(summary, "calculator-job-summary-1")
        same(summary["command"], command, "Runner command")
        same(
            summary["campaign_sha256"],
            artifacts.pins["campaign/campaign.json"]["sha256"],
            "Campaign reference",
        )
        same(
            summary["manifest_sha256"], digest(expected_manifest), "Manifest reference"
        )
        require(
            summary["status"] in {"complete", "incomplete"},
            "Unverified/retried campaign",
        )
    require(verified["stop_reason"] is None, "Verify stop reason")
    for key in (
        "jobs",
        "counts",
        "attempts",
        "output_bytes",
        "status",
        "abandoned_attempts",
    ):
        same(run[key], verified[key], "Run/verify agreement")
    same(
        [j["id"] for j in verified["jobs"]],
        [j["id"] for j in expected_campaign["job_roster"]],
        "Job roster/order",
    )
    require(
        all(
            j["state"] not in {"corrupted", "attempts_exhausted"}
            and j["attempts"] in (0, 1)
            and j["error"] is None
            for j in verified["jobs"]
        ),
        "Invalid runner job",
    )
    same(
        verified["counts"],
        {
            state: sum(j["state"] == state for j in verified["jobs"])
            for state in verified["counts"]
        },
        "Runner state counts",
    )
    same(
        verified["attempts"],
        sum(j["attempts"] for j in verified["jobs"]),
        "Runner attempt count",
    )
    same(
        verified["abandoned_attempts"],
        sum(j["attempts"] == 1 and j["receipt"] is None for j in verified["jobs"]),
        "Abandoned attempt count",
    )
    complete = not any(
        j["state"] in {"unfinished", "unstarted"} for j in verified["jobs"]
    )
    same(
        verified["status"],
        "complete" if complete else "incomplete",
        "Runner completeness",
    )
    rows = indexed(plan["rows"])
    predictions: dict = {}
    diagnostics, stream_bytes = [], 0
    limits = protocol["execution"]
    for job, roster, specification in zip(
        verified["jobs"],
        expected_campaign["job_roster"],
        expected_campaign["manifest"]["jobs"],
        strict=True,
    ):
        identity, configuration = job["id"], roster["configuration"]
        require(job["kind"] == "rbs", "Runner kind")
        batch = [rows[i] for i in roster["record_ids"]]
        request_raw = canonical([request(row) for row in batch])
        require(
            artifacts.read(f"campaign/jobs/{identity}/request.json", 1048576)
            == request_raw,
            "Copied request",
        )
        elapsed, outcome = None, "unstarted"
        if job["attempts"] == 0:
            require(
                job["state"] == "unstarted"
                and job["receipt"] is None
                and job["stdout"] is None
                and job["exit_code"] is None,
                "Unstarted job",
            )
            scores = [
                {
                    "id": r["id"],
                    "status": "not_run",
                    "reason": "unstarted",
                    "predicted": None,
                }
                for r in batch
            ]
        elif job["receipt"] is None:
            require(
                job["state"] == "unfinished"
                and job["stdout"] is None
                and job["exit_code"] is None,
                "Abandoned attempt",
            )
            outcome = "abandoned"
            for stream in ("stdout", "stderr"):
                path = f"campaign/jobs/{identity}/attempt-0001/{stream}"
                if path in artifacts.pins:
                    stream_bytes += len(
                        artifacts.read(path, limits[f"{stream}_bytes_per_job"])
                    )
            scores = [
                {
                    "id": r["id"],
                    "status": "failed",
                    "reason": "transport:abandoned",
                    "predicted": None,
                }
                for r in batch
            ]
        else:
            prefix = f"jobs/{identity}/attempt-0001"
            same(job["receipt"], f"{prefix}/receipt.json", "Attempt path")
            receipt = artifacts.json("campaign/" + job["receipt"])
            validate_schema(receipt, "calculator-job-receipt-1")
            for key, value in (
                ("campaign_sha256", verified["campaign_sha256"]),
                ("job_id", identity),
                ("kind", "rbs"),
                ("attempt", 1),
                (
                    "request",
                    {
                        "path": f"jobs/{identity}/request.json",
                        "bytes": len(request_raw),
                        "sha256": digest(request_raw),
                    },
                ),
            ):
                same(receipt[key], value, f"Receipt {key}")
            same(receipt["argv"], rbs_argv(specification["options"]), "Prediction argv")
            same(
                job["state"],
                receipt["outcome"] if receipt["terminal"] else "unfinished",
                "Receipt state",
            )
            same(job["exit_code"], receipt["exit_code"], "Receipt exit")
            same(
                job["stdout"],
                {k: receipt["stdout"][k] for k in ("path", "sha256", "bytes")},
                "Summary stdout",
            )
            streams = {}
            for stream in ("stdout", "stderr"):
                pin = receipt[stream]
                same(pin["path"], f"{prefix}/{stream}", "Stream path")
                raw = artifacts.read(
                    "campaign/" + pin["path"], limits[f"{stream}_bytes_per_job"]
                )
                same(
                    {k: pin[k] for k in ("bytes", "sha256")},
                    artifacts.pins["campaign/" + pin["path"]],
                    "Receipt stream identity",
                )
                stream_bytes += len(raw)
                streams[stream] = raw
            elapsed, outcome = receipt["elapsed_seconds"], receipt["outcome"]
            if job["state"] in {"succeeded", "partial"}:
                require(
                    not receipt["stdout"]["truncated"]
                    and not receipt["stderr"]["truncated"]
                    and receipt["signal"] is None,
                    "Successful transport contradiction",
                )
                scores = native_scores(
                    streams["stdout"],
                    batch,
                    plan["expected"][configuration],
                    receipt["exit_code"],
                    budget_seconds=specification["options"]["seconds_per_record"],
                )
            else:
                scores = [
                    {
                        "id": r["id"],
                        "status": "failed",
                        "reason": f"transport:{outcome}",
                        "predicted": None,
                    }
                    for r in batch
                ]
        launch = f"campaign/jobs/{identity}/attempt-0001/launch.json"
        if job["attempts"] and launch in artifacts.pins:
            artifacts.read(launch, 1048576)  # Opaque runner-verified launch identity.
        predictions.setdefault(configuration, []).extend(scores)
        diagnostics.append(
            {
                "id": identity,
                "configuration": configuration,
                "state": job["state"],
                "outcome": outcome,
                "attempts": job["attempts"],
                "elapsed_seconds": elapsed,
                "exit_code": job["exit_code"],
            }
        )
    require(
        stream_bytes <= limits["output_bytes_total_per_campaign"], "Campaign stream cap"
    )
    same(stream_bytes, verified["output_bytes"], "Campaign stream accounting")
    require(set(artifacts.used) == set(artifacts.pins), "Unconsumed acquisition files")
    return predictions, {
        "stop_reason": run["stop_reason"],
        "jobs": diagnostics,
        "output_bytes": stream_bytes,
        "files": artifacts.used,
    }


def evaluate(
    candidate_path,
    plan_path,
    freeze_path,
    freeze_hash,
    acquisition_path,
    acquisition_hash,
    output_directory,
):
    """Admit every campaign before opening measurement fields or computing ranks."""
    protocol, raw_protocol = load_protocol()
    rows = load_inputs(protocol)
    freeze = checked_json(freeze_path, freeze_hash, 131072)
    require(
        freeze["schema_version"] == "native-rbs-development-freeze-1"
        and freeze["execution_authorized"] is True,
        "Execution freeze",
    )
    same(freeze["protocol_sha256"], digest(raw_protocol), "Frozen protocol")
    same(
        freeze["candidate_receipt_sha256"],
        protocol["candidate"]["provisional_receipt_sha256"],
        "Frozen candidate",
    )
    candidate = checked_json(candidate_path, freeze["candidate_receipt_sha256"], 131072)
    plan = checked_json(plan_path, freeze["plan_sha256"], 2097152)
    expected_plan = build_plan(protocol, candidate, rows)
    expected_plan["protocol_sha256"] = digest(raw_protocol)
    expected_plan["tool_files"] = {
        name: digest(read_bytes(ROOT / name, 1048576)) for name in CODE_FILES
    }
    same(plan, expected_plan, "Prepared plan/code")
    same(
        freeze["runtime"]["regsite_version"],
        candidate["package_version"],
        "Runtime version",
    )
    same(
        freeze["runtime"]["python"]["executable_sha256"],
        candidate["runtime_executable"]["sha256"],
        "Runtime executable",
    )
    same(
        freeze["runtime"]["code"], protocol["candidate"]["runtime_code"], "Runtime code"
    )
    acquisition = checked_json(acquisition_path, acquisition_hash, 1048576)
    require(
        acquisition["schema_version"] == "native-rbs-development-acquisition-1",
        "Acquisition schema",
    )
    same(acquisition["freeze_sha256"], freeze_hash, "Acquisition freeze")
    require(
        set(acquisition["campaigns"]) == set(plan["campaigns"]),
        "Acquisition campaign roster",
    )
    predictions: dict = {}
    diagnostics = {}
    for name in plan["campaigns"]:
        scores, report = admit_campaign(
            plan, name, acquisition["campaigns"][name], freeze["runtime"], protocol
        )
        require(
            not (predictions.keys() & scores.keys()), "Duplicate configuration campaign"
        )
        predictions.update(scores)
        diagnostics[name] = report
    require(
        set(predictions) == {c["id"] for c in protocol["configurations"]},
        "Admitted configuration roster",
    )
    for scores in predictions.values():
        require(
            set(indexed(scores)) == {r["id"] for r in rows}, "Admitted record roster"
        )
    # No output/result selection is allowed to alter which public labels are joined.
    development = checked_json(
        ROOT / INPUT_PINS["development"]["path"],
        INPUT_PINS["development"]["sha256"],
        8 * 1024**2,
    )
    selected_ids = {r["id"] for r in rows}
    labels = {
        r["id"]: r["observed"]
        for r in development["records"]
        if r["id"] in selected_ids
    }
    result = {
        "schema_version": "native-rbs-development-recheck-result-1",
        "protocol_sha256": digest(raw_protocol),
        "plan_sha256": freeze["plan_sha256"],
        "freeze_sha256": freeze_hash,
        "acquisition_sha256": acquisition_hash,
        "candidate_receipt_sha256": freeze["candidate_receipt_sha256"],
        "input_pins": INPUT_PINS,
        "tool_files": expected_plan["tool_files"],
        "limitations": protocol["limitations"],
        "runner_diagnostics": diagnostics,
        **analyze(rows, labels, predictions, protocol),
    }
    for name, summary in result["configurations"].items():
        jobs = [
            j
            for campaign in diagnostics.values()
            for j in campaign["jobs"]
            if j["configuration"] == name
        ]
        times = [j["elapsed_seconds"] for j in jobs if j["elapsed_seconds"] is not None]
        summary["runtime_diagnostic"] = {
            "n_jobs": len(jobs),
            "attempted_jobs": sum(j["attempts"] for j in jobs),
            "state_counts": dict(sorted(Counter(j["state"] for j in jobs).items())),
            "jobs_with_elapsed": len(times),
            "elapsed_sum_seconds": sum(times),
            "elapsed_max_seconds": max(times) if times else None,
            "interpretation": "Job timing; not isolated engine or per-record timing",
        }
    output = external_directory(output_directory)
    publish(output / "report.json", result)
    return result


def load_protocol():
    """Use the committed protocol; execution authority is a separate receipt."""
    raw = read_bytes(PROTOCOL, 65536)
    protocol = parse_json(raw)
    require(
        protocol["schema_version"] == "native-rbs-development-recheck-protocol-1",
        "Protocol schema",
    )
    require(protocol["stage"] == "exploratory_consumed_development", "Protocol stage")
    same(protocol["inputs"], INPUT_PINS, "Public input pins")
    return protocol, raw


def external_directory(path):
    """Refuse repository/symlink destinations and never overwrite a directory."""
    path = Path(path)
    require(path.is_absolute(), "Output directory must be absolute")
    require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        "Output path contains symlink",
    )
    require(
        not any((p / ".git").exists() for p in (path, *path.parents)),
        "Output must be outside repositories",
    )
    path.mkdir(mode=0o700)
    return path


def prepare(candidate_path, output_directory):
    """Publish external requests and manifests, with plan.json committed last.

    A failed write retains the partial new directory as evidence. It cannot be
    resumed or overwritten; no runtime, backend or prediction is executed.
    """
    protocol, raw = load_protocol()
    rows = load_inputs(protocol)
    candidate = checked_json(
        candidate_path, protocol["candidate"]["provisional_receipt_sha256"], 131072
    )
    plan = build_plan(protocol, candidate, rows)
    plan["protocol_sha256"] = digest(raw)
    plan["tool_files"] = {
        name: digest(read_bytes(ROOT / name, 1048576)) for name in CODE_FILES
    }
    output = external_directory(output_directory)
    publish(output / "protocol.json", protocol)
    for name, campaign in plan["campaigns"].items():
        folder = output / name
        folder.mkdir(mode=0o700)
        (folder / "requests").mkdir(mode=0o700)
        for path, batch in plan["requests"].items():
            publish(folder / path, batch)
        publish(folder / "manifest.json", campaign["manifest"])
    publish(output / "plan.json", plan)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparer = commands.add_parser(
        "prepare", help="Create new external requests/manifests; no predictions"
    )
    preparer.add_argument("--candidate", type=Path, required=True)
    preparer.add_argument("--output", type=Path, required=True)
    evaluator = commands.add_parser(
        "evaluate", help="Verify saved artifacts, then join public HC labels"
    )
    for name in ("candidate", "plan", "freeze", "acquisition", "output"):
        evaluator.add_argument(f"--{name}", type=Path, required=True)
    evaluator.add_argument("--freeze-sha256", required=True)
    evaluator.add_argument("--acquisition-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            plan = prepare(args.candidate, args.output)
            summary = {
                "status": "prepared",
                "plan_sha256": digest(canonical(plan)),
                "records": len(plan["rows"]),
                "jobs": sum(len(c["job_roster"]) for c in plan["campaigns"].values()),
                "predictions_executed": 0,
            }
        else:
            result = evaluate(
                args.candidate,
                args.plan,
                args.freeze,
                args.freeze_sha256,
                args.acquisition,
                args.acquisition_sha256,
                args.output,
            )
            summary = {
                "status": "evaluated",
                "report_sha256": digest(canonical(result)),
                "predictions_executed": 0,
            }
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"native development recheck: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

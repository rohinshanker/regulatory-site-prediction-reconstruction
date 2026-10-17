"""Collect every observable candidate from an admitted input-only query panel."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from regsite.backend import RnaStructure
from regsite.profiles import get_profile
from regsite.rbs import predict


def collect(
    source: Path,
    backend,
    *,
    input_sha256: str,
    code_commit: str,
    profile: str,
    seconds: float = 3600,
) -> dict:
    """Score candidates independently; preserve unsupported queries and timeouts.

    The caller admits an exact input-only envelope. No label, source-row ordering,
    normalization, ranking or evaluation is read or performed here. Each supplied
    start has its own 60-second limit inside the finite collection deadline.
    """
    if type(seconds) not in (int, float) or not 0 < seconds <= 3600:
        raise ValueError("candidate collection budget must be within (0,3600]")
    get_profile(profile)
    if not re.fullmatch("[0-9a-f]{40}", code_commit):
        raise ValueError("code_commit must be an exact Git SHA")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != input_sha256:
        raise ValueError("candidate input hash mismatch")
    records = json.loads(raw)["records"]
    deadline = time.monotonic() + seconds
    outputs = []
    for row in records:
        output = {
            "id": row["id"],
            "admission_status": row["admission_status"],
            "candidates": [],
        }
        if row["admission_status"] != "extractable":
            output.update(status="unsupported", reason=row["admission_status"])
            outputs.append(output)
            continue
        for start in row["start_positions"]:
            remaining = deadline - time.monotonic()
            candidate = {
                "start": start,
                "status": "failed",
                "score": None,
                "reason": "collection_budget_exhausted",
                "prediction": None,
            }
            if remaining > 0:
                request = {
                    key: row[key]
                    for key in (
                        "id",
                        "sequence",
                        "strand",
                        "temperature_c",
                        "anti_sd",
                        "host",
                    )
                }
                request["start_positions"] = [start]
                prediction = predict(
                    request,
                    backend,
                    profile=profile,
                    seconds=60,
                    execution_seconds=min(60, remaining),
                )
                site = prediction["sites"][0] if prediction["sites"] else {}
                status = prediction["status"]
                candidate.update(
                    status="failed" if status == "invalid_input" else status,
                    score=site.get("tir"),
                    reason=site.get("reason", prediction.get("reason")),
                    prediction=prediction,
                )
            output["candidates"].append(candidate)
        outputs.append(output)
    return {
        "schema_version": "rbs-candidate-collection-1",
        "input_sha256": input_sha256,
        "code_commit": code_commit,
        "profile": profile,
        "seconds_per_candidate": 60,
        "seconds_per_collection": float(seconds),
        "records": outputs,
    }


def main(argv=None):
    """Collect predictions only, requiring caller-pinned input and code identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("backend_root")
    parser.add_argument("output", type=Path)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument(
        "--profile",
        choices=["historical", "footprint2017", "context2017"],
        required=True,
    )
    parser.add_argument("--seconds", type=float, default=3600)
    args = parser.parse_args(argv)
    result = collect(
        args.source,
        RnaStructure.open(args.backend_root),
        input_sha256=args.input_sha256,
        code_commit=args.code_commit,
        profile=args.profile,
        seconds=args.seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"queries": len(result["records"]), "profile": args.profile}))


if __name__ == "__main__":
    main()

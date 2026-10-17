"""Collect deterministic mechanistic features for the pinned public development set."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from experiments.rbs import standby
from regsite.backend import RnaStructure
from regsite.profiles import get_profile
from regsite.rbs import predict


def collect(
    source: Path, backend, *, profile: str, code_commit: str, seconds: float = 1800
) -> dict:
    """Retain every row; fail the collection rather than silently truncate a budget."""
    if type(seconds) not in (int, float) or not 0 < seconds <= 3600:
        raise ValueError("collection budget must be within (0,3600]")
    get_profile(profile)
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != standby.SOURCE_SHA256:
        raise ValueError("2014 development source hash mismatch")
    if not re.fullmatch("[0-9a-f]{40}", code_commit):
        raise ValueError("code_commit must be an exact Git SHA")
    records = json.loads(raw)["records"]
    deadline = time.monotonic() + seconds
    results = []
    for row in records:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("development collection time budget exhausted")
        results.append(
            predict(
                {
                    "id": row["id"],
                    "sequence": row["sequence"],
                    "start_positions": [row["start"]],
                    "anti_sd": "ACCUCCUUA",
                    "temperature_c": 37,
                    "host": standby.HOST,
                },
                backend,
                profile=profile,
                seconds=60,
                execution_seconds=min(60, remaining),
            )
        )
    return {
        "collection_commit": code_commit,
        "dataset_sha256": standby.SOURCE_SHA256,
        "profile": profile,
        "seconds_per_record": 60,
        "seconds_per_collection": seconds,
        "results": results,
    }


def main(argv=None):
    """Run only pinned development inputs; no browser, network or final labels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("backend_root")
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--profile",
        choices=["historical", "footprint2017", "context2017"],
        default="context2017",
    )
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--seconds", type=float, default=1800)
    args = parser.parse_args(argv)
    result = collect(
        args.source,
        RnaStructure.open(args.backend_root),
        profile=args.profile,
        code_commit=args.code_commit,
        seconds=args.seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"n_records": len(result["results"]), "profile": args.profile}))


if __name__ == "__main__":
    main()

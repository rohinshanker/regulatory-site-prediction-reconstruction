"""Offline JSON/CSV command-line entry point for the implemented RBS profile."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.backend import RnaStructure
from regsite.io import load_requests, write_csv, write_json
from regsite.profiles import PROFILES
from regsite.rbs import predict
from regsite.sequence import InputError
from regsite.structures import BackendError


def main(argv: list[str] | None = None) -> int:
    """Return 0 for completed predictions, 1 for failed records, 2 for setup/input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON request or array; '-' reads standard input")
    parser.add_argument(
        "--backend-root",
        default=os.environ.get("REGSITE_RNASTRUCTURE"),
        help="separate RNAstructure 6.6 installation (exe/, data_tables/)",
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--profile", choices=[p.name for p in PROFILES], default="historical"
    )
    parser.add_argument(
        "--seconds-per-record",
        type=float,
        default=60,
        help="folding wall-time budget per record, >0 and <=120",
    )
    args = parser.parse_args(argv)
    try:
        if not args.backend_root:
            raise InputError("set --backend-root or REGSITE_RNASTRUCTURE")
        if not 0 < args.seconds_per_record <= 120:
            raise InputError("seconds-per-record must be >0 and <=120")
        with (
            nullcontext(sys.stdin) if args.input == "-" else open(args.input) as stream
        ):
            requests = load_requests(stream)
        backend = RnaStructure.open(args.backend_root)
        results = [
            predict(
                request, backend, seconds=args.seconds_per_record, profile=args.profile
            )
            for request in requests
        ]
        if args.format == "csv":
            write_csv(results, sys.stdout)
        else:
            version = "1.0" if args.profile == "historical" else "1.1"
            write_json({"schema_version": version, "results": results}, sys.stdout)
        return int(any(r["status"] in ("failed", "invalid_input") for r in results))
    except (InputError, BackendError, OSError, UnicodeError) as exc:
        print(f"regsite: {exc}", file=sys.stderr)
        return 2

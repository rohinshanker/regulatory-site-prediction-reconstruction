"""Offline native transcript-context scoring with explicit genomic export."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.backend import RnaStructure
from regsite.io import write_json
from regsite.native import predict_native
from regsite.native_io import load_native, write_gff3
from regsite.profiles import PROFILES
from regsite.sequence import InputError
from regsite.structures import BackendError


def main(argv: list[str] | None = None) -> int:
    """Return 0 for completed scenarios, 1 for failed rows, 2 for setup errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="native evidence JSON batch; '-' reads stdin")
    parser.add_argument(
        "--backend-root", default=os.environ.get("REGSITE_RNASTRUCTURE")
    )
    parser.add_argument(
        "--profile", choices=[p.name for p in PROFILES], default="context2017"
    )
    parser.add_argument(
        "--mode",
        choices=("supplied_start", "conditional_scan"),
        default="supplied_start",
    )
    parser.add_argument("--format", choices=("json", "gff3"), default="json")
    parser.add_argument("--seconds-per-record", type=float, default=60)
    parser.add_argument("--seconds-per-batch", type=float, default=300)
    args = parser.parse_args(argv)
    try:
        if not args.backend_root:
            raise InputError("set --backend-root or REGSITE_RNASTRUCTURE")
        with (
            nullcontext(sys.stdin) if args.input == "-" else open(args.input)
        ) as stream:
            value = load_native(stream)
        result = predict_native(
            value,
            RnaStructure.open(args.backend_root),
            profile=args.profile,
            mode=args.mode,
            seconds_per_record=args.seconds_per_record,
            seconds_per_batch=args.seconds_per_batch,
        )
        if args.format == "gff3":
            write_gff3(result, sys.stdout)
        else:
            write_json(result, sys.stdout)
        return int(
            any(r["status"] in ("failed", "invalid_input") for r in result["results"])
        )
    except (InputError, BackendError, OSError, UnicodeError) as exc:
        print(f"regsite-native: {exc}", file=sys.stderr)
        return 2

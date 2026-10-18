"""Offline historical Promoter scoring with explicit calibration and scan scope."""

import argparse
import sys
from contextlib import nullcontext

from regsite.promoter import ParameterError
from regsite.promoter_io import (
    SetupError,
    load_requests,
    predict_batch,
    write_csv,
    write_gff3,
    write_json,
)


def main(argv: list[str] | None = None) -> int:
    """Return 0 for completion, 1 for record errors, 2 for atomic setup errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON single/batch request; '-' reads stdin")
    parser.add_argument("--format", choices=("json", "csv", "gff3"), default="json")
    parser.add_argument("--calibration", choices=("ecoli_mg1655", "in_vitro"))
    parser.add_argument("--states", choices=("selected", "all"))
    parser.add_argument("--seconds-per-record", type=float)
    parser.add_argument("--seconds-per-batch", type=float)
    args = parser.parse_args(argv)
    try:
        with (
            nullcontext(sys.stdin)
            if args.input == "-"
            else open(args.input, encoding="utf-8")
        ) as stream:
            value = load_requests(stream)
        result = predict_batch(
            value,
            seconds_per_record=args.seconds_per_record,
            seconds_per_batch=args.seconds_per_batch,
            cli_calibration=args.calibration,
            cli_states=args.states,
            output_format=args.format,
        )
        {"json": write_json, "csv": write_csv, "gff3": write_gff3}[args.format](
            result, sys.stdout
        )
        return int(
            any(r["status"] in ("invalid_input", "failed") for r in result["results"])
        )
    except (SetupError, ParameterError, OSError, UnicodeError) as exc:
        print(f"regsite-promoter: {exc}", file=sys.stderr)
        return 2

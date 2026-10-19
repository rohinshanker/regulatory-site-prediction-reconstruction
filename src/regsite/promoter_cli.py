"""Offline historical Promoter scoring with explicit calibration and scan scope."""

import argparse
import io
import sys
from contextlib import nullcontext

from regsite.promoter import ParameterError
from regsite.promoter_io import (
    LIMITS,
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
            nullcontext(sys.stdin.buffer)
            if args.input == "-"
            else open(args.input, "rb")
        ) as stream:
            raw = stream.read(int(LIMITS["max_input_json_bytes"]) + 1)
            if len(raw) > LIMITS["max_input_json_bytes"]:
                raise SetupError("max_input_json_bytes exceeded by received input")
            value = load_requests(io.StringIO(raw.decode("utf-8")))
        result = predict_batch(
            value,
            seconds_per_record=args.seconds_per_record,
            seconds_per_batch=args.seconds_per_batch,
            cli_calibration=args.calibration,
            cli_states=args.states,
            output_format=args.format,
        )
        stream = io.StringIO()
        {"json": write_json, "csv": write_csv, "gff3": write_gff3}[args.format](
            result, stream
        )
        rendered = stream.getvalue()
        # Encode completely before writing; stream encoding/newline settings must
        # not change the documented UTF-8 wire representation.
        sys.stdout.buffer.write(rendered.encode("utf-8"))
        return int(
            any(r["status"] in ("invalid_input", "failed") for r in result["results"])
        )
    except (SetupError, ParameterError, OSError, UnicodeError) as exc:
        print(f"regsite-promoter: {exc}", file=sys.stderr)
        return 2

"""Compute a bounded reinitiation-only contribution from supplied energies."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.coupling import invalid_result, predict_coupling
from regsite.coupling_export import csv_bytes
from regsite.coupling_io import CouplingInputError, load_request, result_bytes


def main(argv: list[str] | None = None) -> int:
    """Write native JSON or CSV; return 0 complete, 1 partial, 2 invalid/I/O error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="coupling-request-1 JSON; '-' reads stdin")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    serialize = csv_bytes if args.format == "csv" else result_bytes
    try:
        try:
            with (
                nullcontext(sys.stdin.buffer)
                if args.input == "-"
                else open(args.input, "rb")
            ) as stream:
                request = load_request(stream)
        except CouplingInputError:
            result = invalid_result("invalid_json_or_input_limit")
        else:
            result = predict_coupling(request)
        raw = serialize(result)
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "invalid_input": 2}[result["status"]]
    except (OSError, CouplingInputError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print(
            "regsite-coupling: Input or output unavailable or exceeds byte limit",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

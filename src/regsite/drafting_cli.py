"""Compute stationary initiation-region passage from supplied common-unit rates."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.drafting import invalid_result, predict
from regsite.drafting_io import DraftingInputError, load_request, result_bytes


def main(argv: list[str] | None = None) -> int:
    """Write one authoritative result; exit 0 complete, 1 partial, 2 invalid."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="drafting-request-1 JSON; '-' reads stdin")
    args = parser.parse_args(argv)
    try:
        try:
            with (
                nullcontext(sys.stdin.buffer)
                if args.input == "-"
                else open(args.input, "rb")
            ) as stream:
                request = load_request(stream)
        except DraftingInputError:
            result = invalid_result("invalid_json_or_input_limit")
        except OSError:
            result = invalid_result("input_unavailable")
        else:
            result = predict(request)
        try:
            raw = result_bytes(result)
        except DraftingInputError:
            result = invalid_result("result_serialization_failure")
            raw = result_bytes(result)
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "invalid_input": 2}[result["status"]]
    except (OSError, DraftingInputError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print("regsite-drafting: output unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

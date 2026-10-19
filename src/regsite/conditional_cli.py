"""Compute admitted conditional RNA states or supplied-energy responses offline."""

import argparse
import json
import sys
from contextlib import nullcontext
from typing import BinaryIO

from regsite.conditional import (
    INPUT_LIMIT,
    invalid_result,
    predict_conditional,
    result_bytes,
)
from regsite.conditional_math import ConditionalError


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def load_request(stream: BinaryIO) -> object:
    """Bound received bytes before strict UTF-8 decoding and JSON parsing."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise ConditionalError(
            "input_limit", "Request exceeds 65536 received bytes", "invalid_input"
        )
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ConditionalError(
            "invalid_json",
            "Expected finite UTF-8 JSON without duplicate keys",
            "invalid_input",
        ) from exc


def main(argv: list[str] | None = None) -> int:
    """Emit a full JSON result; return 0 complete, 1 failed/no-mRNA, or 2 refused."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="conditional JSON request; '-' for stdin")
    parser.add_argument(
        "--backend-root",
        help="separate admitted original RNAstructure installation; otherwise use "
        "REGSITE_RNASTRUCTURE (structural profile only)",
    )
    args = parser.parse_args(argv)
    try:
        try:
            with (
                nullcontext(sys.stdin.buffer)
                if args.input == "-"
                else open(args.input, "rb")
            ) as stream:
                request = load_request(stream)
        except ConditionalError as exc:
            result = invalid_result(exc.code, str(exc))
        else:
            result = predict_conditional(request, args.backend_root)
        raw = result_bytes(result)
        sys.stdout.buffer.write(raw)
        if result["status"] == "ok":
            return 0
        return 2 if result["status"] in ("invalid_input", "unsupported") else 1
    except (OSError, ConditionalError) as exc:
        # Do not expose local paths or write a second/partial JSON document.
        message = (
            "Result exceeds output byte limit"
            if isinstance(exc, ConditionalError)
            else "Input or output is unavailable"
        )
        print(f"regsite-conditional: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

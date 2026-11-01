"""Evaluate explicit ligand concentrations under fixed supplied-energy assumptions."""

import argparse
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO

from regsite.conditional_cli import load_request
from regsite.conditional_math import ConditionalError
from regsite.conditional_sweep import SweepError, invalid_result, result_bytes, sweep


@contextmanager
def _input_stream(path: str) -> Iterator[BinaryIO]:
    if path == "-":
        yield sys.stdin.buffer
        return
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError("regular no-follow file input is unavailable")
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("input must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            yield stream
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    """Return 0 complete, 1 partial, 2 refused input or output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", help="conditional-sweep-request-1 JSON, or '-' for stdin"
    )
    args = parser.parse_args(argv)
    try:
        try:
            with _input_stream(args.input) as stream:
                request = load_request(stream)
        except ConditionalError as exc:
            result = invalid_result(exc.code)
        except OSError:
            result = invalid_result("input_unavailable")
        else:
            result = sweep(request)
        try:
            raw = result_bytes(result)
        except SweepError:
            raw = result_bytes(invalid_result("result_serialization_failure"))
            result = {"status": "invalid_input"}
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "invalid_input": 2}[result["status"]]
    except (OSError, SweepError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print("regsite-conditional-sweep: output unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

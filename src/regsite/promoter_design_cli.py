"""Enumerate a bounded explicit Promoter substitution neighborhood."""

import argparse
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO

from regsite.promoter_design import design, invalid_result
from regsite.promoter_design_io import DesignError, load_request, result_bytes


@contextmanager
def _input_stream(path: str) -> Iterator[BinaryIO]:
    """Use binary stdin or a regular file without following its final symlink."""
    if path == "-":
        yield sys.stdin.buffer
        return
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError("no-follow input unavailable")
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("regular file required")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            yield stream
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    """Write one complete JSON result; exit 0 complete, 1 partial/none, 2 invalid."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="promoter-design-request-1 JSON; '-' for stdin")
    args = parser.parse_args(argv)
    try:
        try:
            with _input_stream(args.input) as stream:
                request = load_request(stream)
        except DesignError as exc:
            result = invalid_result(str(exc))
        except OSError:
            result = invalid_result("input_unavailable")
        else:
            result = design(request)
        try:
            raw = result_bytes(result)
        except DesignError:
            result = invalid_result("result_serialization_failure")
            raw = result_bytes(result)
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "no_candidate": 1, "invalid_input": 2}[
            result["status"]
        ]
    except (OSError, DesignError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print("regsite-promoter-design: output unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

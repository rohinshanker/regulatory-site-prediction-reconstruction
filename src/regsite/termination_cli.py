"""Score intrinsic-termination candidates using an explicit external backend."""

import argparse
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO

from regsite.termination import BackendInput, invalid_result, predict_termination
from regsite.termination_backend import TerminationBackendError, load_backend
from regsite.termination_io import TerminationInputError, load_request, result_bytes


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
    """Write one result; exit 0 complete, 1 partial, 2 invalid or transport error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="termination-request-1 JSON; '-' reads stdin")
    parser.add_argument(
        "--backend-manifest", help="explicit local verified backend JSON"
    )
    args = parser.parse_args(argv)
    try:
        try:
            with _input_stream(args.input) as stream:
                request = load_request(stream)
        except TerminationInputError:
            result = invalid_result("invalid_json_or_input_limit")
        else:
            backend: BackendInput = None
            if args.backend_manifest is not None:
                try:
                    backend = load_backend(args.backend_manifest)
                except TerminationBackendError as exc:
                    backend = exc
            result = predict_termination(request, backend=backend)
        raw = result_bytes(result)
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "invalid_input": 2}[result["status"]]
    except (OSError, TerminationInputError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print(
            "regsite-termination: input or output unavailable or oversized",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

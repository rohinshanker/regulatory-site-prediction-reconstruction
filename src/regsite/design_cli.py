"""Run bounded local RBS leader design with explicit model and resource limits."""

import argparse
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import BinaryIO

from regsite.backend import RnaStructure
from regsite.design import design, invalid_result, parse_request
from regsite.design_io import DesignError, load_request, result_bytes
from regsite.structures import BackendError


@contextmanager
def _input_stream(path: str) -> Iterator[BinaryIO]:
    """Read stdin or a regular file without following a final symlink."""
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
    """Emit one complete JSON result: 0 complete, 1 partial/none, 2 refused."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="rbs-design-request-1 JSON, or '-' for stdin")
    parser.add_argument(
        "--backend-root", default=os.environ.get("REGSITE_RNASTRUCTURE")
    )
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
            try:
                parse_request(request)
                if not args.backend_root:
                    raise DesignError("backend_required")
                backend = RnaStructure.open(args.backend_root)
                result = design(request, backend)
            except DesignError as exc:
                result = invalid_result(str(exc))
            except (BackendError, OSError, UnicodeError):
                result = invalid_result("backend_unavailable")
        try:
            raw = result_bytes(result)
        except DesignError:
            raw = result_bytes(invalid_result("result_serialization_failure"))
            result = {"status": "invalid_input"}
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return {"complete": 0, "partial": 1, "no_candidate": 1, "invalid_input": 2}[
            result["status"]
        ]
    except (OSError, DesignError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print("regsite-design: output unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

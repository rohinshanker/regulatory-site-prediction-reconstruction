"""Run bounded multi-target RBS design with explicit immutable coding intervals."""

import argparse
import os
import sys

from regsite.backend import RnaStructure
from regsite.design_cli import _input_stream
from regsite.design_io import DesignError, load_request, result_bytes
from regsite.rbs_vector_design import design, invalid_result, parse_request
from regsite.structures import BackendError


def main(argv: list[str] | None = None) -> int:
    """Emit a full result: 0 complete, 1 partial/none, 2 refused/setup/transport."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", help="rbs-vector-design-request-1 JSON, or '-' for stdin"
    )
    parser.add_argument(
        "--backend-root", default=os.environ.get("REGSITE_RNASTRUCTURE")
    )
    args = parser.parse_args(argv)
    try:
        try:
            with _input_stream(args.input) as stream:
                value = load_request(stream)
        except DesignError as exc:
            result = invalid_result(str(exc))
        except OSError:
            result = invalid_result("input_unavailable")
        else:
            try:
                parse_request(value)
                if not args.backend_root:
                    raise DesignError("backend_required")
                result = design(value, RnaStructure.open(args.backend_root))
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
        print("regsite-rbs-vector-design: output unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

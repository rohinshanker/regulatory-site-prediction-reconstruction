"""Run and compare explicitly supplied current and recoded sequences offline."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.backend import RnaStructure
from regsite.paired import PairError, predict_pair
from regsite.paired_io import export_text, load_request
from regsite.structures import BackendError


def main(argv: list[str] | None = None) -> int:
    """Return 0 complete/incomparable, 1 partial/unavailable, or 2 atomic setup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="paired regulatory JSON request; '-' for stdin")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--backend-root",
        default=os.environ.get("REGSITE_RNASTRUCTURE"),
        help="separate verified RNAstructure installation, required only for RBS",
    )
    args = parser.parse_args(argv)
    try:
        with (
            nullcontext(sys.stdin)
            if args.input == "-"
            else open(args.input, encoding="utf-8")
        ) as stream:
            request = load_request(stream)
        backend = None
        if isinstance(request, dict) and request.get("calculator") == "rbs":
            if not args.backend_root:
                raise PairError("set --backend-root or REGSITE_RNASTRUCTURE for RBS")
            backend = RnaStructure.open(args.backend_root)
        result = predict_pair(request, backend)
        text = export_text(result, args.format)
        sys.stdout.write(text)
        return int(result["status"] in ("partial", "unavailable"))
    except (PairError, BackendError, OSError, UnicodeError) as exc:
        print(f"regsite-compare: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

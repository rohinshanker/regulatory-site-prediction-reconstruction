"""Run a frozen assay-response model locally on explicit supplied-start requests."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.backend import RnaStructure
from regsite.io import load_requests, write_json
from regsite.learned import RESULT_VERSION, predict_learned, validate_model
from regsite.learning import RidgeModel
from regsite.native_io import load_native
from regsite.structures import BackendError


def main(argv: list[str] | None = None) -> int:
    """Return 0 for successful inference, 1 for incomplete rows, 2 for setup errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="frozen ridge JSON artifact")
    parser.add_argument("input", help="request JSON (one or batch); '-' reads stdin")
    parser.add_argument(
        "--backend-root", default=os.environ.get("REGSITE_RNASTRUCTURE")
    )
    parser.add_argument("--seconds-per-record", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        with open(args.model) as stream:
            model = RidgeModel.from_dict(load_native(stream))
        validate_model(model)
        backend = None
        if model.provenance["feature_kind"] == "context-energy-sequence-v1":
            if not args.backend_root:
                raise ValueError(
                    "energy regression requires --backend-root or REGSITE_RNASTRUCTURE"
                )
            backend = RnaStructure.open(args.backend_root)
        with (
            nullcontext(sys.stdin) if args.input == "-" else open(args.input)
        ) as stream:
            requests = load_requests(stream)
        results = [
            predict_learned(value, model, backend, seconds=args.seconds_per_record)
            for value in requests
        ]
        write_json({"schema_version": RESULT_VERSION, "results": results}, sys.stdout)
        return int(any(row["status"] != "ok" for row in results))
    except (ValueError, BackendError, OSError, UnicodeError) as exc:
        print(f"regsite-learned: {exc}", file=sys.stderr)
        return 2

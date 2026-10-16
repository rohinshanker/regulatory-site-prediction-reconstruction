"""Reproducible source acquisition, preparation, historical audit and evaluation."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs.datasets import PINS, digest, prepare, write_json
from benchmarks.rbs.evaluation import evaluate


def main(argv=None):
    """Run one explicit benchmark operation; failures exit without partial results."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("source_root", type=Path)
    fetch_parser.add_argument("--sources", nargs="+", choices=sorted(PINS), default=sorted(PINS))
    prep = commands.add_parser("prepare")
    prep.add_argument("source_root", type=Path)
    prep.add_argument("public_dir", type=Path)
    prep.add_argument("private_dir", type=Path)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("source_root", type=Path)
    audit_parser.add_argument("output", type=Path)
    score = commands.add_parser("score")
    score.add_argument("measurements", type=Path)
    score.add_argument("predictions", type=Path)
    score.add_argument("output", type=Path)
    score.add_argument("--comparison", required=True, choices=[
        "reconstruction-versus-experiment", "live-versus-experiment", "reconstruction-versus-live"])
    score.add_argument("--prediction-identity", required=True,
                       help="Frozen commit/settings digest or private live-job manifest digest")
    score.add_argument("--reference", help="Predeclared control ID; required for experimental comparison")
    args = parser.parse_args(argv)
    if args.command == "fetch":
        from benchmarks.rbs.fetch import fetch
        result = fetch(args.source_root, args.sources)
    elif args.command == "prepare":
        result = prepare(args.source_root, args.public_dir, args.private_dir)
    elif args.command == "audit":
        from benchmarks.rbs.audit import audit
        result = audit(args.source_root)
        write_json(args.output, result)
    else:
        if args.comparison.endswith("experiment") and not args.reference:
            parser.error("Experimental evaluation requires a predeclared --reference")
        if not args.prediction_identity.strip():
            parser.error("A prediction identity is required")
        measurements = args.measurements.read_bytes()
        predictions = args.predictions.read_bytes()
        result = evaluate(json.loads(measurements)["records"], json.loads(predictions)["records"], args.reference)
        result.update(comparison=args.comparison, prediction_identity=args.prediction_identity,
                      measurements_sha256=digest(measurements), predictions_sha256=digest(predictions))
        write_json(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

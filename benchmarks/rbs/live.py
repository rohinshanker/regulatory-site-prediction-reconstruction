"""Validate a private v2.1.1 CSV export against a frozen diagnostic input.

This checks serialization, coordinates and reported component arithmetic. It does
not predict energies, refit parameters or establish agreement with experiments.
"""

import argparse
import csv
import io
import json
import math
from pathlib import Path

from benchmarks.rbs.datasets import digest

COLUMNS = ["start_position", "ORF_number", "tir", "dG_total", "dG_mRNA_rRNA",
           "dG_spacing", "dG_stacking", "dG_standby", "dG_start", "dG_mRNA", "warnings"]


def validate_export(case, content):
    """Return structural/coverage checks; reject malformed or inconsistent output."""
    if digest(case["sequence"]) != case["sequence_sha256"]:
        raise ValueError("Frozen input hash mismatch")
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames != COLUMNS:
        raise ValueError("Unexpected live CSV schema")
    starts, warnings, max_residual = [], 0, 0.0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Truncated or overlong CSV row")
        start = int(row["start_position"])
        if start in starts or start < 0 or start + 3 > len(case["sequence"]):
            raise ValueError("Duplicate or out-of-range start")
        if case["sequence"][start:start + 3] not in {"ATG", "GTG", "TTG", "CTG"}:
            raise ValueError("Returned start does not address a declared start codon")
        values = {key: float(row[key]) for key in COLUMNS[2:10]}
        if any(not math.isfinite(value) for value in values.values()) or values["tir"] <= 0:
            raise ValueError("Live predictions must contain finite energies and a positive rate")
        total = sum(values[key] for key in COLUMNS[4:9]) - values["dG_mRNA"]
        residual = abs(total - values["dG_total"])
        if residual > 1e-8:
            raise ValueError("Exported energy components do not sum to total")
        starts.append(start)
        warnings += bool(row["warnings"].strip())
        max_residual = max(max_residual, residual)
    return {"id": case["id"], "csv_sha256": digest(content), "n_candidates": len(starts),
            "candidate_starts_zero_based": starts, "n_candidates_with_warnings": warnings,
            "selected_start_returned": (case["selected_start_zero_based"] in starts
                                        if case["selected_start_zero_based"] is not None else None),
            "max_component_sum_residual_kcal_mol": max_residual,
            "scope": "export integrity and target coverage; not experimental accuracy"}


def main(argv=None):
    """Check one export; preserve byte identity rather than universal-newline input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path)
    parser.add_argument("case")
    parser.add_argument("csv", type=Path)
    args = parser.parse_args(argv)
    cases = json.loads(args.panel.read_text())["records"]
    case = next(row for row in cases if row["id"] == args.case)
    result = validate_export(case, args.csv.read_bytes().decode("utf-8"))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

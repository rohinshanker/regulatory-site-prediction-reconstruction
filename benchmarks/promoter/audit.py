"""Reproduce published columns and parameter identities, without running a model.

Workbook ingestion alone uses optional openpyxl==3.1.5. Tests and arithmetic use
the standard library. No held-out experimental dataset is calibrated here.
"""

import argparse
import ast
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

from benchmarks.rbs.metrics import correlation, finite_number, ranks

OBSERVED = "Observed log(TX/Txref)"
PREDICTED = "Predicted log(TX/Txref)"
SHEETS = (
    "La Fleur et al (Fig 3a)",
    "Urtecho et al (Fig 3c, S7b)",
    "Hossain et al (Fig 3d, S7d)",
    "Yu et al (Fig S3)",
    "Lagator 36N",
    "Lagator Pl",
    "Lagator Pr",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def errors(pairs, slope):
    """Compute errors with an explicitly supplied slope; never estimate one."""
    if not finite_number(slope):
        raise ValueError("slope must be finite")
    residuals = [observed - slope * predicted for observed, predicted in pairs]
    return {
        "slope": slope,
        "mae": math.fsum(map(abs, residuals)) / len(pairs),
        "mse": math.fsum(x * x for x in residuals) / len(pairs),
    }


def sheet_report(rows):
    """Audit complete sheet rows with explicit finite-pair and sequence counts."""
    header, *data = rows
    if header.count(OBSERVED) != 1 or header.count(PREDICTED) != 1:
        raise ValueError("unique observed/predicted headers required")
    oi, pi = header.index(OBSERVED), header.index(PREDICTED)
    if any(len(row) != len(header) for row in data):
        raise ValueError("ragged worksheet")
    pairs = [
        (row[oi], row[pi])
        for row in data
        if finite_number(row[oi]) and finite_number(row[pi])
    ]
    if not pairs:
        raise ValueError("no finite measurement/prediction pairs")
    observed, predicted = zip(*pairs, strict=True)
    r = correlation(observed, predicted)
    report = {
        "rows": len(data),
        "paired_rows": len(pairs),
        "excluded_nonfinite_pairs": len(data) - len(pairs),
        "pearson_squared": r * r if r is not None else None,
        "spearman": correlation(ranks(observed), ranks(predicted)),
        "as_supplied_errors": errors(pairs, 1),
    }
    if "Slope" in header:
        index = header.index("Slope")
        supplied = {row[index] for row in data if finite_number(row[index])}
        if len(supplied) != 1:
            raise ValueError("worksheet slope must be unique")
        report["worksheet_calibrated_errors"] = errors(pairs, supplied.pop())
        report["calibration_scope"] = (
            "Published fitted-domain diagnostic; not untouched accuracy"
        )
    sequence_columns = [
        i for i, name in enumerate(header) if name in ("Promoter Sequence", "Promoter")
    ]
    if len(sequence_columns) != 1:
        raise ValueError("one promoter sequence column required")
    sequences = [row[sequence_columns[0]] for row in data]
    valid = [
        seq.upper()
        for seq in sequences
        if isinstance(seq, str) and seq and not set(seq.upper()) - set("ACGT")
    ]
    report["sequence_counts"] = {
        "valid_acgt_rows": len(valid),
        "unique_strings": len(set(valid)),
        "invalid_or_missing_rows": len(data) - len(valid),
        "length_counts": dict(sorted(Counter(map(len, valid)).items())),
    }
    return report


def read_npy(raw):
    """Read the pinned one-dimensional float64 NPY v1 arrays without pickle."""
    if raw[:8] != b"\x93NUMPY\x01\x00" or len(raw) < 10:
        raise ValueError("expected NPY version 1")
    length = struct.unpack("<H", raw[8:10])[0]
    header = ast.literal_eval(raw[10 : 10 + length].decode("ascii").strip())
    shape = header["shape"]
    if (
        header["descr"] != "<f8"
        or header["fortran_order"] is not False
        or not isinstance(shape, tuple)
        or len(shape) != 1
        or type(shape[0]) is not int
        or shape[0] < 1
    ):
        raise ValueError("expected one-dimensional little-endian float64")
    data = raw[10 + length :]
    if len(data) != 8 * shape[0]:
        raise ValueError("NPY length mismatch")
    values = struct.unpack(f"<{shape[0]}d", data)
    if not all(map(math.isfinite, values)):
        raise ValueError("nonfinite coefficient")
    return values


def parameter_report(rows, coefficients, intercept):
    """Cross-check every active array coefficient against the source workbook."""
    if len(coefficients) != 343 or len(intercept) != 1:
        raise ValueError("unexpected model array dimensions")
    groups = {}
    for region, encoded, *_ in rows[1:]:
        groups.setdefault(region, []).append(ast.literal_eval(encoded))
    categorical = [
        ("h10 position 0", 0, 64),
        ("h10 position 3", 64, 64),
        ("h35 position 0", 128, 64),
        ("h35 position 3", 192, 64),
        ("disc 3mer", 256, 64),
        ("10ext 2mer", 320, 16),
    ]
    for name, start, count in categorical:
        entries = sorted(groups[name])
        if len(entries) != count or len({x[0] for x in entries}) != count:
            raise ValueError("categorical coefficient count/identifiers")
        if tuple(x[1] for x in entries) != tuple(coefficients[start : start + count]):
            raise ValueError("categorical coefficient mismatch")
    for name, index in (
        ("UP Distal", 339),
        ("UP Proximal", 340),
        ("ITR", 341),
        ("Spacer", 342),
    ):
        if len(groups[name]) != 1 or groups[name][0][1] != coefficients[index]:
            raise ValueError("numeric coefficient mismatch")
    spacers = sorted((int(key), value) for key, value in groups["Spacer Length"])
    if [key for key, value in spacers] != list(range(15, 21)):
        raise ValueError("spacer parameter domain")
    if any(
        abs(value - (0.1463 * key * key - 4.9113 * key + 41.119)) > 1e-12
        for key, value in spacers
    ):
        raise ValueError("spacer polynomial mismatch")
    return {
        "active_categorical_exact_matches": 336,
        "active_numeric_exact_matches": 4,
        "spacer_polynomial_matches": 6,
        "unused_array_spacer_coefficients": 3,
        "array_length": 343,
        "workbook_parameter_rows": len(rows) - 1,
        "intercept": intercept[0],
        "intercept_training_provenance": "not independently recovered",
    }


def audit(root, manifest):
    """Read hash-verified source assets and emit only aggregate audit results."""
    import openpyxl

    assets = manifest["audit_assets"]
    for asset in assets.values():
        if sha256(root / asset["path"]) != asset["sha256"]:
            raise ValueError(f"source hash changed: {asset['path']}")
    workbook = openpyxl.load_workbook(
        root / assets["workbook"]["path"], read_only=True, data_only=True
    )
    try:
        reports = {name: sheet_report(list(workbook[name].values)) for name in SHEETS}
        parameters = parameter_report(
            list(workbook["Model Parameters (Fig 2E)"].values),
            read_npy((root / assets["coefficients"]["path"]).read_bytes()),
            read_npy((root / assets["intercept"]["path"]).read_bytes()),
        )
    finally:
        workbook.close()
    return {
        "schema_version": "promoter-published-audit-1",
        "comparison": "published-column-reproduction",
        "project_model_executed": False,
        "no_refitting_or_outlier_trimming": True,
        "audit_assets": assets,
        "sheets": reports,
        "parameters": parameters,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = audit(args.source_root, json.loads(args.manifest.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

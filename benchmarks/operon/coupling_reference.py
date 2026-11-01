"""Independent artificial coupling arithmetic and saved-result verification.

Only admitted public equations/contracts inform expectations. This module never
imports the candidate, starts processes, retrieves sources, or fits parameters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from typing import Any


class AdmissionError(ValueError):
    """An input cannot be admitted to this bounded evaluation."""


MAX_BYTES = 4_194_304
SCORES = (
    "upstream_independent",
    "downstream_independent",
    "reinitiation_contribution",
    "downstream_total",
    "fold_change",
)
SOURCE_PATHS = (
    "benchmarks/operon-coupling/source-manifest.json",
    "benchmarks/operon-coupling/synthetic-fixtures.json",
    "docs/validation/operon-coupling-runtime.md",
    "docs/validation/operon-coupling-source.md",
    "schemas/coupling-request-1.schema.json",
    "schemas/coupling-result-1.schema.json",
)
NUMERICS = {
    "decimal_precision": 80,
    "input_interpretation": (
        "exact decimal spelling of the binary64 JSON request numbers"
    ),
    "linear_absolute_tolerance": "0",
    "linear_relative_tolerance": "1e-12",
    "linear_target": (
        "nearest binary64 conversion of Decimal value; "
        "zero/inf conversion means expected null"
    ),
    "linear_ulp_allowance": 4,
    "log_absolute_tolerance": "1e-12",
    "log_relative_tolerance": "1e-12",
    "rounding": "ROUND_HALF_EVEN",
    "zero_is_not_missing": True,
}
EQUATIONS = {
    "beta": "0.45",
    "coefficient_minus4": "0.0220",
    "coefficient_zero_to25": "0.0072",
    "distance": "oriented_downstream_start-oriented_upstream_end",
    "fold_change": "total/independent",
    "independent": "exp(-beta*G_down)",
    "k_p": "10",
    "reinitiation": "k_p*k(d)*upstream",
    "total": "independent+reinitiation",
    "unfolding_correction": None,
    "upstream": "exp(-beta*G_up)",
}


def require(condition: bool, message: str) -> None:
    """Fail explicitly rather than silently accepting an incomplete input."""
    if not condition:
        raise AdmissionError(message)


def canonical(value: Any) -> bytes:
    """Encode finite JSON for content identities, preserving numeric spelling."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def pretty(value: Any) -> bytes:
    """Encode deterministic, portable artifacts with exactly one trailing LF."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "sha256": sha(data)}


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(data: bytes) -> Any:
    """Bound bytes, nesting and nonfinite numbers before consuming JSON."""
    require(len(data) <= MAX_BYTES, "JSON byte limit")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise AdmissionError(f"Invalid JSON: {error}") from error
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(nodes <= 100_000 and depth <= 32, "JSON structure limit")
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
        elif isinstance(item, float):
            require(math.isfinite(item), "Nonfinite JSON number")
    return value


def read_bytes(path: Path, expected: dict[str, Any] | None = None) -> bytes:
    """Read one explicitly named file, bounded irrespective of advertised size."""
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, f"File byte limit: {path.name}")
    if expected is not None:
        require(pin(data) == expected, f"File identity mismatch: {path.name}")
    return data


def write_new(path: Path, value: Any) -> None:
    """Publish complete bytes atomically without replacing an existing artifact."""
    data = pretty(value)
    require(len(data) <= MAX_BYTES, "Output byte limit")
    descriptor, temporary = tempfile.mkstemp(prefix=".coupling-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def coefficient(distance: int) -> Decimal | None:
    """Return only the explicitly admitted source coefficient domain."""
    require(type(distance) is int, "Distance must be an integer")
    if distance == -4:
        return Decimal("0.0220")
    if 0 <= distance <= 25:
        return Decimal("0.0072")
    return None


def scalar_checks(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconcile all five supplied source fixtures, without calling a scorer."""
    require(
        source.get("schema_version") == "operon-coupling-synthetic-1", "Source schema"
    )
    require(len(source["cases"]) == 5, "Source fixture count")
    checked = []
    for case in source["cases"]:
        k = coefficient(case["distance_nt"])
        require(k == Decimal(case["k_reinit"]), "Source coefficient")
        require(Decimal(case["k_p"]) == 10, "Source k_p")
        reinit = (
            Decimal(10) * Decimal(case["k_reinit"]) * Decimal(case["upstream_rate"])
        )
        total = Decimal(case["independent_rate"]) + reinit
        require(reinit == Decimal(case["reinitiation_rate"]), "Source reinitiation")
        require(total == Decimal(case["total_rate"]), "Source total")
        checked.append(
            {"id": case["id"], "reinitiation": str(reinit), "total": str(total)}
        )
    require(
        all(coefficient(d) is None for d in source["unsupported_distances_nt"]),
        "Source unsupported domain",
    )
    return checked


def scalar_oracle(up: float, down: float, distance: int) -> dict[str, Any] | None:
    """Evaluate direct exponentials in Decimal, independently of log-space code."""
    for energy in (up, down):
        require(
            type(energy) in (int, float) and abs(energy) <= 1e6,
            "Energy outside admitted bounds",
        )
    k = coefficient(distance)
    if k is None:
        return None
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_HALF_EVEN
        beta = Decimal("0.45")
        upstream = (-beta * Decimal(str(up))).exp()
        independent = (-beta * Decimal(str(down))).exp()
        reinit = Decimal(10) * k * upstream
        total = independent + reinit
        values = (upstream, independent, reinit, total, total / independent)
        result = {}
        for name, value in zip(SCORES, values, strict=True):
            linear = float(value)
            result[name] = {
                "decimal_value": str(value),
                "decimal_log_value": str(value.ln()),
                "value": linear if math.isfinite(linear) and linear > 0 else None,
                "log_value": float(value.ln()),
            }
        return result


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGU", "UGCA"))[::-1]


def geometry(record: dict[str, Any]) -> dict[str, Any]:
    """Independently check complete CDSs and project their half-open intervals."""
    sequence = "".join(record["sequence"].split()).upper().replace("T", "U")
    require(bool(sequence) and set(sequence) <= set("ACGU"), "Invalid fixture RNA")
    require(record["strand"] in ("+", "-"), "Invalid fixture strand")
    length = len(sequence)
    oriented = sequence if record["strand"] == "+" else reverse_complement(sequence)
    result: dict[str, Any] = {
        "sequence_sha256": sha(sequence.encode("ascii")),
        "oriented_sequence_sha256": sha(oriented.encode("ascii")),
        "sequence_length": length,
        "strand": record["strand"],
    }
    for label in ("upstream", "downstream"):
        cds = record[label]
        start, end = cds["interval"]
        require(
            type(start) is int and type(end) is int and 0 <= start < end <= length,
            "Invalid fixture interval",
        )
        require(end - start >= 6 and (end - start) % 3 == 0, "Incomplete fixture CDS")
        a, b = (
            (start, end) if record["strand"] == "+" else (length - end, length - start)
        )
        codons = [oriented[i : i + 3] for i in range(a, b, 3)]
        require(codons[0] in ("AUG", "GUG", "UUG"), "Invalid fixture start")
        require(codons[-1] in ("UAA", "UAG", "UGA"), "Invalid fixture stop")
        require(not set(codons[1:-1]) & {"UAA", "UAG", "UGA"}, "Internal fixture stop")
        result[label] = {
            "id": cds["id"],
            "interval": [start, end],
            "oriented_interval": [a, b],
            "start_codon": codons[0],
            "stop_codon": codons[-1],
        }
    up_start, up_end = result["upstream"]["oriented_interval"]
    down_start, down_end = result["downstream"]["oriented_interval"]
    require(up_start < down_start and up_end < down_end, "Fixture CDS order")
    distance = down_start - up_end
    require(distance >= 0 or (down_start - up_start) % 3 != 0, "Same-frame overlap")
    result["distance_nt"] = distance
    return result


def artificial_record(spec: dict[str, Any], provenance: str) -> dict[str, Any]:
    """Construct the prospective toy transcript; never use biological sequences."""
    distance = spec["distance_nt"]
    require(
        type(distance) is int and -20 <= distance <= 30, "Fixture construction bounds"
    )
    up = [3, 33]
    down = [33 + distance, 63 + distance]
    sequence = ["C"] * (down[1] + 7)
    assigned: dict[int, str] = {}
    for start, codon in (
        (up[0], spec["upstream_start"]),
        (up[1] - 3, "UGA" if distance == -4 else "UAA"),
        (down[0], spec["downstream_start"]),
        (down[1] - 3, "UAG"),
    ):
        for offset, base in enumerate(codon):
            position = start + offset
            require(
                position not in assigned or assigned[position] == base, "Codon overlap"
            )
            assigned[position] = base
            sequence[position] = base
    text = "".join(sequence)
    require(spec["strand"] in ("+", "-"), "Fixture strand")
    if spec["strand"] == "-":
        text = reverse_complement(text)
        up, down = ([len(text) - b, len(text) - a] for a, b in (up, down))
    require(spec["input_style"] in ("rna", "dna_whitespace"), "Fixture input style")
    if spec["input_style"] == "dna_whitespace":
        text = text.replace("U", "T").lower()
        text = (
            " \n" + " \n".join(text[i : i + 11] for i in range(0, len(text), 11)) + "\t"
        )
    record = {
        "id": spec["id"],
        "sequence": text,
        "strand": spec["strand"],
        "upstream": {"id": "toy-up", "interval": up},
        "downstream": {"id": "toy-down", "interval": down},
        "energies": {
            "upstream_total_kcal_mol": float(spec["upstream_energy"]),
            "downstream_independent_total_kcal_mol": float(spec["downstream_energy"]),
            "beta_mol_per_kcal": 0.45,
            "provenance": provenance,
        },
    }
    require(
        geometry(record)["distance_nt"] == distance, "Fixture distance construction"
    )
    return record


def build_fixture(protocol_data: bytes, source_data: bytes) -> dict[str, Any]:
    """Prepare all expected records before an independently gated candidate run."""
    protocol = strict_json(protocol_data)
    require(
        protocol["schema_version"] == "coupling-numeric-protocol-1", "Protocol schema"
    )
    require(protocol["numerics"] == NUMERICS, "Protocol numerics")
    require(protocol["equations"] == EQUATIONS, "Protocol equations")
    require(
        pin(source_data) == protocol["source_pins"][SOURCE_PATHS[1]],
        "Source fixture pin",
    )
    specs = protocol["case_specs"]
    require(
        len(specs) == protocol["request"]["n_records"] == 24, "Protocol roster size"
    )
    require(len({s["id"] for s in specs}) == len(specs), "Duplicate fixture ID")
    records = []
    expected = []
    decimals = []
    for index, spec in enumerate(specs):
        record = artificial_record(spec, protocol["request"]["provenance"])
        energies = record["energies"]
        scores = scalar_oracle(
            energies["upstream_total_kcal_mol"],
            energies["downstream_independent_total_kcal_mol"],
            spec["distance_nt"],
        )
        reason: str | None
        status, reason, numeric = (
            "unsupported_distance",
            "no_admitted_distance_coefficient",
            None,
        )
        decimal_scores = None
        if scores is not None:
            numeric = {
                name: {k: value[k] for k in ("value", "log_value")}
                for name, value in scores.items()
            }
            decimal_scores = {
                name: {k: value[k] for k in ("decimal_value", "decimal_log_value")}
                for name, value in scores.items()
            }
            out_of_range = any(value["value"] is None for value in numeric.values())
            status = "numerical_range" if out_of_range else "ok"
            reason = "linear_score_outside_binary64" if out_of_range else None
        k = coefficient(spec["distance_nt"])
        records.append(record)
        expected.append(
            {
                "index": index,
                "id": record["id"],
                "status": status,
                "reason": reason,
                "geometry": geometry(record),
                "energies": energies,
                "coefficient": float(k) if k is not None else None,
                "scores": numeric,
                "unfolding_correction": None,
            }
        )
        decimals.append({"id": record["id"], "scores": decimal_scores})
    return {
        "schema_version": "coupling-numeric-fixtures-1",
        "protocol": pin(protocol_data),
        "source_scalar_fixture": pin(source_data),
        "source_checks": scalar_checks(strict_json(source_data)),
        "request": {
            "schema_version": "coupling-request-1",
            "records": records,
            "settings": {"seconds_total": protocol["request"]["seconds_total"]},
        },
        "expected_records": expected,
        "decimal_scores": decimals,
    }


def prepare(protocol_path: Path, protocol_sha: str, root: Path, output: Path) -> None:
    """Verify the explicit public allowlist, then atomically write new fixtures."""
    data = read_bytes(protocol_path)
    require(sha(data) == protocol_sha, "Protocol trust pin mismatch")
    protocol = strict_json(data)
    require(
        set(protocol["source_pins"]) == set(SOURCE_PATHS), "Public source allowlist"
    )
    public = {
        name: read_bytes(root / name, protocol["source_pins"][name])
        for name in SOURCE_PATHS
    }
    write_new(output, build_fixture(data, public[SOURCE_PATHS[1]]))


def differences(expected: Any, observed: Any, path: str = "") -> list[str]:
    """Compare complete expected records; only score numbers have a tolerance."""
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return [path]
        fields = [f"{path}/{key}" for key in sorted(expected.keys() ^ observed.keys())]
        for key in sorted(expected.keys() & observed.keys()):
            fields.extend(differences(expected[key], observed[key], f"{path}/{key}"))
        return fields
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            return [path]
        return [
            field
            for index, (a, b) in enumerate(zip(expected, observed, strict=True))
            for field in differences(a, b, f"{path}/{index}")
        ]
    if type(expected) is float:
        if (
            type(observed) not in (int, float)
            or not abs(observed) <= sys.float_info.max
        ):
            return [path]
        if path.startswith("/scores/"):
            if path.endswith("/log_value"):
                matches = math.isclose(expected, observed, rel_tol=1e-12, abs_tol=1e-12)
            else:
                matches = observed > 0 and abs(expected - observed) <= max(
                    1e-12 * abs(expected), 4 * math.ulp(expected)
                )
        else:
            matches = expected == observed
        return [] if matches else [path]
    return [] if type(expected) is type(observed) and expected == observed else [path]


def compare_records(fixture: dict[str, Any], records: Any) -> list[dict[str, Any]]:
    """Retain every case, including expected unsupported and numerical outcomes."""
    expected = fixture["expected_records"]
    require(
        isinstance(records, list) and len(records) == len(expected),
        "Result roster size",
    )
    cases = []
    for wanted, actual in zip(expected, records, strict=True):
        require(
            isinstance(actual, dict)
            and type(actual.get("index")) is int
            and actual["index"] == wanted["index"]
            and actual.get("id") == wanted["id"],
            "Result roster identity/order",
        )
        fields = differences(wanted, actual)
        cases.append(
            {
                "index": wanted["index"],
                "id": wanted["id"],
                "expected_status": wanted["status"],
                "observed_status": actual.get("status"),
                "conforms": not fields,
                "mismatched_fields": fields,
            }
        )
    return cases


def exact_keys(value: Any, names: str, label: str) -> None:
    require(
        isinstance(value, dict) and set(value) == set(names.split()), f"{label} keys"
    )


def finite_number(value: Any) -> bool:
    return type(value) in (int, float) and abs(value) <= sys.float_info.max


def record_shape(record: Any) -> None:
    """Validate the public record structure independently of expected outcomes."""
    exact_keys(
        record,
        "index id status reason geometry energies coefficient scores "
        "unfolding_correction",
        "Record",
    )
    require(type(record["index"]) is int and 0 <= record["index"] <= 99, "Record index")
    require(
        record["id"] is None
        or isinstance(record["id"], str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", record["id"]) is not None,
        "Record ID",
    )
    require(record["unfolding_correction"] is None, "Unexpected unfolding correction")
    status = record["status"]
    require(
        status
        in (
            "ok",
            "numerical_range",
            "unsupported_distance",
            "invalid_input",
            "unsupported_geometry",
            "not_evaluated",
        ),
        "Record status",
    )
    if status in ("invalid_input", "unsupported_geometry", "not_evaluated"):
        require(isinstance(record["reason"], str), "Failure reason")
        require(
            all(
                record[key] is None
                for key in ("geometry", "energies", "coefficient", "scores")
            ),
            "Failure null fields",
        )
        if status == "not_evaluated":
            require(record["reason"] == "time_budget_exhausted", "Deadline reason")
        return
    require(record["id"] is not None, "Valid-geometry record ID")
    g = record["geometry"]
    exact_keys(
        g,
        "sequence_sha256 oriented_sequence_sha256 strand distance_nt "
        "upstream downstream sequence_length",
        "Geometry",
    )
    for key in ("sequence_sha256", "oriented_sequence_sha256"):
        require(
            isinstance(g[key], str)
            and re.fullmatch(r"[a-f0-9]{64}", g[key]) is not None,
            "Sequence hash",
        )
    require(g["strand"] in ("+", "-"), "Geometry strand")
    require(type(g["distance_nt"]) is int, "Geometry distance")
    require(
        type(g["sequence_length"]) is int and 1 <= g["sequence_length"] <= 100_000,
        "Geometry length",
    )
    for name in ("upstream", "downstream"):
        cds = g[name]
        exact_keys(cds, "id interval oriented_interval start_codon stop_codon", "CDS")
        require(
            isinstance(cds["id"], str)
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", cds["id"]) is not None,
            "CDS ID",
        )
        for key in ("interval", "oriented_interval"):
            interval = cds[key]
            require(
                isinstance(interval, list)
                and len(interval) == 2
                and all(type(x) is int and 0 <= x <= 100_000 for x in interval),
                "CDS interval",
            )
        require(
            cds["start_codon"] in ("AUG", "GUG", "UUG")
            and cds["stop_codon"] in ("UAA", "UAG", "UGA"),
            "CDS codons",
        )
    e = record["energies"]
    exact_keys(
        e,
        "upstream_total_kcal_mol downstream_independent_total_kcal_mol "
        "beta_mol_per_kcal provenance",
        "Energies",
    )
    require(
        all(
            finite_number(e[key]) and abs(e[key]) <= 1e6
            for key in (
                "upstream_total_kcal_mol",
                "downstream_independent_total_kcal_mol",
            )
        ),
        "Result energy bounds",
    )
    require(
        finite_number(e["beta_mol_per_kcal"]) and e["beta_mol_per_kcal"] == 0.45,
        "Result beta",
    )
    require(
        isinstance(e["provenance"], str) and 1 <= len(e["provenance"]) <= 1000,
        "Result provenance",
    )
    if status == "unsupported_distance":
        require(
            record["reason"] == "no_admitted_distance_coefficient"
            and record["coefficient"] is None
            and record["scores"] is None,
            "Unsupported fields",
        )
        return
    require(
        finite_number(record["coefficient"])
        and record["coefficient"] in (0.0072, 0.022),
        "Result coefficient",
    )
    exact_keys(record["scores"], " ".join(SCORES), "Scores")
    missing = 0
    for score in record["scores"].values():
        exact_keys(score, "value log_value", "Score")
        require(finite_number(score["log_value"]), "Log value")
        require(
            score["value"] is None
            or finite_number(score["value"])
            and score["value"] > 0,
            "Linear value",
        )
        missing += score["value"] is None
    require(
        (status == "ok" and missing == 0 and record["reason"] is None)
        or (
            status == "numerical_range"
            and missing > 0
            and record["reason"] == "linear_score_outside_binary64"
        ),
        "Status/null/reason contradiction",
    )


def result_accounting(result: Any) -> None:
    """Reject inconsistent envelopes/denominators before numerical comparison."""
    exact_keys(
        result,
        "schema_version model request_sha256 status reason settings coverage "
        "warnings records prediction_sha256",
        "Result",
    )
    require(result["schema_version"] == "coupling-result-1", "Result schema")
    require(result["reason"] is None, "Envelope reason")
    exact_keys(result["settings"], "seconds_total", "Settings")
    budget = result["settings"]["seconds_total"]
    require(finite_number(budget) and 0 < budget <= 60, "Result budget")
    warnings = result["warnings"]
    require(
        isinstance(warnings, list)
        and len(warnings) == 4
        and all(isinstance(w, str) for w in warnings),
        "Warnings shape",
    )
    for key in ("request_sha256", "prediction_sha256"):
        require(
            isinstance(result[key], str)
            and re.fullmatch(r"[a-f0-9]{64}", result[key]) is not None,
            "Result hash shape",
        )
    records = result["records"]
    require(isinstance(records, list) and 1 <= len(records) <= 24, "Record count bound")
    for record in records:
        record_shape(record)
    n = len(records)
    ok = sum(r["status"] == "ok" for r in records)
    not_evaluated = sum(r["status"] == "not_evaluated" for r in records)
    counts = {
        "requested": n,
        "returned": n,
        "successful": ok,
        "failed_or_unsupported": n - ok - not_evaluated,
        "not_evaluated": not_evaluated,
    }
    require(not differences(counts, result["coverage"]), "Coverage accounting")
    require(
        result["status"] == ("complete" if ok == n else "partial"), "Envelope status"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--protocol", required=True, type=Path)
    prep.add_argument("--protocol-sha256", required=True)
    prep.add_argument("--root", required=True, type=Path)
    prep.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        prepare(args.protocol, args.protocol_sha256, args.root, args.output)
    except (AdmissionError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"coupling-reference: {error}", file=sys.stderr)
        return 2
    print("Prepared artificial fixtures; predictions_executed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

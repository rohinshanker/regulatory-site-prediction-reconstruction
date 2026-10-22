"""Independent artificial stationary oracle and offline public-contract checker.

This module imports no predictor. The CLI checks frozen expectations; it never
constructs expectations from the supplied candidate results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

INPUT_LIMIT = 1_048_576
OUTPUT_LIMIT = 4_194_304
FIXTURE_LIMIT = 524_287
DECIMAL_PRECISION = 120
RELATIVE = Fraction(1, 10**11)
LOG_ABSOLUTE = 1e-10
MIN_NORMAL = Fraction.from_float(sys.float_info.min)
FIXTURE_SHA256 = "54ff3c58945f43cd636ac42474c8ede4f39fe25fe49a62aa32327952973a69b6"
ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(__file__).resolve()
FIXTURE = ROOT / "benchmarks/rbs/drafting-numeric-fixtures.json"
PINS = {
    "docs/validation/rbs-drafting-contract.md": (
        "2e3823d8f797e058c4bfe1a162835ff17837d8ee5d36e3180fa37cccd3b718ba"
    ),
    "docs/validation/rbs-kinetics-source-admission.md": (
        "d6d32127688bbb8535043209ee8688f0fb69b7b4fcc5f73e69f23693bbe4b196"
    ),
    "benchmarks/rbs/kinetics-scalar-fixtures.json": (
        "3875449a71cdb2f5fbccd453e0c895e3bc7aeb39755194da2ab8fe698b457758"
    ),
    "benchmarks/rbs/kinetics-source-manifest.json": (
        "4f329f3be98cc601a4da31c13ddff291c5574070691f9d02310218ffeb63404e"
    ),
}
MODEL = {
    "id": "espahborujeni2016-supplied-rate-stationary-1",
    "source_doi": "10.1021/jacs.6b01453",
    "theory_sha256": (
        "a9ded599cbb0313d610267cb9fbdfd21abb1bdb7a467894701fa9b295f3fd6d6"
    ),
    "backend": None,
    "rate_origin": "caller_supplied",
}
# Explicit public schema identity supplied by coordinator B, never inferred.
WARNINGS = [
    "Rates and provenance are unverified caller inputs, not measurement evidence.",
    "Stationary memoryless states omit ribosome traffic and transcript turnover.",
    "Throughput is initiation-region passage, not completed protein production.",
    "Neither native-host accuracy nor hosted parity is established.",
]
WARNING_SOURCE = {
    "source_commit": "356abc2d40198a95f807967a38126a14b0f3d0c9",
    "schema_path": "schemas/drafting-result-1.schema.json",
    "schema_sha256": (
        "0b5dc941cac51ff8cbe7d70e63a0a6633a3a9bffe1f6991625ab2dc018b62371"
    ),
    "evidence": "Coordinator-supplied public schema identity; bytes not read here.",
}

ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
RESULT_KEYS = {
    "schema_version",
    "model",
    "request_sha256",
    "status",
    "reason",
    "coverage",
    "warnings",
    "records",
    "prediction_sha256",
}
RECORD_KEYS = {"index", "id", "status", "reason", "input", "occupancies", "throughput"}


class Invalid(ValueError):
    """Invalid checked data or invocation/trust failure, contextualized by caller."""


def require(condition: bool, message: str) -> None:
    """Raise a deterministic error when an invariant fails."""
    if not condition:
        raise Invalid(message)


def canonical(value: Any) -> bytes:
    """Public hash serialization, preserving parsed int versus float forms."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def authoritative(value: Any) -> bytes:
    """Public authoritative result serialization."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes) -> Any:
    """Parse strict UTF-8 JSON, including finite converted JSON numbers."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def floating(token: str) -> float:
        value = float(token)
        require(math.isfinite(value), "nonfinite JSON number")
        return value

    def constant(token: str) -> Any:
        raise Invalid("nonfinite JSON token")

    try:
        text = data.decode("utf-8", errors="strict")
        require(not text.startswith("\ufeff"), "UTF-8 BOM")
        return json.loads(
            text, object_pairs_hook=pairs, parse_float=floating, parse_constant=constant
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid(f"strict JSON: {exc}") from exc


def read_bounded(path: Path, limit: int) -> bytes:
    """Read one explicit regular file, without following a final symlink."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            require(stat.S_ISREG(info.st_mode), "not a regular file")
            require(info.st_size <= limit, "file exceeds byte limit")
            data = handle.read(limit + 1)
        require(len(data) <= limit, "file grew beyond byte limit")
        return data
    except OSError as exc:
        raise Invalid(f"cannot read explicit file: {path}: {exc.strerror}") from exc


def number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def oracle(rates: dict[str, Any]) -> dict[str, Fraction]:
    """Renewal residence times using exact normalized binary64 inputs.

    A cycle starts just after B clears. It visits U for mean 1/(a+f),
    F with probability f/(a+f) for mean 1/b, then B for mean 1/e.
    """
    a, b, f, e = (
        Fraction.from_float(float(rates[k])) for k in ("a1", "a2", "a_fold", "a_elong")
    )
    require(0 < b <= a < e and f >= 0, "oracle domain")
    residence = (Fraction(1) / (a + f), f / (a + f) / b, Fraction(1) / e)
    duration = sum(residence, Fraction(0))
    return dict(
        zip(
            ("accessible", "folded", "occupied", "throughput"),
            (*[t / duration for t in residence], 1 / duration),
            strict=True,
        )
    )


def balance_solution(rates: dict[str, Any]) -> list[Fraction]:
    """Independent exact elimination of two balances and normalization."""
    a, b, f, e = (
        Fraction.from_float(float(rates[k])) for k in ("a1", "a2", "a_fold", "a_elong")
    )
    rows = [
        [-(a + f), Fraction(0), e, Fraction(0)],
        [f, -b, Fraction(0), Fraction(0)],
        [Fraction(1), Fraction(1), Fraction(1), Fraction(1)],
    ]
    for i in range(3):
        # All three pivots are nonzero for this admitted positive domain.
        pivot = rows[i][i]
        rows[i] = [v / pivot for v in rows[i]]
        for j in range(3):
            if j != i:
                factor = rows[j][i]
                rows[j] = [
                    v - factor * p for v, p in zip(rows[j], rows[i], strict=True)
                ]
    return [row[-1] for row in rows]


def expectation(exact: Fraction) -> dict[str, Any]:
    """Freeze exact value, binary64 representation and predeclared interval."""
    if not exact:
        return {
            "exact": "0",
            "value": 0.0,
            "ln_value": None,
            "representation": "exact_zero",
            "linear_interval": [0.0, 0.0],
            "zero_boundary_ambiguous": False,
        }
    rounded = float(exact)
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        logarithm = float((Decimal(exact.numerator) / Decimal(exact.denominator)).ln())
    low, high = (float(exact * (1 + sign * RELATIVE)) for sign in (-1, 1))
    return {
        "exact": str(exact),
        "value": rounded if rounded else None,
        "ln_value": logarithm,
        "representation": "finite" if rounded else "underflow",
        "linear_interval": [low, high],
        "zero_boundary_ambiguous": low == 0 and high > 0,
    }


def normalized(record: Any) -> dict[str, Any] | None:
    """Validate the public record shape without importing runtime validation."""
    if not isinstance(record, dict) or set(record) != {
        "id",
        "rates",
        "rate_unit",
        "rate_provenance",
    }:
        return None
    rates = record["rates"]
    if not (
        isinstance(record["id"], str)
        and ID.fullmatch(record["id"])
        and record["rate_unit"] in ("per_second", "per_model_time")
        and isinstance(record["rate_provenance"], str)
        and 0 < len(record["rate_provenance"]) <= 1024
        and record["rate_provenance"].strip()
        and isinstance(rates, dict)
        and set(rates) == {"a1", "a2", "a_fold", "a_elong"}
    ):
        return None
    try:
        if not all(
            type(v) in (int, float) and math.isfinite(float(v)) for v in rates.values()
        ):
            return None
        converted = {k: float(v) for k, v in rates.items()}
        if converted["a_fold"] == 0:
            converted["a_fold"] = 0.0
    except OverflowError:
        return None
    return {**record, "rates": converted}


def expected_request(wire: bytes) -> dict[str, Any]:
    """Original contract interpretation for freezing synthetic requests only."""
    invalid: dict[str, Any] = {
        "request_sha256": None,
        "status": "invalid_input",
        "coverage": None,
        "records": [],
    }
    if len(wire) > INPUT_LIMIT:
        return invalid
    try:
        request = strict_json(wire)
        encoded = canonical(request)
    except (Invalid, ValueError, UnicodeError, RecursionError):
        return invalid
    if len(encoded) > INPUT_LIMIT:
        return invalid
    invalid["request_sha256"] = digest(encoded)
    if not (
        isinstance(request, dict)
        and set(request) == {"schema_version", "records"}
        and request["schema_version"] == "drafting-request-1"
        and isinstance(request["records"], list)
        and 1 <= len(request["records"]) <= 100
    ):
        return invalid
    roster = request["records"]
    ids = [
        r.get("id")
        for r in roster
        if isinstance(r, dict)
        and isinstance(r.get("id"), str)
        and ID.fullmatch(r["id"])
    ]
    if len(ids) != len(set(ids)):
        return invalid
    records = []
    for i, raw in enumerate(roster):
        identifier = raw.get("id") if isinstance(raw, dict) else None
        identifier = (
            identifier
            if isinstance(identifier, str) and ID.fullmatch(identifier)
            else None
        )
        record = normalized(raw)
        status = "invalid_input"
        quantities = None
        if record is not None:
            a, b, f, e = (record["rates"][k] for k in ("a1", "a2", "a_fold", "a_elong"))
            status = "unsupported_domain"
            if 0 < b <= a < e and f >= 0:
                status = "ok"
                quantities = {
                    k: expectation(v) for k, v in oracle(record["rates"]).items()
                }
        records.append(
            {
                "index": i,
                "id": identifier,
                "status": status,
                "input": record,
                "quantities": quantities,
            }
        )
    success = sum(r["status"] == "ok" for r in records)
    return {
        "request_sha256": invalid["request_sha256"],
        "status": "complete" if success == len(records) else "partial",
        "coverage": {
            "requested_records": len(records),
            "evaluated_records": len(records),
            "successful_records": success,
            "complete": success == len(records),
        },
        "records": records,
    }


def load_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    """Authenticate fixture bytes and historical source-reference identities."""
    raw = read_bounded(path, FIXTURE_LIMIT)
    require(digest(raw) == FIXTURE_SHA256, "fixture SHA-256 mismatch")
    panel = strict_json(raw)
    require(
        isinstance(panel, dict)
        and set(panel)
        == {"schema_version", "pins", "derivation", "cases", "denominators"},
        "fixture structure",
    )
    require(
        panel["schema_version"] == "drafting-numeric-fixtures-1"
        and panel["pins"] == PINS,
        "fixture schema/pins",
    )
    # PINS describe the preparation baseline, not mutable integrated documents.
    # Their source bytes were checked at preparation; only fixture bytes are read.
    cases = panel["cases"]
    require(isinstance(cases, list) and 0 < len(cases) <= 500, "fixture case bound")
    ids = set()
    records = 0
    for case in cases:
        require(
            isinstance(case, dict)
            and set(case) == {"id", "category", "wire", "trailing_spaces", "expected"},
            "fixture case shape",
        )
        require(
            isinstance(case["id"], str)
            and ID.fullmatch(case["id"]) is not None
            and case["id"] not in ids,
            "fixture case ID",
        )
        ids.add(case["id"])
        require(
            isinstance(case["category"], str)
            and bool(case["category"])
            and isinstance(case["wire"], str)
            and type(case["trailing_spaces"]) is int
            and 0 <= case["trailing_spaces"] <= INPUT_LIMIT + 1,
            "fixture wire recipe",
        )
        # Re-derive exclusively from frozen artificial inputs, never candidate data.
        wire = case["wire"].encode("utf-8") + b" " * case["trailing_spaces"]
        require(case["expected"] == expected_request(wire), "fixture expectations")
        records += len(case["expected"]["records"])
    require(
        records <= 500 and panel["denominators"] == denominators(cases),
        "fixture denominators",
    )
    return panel


def denominators(cases: list[dict[str, Any]]) -> dict[str, int]:
    records = [r for c in cases for r in c["expected"]["records"]]
    return {
        "requests": len(cases),
        "records": len(records),
        "successful_records": sum(r["status"] == "ok" for r in records),
        "invalid_records": sum(r["status"] == "invalid_input" for r in records),
        "unsupported_records": sum(
            r["status"] == "unsupported_domain" for r in records
        ),
        "invalid_envelopes": sum(
            c["expected"]["status"] == "invalid_input" for c in cases
        ),
    }


def load_identity(path: Path, sha256: str) -> dict[str, Any]:
    """Accept a separately frozen explicit identity receipt, never infer warnings."""
    raw = read_bounded(path, INPUT_LIMIT)
    require(
        HEX.fullmatch(sha256) is not None and digest(raw) == sha256,
        "identity receipt SHA-256 mismatch",
    )
    receipt = strict_json(raw)
    require(
        isinstance(receipt, dict)
        and set(receipt) == {"schema_version", "model", "warnings", "candidate"}
        and receipt["schema_version"] == "drafting-candidate-identity-1",
        "identity receipt schema",
    )
    model = receipt["model"]
    require(
        isinstance(model, dict)
        and set(model) == {*MODEL, "implementation_version"}
        and all(model[k] == v for k, v in MODEL.items())
        and isinstance(model["implementation_version"], str)
        and bool(model["implementation_version"].strip()),
        "public model identity",
    )
    warnings = receipt["warnings"]
    require(
        isinstance(warnings, list)
        and len(warnings) > 0
        and all(isinstance(w, str) and bool(w.strip()) for w in warnings)
        and len(set(warnings)) == len(warnings)
        and warnings == WARNINGS,
        "exact public warning identity",
    )
    candidate = receipt["candidate"]
    require(
        isinstance(candidate, dict)
        and set(candidate) == {"source_commit", "wheel_sha256", "settings_sha256"}
        and isinstance(candidate["source_commit"], str)
        and re.fullmatch(r"[0-9a-f]{40}", candidate["source_commit"]) is not None
        and all(
            isinstance(candidate[k], str) and HEX.fullmatch(candidate[k])
            for k in ("wheel_sha256", "settings_sha256")
        ),
        "candidate claims/settings identity",
    )
    return receipt


def equal(actual: Any, expected: Any) -> bool:
    """JSON structural equality that does not mistake booleans for numbers."""
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(equal(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(equal(a, e) for a, e in zip(actual, expected, strict=True))
        )
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return (
            number(actual)
            and float(actual) == expected
            and (
                expected != 0 or math.copysign(1, actual) == math.copysign(1, expected)
            )
        )
    return type(actual) is type(expected) and actual == expected


def quantity_errors(value: Any, expected: dict[str, Any], occupancy: bool) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "value",
        "ln_value",
        "representation",
    }:
        return ["quantity keys"]
    errors = []
    representation = expected["representation"]
    if value["representation"] != representation:
        errors.append("representation")
    linear, logarithm = value["value"], value["ln_value"]
    if representation == "exact_zero":
        if not number(linear) or linear != 0 or logarithm is not None:
            errors.append("exact zero value/log")
    else:
        if occupancy and number(logarithm) and logarithm > 0:
            errors.append("occupancy log upper bound")
        if (
            not number(logarithm)
            or abs(logarithm - expected["ln_value"]) > LOG_ABSOLUTE
        ):
            errors.append("finite log tolerance")
        if representation == "underflow":
            if linear is not None:
                errors.append("underflow null")
        elif not number(linear) or linear <= 0 or (occupancy and linear > 1):
            errors.append("positive finite linear value")
        else:
            exact = Fraction(expected["exact"])
            if exact < MIN_NORMAL:
                lo, hi = expected["linear_interval"]
                good = lo <= linear <= hi
            else:
                good = abs(Fraction(linear) - exact) <= exact * RELATIVE
            if not good:
                errors.append("linear tolerance")
    return errors


def check_result(
    raw: bytes, case: dict[str, Any], identity: dict[str, Any]
) -> list[str]:
    """Check one external payload against frozen inputs and exact expectations."""
    errors: list[str] = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            errors.append(label)

    try:
        require(len(raw) <= OUTPUT_LIMIT, "wire result exceeds byte limit")
        result = strict_json(raw)
        require(
            len(authoritative(result)) <= OUTPUT_LIMIT,
            "authoritative result exceeds byte limit",
        )
        require(
            isinstance(result, dict) and set(result) == RESULT_KEYS,
            "result envelope keys",
        )
    except (Invalid, ValueError, UnicodeError, RecursionError) as exc:
        return [str(exc)]
    expected = case["expected"]
    check(result["schema_version"] == "drafting-result-1", "result schema")
    check(equal(result["model"], identity["model"]), "model identity")
    check(equal(result["warnings"], identity["warnings"]), "exact warnings")
    check(result["request_sha256"] == expected["request_sha256"], "request hash")
    hashed = {k: v for k, v in result.items() if k != "prediction_sha256"}
    check(result["prediction_sha256"] == digest(canonical(hashed)), "prediction hash")
    check(result["status"] == expected["status"], "envelope status")
    check(equal(result["coverage"], expected["coverage"]), "coverage")
    reason = result["reason"]
    check(
        (isinstance(reason, str) and bool(reason.strip()))
        if expected["status"] == "invalid_input"
        else reason is None,
        "envelope reason",
    )
    records = result["records"]
    if not isinstance(records, list):
        return [*errors, "record roster type"]
    check(len(records) == len(expected["records"]), "record roster count")
    for i, exp in enumerate(expected["records"]):
        prefix = f"record[{i}] "
        if i >= len(records):
            errors.append(prefix + "missing")
            continue
        record = records[i]
        if not isinstance(record, dict) or set(record) != RECORD_KEYS:
            errors.append(prefix + "keys")
            continue
        for field in ("index", "id", "status", "input"):
            check(equal(record[field], exp[field]), prefix + field)
        check(
            (record["reason"] is None)
            if exp["status"] == "ok"
            else (isinstance(record["reason"], str) and bool(record["reason"].strip())),
            prefix + "reason",
        )
        if exp["status"] != "ok":
            check(
                record["occupancies"] is None and record["throughput"] is None,
                prefix + "refusal null quantities",
            )
            continue
        occupancies, throughput = record["occupancies"], record["throughput"]
        if not isinstance(occupancies, dict) or set(occupancies) != {
            "accessible",
            "folded",
            "occupied",
        }:
            errors.append(prefix + "occupancy keys")
        else:
            for key in ("accessible", "folded", "occupied"):
                errors.extend(
                    prefix + key + ": " + e
                    for e in quantity_errors(
                        occupancies[key], exp["quantities"][key], True
                    )
                )
        if not isinstance(throughput, dict) or set(throughput) != {"unit", "quantity"}:
            errors.append(prefix + "throughput keys")
        else:
            check(throughput["unit"] == exp["input"]["rate_unit"], prefix + "unit")
            errors.extend(
                prefix + "throughput: " + e
                for e in quantity_errors(
                    throughput["quantity"], exp["quantities"]["throughput"], False
                )
            )
    return errors


def result_paths(specs: list[str], cases: list[dict[str, Any]]) -> dict[str, Path]:
    paths = {}
    known = {c["id"] for c in cases}
    for spec in specs:
        identifier, separator, name = spec.partition("=")
        require(
            bool(separator) and bool(name) and identifier in known,
            "result must be a frozen CASE=PATH",
        )
        require(identifier not in paths, "duplicate result case")
        paths[identifier] = Path(name)
    return paths


def report(
    panel: dict[str, Any], identity: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    rows = []
    for case in panel["cases"]:
        transport_failure = False
        result_sha256 = None
        result_bytes = None
        if case["id"] not in paths:
            errors = ["missing result path"]
        else:
            try:
                raw = read_bounded(paths[case["id"]], OUTPUT_LIMIT)
                result_sha256 = digest(raw)
                result_bytes = len(raw)
                errors = check_result(raw, case, identity)
            except Invalid as exc:
                errors = [str(exc)]
                transport_failure = True
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "passed": not errors,
                "failures": errors,
                "transport_failure": transport_failure,
                "result_sha256": result_sha256,
                "result_bytes": result_bytes,
                "expected_records": len(case["expected"]["records"]),
                "credited_records": 0 if errors else len(case["expected"]["records"]),
            }
        )
    return {
        "schema_version": "drafting-numeric-report-1",
        "fixture_sha256": FIXTURE_SHA256,
        "expected": panel["denominators"],
        "checked_requests": len(paths),
        "transport_failures": sum(r["transport_failure"] for r in rows),
        "passed_requests": sum(r["passed"] for r in rows),
        "credited_records": sum(r["credited_records"] for r in rows),
        "all_passed": all(r["passed"] for r in rows),
        "cases": rows,
    }


def write_report(path: Path, data: bytes, protected: list[Path]) -> None:
    """Publish a complete private file atomically, refusing any collision."""
    target = path.resolve(strict=False)
    require(
        target not in {p.resolve(strict=False) for p in protected},
        "output collides with protected input",
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".drafting-numeric-", dir=path.parent
        ) as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            # link refuses all existing files, including dangling symlinks.
            os.link(handle.name, path, follow_symlinks=False)
    except OSError as exc:
        raise Invalid(f"cannot publish report: {exc.strerror}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--identity-sha256", required=True)
    parser.add_argument("--result", action="append", default=[], metavar="CASE=PATH")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        panel = load_fixture()
        identity = load_identity(args.identity, args.identity_sha256)
        paths = result_paths(args.result, panel["cases"])
        outcome = report(panel, identity, paths)
        outcome["identity_sha256"] = args.identity_sha256
        outcome["checker_sha256"] = digest(read_bounded(CHECKER, INPUT_LIMIT))
        data = authoritative(outcome)
        if args.output is not None:
            write_report(
                args.output,
                data,
                [
                    FIXTURE,
                    CHECKER,
                    args.identity,
                    *paths.values(),
                    *(ROOT / name for name in PINS),
                ],
            )
        else:
            sys.stdout.write(data.decode("ascii"))
        if outcome["transport_failures"]:
            return 2
        return 0 if outcome["all_passed"] else 1
    except (Invalid, ValueError, UnicodeError, RecursionError) as exc:
        sys.stderr.write(f"drafting-numeric setup/trust error: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())

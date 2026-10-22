"""Stationary three-state occupancies from four caller-supplied common-unit rates.

Original arithmetic from the admitted stationary balances; no sequence model,
rate defaults, folding engine, or equilibrium-to-time conversion is involved.
"""

import hashlib
import math
import re
from fractions import Fraction

from regsite import __version__
from regsite.drafting_io import OBJECT_LIMIT, canonical_bytes, canonical_hash

MODEL_ID = "espahborujeni2016-supplied-rate-stationary-1"
THEORY_SHA256 = "a9ded599cbb0313d610267cb9fbdfd21abb1bdb7a467894701fa9b295f3fd6d6"
WARNINGS = [
    "Rates and provenance are unverified caller inputs, not measurement evidence.",
    "Stationary memoryless states omit ribosome traffic and transcript turnover.",
    "Throughput is initiation-region passage, not completed protein production.",
    "Neither native-host accuracy nor hosted parity is established.",
]
RATE_KEYS = {"a1", "a2", "a_fold", "a_elong"}


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None
    )


def _finish(result: dict) -> dict:
    result["prediction_sha256"] = canonical_hash(result)
    return result


def _envelope(request_hash: str | None) -> dict:
    return {
        "schema_version": "drafting-result-1",
        "model": {
            "id": MODEL_ID,
            "implementation_version": __version__,
            "source_doi": "10.1021/jacs.6b01453",
            "theory_sha256": THEORY_SHA256,
            "backend": None,
            "rate_origin": "caller_supplied",
        },
        "request_sha256": request_hash,
        "status": "invalid_input",
        "reason": None,
        "coverage": None,
        "warnings": list(WARNINGS),
        "records": [],
    }


def invalid_result(reason: str, request_sha256: str | None = None) -> dict:
    """Return a hash-bound refusal when no roster can be accepted."""
    result = _envelope(request_sha256)
    result["reason"] = reason
    return _finish(result)


def _quantity(quantity: Fraction) -> dict:
    # Exact integer ratios avoid overflow/cancellation of floating products.
    # math.log accepts arbitrary-size integers; only the final logs are binary64.
    log_value = math.log(quantity.numerator) - math.log(quantity.denominator)
    value = float(quantity)
    if not math.isfinite(log_value) or not math.isfinite(value):
        raise ValueError("nonfinite_quantity")
    return {
        "value": value if value > 0 else None,
        "ln_value": log_value,
        "representation": "finite" if value > 0 else "underflow",
    }


def _stationary(rates: dict[str, float]) -> tuple[dict, dict]:
    # Binary64 inputs are exact rationals with bounded-size integer components.
    # This three-state calculation stays small even at the subnormal/max bounds.
    a, b, f, e = (Fraction(rates[key]) for key in ("a1", "a2", "a_fold", "a_elong"))
    accessible, folded, occupied = b * e, f * e, b * (a + f)
    total = accessible + folded + occupied
    occupancies = {
        "accessible": _quantity(accessible / total),
        "folded": (
            _quantity(folded / total)
            if f
            else {"value": 0.0, "ln_value": None, "representation": "exact_zero"}
        ),
        "occupied": _quantity(occupied / total),
    }
    # Do not multiply an already rounded (possibly zero) occupancy by clearance.
    return occupancies, _quantity(e * occupied / total)


def _record(index: int, value: object) -> dict:
    record_id = value.get("id") if isinstance(value, dict) else None
    result: dict = {
        "index": index,
        "id": record_id if _valid_id(record_id) else None,
        "status": "invalid_input",
        "reason": "invalid_record",
        "input": None,
        "occupancies": None,
        "throughput": None,
    }
    if (
        not isinstance(value, dict)
        or value.keys() != {"id", "rates", "rate_unit", "rate_provenance"}
        or not _valid_id(record_id)
        or value["rate_unit"] not in ("per_second", "per_model_time")
        or not isinstance(value["rate_provenance"], str)
        or not value["rate_provenance"].strip()
        or len(value["rate_provenance"]) > 1024
        or not isinstance(value["rates"], dict)
        or value["rates"].keys() != RATE_KEYS
    ):
        return result
    rates: dict[str, float] = {}
    for key, number in value["rates"].items():
        if isinstance(number, bool) or not isinstance(number, (float, int)):
            result["reason"] = "invalid_rate"
            return result
        try:
            converted = float(number)
        except OverflowError:
            result["reason"] = "invalid_rate"
            return result
        if not math.isfinite(converted):
            result["reason"] = "invalid_rate"
            return result
        rates[key] = 0.0 if converted == 0 else converted
    result["input"] = {**value, "rates": rates}
    if not (0 < rates["a2"] <= rates["a1"] < rates["a_elong"] and rates["a_fold"] >= 0):
        result.update(
            status="unsupported_domain", reason="outside_admitted_rate_domain"
        )
        return result
    try:
        occupancies, quantity = _stationary(rates)
    except (ValueError, OverflowError):
        result.update(status="numerical_failure", reason="unrepresentable_calculation")
        return result
    result.update(
        status="ok",
        reason=None,
        occupancies=occupancies,
        throughput={"unit": value["rate_unit"], "quantity": quantity},
    )
    return result


def predict(request: object) -> dict:
    """Evaluate every admitted record, preserving failures and caller provenance.

    Args:
        request: A drafting-request-1 JSON object, bounded to OBJECT_LIMIT
            canonical bytes. Numbers convert explicitly to finite binary64.

    Returns:
        A deterministic drafting-result-1 envelope. No caller object is mutated.
        Non-JSON or oversized API objects cannot acquire a request hash.
    """
    try:
        raw = canonical_bytes(request)
    except (ValueError, TypeError, RecursionError):
        return invalid_result("request_is_not_finite_json")
    if len(raw) > OBJECT_LIMIT:
        return invalid_result("api_object_byte_limit")
    request_hash = hashlib.sha256(raw).hexdigest()
    if (
        not isinstance(request, dict)
        or request.keys() != {"schema_version", "records"}
        or request["schema_version"] != "drafting-request-1"
        or not isinstance(request["records"], list)
        or not 1 <= len(request["records"]) <= 100
    ):
        return invalid_result("invalid_envelope", request_hash)
    ids = [
        item["id"]
        for item in request["records"]
        if isinstance(item, dict) and _valid_id(item.get("id"))
    ]
    if len(ids) != len(set(ids)):
        return invalid_result("duplicate_record_id", request_hash)
    records = [_record(index, item) for index, item in enumerate(request["records"])]
    successful = sum(item["status"] == "ok" for item in records)
    result = _envelope(request_hash)
    result.update(
        status="complete" if successful == len(records) else "partial",
        records=records,
        coverage={
            "requested_records": len(records),
            "evaluated_records": len(records),
            "successful_records": successful,
            "complete": successful == len(records),
        },
    )
    return _finish(result)

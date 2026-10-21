"""Historical reinitiation contributions from explicitly supplied CDS energies.

This component does not infer RNA unfolding or derive energies from sequence.
"""

import math
import re
import time
from collections.abc import Callable

from regsite import __version__
from regsite.coupling_geometry import CouplingGeometryError, validate_pair_geometry
from regsite.coupling_io import OBJECT_LIMIT, canonical_bytes, canonical_hash

MODEL_ID = "tian2015-reinitiation-only-1"
BETA = 0.45
K_P = 10.0
MAX_RECORDS = 100
WARNINGS = [
    "Energies and their common convention are supplied by the caller, not verified.",
    "Reinitiation only: RNA unfolding and sequence-derived energies are unavailable.",
    "Historical E. coli component; native-host calibration is unestablished.",
    "Assumes initiation-limited translation; outputs are relative scores, not rates.",
]


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None
    )


def _finite(value: object, lower: float, upper: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and lower <= value <= upper
    )


def _model() -> dict:
    return {
        "id": MODEL_ID,
        "implementation_version": __version__,
        "source_doi": "10.1093/nar/gkv635",
        "source_pdf_sha256": (
            "83bbe3bcd87380b4716c93ad0844134ed71cf4f977d6486ef3d3d38f0a566ff7"
        ),
        "beta_mol_per_kcal": BETA,
        "k_p": K_P,
        "coefficient_domain": {"distance_0_to_25": 0.0072, "distance_minus_4": 0.022},
        "score_scale": (
            "dimensionless exp(-beta*G); no intercept or absolute conversion"
        ),
        "backend": None,
    }


def _finish(result: dict) -> dict:
    result["prediction_sha256"] = canonical_hash(result)
    return result


def invalid_result(reason: str, request_sha256: str | None = None) -> dict:
    """Return an explicit refusal without claiming an accepted record roster."""
    return _finish(
        {
            "schema_version": "coupling-result-1",
            "model": _model(),
            "request_sha256": request_sha256,
            "status": "invalid_input",
            "reason": reason,
            "settings": None,
            "coverage": None,
            "warnings": list(WARNINGS),
            "records": [],
        }
    )


def _empty_record(index: int, record: object) -> dict:
    record_id = record.get("id") if isinstance(record, dict) else None
    return {
        "index": index,
        "id": record_id if _valid_id(record_id) else None,
        "status": "not_evaluated",
        "reason": "time_budget_exhausted",
        "geometry": None,
        "energies": None,
        "coefficient": None,
        "scores": None,
        "unfolding_correction": None,
    }


def _linear(log_value: float) -> float | None:
    try:
        value = math.exp(log_value)
    except OverflowError:
        return None
    return value if value > 0 else None


def _scores(
    upstream_energy: float, downstream_energy: float, coefficient: float
) -> dict:
    upstream = -BETA * upstream_energy
    independent = -BETA * downstream_energy
    reinitiation = upstream + math.log(K_P * coefficient)
    larger = max(independent, reinitiation)
    total = larger + math.log1p(math.exp(-abs(independent - reinitiation)))
    logs = {
        "upstream_independent": upstream,
        "downstream_independent": independent,
        "reinitiation_contribution": reinitiation,
        "downstream_total": total,
        "fold_change": total - independent,
    }
    return {
        name: {"log_value": value, "value": _linear(value)}
        for name, value in logs.items()
    }


def _record(index: int, value: object) -> dict:
    result = _empty_record(index, value)
    result.update(status="invalid_input", reason="invalid_record")
    keys = {"id", "sequence", "strand", "upstream", "downstream", "energies"}
    if (
        not isinstance(value, dict)
        or value.keys() != keys
        or not _valid_id(value["id"])
    ):
        return result
    energy = value["energies"]
    energy_keys = {
        "upstream_total_kcal_mol",
        "downstream_independent_total_kcal_mol",
        "beta_mol_per_kcal",
        "provenance",
    }
    if (
        not isinstance(energy, dict)
        or energy.keys() != energy_keys
        or not _finite(energy["upstream_total_kcal_mol"], -1e6, 1e6)
        or not _finite(energy["downstream_independent_total_kcal_mol"], -1e6, 1e6)
        or not _finite(energy["beta_mol_per_kcal"], BETA, BETA)
        or not isinstance(energy["provenance"], str)
        or not 1 <= len(energy["provenance"].strip()) <= 1000
        or len(energy["provenance"]) > 1000
    ):
        result["reason"] = "invalid_or_incompatible_energies"
        return result
    try:
        geometry = validate_pair_geometry(
            value["sequence"], value["strand"], value["upstream"], value["downstream"]
        )
    except CouplingGeometryError as exc:
        result.update(status=exc.code, reason=str(exc))
        return result
    result["geometry"] = {
        key: item
        for key, item in geometry.items()
        if key not in ("sequence", "oriented_sequence")
    }
    result["geometry"]["sequence_length"] = len(geometry["sequence"])
    result["energies"] = dict(energy)
    distance = geometry["distance_nt"]
    if distance == -4:
        coefficient = 0.022
    elif 0 <= distance <= 25:
        coefficient = 0.0072
    else:
        result.update(
            status="unsupported_distance", reason="no_admitted_distance_coefficient"
        )
        return result
    result["coefficient"] = coefficient
    result["scores"] = _scores(
        energy["upstream_total_kcal_mol"],
        energy["downstream_independent_total_kcal_mol"],
        coefficient,
    )
    if any(item["value"] is None for item in result["scores"].values()):
        result.update(status="numerical_range", reason="linear_score_outside_binary64")
    else:
        result.update(status="ok", reason=None)
    return result


def predict_coupling(
    request: object, *, clock: Callable[[], float] = time.monotonic
) -> dict:
    """Evaluate a bounded batch with explicit per-record failures and source scope.

    Args:
        request: A coupling-request-1 envelope using supplied independent energies,
            bounded to OBJECT_LIMIT bytes of canonical ASCII JSON. CLI received
            bytes have a separate, smaller transport limit.
        clock: Monotonic seconds; injectable for deterministic deadline tests.

    Returns:
        A hash-bound complete, partial, or invalid_input coupling-result-1 object.
        The caller's request is never modified. No backend or network is used.
    """
    started = clock()
    try:
        raw = canonical_bytes(request)
        request_hash = canonical_hash(request)
    except (ValueError, TypeError, RecursionError):
        return invalid_result("request_is_not_finite_json")
    if len(raw) > OBJECT_LIMIT:
        return invalid_result("api_object_byte_limit", request_hash)
    if (
        not isinstance(request, dict)
        or request.keys() != {"schema_version", "records", "settings"}
        or request["schema_version"] != "coupling-request-1"
        or not isinstance(request["records"], list)
        or not 1 <= len(request["records"]) <= MAX_RECORDS
        or not isinstance(request["settings"], dict)
        or request["settings"].keys() != {"seconds_total"}
        or not _finite(request["settings"]["seconds_total"], 0, 60)
        or request["settings"]["seconds_total"] == 0
    ):
        return invalid_result("invalid_envelope", request_hash)
    ids = [
        v["id"]
        for v in request["records"]
        if isinstance(v, dict) and _valid_id(v.get("id"))
    ]
    if len(ids) != len(set(ids)):
        return invalid_result("duplicate_record_id", request_hash)
    deadline = started + request["settings"]["seconds_total"]
    records = []
    expired = False
    for index, value in enumerate(request["records"]):
        expired = expired or clock() >= deadline
        result = _empty_record(index, value)
        if not expired:
            result = _record(index, value)
            expired = clock() >= deadline
            if expired:
                result = _empty_record(index, value)
        records.append(result)
    successful = sum(row["status"] == "ok" for row in records)
    not_evaluated = sum(row["status"] == "not_evaluated" for row in records)
    return _finish(
        {
            "schema_version": "coupling-result-1",
            "model": _model(),
            "request_sha256": request_hash,
            "status": "complete" if successful == len(records) else "partial",
            "reason": None,
            "settings": dict(request["settings"]),
            "coverage": {
                "requested": len(records),
                "returned": len(records),
                "successful": successful,
                "failed_or_unsupported": len(records) - successful - not_evaluated,
                "not_evaluated": not_evaluated,
            },
            "warnings": list(WARNINGS),
            "records": records,
        }
    )

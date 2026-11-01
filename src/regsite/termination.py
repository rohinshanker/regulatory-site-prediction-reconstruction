"""Bounded intrinsic-termination candidate scoring with an external engine.

The native background score is not termination efficiency or readthrough.
"""

import hashlib
import re
import time
from collections.abc import Callable

from regsite import __version__
from regsite.termination_backend import TerminationBackend, TerminationBackendError
from regsite.termination_io import (
    OBJECT_LIMIT,
    canonical_bytes,
    canonical_hash,
    validate_depth,
)
from regsite.termination_output import parse_output

MODEL_ID = "transtermhp-2.09-fragment-1"
MAX_RECORDS = 20
MAX_BASES = 100_000
WHITESPACE = str.maketrans("", "", " \t\r\n\v\f")
TABLES = tuple(range(26, 85, 2))
WARNINGS = [
    "Native retained motif candidates; no termination-efficiency or readthrough model.",
    "Fixed historical background scores are not probabilities or host calibration.",
    "Synthetic boundary annotations are bookkeeping, not inferred genes.",
    "Native pruning can remove opposite-strand candidates; mirrors are not restored.",
    "Candidate scores depend on the supplied sequence and its background composition.",
    "Unavailable flanks are not searched; no candidates is not measured absence.",
    "Boundary-overlapping forward candidates retain geometry with null confidence.",
]
BackendInput = TerminationBackend | TerminationBackendError | None


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None
    )


def _number(value: object, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.001 <= value <= maximum
    )


def _model(backend: BackendInput = None) -> dict:
    return {
        "id": MODEL_ID,
        "implementation_version": __version__,
        "source_doi": "10.1186/gb-2007-8-2-r22",
        "source_archive_sha256": (
            "b636db1c0fe9731cc760d8f3639209d07f7f35309d83013cc9f9e40798ce8be0"
        ),
        "background_sha256": (
            "fce89a92ab487aaea5a54015e859e1fb5e31f4f9985c9df7831ee09a367db1fe"
        ),
        "backend": (
            backend.identity
            if backend is not None and not isinstance(backend, TerminationBackendError)
            else None
        ),
    }


def _finish(result: dict) -> dict:
    identity = {
        **result,
        "records": [
            {key: value for key, value in record.items() if key != "execution"}
            for record in result["records"]
        ],
    }
    result["prediction_sha256"] = canonical_hash(identity)
    result["result_sha256"] = canonical_hash(result)
    return result


def invalid_result(reason: str, request_sha256: str | None = None) -> dict:
    """Refuse an envelope without claiming an accepted record roster."""
    return _finish(
        {
            "schema_version": "termination-result-1",
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


def _empty_record(index: int, value: object) -> dict:
    record_id = value.get("id") if isinstance(value, dict) else None
    return {
        "index": index,
        "id": record_id if _valid_id(record_id) else None,
        "status": "not_evaluated",
        "reason": "time_budget_exhausted",
        "input": None,
        "coverage": None,
        "backgrounds": None,
        "attempted": False,
        "execution": None,
        "candidates": None,
    }


def _background(sequence: str) -> dict:
    count = sum(base in "AT" for base in sequence)
    length = len(sequence)
    fraction = count / length
    selected = min(TABLES, key=lambda table: abs(float(table) - 100.0 * fraction))
    return {
        "at_count": count,
        "gc_count": length - count,
        "length": length,
        "at_fraction": fraction,
        "selected_at_percent": selected,
        "exact_table_tie": any(100 * count == length * k for k in range(27, 84, 2)),
        "endpoint_clamped": 100 * count < 26 * length or 100 * count > 84 * length,
    }


def _prepare(index: int, value: object) -> tuple[dict, str | None]:
    result = _empty_record(index, value)
    result.update(status="invalid_input", reason="invalid_record")
    if (
        not isinstance(value, dict)
        or value.keys() != {"id", "sequence"}
        or not _valid_id(value["id"])
        or not isinstance(value["sequence"], str)
    ):
        return result, None
    sequence = value["sequence"].translate(WHITESPACE).upper()
    if not sequence or re.fullmatch(r"[ACGT]+", sequence) is None:
        result["reason"] = "invalid_sequence_alphabet"
        return result, None
    length = len(sequence)
    result["input"] = {
        "sequence_length": length,
        "sequence_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
    }
    result.update(status="unsupported_domain", reason="sequence_length_outside_domain")
    if not 75 <= length <= MAX_BASES:
        return result, None
    positions = length - 75
    result["coverage"] = {
        "forward_anchors": {"start": 59, "end": length - 16, "count": positions},
        "reverse_anchors": {"start": 16, "end": length - 59, "count": positions},
        "total_anchor_positions": 2 * positions,
    }
    if positions == 0:
        result["reason"] = "no_search_positions"
        return result, None
    result["backgrounds"] = {
        "interior": _background(sequence[2:-2]),
        "synthetic_boundary": _background(sequence[:2] + sequence[-2:]),
    }
    if any(
        group["at_count"] == 0 or group["gc_count"] == 0
        for group in result["backgrounds"].values()
    ):
        result["reason"] = "uniform_background"
        return result, None
    result.update(status="not_evaluated", reason="time_budget_exhausted")
    return result, sequence


def _coverage(records: list[dict]) -> dict:
    successes = [record for record in records if record["status"] == "ok"]
    return {
        "requested_records": len(records),
        "domain_eligible_records": sum(
            record["backgrounds"] is not None
            and record["reason"] != "uniform_background"
            for record in records
        ),
        "attempted_records": sum(record["attempted"] for record in records),
        "successful_records": len(successes),
        "not_evaluated_records": sum(
            record["status"] == "not_evaluated" for record in records
        ),
        "failed_records": sum(
            record["status"] not in {"ok", "not_evaluated"} for record in records
        ),
        "retained_candidates": sum(len(record["candidates"]) for record in successes),
        "admitted_candidate_scores": sum(
            candidate["confidence"] is not None
            for record in successes
            for candidate in record["candidates"]
        ),
    }


def predict_termination(
    request: object,
    *,
    backend: BackendInput = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Score one bounded roster while preserving failures and unattempted records.

    Args:
        request: A strict termination-request-1 envelope.
        backend: Explicitly verified external backend, its loading error, or None.
        clock: Monotonic seconds, injectable for deterministic budget tests.

    Returns:
        A complete, partial or invalid-input hash-bound result. The time budget
        begins at this API call, after request transport and backend loading.
        Filesystem/setup work is checked afterward, not asynchronously interrupted.
    """
    started = clock()
    try:
        validate_depth(request)
        raw = canonical_bytes(request)
    except (ValueError, TypeError, RecursionError):
        return invalid_result("request_is_not_bounded_finite_json")
    request_hash = hashlib.sha256(raw).hexdigest()
    if len(raw) > OBJECT_LIMIT:
        return invalid_result("api_object_byte_limit", request_hash)
    if (
        not isinstance(request, dict)
        or request.keys() != {"schema_version", "records", "settings"}
        or request["schema_version"] != "termination-request-1"
        or not isinstance(request["records"], list)
        or not 1 <= len(request["records"]) <= MAX_RECORDS
    ):
        return invalid_result("invalid_envelope", request_hash)
    settings = request["settings"]
    if (
        not isinstance(settings, dict)
        or settings.keys() != {"max_seconds", "per_record_seconds"}
        or not _number(settings["max_seconds"], 300)
        or not _number(settings["per_record_seconds"], 60)
    ):
        return invalid_result("invalid_settings", request_hash)
    ids = [
        record["id"]
        for record in request["records"]
        if isinstance(record, dict) and _valid_id(record.get("id"))
    ]
    if len(ids) != len(set(ids)):
        return invalid_result("duplicate_record_id", request_hash)
    deadline = started + settings["max_seconds"]
    records = []
    for index, value in enumerate(request["records"]):
        if clock() >= deadline:
            records.append(_empty_record(index, value))
            continue
        result, sequence = _prepare(index, value)
        records.append(result)
        if sequence is None:
            continue
        remaining = deadline - clock()
        if remaining <= 0:
            continue
        if backend is None or isinstance(backend, TerminationBackendError):
            result.update(
                status="backend_failure",
                reason=backend.code if backend is not None else "backend_unavailable",
            )
            continue
        result["attempted"] = True
        try:
            native = backend.run(
                sequence,
                timeout_seconds=min(remaining, settings["per_record_seconds"]),
            )
            result["execution"] = native.diagnostics
            candidates = parse_output(native.stdout, sequence)
            if clock() >= deadline:
                result.update(
                    status="backend_failure", reason="batch_deadline_exceeded"
                )
                continue
            result.update(status="ok", reason=None, candidates=candidates)
        except TerminationBackendError as exc:
            result.update(status="backend_failure", reason=exc.code)
            if exc.diagnostics is not None:
                result["execution"] = exc.diagnostics
    return _finish(
        {
            "schema_version": "termination-result-1",
            "model": _model(backend),
            "request_sha256": request_hash,
            "status": "complete"
            if all(r["status"] == "ok" for r in records)
            else "partial",
            "reason": None,
            "settings": dict(settings),
            "coverage": _coverage(records),
            "warnings": list(WARNINGS),
            "records": records,
        }
    )

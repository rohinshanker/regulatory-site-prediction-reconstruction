"""Bounded ligand-total sweeps of the unchanged supplied-energy component."""

import hashlib
import json
import time
from copy import deepcopy

from regsite import __version__, conditional
from regsite.conditional_math import ConditionalError

OUTPUT_LIMIT = 8_388_608
NATIVE_LIMIT = 65_536
ALGORITHM = {
    "id": "explicit-conditional-concentration-sweep-1",
    "implementation_version": __version__,
}
WARNINGS = [
    "Supplied energies, affinity, concentrations and volumes are caller assumptions.",
    "Responses use the published-volume reconstruction "
    "without physical Kd equivalence.",
    "Sequence-to-switch inference, host accuracy and efficacy are unestablished.",
    "The outer admission budget preserves each admitted point's native time budget.",
]


class SweepError(ValueError):
    """An explicit sweep contract was violated."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SweepError(code)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def result_bytes(value: dict) -> bytes:
    """Finish authoritative finite output before writing any stdout prefix."""
    try:
        raw = (
            json.dumps(
                value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise SweepError("result_serialization_failure") from exc
    require(len(raw) <= OUTPUT_LIMIT, "output_byte_limit")
    return raw


def parse_request(value: object) -> tuple[dict, list[dict]]:
    """Reuse pure native admission without running the scalar calculation."""
    raw = conditional._parsed_bytes(value)
    request = json.loads(raw)
    conditional._object(
        request, "schema_version template ligand_total_molar seconds_total"
    )
    require(request["schema_version"] == "conditional-sweep-request-1", "sweep_schema")
    conditional._number(request["seconds_total"], positive=True, upper=120)
    template = conditional._object(
        request["template"], "schema_version id profile input provenance settings"
    )
    require(
        template["schema_version"] == "conditional-aptamer-request-1", "template_schema"
    )
    require(
        template["profile"] == "supplied_energy_response", "supplied_energy_required"
    )
    conditional._text(template["id"])
    conditional._provenance(template["provenance"])
    conditional._settings(template["settings"], template["profile"])
    data = conditional._response_input(template["input"])
    require(
        data["occupancy"]["mode"] == "published2015_volume", "volume_occupancy_required"
    )
    points = request["ligand_total_molar"]
    require(type(points) is list and 1 <= len(points) <= 64, "point_roster")
    concentrations = [conditional._number(point, lower=0) for point in points]
    generated = []
    for concentration in concentrations:
        point_request = deepcopy(template)
        point_request["input"]["occupancy"]["ligand_total_molar"] = concentration
        # Each complete generated native request must also fit the native input cap.
        conditional._parsed_bytes(point_request)
        generated.append(point_request)
    return request, generated


def _finish(result: dict) -> dict:
    result["result_sha256"] = digest(result)
    return result


def invalid_result(reason: str) -> dict:
    """Refuse without constructing a partial or invented point roster."""
    return _finish(
        {
            "schema_version": "conditional-sweep-result-1",
            "algorithm": deepcopy(ALGORITHM),
            "status": "invalid_input",
            "reason": reason,
            "request": None,
            "request_sha256": None,
            "sweep_id": None,
            "model": None,
            "coverage": None,
            "points": [],
            "warnings": list(WARNINGS),
        }
    )


def _point(request: dict, model: dict) -> tuple[dict, bool]:
    row: dict = {
        "status": "failed",
        "reasons": [],
        "native": None,
        "native_json_sha256": None,
    }
    try:
        native = conditional.predict_conditional(deepcopy(request))
        raw = conditional.result_bytes(native)
        row["native_json_sha256"] = hashlib.sha256(raw).hexdigest()
        require(
            len(raw) + 6 * len(raw.splitlines()) <= NATIVE_LIMIT, "native_result_limit"
        )
        require(type(native) is dict, "native_shape")
        row["native"] = native
        require(set(native) == set(conditional.invalid_result()), "native_shape")
        require(
            native["schema_version"] == "conditional-aptamer-result-1"
            and native["request_sha256"] == digest(request)
            and native["model"] == model
            and native["id"] == request["id"]
            and native["profile"] == request["profile"]
            and native["input"] == request["input"]
            and native["provenance"] == request["provenance"]
            and native["settings"]
            == conditional._settings(request["settings"], request["profile"]),
            "native_identity_mismatch",
        )
        require(native["states"] == [], "native_shape")
        status, reasons = native["status"], native["reasons"]
        require(
            status in {"ok", "failed", "no_mrna", "unsupported", "invalid_input"},
            "native_shape",
        )
        require(
            type(reasons) is list and all(type(r) is str and r for r in reasons),
            "native_shape",
        )
        require(
            type(native["complete"]) is bool and native["complete"] == (status == "ok"),
            "native_shape",
        )
        require(not reasons if status == "ok" else bool(reasons), "native_shape")
        require(
            type(native["response"]) is dict
            if status == "ok"
            else native["response"] is None or type(native["response"]) is dict,
            "native_shape",
        )
        row.update(status=status, reasons=reasons)
        return row, False
    except SweepError as exc:
        row["reasons"] = [str(exc)]
        return row, True
    except ConditionalError as exc:
        row["reasons"] = [exc.code]
        return row, exc.code == "result_limit"
    except (OSError, UnicodeError):
        row["reasons"] = ["prediction_execution_failed"]
        return row, False
    except (KeyError, TypeError, ValueError, RecursionError):
        row["reasons"] = ["invalid_native_result"]
        return row, True


def sweep(value: object) -> dict:
    """Evaluate exactly the caller's concentration roster without fitting."""
    started = time.monotonic()
    try:
        request, generated = parse_request(value)
    except ConditionalError as exc:
        return invalid_result(exc.code)
    except SweepError as exc:
        return invalid_result(str(exc))
    deadline = started + float(request["seconds_total"])
    model = conditional.invalid_result()["model"]
    rows = [
        {
            "index": index,
            "ligand_total_molar": point["input"]["occupancy"]["ligand_total_molar"],
            "point_request_sha256": digest(point),
            "attempted": False,
            "status": "not_run",
            "reasons": ["not_attempted"],
            "native": None,
            "native_json_sha256": None,
        }
        for index, point in enumerate(generated)
    ]
    stop = None
    for row, point in zip(rows, generated, strict=True):
        if time.monotonic() >= deadline and stop is None:
            stop = "deadline_exceeded"
        if stop is not None:
            row["reasons"] = [stop]
            continue
        row["attempted"] = True
        outcome, fatal = _point(point, model)
        row.update(outcome)
        if fatal:
            stop = row["reasons"][0]
    elapsed = max(0, time.monotonic() - started)
    deadline_exceeded = (
        elapsed > request["seconds_total"] or stop == "deadline_exceeded"
    )
    successful = sum(row["status"] == "ok" for row in rows)
    complete = successful == len(rows) and not deadline_exceeded
    return _finish(
        {
            "schema_version": "conditional-sweep-result-1",
            "algorithm": deepcopy(ALGORITHM),
            "status": "complete" if complete else "partial",
            "reason": None
            if complete
            else stop
            or ("deadline_exceeded" if deadline_exceeded else "point_failures"),
            "request": request,
            "request_sha256": digest(request),
            "sweep_id": digest(
                {"request": request, "algorithm": ALGORITHM, "model": model}
            ),
            "model": model,
            "coverage": {
                "planned": len(rows),
                "attempted": sum(row["attempted"] for row in rows),
                "successful": successful,
                "failed": sum(
                    row["attempted"] and row["status"] != "ok" for row in rows
                ),
                "not_run": sum(not row["attempted"] for row in rows),
                "deadline_exceeded": deadline_exceeded,
                "elapsed_seconds": elapsed,
            },
            "points": rows,
            "warnings": list(WARNINGS),
        }
    )

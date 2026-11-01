"""Deterministic bounded substitutions over fixed historical Promoter targets."""

import hashlib
import itertools
import json
import math
import time
from collections import Counter
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import cast

from regsite import __version__, promoter, promoter_io
from regsite import promoter_design_io as io
from regsite.promoter_design_io import DesignError, canonical, digest, pretty

ALGORITHM = {
    "id": "bounded-promoter-substitution-enumeration-1",
    "implementation_version": __version__,
}
WARNINGS = [
    "Original bounded enumeration, not the published or hosted design optimizer.",
    "Targets are relative model log scores, not measured or host-calibrated rates.",
    "Complete-context membership does not imply that an edit affects a score.",
    "Only explicit constraints are enforced; coding regions are not inferred.",
    "Outer deadlines are cooperative; late completed native outcomes are retained.",
]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise DesignError(reason)


def _object(value: object, keys: str, reason: str) -> dict:
    _require(type(value) is dict and set(value) == set(keys.split()), reason)
    assert isinstance(value, dict)
    return value


def _integer(value: object, low: int, high: int, reason: str) -> int:
    _require(type(value) in (int, float), reason)
    number = cast(int | float, value)
    _require(low <= number <= high and number == int(number), reason)
    return int(number)


def _number(value: object, reason: str, bound: float | None = None) -> float:
    _require(type(value) in (int, float), reason)
    try:
        number = float(cast(int | float, value))
    except OverflowError as exc:
        raise DesignError(reason) from exc
    _require(math.isfinite(number) and (bound is None or abs(number) <= bound), reason)
    return number


def _same(left: object, right: object, reason: str) -> None:
    _require(canonical(left) == canonical(right), reason)


@dataclass
class Plan:
    """Complete pure preflight and fixed identity, with no predictor execution."""

    request: dict
    params: promoter.PromoterParameters
    model: dict
    identity: dict
    targets: list[dict]
    constraints: dict
    limits: dict


def _prepare_native(request: dict, identity: dict) -> promoter_io.PreparedRecord:
    raw = {key: value for key, value in request.items() if key != "schema_version"}
    prepared = promoter_io._prepare(raw, identity, set(), {}, Counter())
    _require(
        prepared.result["status"] not in ("invalid_input", "unsupported"),
        "invalid_native_request",
    )
    return prepared


def parse_request(value: object) -> Plan:
    """Freeze the full bounded request and validate all constraints without scoring."""
    raw = canonical(value)
    _require(len(raw) <= io.INPUT_LIMIT, "canonical_input_limit")
    request = _object(
        json.loads(raw),
        "schema_version promoter target_log_scores "
        "editable_positions immutable_intervals max_changes limits",
        "request_fields",
    )
    _require(request["schema_version"] == "promoter-design-request-1", "request_schema")
    native = request["promoter"]
    required = {"schema_version", "id", "sequence", "calibration", "scan", "output"}
    _require(
        type(native) is dict
        and required <= native.keys()
        and native.keys() <= promoter_io.FIELDS | {"schema_version"},
        "native_fields",
    )
    _require(native["schema_version"] == "1.0", "native_schema")
    sequence = native["sequence"]
    _require(
        type(sequence) is str
        and 1 <= len(sequence) <= 1000
        and not sequence.strip("ACGT"),
        "canonical_dna_required",
    )
    _same(native["output"], promoter_io.OUTPUT_DEFAULTS, "selected_elements_required")
    scan = _object(native["scan"], "mode positions", "target_roster")
    _require(
        scan["mode"] == "positions"
        and type(scan["positions"]) is list
        and 1 <= len(scan["positions"]) <= 8,
        "target_roster",
    )
    desired = request["target_log_scores"]
    _require(
        type(desired) is list and len(desired) == len(scan["positions"]),
        "target_vector",
    )
    targets = []
    seen = set()
    for index, (position, score) in enumerate(
        zip(scan["positions"], desired, strict=True)
    ):
        position = _object(position, "strand tss", "target_roster")
        strand = position["strand"]
        _require(strand in ("+", "-"), "target_strand")
        forward = _integer(position["tss"], 0, len(sequence) - 1, "target_coordinate")
        _require((strand, forward) not in seen, "duplicate_target")
        seen.add((strand, forward))
        oriented = forward if strand == "+" else len(sequence) - 1 - forward
        _require(
            oriented >= 67 and oriented + 20 <= len(sequence), "incomplete_context"
        )
        interval = promoter.oriented_to_local_interval(
            len(sequence), strand, (oriented - 67, oriented + 20)
        )
        targets.append(
            {
                "index": index,
                "strand": strand,
                "forward_base": forward,
                "oriented_base": oriented,
                "target_log_score": _number(score, "target_score", 1e6),
                "admission_interval": list(interval),
            }
        )
    positions = request["editable_positions"]
    _require(type(positions) is list and len(positions) <= 1000, "editable_positions")
    editable = sorted(
        _integer(p, 0, len(sequence) - 1, "editable_position") for p in positions
    )
    _require(len(set(editable)) == len(editable), "duplicate_editable_position")
    intervals = request["immutable_intervals"]
    _require(type(intervals) is list and len(intervals) <= 1000, "immutable_intervals")
    immutable = []
    previous = 0
    for interval in intervals:
        _require(type(interval) is list and len(interval) == 2, "immutable_interval")
        left, right = [
            _integer(p, 0, len(sequence), "immutable_interval") for p in interval
        ]
        _require(previous <= left < right, "immutable_interval_order")
        immutable.append([left, right])
        previous = right
    for position in editable:
        _require(
            any(
                t["admission_interval"][0] <= position < t["admission_interval"][1]
                for t in targets
            ),
            "edit_outside_context",
        )
        _require(not any(a <= position < b for a, b in immutable), "edit_is_immutable")
    changes = _integer(request["max_changes"], 0, min(2, len(editable)), "max_changes")
    supplied_limits = _object(
        request["limits"],
        "max_candidates seconds_per_candidate seconds_total",
        "limits_fields",
    )
    limits: dict = {
        "max_candidates": _integer(
            supplied_limits["max_candidates"], 1, 64, "max_candidates"
        )
    }
    for key, maximum in (("seconds_per_candidate", 10), ("seconds_total", 120)):
        seconds = _number(supplied_limits[key], key)
        _require(0 < seconds <= maximum, key)
        limits[key] = seconds
    size = sum(
        math.comb(len(editable), count) * 3**count for count in range(changes + 1)
    )
    _require(size <= limits["max_candidates"], "candidate_limit")
    params = promoter.load_parameters()
    model, identity = promoter_io.model_identity(params)
    _prepare_native(native, identity)
    return Plan(
        request,
        params,
        model,
        identity,
        targets,
        {
            "editable_positions": editable,
            "immutable_intervals": immutable,
            "max_changes": changes,
        },
        limits,
    )


def _edits(plan: Plan, sequence: str) -> list[dict]:
    original = plan.request["promoter"]["sequence"]
    return [
        {
            "position": index,
            "from": old,
            "to": new,
            "oriented": [
                {
                    "target_index": target["index"],
                    "position": index
                    if target["strand"] == "+"
                    else len(original) - 1 - index,
                    "from": promoter.orient(old, target["strand"]),
                    "to": promoter.orient(new, target["strand"]),
                }
                for target in plan.targets
            ],
        }
        for index, (old, new) in enumerate(zip(original, sequence, strict=True))
        if old != new
    ]


def _sequences(plan: Plan) -> Iterator[str]:
    original = plan.request["promoter"]["sequence"]
    for count in range(plan.constraints["max_changes"] + 1):
        for positions in itertools.combinations(
            plan.constraints["editable_positions"], count
        ):
            alternatives = [
                [base for base in "ACGT" if base != original[p]] for p in positions
            ]
            for replacements in itertools.product(*alternatives):
                bases = list(original)
                for position, base in zip(positions, replacements, strict=True):
                    bases[position] = base
                yield "".join(bases)


def _candidate(plan: Plan, design_id: str, index: int, sequence: str) -> dict:
    sequence_hash = hashlib.sha256(sequence.encode()).hexdigest()
    native_request = deepcopy(plan.request["promoter"])
    native_request["sequence"] = sequence
    return {
        "index": index,
        "candidate_id": digest(
            {"design_id": design_id, "index": index, "sequence_sha256": sequence_hash}
        ),
        "sequence": sequence,
        "sequence_sha256": sequence_hash,
        "edits": _edits(plan, sequence),
        "native_request": native_request,
        "native_request_sha256": digest(native_request),
        "attempted": False,
        "status": "not_run",
        "reason": "not_started",
        "native": None,
        "native_sha256": None,
        "native_bytes": None,
        "native_admitted": False,
        "objective": None,
        "observed_log_scores": None,
        "absolute_log_errors": None,
    }


def _constraints(plan: Plan, row: dict) -> None:
    sequence = row["sequence"]
    original = plan.request["promoter"]["sequence"]
    _require(
        type(sequence) is str
        and len(sequence) == len(original)
        and not sequence.strip("ACGT"),
        "candidate_constraints",
    )
    edits = _edits(plan, sequence)
    _require(
        len(edits) <= plan.constraints["max_changes"]
        and all(
            edit["position"] in plan.constraints["editable_positions"] for edit in edits
        )
        and all(
            sequence[a:b] == original[a:b]
            for a, b in plan.constraints["immutable_intervals"]
        ),
        "candidate_constraints",
    )
    _same(edits, row["edits"], "candidate_constraints")
    expected = {**plan.request["promoter"], "sequence": sequence}
    _same(row["native_request"], expected, "candidate_constraints")
    _same(row["native_request_sha256"], digest(expected), "candidate_constraints")
    _prepare_native(expected, plan.identity)


def _site(prepared: promoter_io.PreparedRecord, native: dict, target: dict) -> dict:
    """Reconstruct native serialization/coordinates, never rescore feature terms."""
    assert prepared.sequence is not None and prepared.calibration is not None
    assert prepared.scope_id is not None
    _require(type(native) is dict, "native_site_shape")
    status = cast(str, native.get("status"))
    _require(status in ("ok", "failed", "no_candidate"), "native_site_status")
    _require(
        native.get("state_count") == 30 and type(native.get("state_count")) is int,
        "native_context",
    )
    attempted = cast(bool, native.get("attempted"))
    _require(type(attempted) is bool, "native_site_shape")
    selected = None
    ties = None
    reason = native.get("reason")
    if status == "ok":
        _require(
            attempted and reason is None and type(native.get("selected")) is dict,
            "native_score_shape",
        )
        state = native["selected"]
        d = _integer(state.get("discriminator_length"), 6, 10, "native_state")
        s = _integer(state.get("spacer_length"), 15, 20, "native_state")
        ties = _integer(native.get("tie_count"), 1, 30, "native_state")
        terms = _object(
            state.get("terms"), " ".join(promoter.TERM_SOURCE_NAMES), "native_terms"
        )
        for value in terms.values():
            _number(value, "native_terms")
        windows = promoter.state_windows(target["oriented_base"], d, s)
        oriented = promoter.orient(prepared.sequence, target["strand"])
        elements = {
            name: oriented[a:b]
            for name, (a, b) in windows.items()
            if name not in ("gap", "extended10")
        }
        selected = promoter.StateScore(d, s, terms, windows, elements)
    else:
        _require(
            status == "failed"
            and reason in ("deadline_exceeded", "nonfinite_arithmetic")
            and (attempted or reason == "deadline_exceeded"),
            "native_context",
        )
    expected = promoter.SiteResult(
        target["strand"],
        target["forward_base"],
        target["oriented_base"],
        len(prepared.sequence),
        status,
        reason,
        30,
        ties,
        selected,
        None,
        prepared.calibration,
    ).to_dict(elements=True, projection=prepared.result["projection"])
    site_id = (
        f"psite1:{prepared.scope_id[:32]}:{target['strand']}:{target['forward_base']}"
    )
    expected.update(site_id=site_id, attempted=attempted)
    if selected is not None:
        expected["selected"]["state_id"] = (
            f"{site_id}:d{selected.discriminator_length}s{selected.spacer_length}"
        )
    _same(native, expected, "native_site_contract")
    return expected


def _admit(plan: Plan, request: dict, native: dict) -> tuple[str, list[float] | None]:
    _object(native, "schema_version model batch results", "native_shape")
    _require(native["schema_version"] == "1.0", "native_schema")
    _same(native["model"], plan.model, "native_model")
    _require(
        type(native["results"]) is list and len(native["results"]) == 1, "native_roster"
    )
    prepared = _prepare_native(request, plan.identity)
    record = native["results"][0]
    _object(record, " ".join(prepared.result), "native_record_shape")
    expected = deepcopy(prepared.result)
    if record["status"] == "unsupported":
        errors = record["errors"]
        _require(type(errors) is list and bool(errors), "native_failure_shape")
        for error in errors:
            _object(error, "code field message", "native_failure_shape")
            _require(
                error["code"] in ("unsupported_control", "model_unavailable")
                and type(error["field"]) is str
                and type(error["message"]) is str,
                "native_failure_shape",
            )
        expected.update(
            status="unsupported",
            prediction_id=None,
            coverage=None,
            errors=errors,
            reasons=list(dict.fromkeys(error["code"] for error in errors)),
        )
    else:
        _require(
            type(record["sites"]) is list and len(record["sites"]) == len(plan.targets),
            "native_roster",
        )
        expected["sites"] = [
            _site(prepared, site, target)
            for site, target in zip(record["sites"], plan.targets, strict=True)
        ]
        promoter_io._summarize(expected)
    _same(record, expected, "native_record_contract")
    seconds = plan.limits["seconds_per_candidate"]
    batch_id = digest(
        {
            "input": request,
            "model": {
                key: plan.identity[key]
                for key in ("id", "implementation_version", "parameter_json_sha256")
            },
            "limits": promoter_io.LIMITS,
            "seconds_per_record": seconds,
            "seconds_per_batch": seconds,
            "cli_calibration": None,
            "cli_states": None,
        }
    )
    _same(
        native["batch"],
        {
            "batch_id": batch_id,
            "record_count": 1,
            "status_counts": {
                status: int(record["status"] == status)
                for status in promoter_io.STATUSES
            },
            "complete": record["status"] != "failed",
            "limits": dict(promoter_io.LIMITS),
            "seconds_per_record": seconds,
            "seconds_per_batch": seconds,
        },
        "native_batch_contract",
    )
    observed = (
        None
        if record["status"] != "ok"
        else [
            site["selected"]["log_relative_transcription_score"]
            for site in record["sites"]
        ]
    )
    return record["status"], observed


def _evaluate(plan: Plan, row: dict, clock: Callable[[], float]) -> str | None:
    """Retain bounded native evidence and return a reason that stops admission."""
    row["attempted"] = True
    seconds = plan.limits["seconds_per_candidate"]
    try:
        native = promoter_io.predict_batch(
            deepcopy(row["native_request"]),
            plan.params,
            seconds_per_record=seconds,
            seconds_per_batch=seconds,
            clock=clock,
        )
    except Exception:
        row.update(status="failed", reason="prediction_error")
        return "prediction_error"
    try:
        raw = pretty(native)
    except DesignError:
        row.update(status="failed", reason="native_serialization")
        return "native_serialization"
    row.update(native_bytes=len(raw), native_sha256=hashlib.sha256(raw).hexdigest())
    if len(raw) > io.NATIVE_LIMIT or type(native) is not dict:
        reason = "native_output_limit" if len(raw) > io.NATIVE_LIMIT else "native_shape"
        row.update(status="failed", reason=reason)
        return reason
    row["native"] = json.loads(raw)
    try:
        status, observed = _admit(plan, row["native_request"], row["native"])
    except (DesignError, ValueError, TypeError, KeyError, ArithmeticError):
        row.update(status="failed", reason="native_contract")
        return "native_contract"
    row.update(
        status=status,
        native_admitted=True,
        observed_log_scores=observed,
        reason=None if status == "ok" else "native_" + status,
    )
    if observed is not None:
        errors = [
            abs(value - target["target_log_score"])
            for value, target in zip(observed, plan.targets, strict=True)
        ]
        row["absolute_log_errors"] = errors
        try:
            objective = math.fsum(errors) / len(errors)
            _require(math.isfinite(objective), "objective_unrepresentable")
        except (ArithmeticError, DesignError):
            row.update(status="failed", reason="objective_unrepresentable")
        else:
            row["objective"] = objective
    return None


def _finish(result: dict) -> dict:
    result["result_sha256"] = digest(result)
    return result


def invalid_result(reason: str) -> dict:
    """Emit a small refusal without inventing an admitted request or roster."""
    return _finish(
        {
            "schema_version": "promoter-design-result-1",
            "algorithm": dict(ALGORITHM),
            "model": None,
            "model_identity": None,
            "request": None,
            "request_sha256": None,
            "design_id": None,
            "targets": [],
            "constraints": None,
            "limits": None,
            "status": "invalid_input",
            "reason": reason,
            "coverage": None,
            "candidates": [],
            "proposal": None,
            "confirmation": None,
            "selected": None,
            "elapsed_seconds": 0.0,
            "warnings": list(WARNINGS),
        }
    )


def _proposal(row: dict) -> dict:
    return {
        key: deepcopy(row[key])
        for key in (
            "index",
            "candidate_id",
            "sequence",
            "sequence_sha256",
            "edits",
            "native_sha256",
            "objective",
            "observed_log_scores",
            "absolute_log_errors",
        )
    }


def design(value: object, *, clock: Callable[[], float] = time.monotonic) -> dict:
    """Search every declared candidate with fixed budgets and fresh confirmation."""
    start = clock()
    try:
        plan = parse_request(value)
    except DesignError as exc:
        return invalid_result(str(exc))
    except (promoter.ParameterError, promoter.InputError, OSError):
        return invalid_result("model_or_native_setup")
    request_hash = digest(plan.request)
    design_id = digest(
        {
            "request_sha256": request_hash,
            "algorithm": ALGORITHM,
            "model_identity": plan.identity,
            "targets": plan.targets,
            "limits": plan.limits,
        }
    )
    rows = [
        _candidate(plan, design_id, index, sequence)
        for index, sequence in enumerate(_sequences(plan))
    ]
    stop = None
    deadline = start + plan.limits["seconds_total"]
    overrun = False
    for row in rows:
        overrun = overrun or clock() >= deadline
        if stop is None and overrun:
            stop = "total_deadline"
        if stop is not None:
            row["reason"] = stop
            continue
        try:
            _constraints(plan, row)
        except DesignError:
            stop = row["reason"] = "candidate_constraints"
            continue
        if clock() >= deadline:
            overrun = True
            stop = row["reason"] = "total_deadline"
            continue
        stop = _evaluate(plan, row, clock)
        overrun = overrun or clock() >= deadline
    successful = [row for row in rows if row["status"] == "ok"]
    proposal = confirmation = selected = None
    if successful:
        winner = min(
            successful,
            key=lambda row: (row["objective"], len(row["edits"]), row["sequence"]),
        )
        proposal = _proposal(winner)
        fresh = _candidate(plan, design_id, winner["index"], winner["sequence"])
        overrun = overrun or clock() >= deadline
        if stop is None and overrun:
            stop = "total_deadline"
        if stop is None:
            try:
                _constraints(plan, fresh)
            except DesignError:
                stop = "candidate_constraints"
        if stop is None and clock() >= deadline:
            overrun = True
            stop = "total_deadline"
        if stop is None:
            stop = _evaluate(plan, fresh, clock)
            overrun = overrun or clock() >= deadline
        else:
            fresh["reason"] = stop
        matched = (
            fresh["status"] == "ok"
            and fresh["native_sha256"] == winner["native_sha256"]
        )
        status = (
            ("matched" if matched else "mismatch")
            if fresh["status"] == "ok"
            else ("failed" if fresh["attempted"] else "not_run")
        )
        confirmation = {
            "candidate_index": winner["index"],
            "status": status,
            "reason": None
            if matched
            else ("confirmation_mismatch" if status == "mismatch" else fresh["reason"]),
            **{
                key: fresh[key]
                for key in (
                    "attempted",
                    "native_request_sha256",
                    "native",
                    "native_sha256",
                    "native_bytes",
                    "native_admitted",
                )
            },
        }
        if matched:
            selected = deepcopy(proposal)
    finished = clock()
    overrun = overrun or finished >= deadline
    if overrun and stop is None:
        stop = "total_deadline"
    attempted = sum(row["attempted"] for row in rows)
    complete = len(successful) == len(rows) and selected is not None and not overrun
    status = "complete" if complete else ("partial" if successful else "no_candidate")
    result = _finish(
        {
            "schema_version": "promoter-design-result-1",
            "algorithm": dict(ALGORITHM),
            "model": plan.model,
            "model_identity": plan.identity,
            "request": plan.request,
            "request_sha256": request_hash,
            "design_id": design_id,
            "targets": plan.targets,
            "constraints": plan.constraints,
            "limits": plan.limits,
            "status": status,
            "reason": None if complete else (stop or "incomplete_search"),
            "coverage": {
                "planned": len(rows),
                "attempted": attempted,
                "successful": len(successful),
                "failed": attempted - len(successful),
                "not_run": len(rows) - attempted,
                "prediction_calls": attempted
                + int(confirmation is not None and confirmation["attempted"]),
                "all_candidates_scored": len(successful) == len(rows),
                "deadline_exceeded": overrun,
                "stop_reason": stop,
            },
            "candidates": rows,
            "proposal": proposal,
            "confirmation": confirmation,
            "selected": selected,
            "elapsed_seconds": max(0.0, finished - start),
            "warnings": list(WARNINGS),
        }
    )
    try:
        io.result_bytes(result)
    except DesignError:
        return invalid_result("result_serialization_failure")
    return result

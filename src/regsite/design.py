"""Deterministic bounded leader substitutions using unchanged RBS predictors."""

import math
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import combinations, product

from regsite import __version__
from regsite import design_io as wire
from regsite.backend import RnaStructure
from regsite.contracts import RbsRequest
from regsite.profiles import PROFILES, Profile, get_profile
from regsite.rbs import predict
from regsite.sequence import InputError, input_interval, sequence_hash
from regsite.structures import BackendError

ALGORITHM = "exhaustive-rbs-leader-substitutions-1"
WARNINGS = [
    "Target and predictions use model-relative TIR units, not measured expression.",
    "Native host accuracy and biological improvement are not established.",
    "Missing or failed candidates prevent a whole-neighborhood optimum claim.",
    "Only caller-selected leader substitutions are searched; coding DNA is fixed.",
]
FIELDS = {
    "schema_version",
    "rbs",
    "profile",
    "target_tir",
    "editable_positions",
    "max_changes",
    "limits",
}
LIMITS = {"max_candidates", "seconds_per_score", "seconds_total"}


def require(condition: bool, reason: str) -> None:
    """Refuse a violated deterministic contract."""
    if not condition:
        raise wire.DesignError(reason)


def positive(value: object, maximum: float = math.inf) -> bool:
    """Accept finite positive JSON numbers, never booleans or coercions."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 < value <= min(maximum, sys.float_info.max)
    )


@dataclass(frozen=True)
class Request:
    """Validated fixed search domain in supplied-input coordinates."""

    raw: dict
    rbs: RbsRequest
    profile: Profile
    start: int
    positions: tuple[int, ...]
    changes: int
    count: int
    target_log: float
    seconds: float
    total_seconds: float


def parse_request(value: object) -> Request:
    """Admit a complete neighborhood before a backend/scorer is invoked."""
    require(type(value) is dict and set(value) == FIELDS, "request_fields")
    assert isinstance(value, dict)
    require(value["schema_version"] == "rbs-design-request-1", "request_schema")
    try:
        require(len(wire.canonical(value)) <= wire.INPUT_LIMIT, "input_byte_limit")
        native = RbsRequest.from_dict(value["rbs"])
    except (InputError, TypeError, ValueError, RecursionError) as exc:
        raise wire.DesignError("invalid_rbs_request") from exc
    sequence = value["rbs"]["sequence"]
    require(
        type(sequence) is str
        and 0 < len(sequence) <= 1000
        and set(sequence) <= set("ACGT"),
        "canonical_dna_required",
    )
    require(
        native.start_positions is not None and len(native.start_positions) == 1,
        "one_explicit_start_required",
    )
    assert native.start_positions is not None
    start = native.start_positions[0]
    require(
        start > 0
        and native.oriented_sequence[start : start + 3] in {"AUG", "GUG", "UUG"},
        "supported_start_required",
    )
    require(value["profile"] in [p.name for p in PROFILES], "profile")
    profile = get_profile(value["profile"])
    require(positive(value["target_tir"]), "target_tir")
    positions = value["editable_positions"]
    require(
        type(positions) is list and all(type(p) is int for p in positions),
        "editable_positions",
    )
    require(len(positions) == len(set(positions)), "duplicate_editable_position")
    begin = max(0, start - profile.upstream_nt)
    for position in positions:
        oriented = position if native.strand == "+" else len(sequence) - 1 - position
        require(
            0 <= position < len(sequence) and begin <= oriented < start,
            "editable_position_outside_leader_window",
        )
    changes = value["max_changes"]
    require(
        type(changes) is int and 0 <= changes <= min(2, len(positions)), "max_changes"
    )
    limits = value["limits"]
    require(type(limits) is dict and set(limits) == LIMITS, "limits_fields")
    cap = limits["max_candidates"]
    require(type(cap) is int and 1 <= cap <= 256, "candidate_limit")
    require(positive(limits["seconds_per_score"], 120), "score_seconds")
    require(positive(limits["seconds_total"], 3600), "total_seconds")
    count = sum(math.comb(len(positions), k) * 3**k for k in range(changes + 1))
    require(count <= cap, "search_space_limit")
    return Request(
        deepcopy(value),
        native,
        profile,
        start,
        tuple(sorted(positions)),
        changes,
        count,
        math.log(value["target_tir"]),
        float(limits["seconds_per_score"]),
        float(limits["seconds_total"]),
    )


def candidates(request: Request) -> list[str]:
    """Enumerate every allowed candidate once in a stable, outcome-free order."""
    seed = request.raw["rbs"]["sequence"]
    output = [seed]
    for count in range(1, request.changes + 1):
        for positions in combinations(request.positions, count):
            choices = [
                tuple(base for base in "ACGT" if base != seed[p]) for p in positions
            ]
            for bases in product(*choices):
                sequence = list(seed)
                for position, base in zip(positions, bases, strict=True):
                    sequence[position] = base
                output.append("".join(sequence))
    return output


def checked_edits(sequence: str, request: Request) -> list[dict]:
    """Independently verify all immutable bases and return exact edit mappings."""
    seed = request.raw["rbs"]["sequence"]
    require(
        len(sequence) == len(seed) and set(sequence) <= set("ACGT"),
        "candidate_sequence_constraint",
    )
    edits = []
    for i, (old, new) in enumerate(zip(seed, sequence, strict=True)):
        if old != new:
            require(i in request.positions, "immutable_position_changed")
            edits.append(
                {
                    "input_position": i,
                    "oriented_position": i
                    if request.rbs.strand == "+"
                    else len(seed) - 1 - i,
                    "from": old,
                    "to": new,
                }
            )
    require(len(edits) <= request.changes, "edit_count_constraint")
    return edits


def _finish(result: dict) -> dict:
    result["result_sha256"] = wire.digest(result)
    return result


def invalid_result(reason: str) -> dict:
    """Return a small refusal without an invented roster or selected sequence."""
    return _finish(
        {
            "schema_version": "rbs-design-result-1",
            "status": "invalid_input",
            "reason": reason,
            "algorithm": {"id": ALGORITHM, "implementation_version": __version__},
            "request": None,
            "request_sha256": None,
            "design_id": None,
            "backend": None,
            "model": None,
            "coverage": None,
            "candidates": [],
            "best_observed_index": None,
            "selected": None,
            "confirmation": None,
            "warnings": list(WARNINGS),
        }
    )


def _native_result(
    sequence: str,
    request: Request,
    backend: RnaStructure,
    identity: dict,
    model: dict | None,
    remaining: float,
) -> tuple[dict, dict | None, bool]:
    """Score once, retaining ordinary failures and stopping identity substitutions."""
    row: dict = {
        "status": "failed",
        "reason": None,
        "native": None,
        "native_sha256": None,
        "score": None,
    }
    try:
        require(backend.identity == identity, "native_identity_mismatch")
        value = dict(request.raw["rbs"], sequence=sequence)
        native = predict(
            value,
            backend,
            seconds=request.seconds,
            profile=request.profile.name,
            execution_seconds=min(request.seconds, remaining),
        )
        row["native_sha256"] = wire.digest(native)
        pretty = wire.pretty(native)
        require(
            len(pretty) + 6 * len(pretty.splitlines()) <= wire.NATIVE_LIMIT,
            "native_result_limit",
        )
        row["native"] = native
        native_input = asdict(RbsRequest.from_dict(value))
        require(
            native["backend"] == identity and backend.identity == identity,
            "native_identity_mismatch",
        )
        require(
            native["input"] == native_input
            and native["model"]["id"] == request.profile.model_id,
            "native_identity_mismatch",
        )
        require(model is None or native["model"] == model, "native_identity_mismatch")
        model = deepcopy(native["model"])
        expected = wire.digest(
            {
                "input": native_input,
                "model": model,
                "backend": identity,
                "budget_seconds": request.seconds,
            }
        )
        require(native["prediction_id"] == expected, "native_identity_mismatch")
        status = native["status"]
        require(
            status in {"ok", "failed", "unsupported", "no_candidate"},
            "invalid_native_result",
        )
        sites = native["sites"]
        require(type(sites) is list and len(sites) <= 1, "invalid_native_result")
        reason = sites[0]["reason"] if sites else native["reason"]
        if sites:
            begin = max(0, request.start - request.profile.upstream_nt)
            end = min(len(sequence), request.start + request.profile.downstream_nt)
            require(
                sites[0]["window"]
                == {
                    "oriented_start": begin,
                    "oriented_end": end,
                    "input_interval": asdict(
                        input_interval(begin, end, len(sequence), request.rbs.strand)
                    ),
                }
                and sites[0]["start_codon"]
                == asdict(
                    input_interval(
                        request.start,
                        request.start + 3,
                        len(sequence),
                        request.rbs.strand,
                    )
                )
                and sites[0]["codon"]
                == request.rbs.oriented_sequence[request.start : request.start + 3],
                "invalid_native_result",
            )
            require(
                sites[0]["oriented_start"] == request.start
                and sites[0]["status"] == status
                and native["reason"] is None,
                "invalid_native_result",
            )
        if status == "ok":
            require(len(sites) == 1 and reason is None, "invalid_native_result")
            site = sites[0]
            require(
                positive(site["tir"])
                and type(site["log_tir"]) in (int, float)
                and -sys.float_info.max <= site["log_tir"] <= sys.float_info.max,
                "invalid_native_result",
            )
            require(
                math.isclose(
                    math.log(site["tir"]), site["log_tir"], rel_tol=1e-12, abs_tol=1e-12
                ),
                "invalid_native_result",
            )
            row["score"] = {
                "tir": site["tir"],
                "log_tir": site["log_tir"],
                "absolute_log_error": abs(site["log_tir"] - request.target_log),
            }
        else:
            require(type(reason) is str and bool(reason), "invalid_native_result")
            require(
                not sites or sites[0]["tir"] is None and sites[0]["log_tir"] is None,
                "invalid_native_result",
            )
        row.update(status=status, reason=reason)
        return row, model, False
    except wire.DesignError as exc:
        row.update(reason=str(exc))
        return row, model, True
    except (BackendError, OSError, UnicodeError):
        row.update(reason="prediction_execution_failed")
        return row, model, False
    except (KeyError, TypeError, ValueError, RecursionError):
        row.update(reason="invalid_native_result")
        return row, model, True


def design(value: object, backend: RnaStructure) -> dict:
    """Search the declared finite domain and independently confirm one proposal."""
    started = time.monotonic()
    try:
        request = parse_request(value)
    except wire.DesignError as exc:
        return invalid_result(str(exc))
    identity = deepcopy(backend.identity)
    sequences = candidates(request)
    rows: list[dict] = [
        {
            "index": i,
            "sequence": seq,
            "sequence_sha256": sequence_hash(seq),
            "edits": checked_edits(seq, request),
            "attempted": False,
            "status": "not_run",
            "reason": "not_attempted",
            "native": None,
            "native_sha256": None,
            "score": None,
        }
        for i, seq in enumerate(sequences)
    ]
    deadline = started + request.total_seconds
    model: dict | None = None
    calls = 0
    stop: str | None = None
    for row in rows:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop = "deadline"
        if stop is not None:
            row["reason"] = stop
            continue
        row["attempted"] = True
        calls += 1
        outcome, model, fatal = _native_result(
            row["sequence"], request, backend, identity, model, remaining
        )
        row.update(outcome)
        if fatal:
            stop = row["reason"]
        elif time.monotonic() > deadline:
            stop = "deadline"
    successful = [row for row in rows if row["status"] == "ok"]
    best = (
        min(
            successful,
            key=lambda row: (
                row["score"]["absolute_log_error"],
                len(row["edits"]),
                row["sequence"],
            ),
        )
        if successful
        else None
    )
    selected = None
    confirmation: dict = {
        "status": "not_run",
        "reason": "no_successful_candidate",
        "candidate_index": None,
        "native": None,
        "native_sha256": None,
    }
    if best is not None:
        confirmation["candidate_index"] = best["index"]
        remaining = deadline - time.monotonic()
        if stop is not None or remaining <= 0:
            confirmation["reason"] = stop or "deadline"
        else:
            checked_edits(best["sequence"], request)
            calls += 1
            check, _, _ = _native_result(
                best["sequence"], request, backend, identity, model, remaining
            )
            confirmation.update(
                {
                    key: check[key]
                    for key in ("status", "reason", "native", "native_sha256")
                }
            )
            if time.monotonic() > deadline:
                confirmation.update(status="failed", reason="deadline")
            elif (
                check["status"] == "ok"
                and check["native_sha256"] == best["native_sha256"]
            ):
                confirmation["status"] = "verified"
                selected = {
                    key: deepcopy(best[key])
                    for key in (
                        "index",
                        "sequence",
                        "sequence_sha256",
                        "edits",
                        "score",
                    )
                }
            elif check["status"] == "ok":
                confirmation.update(status="failed", reason="confirmation_mismatch")
    complete = len(successful) == len(rows) and selected is not None
    status = "complete" if complete else "partial" if best else "no_candidate"
    reason = (
        None
        if complete
        else stop
        or (
            "candidate_failures"
            if selected
            else "unverified_selection"
            if best
            else "no_successful_candidate"
        )
    )
    return _finish(
        {
            "schema_version": "rbs-design-result-1",
            "status": status,
            "reason": reason,
            "algorithm": {"id": ALGORITHM, "implementation_version": __version__},
            "request": request.raw,
            "request_sha256": wire.digest(request.raw),
            "design_id": wire.digest(
                {
                    "request": request.raw,
                    "algorithm": ALGORITHM,
                    "implementation_version": __version__,
                    "backend": identity,
                }
            ),
            "backend": identity,
            "model": model,
            "coverage": {
                "planned": len(rows),
                "attempted": sum(r["attempted"] for r in rows),
                "successful": len(successful),
                "not_run": sum(not r["attempted"] for r in rows),
                "failed": sum(r["attempted"] and r["status"] != "ok" for r in rows),
                "prediction_calls": calls,
                "all_candidates_scored": len(successful) == len(rows),
                "elapsed_seconds": max(0, time.monotonic() - started),
            },
            "candidates": rows,
            "best_observed_index": best["index"] if best else None,
            "selected": selected,
            "confirmation": confirmation,
            "warnings": list(WARNINGS),
        }
    )

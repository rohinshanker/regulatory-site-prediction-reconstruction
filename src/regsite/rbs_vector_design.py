"""Bounded component-RBS target design with every supplied coding span fixed."""

import hashlib
import math
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import combinations, product

from regsite import __version__, rbs
from regsite import design_io as wire
from regsite.backend import RnaStructure
from regsite.contracts import RbsRequest
from regsite.profiles import PROFILES, Profile, get_profile
from regsite.sequence import InputError, input_interval, sequence_hash
from regsite.structures import BackendError

ALGORITHM = "bounded-rbs-vector-substitution-enumeration-1"
NATIVE_LIMIT = 524_288
FIELDS = {
    "schema_version",
    "rbs",
    "profile",
    "cds",
    "target_tirs",
    "editable_positions",
    "max_changes",
    "limits",
}
WARNINGS = [
    "Targets are component-relative initiation scores, not measured expression.",
    "Coupling and joint protein abundance are not inferred from these targets.",
    "Supplied coding annotations and reading frames are not independently verified.",
    "Every supplied coding interval and every unlisted base remains immutable.",
    "Incomplete candidate coverage cannot establish a whole-neighborhood optimum.",
    "Native host accuracy and biological improvement are not established.",
]
STATUSES = ("failed", "unsupported", "no_candidate", "ok")


def require(condition: bool, reason: str) -> None:
    """Refuse a violated finite input or native-response contract."""
    if not condition:
        raise wire.DesignError(reason)


def _positive(value: object, maximum: float = sys.float_info.max) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 < value <= maximum
    )


def _text(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and all(ord(c) >= 32 and ord(c) != 127 for c in value)
    )


@dataclass(frozen=True)
class Request:
    """Validated whole-transcript target roster and permitted finite edits."""

    raw: dict
    native: RbsRequest
    profile: Profile
    cds: tuple[dict, ...]
    targets: tuple[dict, ...]
    positions: tuple[int, ...]
    changes: int
    count: int
    seconds: float
    total_seconds: float


def parse_request(value: object) -> Request:
    """Admit the entire target/edit domain before opening or using a backend."""
    require(type(value) is dict and set(value) == FIELDS, "request_fields")
    assert isinstance(value, dict)
    require(value["schema_version"] == "rbs-vector-design-request-1", "request_schema")
    try:
        require(len(wire.canonical(value)) <= wire.INPUT_LIMIT, "input_byte_limit")
        native = RbsRequest.from_dict(value["rbs"])
    except (InputError, TypeError, ValueError, RecursionError) as exc:
        raise wire.DesignError("invalid_rbs_request") from exc
    sequence = value["rbs"]["sequence"]
    require(
        type(sequence) is str
        and 0 < len(sequence) <= 10_000
        and set(sequence) <= set("ACGT"),
        "canonical_dna_required",
    )
    require(value["profile"] in [p.name for p in PROFILES], "profile")
    profile = get_profile(value["profile"])
    cds = value["cds"]
    require(type(cds) is list and 1 <= len(cds) <= 10, "cds_roster")
    starts: list[int] = []
    identifiers = set()
    for row in cds:
        require(type(row) is dict and set(row) == {"id", "start", "end"}, "cds_fields")
        identifier, start, end = row["id"], row["start"], row["end"]
        require(_text(identifier) and identifier not in identifiers, "cds_id")
        require(
            type(start) is int
            and type(end) is int
            and 0 < start
            and start + 3 <= end <= len(sequence)
            and (end - start) % 3 == 0,
            "cds_interval",
        )
        require(not starts or start > starts[-1], "cds_order")
        require(
            native.oriented_sequence[start : start + 3] in rbs.START_ENERGIES,
            "supported_start_required",
        )
        starts.append(start)
        identifiers.add(identifier)
    raw_starts = value["rbs"].get("start_positions")
    require(
        type(raw_starts) is list
        and all(type(s) is int for s in raw_starts)
        and raw_starts == starts,
        "explicit_start_roster",
    )
    targets = value["target_tirs"]
    require(
        type(targets) is list
        and len(targets) == len(cds)
        and all(_positive(target) for target in targets),
        "target_tirs",
    )
    positions = value["editable_positions"]
    require(
        type(positions) is list and all(type(p) is int for p in positions),
        "editable_positions",
    )
    require(len(positions) == len(set(positions)), "duplicate_editable_position")
    for position in positions:
        oriented = position if native.strand == "+" else len(sequence) - 1 - position
        require(
            0 <= position < len(sequence)
            and any(
                max(0, start - profile.upstream_nt) <= oriented < start
                for start in starts
            ),
            "editable_position_outside_leader_windows",
        )
        require(
            all(not row["start"] <= oriented < row["end"] for row in cds),
            "editable_position_in_coding_region",
        )
    changes = value["max_changes"]
    require(
        type(changes) is int and 0 <= changes <= min(2, len(positions)), "max_changes"
    )
    limits = value["limits"]
    require(
        type(limits) is dict
        and set(limits) == {"max_candidates", "seconds_per_score", "seconds_total"},
        "limits_fields",
    )
    require(
        type(limits["max_candidates"]) is int and 1 <= limits["max_candidates"] <= 64,
        "candidate_limit",
    )
    require(_positive(limits["seconds_per_score"], 30), "score_seconds")
    require(_positive(limits["seconds_total"], 600), "total_seconds")
    count = sum(math.comb(len(positions), k) * 3**k for k in range(changes + 1))
    require(count <= limits["max_candidates"], "search_space_limit")
    resolved = tuple(
        {
            "id": row["id"],
            "oriented_interval": [row["start"], row["end"]],
            "input_interval": asdict(
                input_interval(row["start"], row["end"], len(sequence), native.strand)
            ),
            "target_tir": float(target),
            "target_log_tir": math.log(target),
        }
        for row, target in zip(cds, targets, strict=True)
    )
    return Request(
        deepcopy(value),
        native,
        profile,
        tuple(deepcopy(cds)),
        resolved,
        tuple(sorted(positions)),
        changes,
        count,
        float(limits["seconds_per_score"]),
        float(limits["seconds_total"]),
    )


def model_identity(profile: Profile) -> dict:
    """Reconstruct the existing native identity without executing a prediction."""
    parameters: dict = deepcopy(rbs.MODEL_PARAMETERS)
    if not profile.historical:
        del parameters["historical_footprint_nt"]
        parameters.update(
            upstream_nt=profile.upstream_nt,
            downstream_nt=profile.downstream_nt,
            coding_footprint_nt=profile.footprint_nt,
            footprint_coordinate="[start, start+13), first coding nucleotide is start",
            footprint_source="https://doi.org/10.1093/nar/gkx061; Methods equation 3",
            context_source=(
                "published 2014/2017 context-inspired bounded reconstruction; "
                "not a recovered production parameter set"
            ),
            standby_model="historical four-base opening; later geometry unimplemented",
        )
        if profile.standby:
            del parameters["standby_nt"]
            parameters["standby_model"] = deepcopy(rbs.STANDBY_PARAMETERS)
            if profile.joint:
                parameters["standby_model"]["binding_candidate_rule"] = (
                    "minimum complete initiation energy across "
                    "eligible returned candidates"
                )
                parameters["joint_search"] = deepcopy(rbs.JOINT_PARAMETERS)
    return {
        "id": profile.model_id,
        "source_commit": rbs.SOURCE_COMMIT,
        "parameters": parameters,
        "implementation_version": __version__,
    }


def candidates(request: Request) -> list[str]:
    """Enumerate the complete allowed neighborhood in the fixed public order."""
    seed = request.raw["rbs"]["sequence"]
    result = [seed]
    for count in range(1, request.changes + 1):
        for positions in combinations(request.positions, count):
            for letters in product(
                *[tuple(b for b in "ACGT" if b != seed[p]) for p in positions]
            ):
                changed = list(seed)
                for position, base in zip(positions, letters, strict=True):
                    changed[position] = base
                result.append("".join(changed))
    return result


def checked_edits(sequence: str, request: Request) -> list[dict]:
    """Recheck immutable bases and coding spans independently of enumeration."""
    seed = request.raw["rbs"]["sequence"]
    require(
        type(sequence) is str
        and len(sequence) == len(seed)
        and set(sequence) <= set("ACGT"),
        "candidate_sequence_constraint",
    )
    edits = []
    for i, (before, after) in enumerate(zip(seed, sequence, strict=True)):
        if before != after:
            oriented = i if request.native.strand == "+" else len(seed) - 1 - i
            require(i in request.positions, "immutable_position_changed")
            require(
                all(not row["start"] <= oriented < row["end"] for row in request.cds),
                "coding_region_changed",
            )
            edits.append(
                {
                    "input_position": i,
                    "oriented_position": oriented,
                    "from": before,
                    "to": after,
                }
            )
    require(len(edits) <= request.changes, "edit_count_constraint")
    return edits


def _targets(request: Request, reason: str) -> list[dict]:
    return [
        {
            "id": row["id"],
            "oriented_start": row["start"],
            "status": "not_evaluated",
            "reason": reason,
            "tir": None,
            "log_tir": None,
            "absolute_log_error": None,
        }
        for row in request.cds
    ]


def _finish(result: dict) -> dict:
    result["result_sha256"] = wire.digest(result)
    return result


def invalid_result(reason: str) -> dict:
    """A bounded refusal contains no invented candidates or backend/model identity."""
    return _finish(
        {
            "schema_version": "rbs-vector-design-result-1",
            "status": "invalid_input",
            "reason": reason,
            "algorithm": {"id": ALGORITHM, "implementation_version": __version__},
            "request": None,
            "request_sha256": None,
            "design_id": None,
            "backend": None,
            "model": None,
            "targets": [],
            "constraints": None,
            "limits": None,
            "coverage": None,
            "candidates": [],
            "proposal": None,
            "selected": None,
            "confirmation": None,
            "warnings": list(WARNINGS),
        }
    )


def _admit_native(
    native: dict, value: dict, request: Request, identity: dict, model: dict
) -> list[dict]:
    """Check native invocation/roster/geometry/scalars without recomputing energies."""
    expected_input = asdict(RbsRequest.from_dict(value))
    require(
        wire.canonical([native["model"], native["backend"], native["input"]])
        == wire.canonical([model, identity, expected_input])
        and native["id"] == request.native.id
        and native["schema_version"] == request.profile.schema_version
        and native["prediction_id"]
        == wire.digest(
            {
                "input": expected_input,
                "model": model,
                "backend": identity,
                "budget_seconds": request.seconds,
            }
        ),
        "native_identity_mismatch",
    )
    require(
        set(native)
        == {
            "schema_version",
            "id",
            "status",
            "reason",
            "sites",
            "warnings",
            "model",
            "backend",
            "input",
            "prediction_id",
        }
        and type(native["warnings"]) is list
        and all(type(w) is str for w in native["warnings"]),
        "invalid_native_result",
    )
    status, sites = native["status"], native["sites"]
    require(status in STATUSES and type(sites) is list, "invalid_native_result")
    if not sites:
        require(
            status == "failed"
            and type(native["reason"]) is str
            and bool(native["reason"]),
            "invalid_native_result",
        )
        return _targets(request, native["reason"])
    require(
        len(sites) == len(request.cds) and native["reason"] is None,
        "native_roster_mismatch",
    )
    targets = []
    for site, coding, target in zip(sites, request.cds, request.targets, strict=True):
        start, length = coding["start"], len(request.native.sequence)
        begin, end = (
            max(0, start - request.profile.upstream_nt),
            min(length, start + request.profile.downstream_nt),
        )
        require(
            type(site["oriented_start"]) is int
            and site["oriented_start"] == start
            and wire.canonical(site["start_codon"])
            == wire.canonical(
                asdict(input_interval(start, start + 3, length, request.native.strand))
            )
            and site["codon"] == request.native.oriented_sequence[start : start + 3]
            and wire.canonical(site["window"])
            == wire.canonical(
                {
                    "oriented_start": begin,
                    "oriented_end": end,
                    "input_interval": asdict(
                        input_interval(begin, end, length, request.native.strand)
                    ),
                }
            ),
            "native_coordinate_mismatch",
        )
        state = site["status"]
        require(state in STATUSES, "invalid_native_result")
        tir, log_tir = site["tir"], site["log_tir"]
        if state == "ok":
            energies = site["energies"]
            require(
                site["reason"] is None
                and _positive(tir)
                and type(log_tir) in (int, float)
                and -sys.float_info.max <= log_tir <= sys.float_info.max
                and type(energies) is dict
                and type(energies.get("dG_total")) in (int, float)
                and -sys.float_info.max <= energies["dG_total"] <= sys.float_info.max,
                "invalid_native_score",
            )
            total = energies["dG_total"]
            try:
                expected_tir = rbs.initiation_rate(total)
            except BackendError as exc:
                raise wire.DesignError("invalid_native_score") from exc
            # Native linear scores can round in the subnormal exponential range.
            # Check both reported scalars against their original equations.
            require(
                math.isclose(tir, expected_tir, rel_tol=1e-12, abs_tol=0.0)
                and math.isclose(
                    log_tir,
                    math.log(2500) - total / 2.222,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                "invalid_native_score",
            )
            error = abs(log_tir - target["target_log_tir"])
        else:
            require(
                type(site["reason"]) is str
                and bool(site["reason"])
                and tir is None
                and log_tir is None
                and site["energies"] is None,
                "invalid_native_score",
            )
            error = None
        targets.append(
            {
                "id": coding["id"],
                "oriented_start": start,
                "status": state,
                "reason": site["reason"],
                "tir": tir,
                "log_tir": log_tir,
                "absolute_log_error": error,
            }
        )
    states = {row["status"] for row in targets}
    require(
        status == next(s for s in STATUSES if s in states), "native_status_mismatch"
    )
    return targets


def _evaluate(
    value: dict,
    request: Request,
    backend: RnaStructure,
    identity: dict,
    model: dict,
    remaining: float,
) -> tuple[dict, bool, bool]:
    """Retain full-roster failures and stop native identity contradictions."""
    result: dict = {
        "status": "failed",
        "reason": None,
        "native": None,
        "native_json_sha256": None,
        "native_bytes": None,
        "native_admitted": False,
        "targets": _targets(request, "native_result_not_admitted"),
        "objective": None,
    }
    called = False
    try:
        require(
            wire.canonical(backend.identity) == wire.canonical(identity),
            "native_identity_mismatch",
        )
        called = True
        native = rbs.predict(
            deepcopy(value),
            backend,
            seconds=request.seconds,
            profile=request.profile.name,
            execution_seconds=min(request.seconds, remaining),
        )
        raw = wire.pretty(native)
        result["native_json_sha256"] = hashlib.sha256(raw).hexdigest()
        result["native_bytes"] = len(raw)
        require(
            len(raw) + 6 * len(raw.splitlines()) <= NATIVE_LIMIT, "native_result_limit"
        )
        require(type(native) is dict, "invalid_native_result")
        result["native"] = native
        require(
            wire.canonical(backend.identity) == wire.canonical(identity),
            "native_identity_mismatch",
        )
        targets = _admit_native(native, value, request, identity, model)
        result.update(
            status=native["status"],
            reason=native["reason"],
            targets=targets,
            native_admitted=True,
        )
        if result["status"] == "ok":
            result["objective"] = math.fsum(
                row["absolute_log_error"] for row in targets
            ) / len(targets)
        elif result["reason"] is None:
            result["reason"] = next(
                row["reason"] for row in targets if row["status"] != "ok"
            )
        return result, False, called
    except wire.DesignError as exc:
        result["reason"] = str(exc)
        return result, True, called
    except (BackendError, OSError, UnicodeError):
        result["reason"] = "prediction_execution_failed"
        return result, False, called
    except (KeyError, TypeError, ValueError, RecursionError):
        result["reason"] = "invalid_native_result"
        return result, True, called


def _proposal(row: dict) -> dict:
    return {
        key: deepcopy(row[key])
        for key in (
            "index",
            "candidate_id",
            "sequence",
            "sequence_sha256",
            "edits",
            "targets",
            "objective",
        )
    }


def design(value: object, backend: RnaStructure) -> dict:
    """Search all admitted noncoding candidates and freshly confirm one proposal."""
    started = time.monotonic()
    try:
        request = parse_request(value)
        identity = deepcopy(backend.identity)
        require(
            type(identity) is dict
            and bool(identity)
            and len(wire.canonical(identity)) <= wire.INPUT_LIMIT,
            "invalid_backend_identity",
        )
    except wire.DesignError as exc:
        return invalid_result(str(exc))
    except (AttributeError, TypeError, ValueError, RecursionError):
        return invalid_result("invalid_backend_identity")
    model = model_identity(request.profile)
    algorithm = {"id": ALGORITHM, "implementation_version": __version__}
    limits = {
        "max_candidates": request.raw["limits"]["max_candidates"],
        "seconds_per_score": request.seconds,
        "seconds_total": request.total_seconds,
        "input_bytes": wire.INPUT_LIMIT,
        "native_bytes": NATIVE_LIMIT,
        "output_bytes": wire.OUTPUT_LIMIT,
    }
    request_sha = wire.digest(request.raw)
    design_id = wire.digest(
        {
            "request_sha256": request_sha,
            "algorithm": algorithm,
            "backend": identity,
            "model": model,
            "targets": request.targets,
            "limits": limits,
        }
    )
    rows: list[dict] = []
    for i, sequence in enumerate(candidates(request)):
        native_request = dict(deepcopy(request.raw["rbs"]), sequence=sequence)
        sequence_sha = sequence_hash(sequence)
        rows.append(
            {
                "index": i,
                "candidate_id": wire.digest(
                    {
                        "design_id": design_id,
                        "index": i,
                        "sequence_sha256": sequence_sha,
                    }
                ),
                "sequence": sequence,
                "sequence_sha256": sequence_sha,
                "edits": checked_edits(sequence, request),
                "attempted": False,
                "status": "not_run",
                "reason": "not_attempted",
                "native_request": native_request,
                "native_request_sha256": wire.digest(native_request),
                "native": None,
                "native_json_sha256": None,
                "native_bytes": None,
                "native_admitted": False,
                "targets": _targets(request, "not_attempted"),
                "objective": None,
            }
        )
    deadline, calls, stop, expired = started + request.total_seconds, 0, None, False
    for row in rows:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            expired = True
            stop = stop or "deadline_exceeded"
        if stop is not None:
            row["reason"] = stop
            row["targets"] = _targets(request, stop)
            continue
        row["attempted"] = True
        outcome, fatal, called = _evaluate(
            row["native_request"], request, backend, identity, model, remaining
        )
        calls += called
        row.update(outcome)
        if fatal:
            stop = row["reason"]
        if time.monotonic() > deadline:
            expired = True
            stop = stop or "deadline_exceeded"
    good = [row for row in rows if row["status"] == "ok"]
    best = (
        min(
            good, key=lambda row: (row["objective"], len(row["edits"]), row["sequence"])
        )
        if good
        else None
    )
    proposal = _proposal(best) if best else None
    selected: dict | None = None
    confirmation: dict | None = None
    if best is not None:
        confirmation = {
            "candidate_index": best["index"],
            "attempted": False,
            "status": "not_run",
            "reason": stop,
            "native": None,
            "native_json_sha256": None,
            "native_bytes": None,
            "native_admitted": False,
            "targets": _targets(request, stop or "not_attempted"),
            "objective": None,
        }
        try:
            checked_edits(best["sequence"], request)
        except wire.DesignError as exc:
            stop = stop or str(exc)
            confirmation.update(status="failed", reason=str(exc))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            expired = True
            stop = stop or "deadline_exceeded"
        if stop is not None:
            confirmation["reason"] = confirmation["reason"] or stop
            confirmation["targets"] = _targets(request, confirmation["reason"])
        else:
            outcome, _, called = _evaluate(
                best["native_request"], request, backend, identity, model, remaining
            )
            calls += called
            confirmation.update(outcome, attempted=True)
            if time.monotonic() > deadline:
                expired = True
                stop = "deadline_exceeded"
                confirmation.update(status="failed", reason=stop)
            elif (
                outcome["status"] == "ok"
                and outcome["native_json_sha256"] == best["native_json_sha256"]
            ):
                confirmation.update(status="verified", reason=None)
                selected = deepcopy(proposal)
            else:
                confirmation.update(
                    status="failed", reason=outcome["reason"] or "confirmation_mismatch"
                )
    attempted = sum(row["attempted"] for row in rows)
    complete = len(good) == len(rows) and selected is not None and not expired
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
            "schema_version": "rbs-vector-design-result-1",
            "status": status,
            "reason": reason,
            "algorithm": algorithm,
            "request": request.raw,
            "request_sha256": request_sha,
            "design_id": design_id,
            "backend": identity,
            "model": model,
            "targets": list(request.targets),
            "constraints": {
                "editable_positions": list(request.positions),
                "max_changes": request.changes,
                "coding_intervals": [[row["start"], row["end"]] for row in request.cds],
            },
            "limits": limits,
            "coverage": {
                "planned": len(rows),
                "attempted": attempted,
                "successful": len(good),
                "failed": attempted - len(good),
                "not_run": len(rows) - attempted,
                "prediction_calls": calls,
                "all_candidates_scored": len(good) == len(rows),
                "deadline_exceeded": expired,
                "stop_reason": stop,
            },
            "candidates": rows,
            "proposal": proposal,
            "selected": selected,
            "confirmation": confirmation,
            "warnings": list(WARNINGS),
        }
    )

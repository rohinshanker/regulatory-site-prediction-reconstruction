"""Orchestrate admitted predictors for explicit supplied transcript organization."""

import hashlib
import json
import math
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import Any

from regsite import __version__, promoter, promoter_io, rbs
from regsite.backend import FoldingSession, RnaStructure
from regsite.contracts import MAX_EXPLICIT_STARTS, MAX_SEQUENCE_LENGTH, RbsRequest
from regsite.profiles import get_profile
from regsite.sequence import InputError
from regsite.transcript_geometry import (
    GeometryError,
    feature,
    promoter_features,
    rbs_features,
)

LIMITS = {
    "max_input_json_bytes": 1_000_000,
    "max_json_depth": 16,
    "max_json_nodes": 20_000,
    "max_bases": 5_000,
    "max_cds": 10,
    "max_promoter_sites": 512,
    "max_seconds_per_component": 120.0,
    "max_seconds_total": 240.0,
    "max_result_json_bytes": 33_554_432,
}
RBS_ENERGIES = (
    "dG_mRNA dG_mRNA_native_prediction dG_cofold_native_prediction "
    "dG_cofold_search dG_search_with_spacing dG_complex dG_spacing dG_start "
    "dG_standby_signed dG_accessible_complex dG_total dG_standby dG_distortion "
    "dG_unfolding dG_unfolding_raw dG_sliding dG_post_footprint"
).split()
PROMOTER_TERMS = (
    "hex10 hex35 discriminator extended10 itr up spacer intercept total binding"
).split()
UNSUPPORTED_CAPABILITIES = [
    "coupling",
    "elongation",
    "decay_stability",
    "termination",
    "native_operon_discovery",
    "joint_protein_abundance",
]


class TranscriptError(ValueError):
    """Atomic invalid-input, setup, native-integrity or export failure."""


@dataclass(frozen=True)
class _DeadlineBackend(RnaStructure):
    """Keep the verified native session inside the enclosing absolute deadline."""

    delegate: RnaStructure
    deadline: float

    def session(self, temperature_c: float, seconds: float = 60) -> FoldingSession:
        session = self.delegate.session(temperature_c, seconds)
        return replace(session, deadline=min(session.deadline, self.deadline))


def _predict_promoter(
    request: dict, params: promoter.PromoterParameters, seconds: float, deadline: float
) -> dict:
    # Preserve declared native budgets in the identity while independently
    # enforcing the absolute execution deadline, including preparation time.
    initial = True

    def clock() -> float:
        nonlocal initial
        if initial:
            initial = False
            return deadline - seconds
        return time.monotonic()

    return promoter_io.predict_batch(
        request,
        params,
        seconds_per_record=seconds,
        seconds_per_batch=seconds,
        clock=clock,
    )


def canonical_bytes(value: object) -> bytes:
    """Authoritative sorted, compact, finite ASCII-escaped JSON, without LF."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def result_bytes(value: object) -> bytes:
    """Authoritative output representation including the final LF."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("ascii")


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _json_copy(document: object) -> Any:
    pending = [(document, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > LIMITS["max_json_depth"] or count > LIMITS["max_json_nodes"]:
            raise TranscriptError("input: JSON depth/node limit exceeded")
        if type(node) is dict:
            if any(type(key) is not str for key in node):
                raise TranscriptError("input: JSON keys must be strings")
            pending.extend((key, depth + 1) for key in node)
            pending.extend((item, depth + 1) for item in node.values())
        elif type(node) is list:
            pending.extend((item, depth + 1) for item in node)
        elif type(node) is str:
            try:
                node.encode("utf-8")
            except UnicodeError as exc:
                raise TranscriptError("input: invalid UTF-8 string") from exc
        elif type(node) not in (int, float, bool, type(None)):
            raise TranscriptError("input: expected JSON values")
    try:
        encoded = canonical_bytes(document)
    except (ValueError, OverflowError) as exc:
        raise TranscriptError("input: expected finite JSON") from exc
    if len(encoded) > LIMITS["max_input_json_bytes"]:
        raise TranscriptError("input: max_input_json_bytes exceeded")
    return json.loads(encoded)


def _object(value: Any, keys: str, field: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise TranscriptError(f"{field}: expected exactly {keys}")
    return value


def _text(value: Any, maximum: int, field: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)
    ):
        raise TranscriptError(f"{field}: invalid string")


def _annotation(value: object, length: int, minimum: int, field: str) -> dict:
    item = _object(value, "id range provenance", field)
    _text(item["id"], 128, field + ".id")
    bounds = item["range"]
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(type(x) is not int for x in bounds)
        or not 0 <= bounds[0] <= bounds[1] - minimum <= length - minimum
    ):
        raise TranscriptError(f"{field}.range: invalid interval")
    provenance = _object(item["provenance"], "kind reference", field + ".provenance")
    if provenance["kind"] not in (
        "user_supplied",
        "annotation",
        "measured",
        "synthetic",
    ):
        raise TranscriptError(f"{field}.provenance.kind: unsupported")
    _text(provenance["reference"], 1024, field + ".provenance.reference")
    return item


def _scan(raw: object, length: int) -> list[tuple[str, int]]:
    if not isinstance(raw, dict):
        raise TranscriptError("promoter.scan: expected object")
    if raw.get("mode") == "scan":
        _object(raw, "mode range strands", "promoter.scan")
        bounds, strands = raw["range"], raw["strands"]
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or any(type(x) is not int for x in bounds)
            or not 0 <= bounds[0] <= bounds[1] <= length
        ):
            raise TranscriptError("promoter.scan.range: invalid interval")
        if (
            not isinstance(strands, list)
            or not strands
            or any(s not in ("+", "-") for s in strands)
            or len(set(strands)) != len(strands)
        ):
            raise TranscriptError("promoter.scan.strands: invalid strands")
        roster = [(s, i) for s in strands for i in range(*bounds)]
    else:
        _object(raw, "mode positions", "promoter.scan")
        if raw["mode"] != "positions" or not isinstance(raw["positions"], list):
            raise TranscriptError("promoter.scan: invalid positions mode")
        roster = []
        for position in raw["positions"]:
            _object(position, "strand tss", "promoter.scan.positions")
            strand, base = position["strand"], position["tss"]
            if (
                strand not in ("+", "-")
                or type(base) is not int
                or not 0 <= base < length
            ):
                raise TranscriptError("promoter.scan.positions: invalid point")
            roster.append((strand, base))
        if len(set(roster)) != len(roster):
            raise TranscriptError("promoter.scan: duplicate position")
    if len(roster) > LIMITS["max_promoter_sites"]:
        raise TranscriptError("promoter.scan: max_promoter_sites exceeded")
    return roster


def _preflight(
    document: object, backend: RnaStructure | None
) -> tuple[dict, dict, dict, list]:
    value = _object(
        _json_copy(document),
        "schema_version id sequence transcript cds rbs promoter projection settings",
        "request",
    )
    if value["schema_version"] != "supplied-transcript-request-1":
        raise TranscriptError("schema_version: expected supplied-transcript-request-1")
    _text(value["id"], 128, "id")
    sequence = value["sequence"]
    if (
        not isinstance(sequence, str)
        or not 1 <= len(sequence) <= LIMITS["max_bases"]
        or set(sequence) - set("ACGT")
    ):
        raise TranscriptError("sequence: expected 1–5000 uppercase ACGT bases")
    transcript = _annotation(value["transcript"], len(sequence), 1, "transcript")
    cds = value["cds"]
    if not isinstance(cds, list) or not 1 <= len(cds) <= LIMITS["max_cds"]:
        raise TranscriptError("cds: expected 1–10 annotations")
    for item in cds:
        _annotation(item, len(sequence), 3, "cds")
    starts = [item["range"][0] for item in cds]
    if starts != sorted(set(starts)) or len({item["id"] for item in cds}) != len(cds):
        raise TranscriptError("cds: IDs unique and starts strictly increasing required")
    settings = _object(
        value["settings"],
        "seconds_per_rbs_record seconds_per_promoter_record seconds_total",
        "settings",
    )
    for name, seconds in settings.items():
        cap = LIMITS[
            "max_seconds_total"
            if name == "seconds_total"
            else "max_seconds_per_component"
        ]
        if type(seconds) not in (int, float) or not 0 < seconds <= cap:
            raise TranscriptError(
                f"settings.{name}: expected finite number in (0,{cap}]"
            )
        settings[name] = float(seconds)
    rb = _object(value["rbs"], "profile anti_sd temperature_c host", "rbs")
    anti_sd = rb["anti_sd"]
    if not isinstance(anti_sd, str) or len(anti_sd) != 9 or set(anti_sd) - set("ACGU"):
        raise TranscriptError("rbs.anti_sd: expected nine uppercase ACGU bases")
    u, v = transcript["range"]
    eligible = [s - u for s in starts if u <= s and s + 3 <= v]
    rb_request = {
        "id": "transcript-rbs",
        "sequence": sequence[u:v],
        "strand": "+",
        "anti_sd": anti_sd,
        "temperature_c": rb["temperature_c"],
        "host": rb["host"],
        "start_positions": eligible,
    }
    try:
        get_profile(rb["profile"])
        RbsRequest.from_dict(rb_request)
    except InputError as exc:
        raise TranscriptError(f"rbs: {exc}") from exc
    pm = _object(value["promoter"], "calibration host scan", "promoter")
    try:
        promoter.resolve_calibration(pm["calibration"], pm["host"])
        projection = value["projection"]
        if projection is not None:
            _object(
                projection,
                "contig origin contig_length sequence_strand topology origin_crossing",
                "projection",
            )
            for field in ("origin", "contig_length"):
                if type(projection[field]) is not int:
                    raise TranscriptError(
                        f"projection.{field}: expected genuine integer"
                    )
            promoter.check_projection(projection, len(sequence))
    except promoter.InputError as exc:
        raise TranscriptError(str(exc)) from exc
    roster = _scan(pm["scan"], len(sequence))
    pm_request = {
        "id": "transcript-promoter",
        "sequence": sequence,
        "calibration": pm["calibration"],
        "scan": pm["scan"],
        "output": {"states": "selected", "legacy_keys": False, "elements": True},
    }
    if pm["host"] is not None:
        pm_request["host"] = pm["host"]
    if projection is not None:
        pm_request["projection"] = projection
    if eligible and (not isinstance(backend, RnaStructure) or not backend.identity):
        raise TranscriptError(
            "backend: eligible CDSs require a verified RnaStructure instance"
        )
    return value, rb_request, pm_request, roster


def _scalar(value: Any, unit: str, reason: str | None) -> dict:
    if value is not None and (
        type(value) not in (int, float) or not math.isfinite(value)
    ):
        raise TranscriptError("native scalar must be finite numeric or null")
    return {
        "value": value,
        "unit": unit,
        "reason": (reason or "value_unavailable") if value is None else None,
    }


def _scalars(site: dict | None, calculator: str, reason: str | None) -> dict:
    site = site or {}
    if calculator == "rbs":
        values = {
            "tir": (site.get("tir"), "relative_initiation_score"),
            "log_tir": (site.get("log_tir"), "ln_relative_initiation_score"),
        }
        values.update(
            {
                name: (score, "kcal/mol")
                for name, score in (
                    (name, (site.get("energies") or {}).get(name))
                    for name in RBS_ENERGIES
                )
            }
        )
    else:
        selected = site.get("selected") or {}
        values = {
            name: (selected.get(name), unit)
            for name, unit in (
                ("relative_transcription_score", "relative_transcription_score"),
                ("log_relative_transcription_score", "ln_relative_transcription_score"),
            )
        }
        values.update(
            {
                name: (score, promoter.TERMS_UNIT)
                for name, score in (
                    (name, selected.get("terms", {}).get(name))
                    for name in PROMOTER_TERMS
                )
            }
        )
        reason = selected.get("score_status") or reason
    return {
        name: _scalar(score, unit, reason) for name, (score, unit) in values.items()
    }


def _component(request: dict, roster: list) -> dict:
    return {
        "request": request,
        "roster": roster,
        "status": "not_evaluated",
        "reason": "deadline_exceeded",
        "declared_seconds": None,
        "prediction": None,
    }


def _record(component: dict, calculator: str) -> dict | None:
    prediction = component["prediction"]
    if prediction is None:
        return None
    required = {"status", "sites", "model", "backend", "input", "prediction_id"}
    if calculator == "promoter":
        if (
            not {"model", "batch", "results"} <= prediction.keys()
            or len(prediction["results"]) != 1
        ):
            raise TranscriptError("native Promoter envelope missing required fields")
        prediction = prediction["results"][0]
        required = {
            "status",
            "sites",
            "input",
            "prediction_id",
            "scan",
            "calibration",
            "projection",
        }
    if not required <= prediction.keys() or not isinstance(prediction["sites"], list):
        raise TranscriptError(f"native {calculator} record missing required fields")
    if prediction["status"] not in ("ok", "no_candidate", "failed", "unsupported"):
        raise TranscriptError(f"native {calculator} invalid preflight/status invariant")
    request = component["request"]
    if calculator == "rbs":
        if prediction["input"] != asdict(RbsRequest.from_dict(request)):
            raise TranscriptError("native RBS input binding mismatch")
    else:
        calibration = promoter.resolve_calibration(
            request["calibration"], request.get("host")
        )
        if (
            prediction["input"]["length"] != len(request["sequence"])
            or prediction["input"]["normalized_dna_sha256"]
            != hashlib.sha256(request["sequence"].encode("ascii")).hexdigest()
            or prediction["scan"] != request["scan"]
            or prediction["projection"] != request.get("projection")
            or prediction["calibration"] != calibration.to_dict()
        ):
            raise TranscriptError("native Promoter request binding mismatch")
    component["status"] = prediction["status"]
    component["reason"] = (
        prediction.get("reason")
        if calculator == "rbs"
        else (prediction.get("reasons") or [None])[0]
    )
    return prediction


def _sites(component: dict, calculator: str) -> dict:
    record = _record(component, calculator)
    found = {}
    if record is not None:
        for i, site in enumerate(record["sites"]):
            required = (
                {
                    "status",
                    "reason",
                    "oriented_start",
                    "start_codon",
                    "window",
                    "tir",
                    "log_tir",
                    "energies",
                }
                if calculator == "rbs"
                else {"status", "reason", "strand", "tss", "selected", "attempted"}
            )
            if not required <= site.keys() or site["status"] not in (
                "ok",
                "failed",
                "unsupported",
                "no_candidate",
            ):
                raise TranscriptError(f"native {calculator} site missing fields/status")
            key: Any = (
                site["oriented_start"]
                if calculator == "rbs"
                else (site["strand"], site["tss"]["forward_base"])
            )
            if key not in component["roster"] or key in found:
                raise TranscriptError(f"native {calculator} unexpected/duplicate site")
            if calculator == "rbs":
                if site["start_codon"] != {"start": key, "end": key + 3, "strand": "+"}:
                    raise TranscriptError(
                        "native RBS start_codon correspondence mismatch"
                    )
                if site["status"] == "ok" and (
                    site["tir"] is None
                    or site["log_tir"] is None
                    or not site["energies"]
                ):
                    raise TranscriptError("native RBS successful site missing scores")
            elif site["status"] == "ok" and site["selected"] is None:
                raise TranscriptError(
                    "native Promoter successful site missing selected state"
                )
            found[key] = (i, site)
        if record["status"] in ("ok", "no_candidate") and len(found) != len(
            component["roster"]
        ):
            raise TranscriptError(
                f"native {calculator} successful record missing sites"
            )
    return found


def _coverage(component: dict, candidates: list[dict]) -> dict:
    return {
        "requested": len(component["roster"]),
        "returned": sum(c["site_index"] is not None for c in candidates),
        "scored": sum(c["status"] == "ok" for c in candidates),
        "not_evaluated": sum(c["status"] == "not_evaluated" for c in candidates),
        "missing": sum(c["site_index"] is None for c in candidates),
    }


def _candidate(component: dict, found: dict, key: Any, calculator: str) -> dict:
    index, site = found.get(key, (None, None))
    status = site["status"] if site is not None else "not_evaluated"
    reason = (
        site["reason"]
        if site is not None
        else (
            component["reason"]
            if component["prediction"] is None
            else "missing_native_site"
        )
    )
    if site is not None and calculator == "promoter" and not site["attempted"]:
        status = "not_evaluated"
    return {
        "site_index": index,
        "status": status,
        "reason": reason,
        "scalars": _scalars(site, calculator, reason),
    }


def _assemble(value: dict, components: dict) -> dict:
    projection = value["projection"]
    u, v = value["transcript"]["range"]
    rb, pm = components["rbs"], components["promoter"]
    rb_sites, pm_sites = _sites(rb, "rbs"), _sites(pm, "promoter")
    cds = []
    for annotation in value["cds"]:
        s, end = annotation["range"]
        offset = s - u
        eligible = u <= s and s + 3 <= v
        item = {
            "annotation": annotation,
            "transcript_offset": offset,
            "eligible": eligible,
            "warnings": ["downstream_clipped"] if eligible and end > v else [],
            "annotation_coordinates": feature(
                [s, end],
                length=len(value["sequence"]),
                offset=0,
                strand="+",
                projection=projection,
            ),
        }
        if eligible:
            item.update(_candidate(rb, rb_sites, offset, "rbs"))
            site = rb_sites.get(offset, (None, None))[1]
            item["features"] = (
                {} if site is None else rbs_features(site, v - u, u, projection)
            )
        else:
            item.update(
                site_index=None,
                status="incompatible_transcript",
                reason=(
                    "start_before_transcript"
                    if s < u
                    else "start_after_transcript"
                    if s >= v
                    else "start_codon_after_transcript"
                ),
                features={},
                scalars=_scalars(None, "rbs", "incompatible_transcript"),
            )
        cds.append(item)
    candidates = []
    for key in pm["roster"]:
        item = {
            "strand": key[0],
            "construct_tss": key[1],
            **_candidate(pm, pm_sites, key, "promoter"),
        }
        site = pm_sites.get(key, (None, None))[1]
        item["features"] = (
            {}
            if site is None
            else promoter_features(site, len(value["sequence"]), projection)
        )
        candidates.append(item)
    rb["coverage"] = _coverage(rb, [item for item in cds if item["eligible"]])
    rb["coverage"]["incompatible"] = sum(not item["eligible"] for item in cds)
    pm["coverage"] = _coverage(pm, candidates)
    complete = all(
        c["status"] in ("ok", "no_candidate", "not_applicable")
        for c in components.values()
    )
    complete = complete and rb["coverage"]["incompatible"] == 0
    scored = sum(c["coverage"]["scored"] for c in components.values())
    return {
        "schema_version": "supplied-transcript-result-1",
        "id": value["id"],
        "implementation_version": __version__,
        "status": "complete" if complete else ("partial" if scored else "unavailable"),
        "request_sha256": _hash(value),
        "request": value,
        "settings": {k: float(n) for k, n in value["settings"].items()},
        "limits": dict(LIMITS)
        | {
            "predictors": {
                "promoter": dict(promoter_io.LIMITS),
                "rbs": {
                    "max_normalized_bases_per_record": MAX_SEQUENCE_LENGTH,
                    "max_explicit_or_scanned_starts": MAX_EXPLICIT_STARTS,
                    "max_seconds_per_record": 120.0,
                },
            }
        },
        "transcript": {
            "annotation": value["transcript"],
            "sequence": value["sequence"][u:v],
            "sequence_sha256": hashlib.sha256(
                value["sequence"][u:v].encode("ascii")
            ).hexdigest(),
            "coordinates": feature(
                [u, v],
                length=len(value["sequence"]),
                offset=0,
                strand="+",
                projection=projection,
            ),
        },
        "components": components,
        "cds": cds,
        "promoter_candidates": candidates,
        "coverage": {
            "cds": len(cds),
            "eligible_cds": len(rb["roster"]),
            "incompatible_cds": rb["coverage"]["incompatible"],
            "scored": scored,
            "complete": complete,
        },
        "unsupported_capabilities": list(UNSUPPORTED_CAPABILITIES),
        "warnings": [
            "component_scores_do_not_estimate_joint_protein_abundance",
            "supplied_annotations_are_not_independently_verified",
        ],
    }


def predict_transcript(document: object, backend: RnaStructure | None = None) -> dict:
    """Validate atomically, run one shared RBS record then one full-construct scan.

    The caller supplies a previously verified backend when any start is eligible.
    Deadlines cooperate between native operations. Received byte limits and JSON
    duplicate detection belong to the caller's parser; parsed input is bounded here.
    """
    started = time.monotonic()
    value, rb_request, pm_request, roster = _preflight(document, backend)
    # Bind the original parsed request, before resolving numeric execution settings.
    original = _json_copy(document)
    settings = value["settings"]
    deadline = started + settings["seconds_total"]
    try:
        params = promoter.load_parameters()
        components = {
            "rbs": _component(rb_request, rb_request["start_positions"]),
            "promoter": _component(pm_request, roster),
        }
        for name in ("rbs", "promoter"):
            component = components[name]
            if name == "rbs" and not component["roster"]:
                component.update(status="not_applicable", reason="no_eligible_cds")
                continue
            call_started = time.monotonic()
            remaining = deadline - call_started
            if remaining <= 0:
                continue
            declared = settings[f"seconds_per_{name}_record"]
            budget = min(declared, remaining)
            component_deadline = min(deadline, call_started + declared)
            component["declared_seconds"] = declared
            if name == "rbs":
                assert backend is not None
                component["prediction"] = rbs.predict(
                    rb_request,
                    _DeadlineBackend(
                        backend.root,
                        backend.identity,
                        backend,
                        component_deadline,
                    ),
                    seconds=settings["seconds_per_rbs_record"],
                    profile=value["rbs"]["profile"],
                    execution_seconds=budget,
                )
            else:
                component["prediction"] = _predict_promoter(
                    pm_request, params, declared, component_deadline
                )
        result = _assemble(value, components)
        result["identities"] = {
            "rbs": {
                "profile": asdict(get_profile(value["rbs"]["profile"])),
                "source_commit": rbs.SOURCE_COMMIT,
                "base_parameters": deepcopy(rbs.MODEL_PARAMETERS),
                "standby_parameters": deepcopy(rbs.STANDBY_PARAMETERS),
                "joint_parameters": deepcopy(rbs.JOINT_PARAMETERS),
                "backend": None if backend is None else deepcopy(backend.identity),
            },
            "promoter": {
                "model": promoter_io.model_identity(params)[0],
                "calibration": asdict(
                    promoter.resolve_calibration(
                        value["promoter"]["calibration"], value["promoter"]["host"]
                    )
                ),
            },
        }
        native_rb = components["rbs"]["prediction"]
        if native_rb is not None:
            expected = result["identities"]["rbs"]
            if (
                native_rb["backend"] != expected["backend"]
                or native_rb["model"]["id"] != expected["profile"]["model_id"]
                or native_rb["model"]["source_commit"] != rbs.SOURCE_COMMIT
                or native_rb["model"]["implementation_version"] != __version__
            ):
                raise TranscriptError("native RBS model/backend binding mismatch")
        native_pm = components["promoter"]["prediction"]
        if (
            native_pm is not None
            and native_pm["model"] != result["identities"]["promoter"]["model"]
        ):
            raise TranscriptError("native Promoter model binding mismatch")
        result["request"] = original
        result["request_sha256"] = _hash(original)
        result["prediction_sha256"] = _hash(result)
        if len(result_bytes(result)) > LIMITS["max_result_json_bytes"]:
            raise TranscriptError("output: max_result_json_bytes exceeded")
        return result
    except (
        GeometryError,
        promoter.ParameterError,
        promoter_io.SetupError,
        AttributeError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        OSError,
    ) as exc:
        raise TranscriptError(f"transcript setup/integrity/export: {exc}") from exc

"""Compare supplied sequences through unchanged public regulatory predictors."""

import hashlib
import json
import math
from typing import Any

from regsite import promoter, promoter_io, rbs
from regsite.backend import RnaStructure
from regsite.contracts import MAX_EXPLICIT_STARTS, MAX_SEQUENCE_LENGTH
from regsite.edits import EditError, EditMap, build_edit_map
from regsite.profiles import get_profile
from regsite.sequence import InputError, normalize_rna, reverse_complement

SIDES = ("current", "recoded")
LIMITS = {
    "max_input_json_bytes": 2_000_000,
    "max_result_json_bytes": 67_108_864,
    "max_candidates_per_side": 512,
    "max_edits": 1_000,
    "max_bases_per_side": 10_000,
    "max_feature_bases": 2_000_000,
    "max_seconds_per_side": 120,
    "max_json_depth": 20,
    "max_json_nodes": 100_000,
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
RBS_FEATURES = (
    "start_codon window binding_interval standby_interval coding_footprint"
).split()
PROMOTER_FEATURES = ("UP gap hex35 spacer extended10 hex10 discriminator itr").split()


class PairError(ValueError):
    """Atomic geometry, identity binding or resource preflight failure."""


def canonical_bytes(value: object) -> bytes:
    """Compact, sorted, finite ASCII JSON used for every wrapper digest."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def result_bytes(value: object) -> bytes:
    """Authoritative output bytes, including the final LF and ASCII escapes."""
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "ascii"
    )


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _finite_json(value: object) -> None:
    pending = [(value, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > LIMITS["max_json_depth"] or count > LIMITS["max_json_nodes"]:
            raise PairError("input: JSON depth/node limit exceeded")
        if type(node) is dict:
            if any(type(key) is not str for key in node):
                raise PairError("input: JSON object keys must be strings")
            pending.extend((v, depth + 1) for v in node.values())
        elif type(node) is list:
            pending.extend((v, depth + 1) for v in node)
        elif type(node) not in (str, int, float, bool, type(None)):
            raise PairError("input: expected JSON values")
    try:
        encoded = canonical_bytes(value)
    except (ValueError, OverflowError) as exc:
        raise PairError("input: expected finite JSON") from exc
    if len(encoded) > LIMITS["max_input_json_bytes"]:
        raise PairError("input: max_input_json_bytes exceeded")


def _object(value: Any, required: set[str], optional: set[str], field: str) -> dict:
    if (
        not isinstance(value, dict)
        or required - value.keys()
        or value.keys() - required - optional
    ):
        raise PairError(
            f"{field}: expected fields {sorted(required)}, optional {sorted(optional)}"
        )
    return value


def _preflight(document: object, backend: RnaStructure | None) -> tuple[dict, EditMap]:
    _finite_json(document)
    value = _object(
        json.loads(canonical_bytes(document)),
        {
            "schema_version",
            "pair",
            "calculator",
            "current_request",
            "recoded_request",
            "settings",
        },
        {"projections"},
        "request",
    )
    if value["schema_version"] != "paired-regulatory-request-1":
        raise PairError("schema_version: expected paired-regulatory-request-1")
    calculator = value["calculator"]
    if calculator not in ("rbs", "promoter"):
        raise PairError("calculator: expected rbs or promoter")
    try:
        geometry = build_edit_map(value["pair"])
    except EditError as exc:
        raise PairError(str(exc)) from exc
    if len(value["pair"]["edits"]) > LIMITS["max_edits"]:
        raise PairError("pair.edits: max_edits exceeded")
    settings = _object(
        value["settings"],
        {"seconds_per_side", "profile"}
        if calculator == "rbs"
        else {"seconds_per_side"},
        set(),
        "settings",
    )
    seconds = settings["seconds_per_side"]
    if (
        type(seconds) not in (int, float)
        or not 0 < seconds <= LIMITS["max_seconds_per_side"]
    ):
        raise PairError("settings.seconds_per_side: expected finite number in (0,120]")
    if calculator == "rbs":
        if not isinstance(backend, RnaStructure):
            raise PairError("backend: RBS requires a verified RnaStructure instance")
        try:
            get_profile(settings["profile"])
        except InputError as exc:
            raise PairError(str(exc)) from exc
    elif "projections" in value:
        raise PairError(
            "projections: only supported for rbs; use Promoter side projections"
        )
    projections = value.get("projections", dict.fromkeys(SIDES))
    _object(projections, set(SIDES), set(), "projections")
    for side in SIDES:
        request = value[side + "_request"]
        required = {"id", "sequence"}
        if calculator == "rbs":
            required |= {"strand", "anti_sd", "temperature_c", "host"}
        if not isinstance(request, dict) or required - request.keys():
            raise PairError(
                f"{side}_request: missing required fields {sorted(required)}"
            )
        if calculator == "promoter" and (
            set(request) & {"records", "defaults"}
            or request.get("schema_version", "1.0") != "1.0"
        ):
            raise PairError(
                f"{side}_request: expected a single Promoter schema 1.0 record"
            )
        if request["id"] != value["pair"][side]["id"]:
            raise PairError(f"{side}_request.id: does not match pair identity")
        try:
            dna = normalize_rna(
                request["sequence"], "sequence", max_length=10_000
            ).replace("U", "T")
        except InputError as exc:
            raise PairError(f"{side}_request.sequence: {exc}") from exc
        if dna != value["pair"][side]["sequence"]:
            raise PairError(f"{side}_request.sequence: does not match pair sequence")
        if calculator == "rbs" and projections[side] is not None:
            try:
                _object(
                    projections[side],
                    {
                        "contig",
                        "origin",
                        "contig_length",
                        "sequence_strand",
                        "topology",
                        "origin_crossing",
                    },
                    set(),
                    f"projections.{side}",
                )
                promoter.check_projection(projections[side], len(dna))
            except (promoter.InputError, TypeError) as exc:
                raise PairError(f"projections.{side}: {exc}") from exc
    return value, geometry


def _roster(request: dict, calculator: str, dna: str) -> list[tuple[str, int]] | None:
    """Resolve geometry separately from scoring/calibration validity."""
    if calculator == "promoter":
        try:
            return promoter_io._scan(request.get("scan"), len(dna))[1]
        except promoter.InputError:
            return None
    strand, starts = request["strand"], request.get("start_positions")
    if strand not in ("+", "-"):
        return None
    oriented = dna.replace("T", "U")
    if strand == "-":
        oriented = reverse_complement(oriented)
    if starts is None:
        starts = [
            i for i in range(len(dna) - 2) if oriented[i : i + 3] in rbs.SCAN_CODONS
        ]
    elif (
        not isinstance(starts, list)
        or len(starts) > 1000
        or any(
            type(i) not in (int, float)
            or isinstance(i, bool)
            or int(i) != i
            or not 0 <= i <= len(dna) - 3
            for i in starts
        )
        or len(set(starts)) != len(starts)
    ):
        return None
    return [
        (strand, int(i) if strand == "+" else len(dna) - 1 - int(i))
        for i in sorted(starts)
    ]


def _scalar(value: float | None, unit: str, reason: str = "value_unavailable") -> dict:
    return {"value": value, "unit": unit, "reason": reason if value is None else None}


def _scalars(site: dict, calculator: str) -> dict:
    if calculator == "rbs":
        energies = site.get("energies") or {}
        values = {
            name: _scalar(energies.get(name), "kcal/mol") for name in RBS_ENERGIES
        }
        values["tir"] = _scalar(site.get("tir"), "relative_initiation_score")
        values["log_tir"] = _scalar(site.get("log_tir"), "ln_relative_initiation_score")
        return values
    selected = site.get("selected") or {}
    terms = selected.get("terms", {})
    values = {
        name: _scalar(terms.get(name), promoter.TERMS_UNIT) for name in PROMOTER_TERMS
    }
    for name, unit in (
        ("log_relative_transcription_score", "ln_relative_transcription_score"),
        ("relative_transcription_score", "relative_transcription_score"),
    ):
        values[name] = _scalar(
            selected.get(name), unit, selected.get("score_status", "value_unavailable")
        )
    return values


def _genomic(projection: dict | None, strand: str, bases: list[int]) -> dict | None:
    if projection is None:
        return None
    genomic = [promoter.project_base(projection, base) for base in bases]
    return {
        "projection": projection,
        "strand": "+" if strand == projection["sequence_strand"] else "-",
        "bases": genomic,
    }


def _features(
    site: dict,
    calculator: str,
    geometry: EditMap,
    side: str,
    strand: str,
    projection: dict | None,
) -> dict:
    intervals: dict = dict.fromkeys(
        RBS_FEATURES if calculator == "rbs" else PROMOTER_FEATURES
    )
    if calculator == "promoter":
        intervals.update((site.get("selected") or {}).get("intervals", {}))
    else:
        for name in RBS_FEATURES:
            raw = site.get(name)
            if name == "window":
                raw = (raw or {}).get("input_interval")
            if raw is not None:
                intervals[name] = [raw["start"], raw["end"]]
        standby = site.get("standby") or {}
        for name in ("original_hairpin", "hairpin", "distal", "proximal"):
            raw = standby.get(name)
            if raw is not None:
                intervals["standby." + name] = [raw["start"], raw["end"]]
        for i, item in enumerate(standby.get("downstream_hairpins", [])):
            raw = item["interval"]
            intervals[f"standby.downstream_hairpins.{i}"] = [raw["start"], raw["end"]]
    features = {}
    length = len(geometry.current if side == "current" else geometry.recoded)
    for name, interval in intervals.items():
        # Native reverse standby may report an empty [L,L) interval. It has
        # no bases even on a circular pair; keep its original interval while
        # mapping the empty set without treating L as a circular base index.
        path_interval = [0, 0] if interval == [length, length] else interval
        mapping = (
            None
            if path_interval is None
            else geometry.map_interval(side, path_interval[0], path_interval[1], strand)
        )
        features[name] = {
            "interval": interval,
            "strand": strand,
            "mapping": mapping,
            "genomic": None
            if mapping is None
            else _genomic(projection, strand, mapping["source_bases"]),
            "reason": "feature_unavailable" if interval is None else None,
        }
    return features


def _side(
    request: dict,
    prediction: dict,
    calculator: str,
    planned: list[tuple[str, int]] | None,
    geometry: EditMap,
    side: str,
    projection: dict | None,
) -> dict:
    record = prediction if calculator == "rbs" else prediction["results"][0]
    if calculator == "promoter":
        projection = record["projection"]
    elif projection is not None:
        projection = promoter.check_projection(
            projection, len(geometry.current if side == "current" else geometry.recoded)
        )
    if calculator == "rbs":
        effective = record["input"] or request
        scoring = {k: effective[k] for k in ("anti_sd", "temperature_c")}
        calibration = {"host": effective["host"], "host_calibration": "not_calibrated"}
        backend = prediction["backend"]
    else:
        scoring = {"selection": "minimum_source_total_first_visited_exact_tie"}
        calibration = record["calibration"]
        backend = {"kind": "stdlib_no_folding_backend"}
    identities = {
        "model_sha256": _hash(prediction["model"]),
        "settings_sha256": _hash(scoring),
        "backend_sha256": _hash(backend),
        "calibration_sha256": _hash(calibration),
    }
    sites: dict[tuple[str, int], tuple[int | None, dict]] = {}
    for native_index, site in enumerate(record["sites"]):
        if calculator == "rbs":
            oriented = site["oriented_start"]
            anchor = (
                oriented
                if request["strand"] == "+"
                else len(geometry.current if side == "current" else geometry.recoded)
                - 1
                - oriented
            )
            key = (request["strand"], anchor)
        else:
            key = (site["strand"], site["tss"]["forward_base"])
        if key in sites or planned is None or key not in planned:
            raise PairError("prediction: unexpected or duplicate candidate identity")
        sites[key] = (native_index, site)
    candidate_scope = _hash(
        {"request": request, "identities": identities, "projection": projection}
    )[:32]
    candidates = []
    for strand, anchor in planned or []:
        index, site = sites.get((strand, anchor), (None, {}))
        codon = (
            None
            if calculator == "promoter"
            else [anchor + i * (1 if strand == "+" else -1) for i in range(3)]
        )
        candidates.append(
            {
                "id": (
                    f"pcandidate1:{candidate_scope}:{side}:"
                    f"{calculator}:{strand}:{anchor}"
                ),
                "strand": strand,
                "anchor": anchor,
                "codon_bases": codon,
                "status": site.get("status", "unavailable"),
                "reason": site.get("reason")
                if site
                else "prediction_candidate_unavailable",
                "site_index": index,
                "scalars": _scalars(site, calculator),
                "features": _features(
                    site, calculator, geometry, side, strand, projection
                ),
                "genomic": _genomic(projection, strand, [anchor]),
            }
        )
    return {
        "request": request,
        "prediction": prediction,
        "prediction_sha256": _hash(prediction),
        "identities": identities,
        "projection": projection,
        "roster_status": "unknown" if planned is None else "known",
        "candidates": candidates,
    }


def _delta(current: dict | None, recoded: dict | None, reason: str | None) -> dict:
    template = current or recoded
    assert template is not None
    if reason is None and (
        current is None
        or recoded is None
        or current["value"] is None
        or recoded["value"] is None
    ):
        reason = "value_unavailable"
    value = None
    if reason is None:
        assert current is not None and recoded is not None
        value = recoded["value"] - current["value"]
        if not math.isfinite(value):
            value, reason = None, "nonfinite_delta"
    return _scalar(value, template["unit"], reason or "value_unavailable")


def _row(
    current: dict | None, recoded: dict | None, sides: dict, reason: str | None
) -> dict:
    mismatches = [
        key
        for key in sides["current"]["identities"]
        if sides["current"]["identities"][key] != sides["recoded"]["identities"][key]
    ]
    paired = current is not None and recoded is not None
    delta_reason = reason
    if current is not None and recoded is not None:
        if mismatches:
            delta_reason = "incompatible_identity"
        elif current["status"] != "ok" or recoded["status"] != "ok":
            delta_reason = "unsuccessful_candidate"
    a, b = (current or {}).get("scalars", {}), (recoded or {}).get("scalars", {})
    changes = {}
    if current is not None and recoded is not None:
        for name in current["features"].keys() | recoded["features"].keys():
            f, g = current["features"].get(name), recoded["features"].get(name)
            fm, gm = (f or {}).get("mapping"), (g or {}).get("mapping")
            changes[name] = {
                "mapped_bases_equal": None
                if fm is None or gm is None
                else fm["complete_base_mapping"]
                and fm["mapped_bases"] == gm["source_bases"],
                "reason": "feature_unavailable" if fm is None or gm is None else None,
            }
    return {
        "current_candidate_id": (current or {}).get("id"),
        "recoded_candidate_id": (recoded or {}).get("id"),
        "status": "paired"
        if paired
        else ("unavailable" if reason == "counterpart_roster_unknown" else "unmatched"),
        "reason": delta_reason,
        "identity_mismatches": mismatches,
        "deltas": {
            name: _delta(a.get(name), b.get(name), delta_reason)
            for name in sorted(a.keys() | b.keys())
        },
        "feature_changes": changes,
    }


def _comparisons(sides: dict, geometry: EditMap) -> list[dict]:
    target = {(c["strand"], c["anchor"]): c for c in sides["recoded"]["candidates"]}
    used = set()
    rows = []
    interrupted = set()
    for candidate in sides["current"]["candidates"]:
        mapped = geometry.map_base("current", candidate["anchor"])
        counterpart = target.get((candidate["strand"], mapped))
        reason = None
        if sides["recoded"]["roster_status"] == "unknown":
            reason = "counterpart_roster_unknown"
        elif mapped is None:
            reason = "unmapped_current_anchor"
        elif counterpart is None:
            reason = "mapped_anchor_absent_from_recoded_roster"
        elif (
            candidate["codon_bases"] is not None
            and [
                geometry.map_base("current", base) for base in candidate["codon_bases"]
            ]
            != counterpart["codon_bases"]
        ):
            reason = "interrupted_codon"
            interrupted.add(counterpart["id"])
        if reason is not None:
            counterpart = None
        else:
            assert counterpart is not None
            used.add(counterpart["id"])
        rows.append(_row(candidate, counterpart, sides, reason))
    for candidate in sides["recoded"]["candidates"]:
        if candidate["id"] in used:
            continue
        if sides["current"]["roster_status"] == "unknown":
            reason = "counterpart_roster_unknown"
        elif candidate["id"] in interrupted:
            reason = "interrupted_codon"
        elif geometry.map_base("recoded", candidate["anchor"]) is None:
            reason = "unmapped_recoded_anchor"
        else:
            reason = "mapped_anchor_absent_from_current_roster"
        rows.append(_row(None, candidate, sides, reason))
    return rows


def predict_pair(document: object, backend: RnaStructure | None = None) -> dict:
    """Preflight both requests, execute real predictors, then compare exact anchors.

    Complete native predictions remain authoritative. Partial-record successful
    comparisons are diagnostic and cannot yield top-level complete status.
    """
    value, geometry = _preflight(document, backend)
    calculator, settings = value["calculator"], value["settings"]
    planned = {}
    for side in SIDES:
        dna = geometry.current if side == "current" else geometry.recoded
        roster = _roster(value[side + "_request"], calculator, dna)
        if roster is not None and len(roster) > LIMITS["max_candidates_per_side"]:
            raise PairError(f"{side}: max_candidates_per_side exceeded")
        planned[side] = roster
    # Conservative source-feature bound: RBS windows/standby intervals fit inside
    # a 200-base context, Promoter selected windows contain at most 89 bases.
    feature_bound = sum(len(planned[s] or []) for s in SIDES) * (
        2000 if calculator == "rbs" else 100
    )
    if feature_bound > LIMITS["max_feature_bases"]:
        raise PairError("max_feature_bases exceeded")
    sides = {}
    for side in SIDES:
        request = value[side + "_request"]
        if calculator == "rbs":
            assert backend is not None
            prediction = rbs.predict(
                request,
                backend,
                seconds=settings["seconds_per_side"],
                profile=settings["profile"],
            )
        else:
            prediction = promoter_io.predict_batch(
                request,
                seconds_per_record=settings["seconds_per_side"],
                seconds_per_batch=settings["seconds_per_side"],
            )
        projection = value.get("projections", {}).get(side)
        sides[side] = _side(
            request, prediction, calculator, planned[side], geometry, side, projection
        )
    rows = _comparisons(sides, geometry)
    coverage: dict[str, Any] = {}
    for side in SIDES:
        part = sides[side]
        candidates = part["candidates"]
        record = (
            part["prediction"]
            if calculator == "rbs"
            else part["prediction"]["results"][0]
        )
        coverage[side] = {
            "expected": None if part["roster_status"] == "unknown" else len(candidates),
            "returned": sum(c["site_index"] is not None for c in candidates),
            "scored": sum(c["status"] == "ok" for c in candidates),
            "complete": part["roster_status"] == "known"
            and record["status"] in ("ok", "no_candidate")
            and all(c["site_index"] is not None for c in candidates),
        }
    paired = sum(row["status"] == "paired" for row in rows)
    comparable = sum(
        row["status"] == "paired" and row["reason"] is None for row in rows
    )
    complete = all(coverage[s]["complete"] for s in SIDES)
    identities_equal = sides["current"]["identities"] == sides["recoded"]["identities"]
    status = (
        "partial"
        if not complete
        else ("complete" if identities_equal else "incomparable")
    )
    if not complete and not comparable:
        status = "unavailable"
    coverage.update(
        paired=paired,
        unmatched=len(rows) - paired,
        comparable=comparable,
        complete=complete,
        diagnostic_only=not complete,
    )
    result = {
        "schema_version": "paired-regulatory-result-1",
        "pair_id": geometry.pair_id,
        "calculator": calculator,
        "status": status,
        "request_sha256": _hash(value),
        "edit_map": geometry.to_dict(),
        "settings": settings,
        "limits": dict(LIMITS)
        | {
            "predictors": {
                "promoter": dict(promoter_io.LIMITS),
                "rbs": {
                    "max_normalized_bases_per_record": MAX_SEQUENCE_LENGTH,
                    "max_explicit_or_scanned_starts": MAX_EXPLICIT_STARTS,
                    "max_seconds_per_record": 120,
                },
            }
        },
        "sides": sides,
        "comparisons": rows,
        "coverage": coverage,
        "warnings": ["predicted_differences_are_not_measured_regulatory_effects"]
        + (["partial_predictions_are_diagnostic_only"] if not complete else []),
    }
    result["prediction_sha256"] = _hash(result)
    if len(result_bytes(result)) > LIMITS["max_result_json_bytes"]:
        raise PairError("output: max_result_json_bytes exceeded")
    return result

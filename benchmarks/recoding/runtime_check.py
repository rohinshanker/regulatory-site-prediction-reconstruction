"""Independent, outcome-free audit of the public paired runtime contract.

Authority: paired-regulatory-runtime.md at 920215602a837b0fd2fed403512f3b3ed59bfda2
(SHA256 2d296cc5a2673e0c608aa0d862e4cc15eb066276290d8b69587864c29413e398).
No predictor, scorer, folding engine, native cache or runtime module is imported.
"""

import copy
import hashlib
import json
import math
from pathlib import Path

from benchmarks.recoding.codon_pairs import match_rbs_candidates
from benchmarks.recoding.edit_maps import build_map, map_interval, project_base

FIXTURE_SHA256 = "9ea3b25074c01502d8149dba99edc2e6cf6011f6940f9d5b3a074bfdcadb357c"
SIDES = ("current", "recoded")
IDENTITIES = ("model_sha256", "settings_sha256", "backend_sha256", "calibration_sha256")
RBS_ENERGIES = (
    "dG_mRNA dG_mRNA_native_prediction dG_cofold_native_prediction dG_cofold_search "
    "dG_search_with_spacing dG_complex dG_spacing dG_start dG_standby_signed "
    "dG_accessible_complex dG_total dG_standby dG_distortion dG_unfolding "
    "dG_unfolding_raw dG_sliding dG_post_footprint"
).split()
PROMOTER_TERMS = (
    "hex10 hex35 discriminator extended10 itr up spacer intercept total binding"
).split()
PROMOTER_FEATURES = "UP gap hex35 spacer extended10 hex10 discriminator itr".split()
RBS_FEATURES = (
    "start_codon window binding_interval standby_interval coding_footprint"
).split()
LIMIT_CEILINGS = {
    "max_input_json_bytes": 2000000,
    "max_result_json_bytes": 67108864,
    "max_candidates_per_side": 512,
    "max_edits": 1000,
    "max_bases_per_side": 10000,
    "max_feature_bases": 2000000,
    "max_seconds_per_side": 120,
    "max_json_depth": 20,
    "max_json_nodes": 100000,
}
WARNING = "predicted_differences_are_not_measured_regulatory_effects"
PARTIAL_WARNING = "partial_predictions_are_diagnostic_only"
AUDIT_SCOPE = "public_hashes_geometry_extraction_arithmetic_accounting"


def canonical_bytes(value):
    """Return the contract's finite compact sorted ASCII JSON bytes."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def sha256(value):
    """Hash a JSON value using the public canonical representation."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def result_bytes(value):
    """Return authoritative sorted indent-2 ASCII JSON with exactly one LF."""
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "ascii"
    )


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, required, optional=()):
    _require(
        type(value) is dict
        and set(required) <= value.keys() <= set(required) | set(optional),
        "Unknown, missing or ambiguous contract fields",
    )


def _same(actual, expected, label):
    _require(canonical_bytes(actual) == canonical_bytes(expected), label)


def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high, "Invalid integer/bounds")
    return value


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON token: " + value)


def _parse(wire, cap):
    _require(type(wire) is bytes and len(wire) <= cap, "Wire byte cap/type")
    try:
        return json.loads(
            wire.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 or JSON depth") from exc


def _tree(value, limits):
    """Bound raw request JSON without traversing cycles recursively."""
    pending, count = [(value, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        _require(
            depth <= limits["max_json_depth"] and count <= limits["max_json_nodes"],
            "Request JSON depth/node cap",
        )
        if type(node) is dict:
            _require(all(type(k) is str for k in node), "JSON keys must be strings")
            pending.extend((v, depth + 1) for v in node.values())
        elif type(node) is list:
            pending.extend((v, depth + 1) for v in node)
        else:
            _require(
                node is None or type(node) in (str, bool) or _finite(node),
                "Expected finite JSON values",
            )


def build_requests(fixture_bytes=None):
    """Build 18 single-strand jobs per calculator from the exact frozen panel.

    The fixture's singular ``projection`` object becomes each Promoter request's
    ``projection``, or the RBS wrapper's plural ``projections``. Fixture Promoter
    ranges are oriented; minus requests instead scan forward [19,L-67). Literal
    RBS anchors become sorted oriented starts, including explicit empty lists.
    No hidden windows, candidate discovery or optional standby run is inferred.

    Returns a list of independent request documents and a byte/count manifest.
    """
    if fixture_bytes is None:
        fixture_bytes = (
            Path(__file__).with_name("runtime-pair-fixtures.json").read_bytes()
        )
    _require(
        type(fixture_bytes) is bytes
        and hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256,
        "Frozen fixture bytes changed",
    )
    fixture = _parse(fixture_bytes, len(fixture_bytes))
    jobs, entries = [], []
    for case in fixture["cases"]:
        pair = case["input"]
        build_map(pair)
        for calculator in ("promoter", "rbs"):
            for strand in ("+", "-"):
                job = {
                    "schema_version": "paired-regulatory-request-1",
                    "pair": copy.deepcopy(pair),
                    "calculator": calculator,
                    "settings": {
                        "seconds_per_side": 30.0 if calculator == "promoter" else 60.0
                    },
                }
                counts = {}
                for side in SIDES:
                    source = pair[side]
                    length = len(source["sequence"])
                    request = {"schema_version": "1.0", **source}
                    if calculator == "promoter":
                        bounds = (
                            [67, length - 19] if strand == "+" else [19, length - 67]
                        )
                        request.update(
                            scan={"mode": "scan", "range": bounds, "strands": [strand]},
                            calibration="ecoli_mg1655",
                            output={
                                "states": "selected",
                                "legacy_keys": False,
                                "elements": False,
                            },
                            projection=copy.deepcopy(case["projection"][side]),
                        )
                        counts[side] = bounds[1] - bounds[0]
                    else:
                        starts = sorted(
                            row["base"] if strand == "+" else length - 1 - row["base"]
                            for row in case["expected_rbs_candidates"][side]
                            if row["strand"] == strand
                        )
                        request.update(
                            strand=strand,
                            start_positions=starts,
                            anti_sd="ACCUCCUUU",
                            temperature_c=37.0,
                            host=None,
                        )
                        counts[side] = len(starts)
                    job[side + "_request"] = request
                if calculator == "rbs":
                    job["settings"]["profile"] = "historical"
                    job["projections"] = copy.deepcopy(case["projection"])
                jobs.append(job)
                entries.append(
                    {
                        "pair_id": pair["pair_id"],
                        "calculator": calculator,
                        "strand": strand,
                        "positions": counts,
                        "request_sha256": sha256(job),
                        "request_bytes": len(canonical_bytes(job)),
                    }
                )
    return jobs, {
        "fixture_sha256": FIXTURE_SHA256,
        "jobs_sha256": sha256(jobs),
        "jobs": entries,
        "counts": {
            calculator: {
                "jobs": sum(e["calculator"] == calculator for e in entries),
                "positions": sum(
                    sum(e["positions"].values())
                    for e in entries
                    if e["calculator"] == calculator
                ),
            }
            for calculator in ("promoter", "rbs")
        },
    }


def _roster(request, calculator, length):
    """Resolve explicit public policies; invalid scan syntax is an unknown roster.

    This checker deliberately requires explicit RBS start_positions. Native
    implicit motif scanning is outside its finite request-builder scope.
    """
    try:
        if calculator == "rbs":
            strand = request["strand"]
            _require(strand in ("+", "-"), "Invalid strand")
            starts = request["start_positions"]
            _require(type(starts) is list, "Explicit starts required")
            for start in starts:
                _integer(start, 0, length - 3)
            _require(len(starts) == len(set(starts)), "Duplicate starts")
            return [
                (strand, s if strand == "+" else length - 1 - s) for s in sorted(starts)
            ]
        scan = request["scan"]
        if scan["mode"] == "positions":
            _keys(scan, ("mode", "positions"))
            _require(type(scan["positions"]) is list, "Invalid positions")
            positions = []
            for row in scan["positions"]:
                _keys(row, ("strand", "tss"))
                _require(row["strand"] in ("+", "-"), "Invalid strand")
                positions.append((row["strand"], _integer(row["tss"], 0, length - 1)))
        else:
            _keys(scan, ("mode", "range", "strands"))
            _same(scan["mode"], "scan", "Unknown scan mode")
            _require(
                type(scan["range"]) is list and len(scan["range"]) == 2,
                "Invalid scan range",
            )
            start = _integer(scan["range"][0], 0, length)
            end = _integer(scan["range"][1], start, length)
            strands = scan["strands"]
            _require(
                type(strands) is list
                and 1 <= len(strands) <= 2
                and all(s in ("+", "-") for s in strands)
                and len(set(strands)) == len(strands),
                "Invalid scan strands",
            )
            positions = [(s, b) for s in strands for b in range(start, end)]
        _require(len(positions) == len(set(positions)), "Duplicate positions")
        return positions
    except (KeyError, TypeError, ValueError):
        return None


def _genomic(projection, bases, strand, length):
    if projection is None:
        return None
    # Validate even an empty feature's projection, without projecting index L.
    first = project_base(projection, 0, strand, length)
    return {
        "projection": projection,
        "strand": first["strand"],
        "bases": [project_base(projection, b, strand, length)["base"] for b in bases],
    }


def _feature(interval, strand, mapping, side, projection, remaining):
    if interval is None:
        return {
            "interval": None,
            "strand": strand,
            "mapping": None,
            "genomic": None,
            "reason": "feature_unavailable",
        }
    _require(type(interval) is list and len(interval) == 2, "Invalid feature interval")
    length = len(
        mapping[side + "_to_" + ("recoded" if side == "current" else "current")]
    )
    start = _integer(interval[0], 0, length)
    end = _integer(
        interval[1],
        start,
        start + length if mapping["topology"] == "circular" else length,
    )
    remaining[0] -= end - start
    _require(remaining[0] >= 0, "Actual source feature-base cap")
    # The B interval oracle rejects a circular start at L, even for [L,L).
    # The public empty interval convention explicitly permits that case.
    if type(start) is int and type(end) is int and start == end == length:
        mapped = {
            "source_bases": [],
            "mapped_bases": [],
            "mapped_runs": [],
            "unmatched_bases": 0,
            "complete_base_mapping": True,
            "contiguous_target_path": True,
        }
    else:
        mapped = map_interval(mapping, side, start, end, strand)
    return {
        "interval": interval,
        "strand": strand,
        "mapping": mapped,
        "genomic": _genomic(projection, mapped["source_bases"], strand, length),
        "reason": None,
    }


def _scalar(value, unit, reason="value_unavailable"):
    _require(value is None or _finite(value), "Nonfinite/non-numeric scalar")
    return {"value": value, "unit": unit, "reason": reason if value is None else None}


def _extract(site, calculator, strand):
    """Extract only public native fields, with no equations or inferred windows."""
    scalars, intervals = {}, {}
    if calculator == "promoter":
        selected = site.get("selected")
        if selected is not None:
            _keys(
                selected,
                (
                    "terms",
                    "relative_transcription_score",
                    "log_relative_transcription_score",
                    "score_status",
                    "intervals",
                ),
                (
                    "state_id",
                    "discriminator_length",
                    "spacer_length",
                    "oriented_intervals",
                    "genomic_intervals",
                    "elements",
                ),
            )
            _keys(selected["terms"], PROMOTER_TERMS, ("source_apparent",))
            _require(
                selected["score_status"] in ("ok", "overflow", "underflow"),
                "Unknown native relative-score status",
            )
        for name in PROMOTER_TERMS:
            value = selected["terms"][name] if selected is not None else None
            scalars[name] = _scalar(value, "source_dG_units")
        for name in (
            "relative_transcription_score",
            "log_relative_transcription_score",
        ):
            value = selected[name] if selected is not None else None
            reason = (
                selected["score_status"]
                if selected is not None
                else "value_unavailable"
            )
            scalars[name] = _scalar(value, name.replace("log_", "ln_"), reason)
        intervals = dict.fromkeys(PROMOTER_FEATURES)
        if selected is not None:
            _keys(selected["intervals"], PROMOTER_FEATURES)
            intervals.update(selected["intervals"])
    else:
        energies = site.get("energies") or {}
        _keys(energies, (), [*RBS_ENERGIES, "units"])
        if energies:
            _same(energies["units"], "kcal/mol", "Native energy units")
        for name in RBS_ENERGIES:
            scalars[name] = _scalar(energies.get(name), "kcal/mol")
        for name, unit in (
            ("tir", "relative_initiation_score"),
            ("log_tir", "ln_relative_initiation_score"),
        ):
            scalars[name] = _scalar(site.get(name), unit)
        native_intervals = {name: site.get(name) for name in RBS_FEATURES}
        window = site.get("window")
        native_intervals["window"] = (
            window["input_interval"] if window is not None else None
        )
        standby = site.get("standby")
        if standby is not None:
            for name in ("original_hairpin", "hairpin", "distal", "proximal"):
                native_intervals["standby." + name] = standby[name]
            for i, hairpin in enumerate(standby["downstream_hairpins"]):
                native_intervals[f"standby.downstream_hairpins.{i}"] = hairpin[
                    "interval"
                ]
        for name, interval in native_intervals.items():
            if interval is None:
                intervals[name] = None
            else:
                _keys(interval, ("start", "end", "strand"))
                _same(interval["strand"], strand, "Native feature strand mismatch")
                intervals[name] = [interval["start"], interval["end"]]
    return scalars, intervals


def _side(document, side, supplied, mapping, roster, remaining):
    calculator = document["calculator"]
    request = document[side + "_request"]
    length = len(document["pair"][side]["sequence"])
    _keys(
        supplied,
        (
            "request",
            "prediction",
            "prediction_sha256",
            "identities",
            "projection",
            "roster_status",
            "candidates",
        ),
    )
    _same(supplied["request"], request, "Retained request changed")
    prediction = supplied["prediction"]
    _same(supplied["prediction_sha256"], sha256(prediction), "Native prediction hash")
    if calculator == "promoter":
        _keys(prediction, ("schema_version", "model", "batch", "results"))
        _same(prediction["schema_version"], "1.0", "Native schema version")
        _require(
            type(prediction["results"]) is list and len(prediction["results"]) == 1,
            "Expected single-record native envelope",
        )
        record = prediction["results"][0]
        _keys(
            record,
            ("id", "status", "projection", "calibration", "sites"),
            (
                "reasons",
                "prediction_id",
                "input",
                "scan",
                "coverage",
                "warnings",
                "errors",
                "metadata",
            ),
        )
        projection = record["projection"]
        # A rejected projection may resolve to null, but cannot invent a projection.
        _require(
            projection == request.get("projection")
            or (
                projection is None
                and record["status"] in ("invalid_input", "unsupported")
            ),
            "Native projection disagrees with request",
        )
        identities = dict(
            zip(
                IDENTITIES,
                map(
                    sha256,
                    (
                        prediction["model"],
                        {"selection": "minimum_source_total_first_visited_exact_tie"},
                        {"kind": "stdlib_no_folding_backend"},
                        record["calibration"],
                    ),
                ),
                strict=True,
            )
        )
    else:
        record = prediction
        _keys(
            record,
            ("schema_version", "id", "status", "model", "backend", "sites"),
            ("reason", "warnings", "input", "prediction_id"),
        )
        _require(
            record["schema_version"] in ("1.0", "1.1", "1.2", "1.3"),
            "Unknown native schema version",
        )
        projection = document.get("projections", dict.fromkeys(SIDES))[side]
        identities = dict(
            zip(
                IDENTITIES,
                map(
                    sha256,
                    (
                        prediction["model"],
                        {
                            "anti_sd": request["anti_sd"].upper().replace("T", "U"),
                            "temperature_c": float(request["temperature_c"]),
                        }
                        if record["status"] != "invalid_input"
                        else {
                            "anti_sd": request["anti_sd"],
                            "temperature_c": request["temperature_c"],
                        },
                        prediction["backend"],
                        {"host": request["host"], "host_calibration": "not_calibrated"},
                    ),
                ),
                strict=True,
            )
        )
    _require(
        record["status"]
        in ("ok", "no_candidate", "invalid_input", "unsupported", "failed"),
        "Unknown native record status",
    )
    _require(record["id"] in (request["id"], None), "Native record ID changed")
    _same(supplied["identities"], identities, "Scientific identity hashes")
    _same(supplied["projection"], projection, "Side projection mismatch")
    if projection is not None:
        project_base(projection, 0, "+", length)
    _same(
        supplied["roster_status"],
        "unknown" if roster is None else "known",
        "Roster status",
    )
    roster = [] if roster is None else roster
    sites = record["sites"]
    _require(type(sites) is list, "Native sites must be a list")
    lookup = {}
    for index, site in enumerate(sites):
        if calculator == "promoter":
            _keys(
                site,
                ("strand", "tss", "status", "reason", "selected"),
                (
                    "site_id",
                    "genomic",
                    "context",
                    "state_count",
                    "complete_state_set",
                    "attempted",
                    "tie_count",
                    "states",
                    "legacy_source_key",
                ),
            )
            _keys(site["tss"], ("forward_base", "oriented_base"))
        else:
            _keys(
                site,
                ("oriented_start", "status", "reason", "start_codon"),
                (
                    "codon",
                    "window",
                    "energies",
                    "tir",
                    "log_tir",
                    "aligned_spacing",
                    "candidate_search",
                    "structures",
                    "binding_interval",
                    "standby_interval",
                    "warnings",
                    "coding_footprint",
                    "post_footprint",
                    "standby",
                    "joint_search",
                ),
            )
        strand = site["strand"] if calculator == "promoter" else request["strand"]
        if calculator == "promoter":
            anchor = site["tss"]["forward_base"]
            _same(
                site["tss"]["oriented_base"],
                anchor if strand == "+" else length - 1 - anchor,
                "Native oriented TSS",
            )
        else:
            oriented = _integer(site["oriented_start"], 0, length - 3)
            anchor = oriented if strand == "+" else length - 1 - oriented
        _integer(anchor, 0, length - 1)
        key = (strand, anchor)
        _require(
            key in roster and key not in lookup, "Extra/duplicate native candidate"
        )
        _require(
            site["status"]
            in ("ok", "no_candidate", "failed", "unsupported", "invalid_input"),
            "Unknown native candidate status",
        )
        lookup[key] = (index, site)
    scope = sha256(
        {"request": request, "identities": identities, "projection": projection}
    )[:32]
    expected = []
    for strand, anchor in roster:
        index, site = lookup.get((strand, anchor), (None, {}))
        scalars, intervals = _extract(site, calculator, strand)
        features = {
            name: _feature(interval, strand, mapping, side, projection, remaining)
            for name, interval in intervals.items()
        }
        step = 1 if strand == "+" else -1
        codon = [anchor + step * i for i in range(3)] if calculator == "rbs" else None
        if index is not None and calculator == "rbs":
            _same(
                intervals["start_codon"],
                [min(codon), max(codon) + 1],
                "Native codon interval",
            )
        expected.append(
            {
                "id": f"pcandidate1:{scope}:{side}:{calculator}:{strand}:{anchor}",
                "strand": strand,
                "anchor": anchor,
                "codon_bases": codon,
                "status": site.get("status", "unavailable"),
                "reason": site["reason"]
                if index is not None
                else "prediction_candidate_unavailable",
                "site_index": index,
                "scalars": scalars,
                "features": features,
                "genomic": _genomic(projection, [anchor], strand, length),
            }
        )
    _same(
        supplied["candidates"],
        expected,
        "Candidate roster/extraction/geometry mismatch",
    )
    returned = len(lookup)
    return expected, {
        "expected": None if supplied["roster_status"] == "unknown" else len(roster),
        "returned": returned,
        "scored": sum(c["status"] == "ok" for c in expected),
        "complete": supplied["roster_status"] == "known"
        and returned == len(roster)
        and record["status"] in ("ok", "no_candidate"),
    }


def _comparisons(document, sides, mapping):
    before, after = (sides[s]["candidates"] for s in SIDES)
    mismatches = [
        k
        for k in IDENTITIES
        if sides["current"]["identities"][k] != sides["recoded"]["identities"][k]
    ]
    paired, reasons = {}, {}
    if document["calculator"] == "rbs":
        rosters = [
            [{"id": c["id"], "base": c["anchor"], "strand": c["strand"]} for c in rows]
            for rows in (before, after)
        ]
        audit = match_rbs_candidates(document["pair"], *rosters)
        paired = {p["current_id"]: p["recoded_id"] for p in audit["pairs"]}
        reasons = {r["id"]: r["reason"] for s in SIDES for r in audit["unmatched_" + s]}
    else:
        lookup = {(c["anchor"], c["strand"]): c["id"] for c in after}
        paired = {
            c["id"]: lookup[(mapping["current_to_recoded"][c["anchor"]], c["strand"])]
            for c in before
            if (mapping["current_to_recoded"][c["anchor"]], c["strand"]) in lookup
        }
    by_id = {c["id"]: c for c in after}
    visits = [(c, by_id.get(paired.get(c["id"]))) for c in before]
    visits += [(None, c) for c in after if c["id"] not in paired.values()]
    comparisons = []
    for current, recoded in visits:
        status, reason = "paired", None
        if current is not None and recoded is not None:
            if mismatches:
                reason = "incompatible_identity"
            elif current["status"] != "ok" or recoded["status"] != "ok":
                reason = "unsuccessful_candidate"
        else:
            side = "current" if current is not None else "recoded"
            other = "recoded" if side == "current" else "current"
            candidate = current if current is not None else recoded
            status = "unmatched"
            if sides[other]["roster_status"] == "unknown":
                status, reason = "unavailable", "counterpart_roster_unknown"
            elif reasons.get(candidate["id"]) == "interrupted_codon":
                reason = "interrupted_codon"
            elif mapping[side + "_to_" + other][candidate["anchor"]] is None:
                reason = "unmapped_" + side + "_anchor"
            else:
                reason = "mapped_anchor_absent_from_" + other + "_roster"
        deltas = {}
        exemplar = current if current is not None else recoded
        for name, scalar in exemplar["scalars"].items():
            value, missing = None, reason or "value_unavailable"
            if reason is None:
                a, b = (
                    current["scalars"][name]["value"],
                    recoded["scalars"][name]["value"],
                )
                if a is not None and b is not None:
                    difference = b - a
                    if _finite(difference):
                        value = difference
                    else:
                        missing = "nonfinite_delta"
            deltas[name] = _scalar(value, scalar["unit"], missing)
        changes = {}
        if status == "paired":
            for name in sorted(current["features"].keys() | recoded["features"].keys()):
                a, b = current["features"].get(name), recoded["features"].get(name)
                if (
                    a is None
                    or b is None
                    or a["mapping"] is None
                    or b["mapping"] is None
                ):
                    changes[name] = {
                        "mapped_bases_equal": None,
                        "reason": "feature_unavailable",
                    }
                else:
                    changes[name] = {
                        "mapped_bases_equal": a["mapping"]["complete_base_mapping"]
                        and a["mapping"]["mapped_bases"]
                        == b["mapping"]["source_bases"],
                        "reason": None,
                    }
        comparisons.append(
            {
                "current_candidate_id": None if current is None else current["id"],
                "recoded_candidate_id": None if recoded is None else recoded["id"],
                "status": status,
                "reason": reason,
                "identity_mismatches": mismatches,
                "deltas": deltas,
                "feature_changes": changes,
            }
        )
    return comparisons, mismatches


def check_result(document, received, expected_limits):
    """Audit supplied strict JSON bytes; return bounded aggregate evidence.

    Caller supplies the original request and the candidate receipt's complete
    expected wrapper limits (including predictors). Wire and authoritative byte
    caps both apply. Native model/backend/calibration dictionaries and untouched
    structures are hash-bound, not admitted as scientifically valid here. The
    caller must independently admit the candidate and validate full native result
    schemas, native input identities, model equations, selected-state semantics,
    backend provenance and deadline execution. This audit checks all wrapper
    extraction against those supplied native fields; it cannot certify inference.
    Only explicit RBS starts are admitted; implicit scan requests are rejected.
    Unknown Promoter scan syntax is retained solely as a diagnostic unknown roster.
    No collector, runtime invocation, score threshold or biological label is added.
    Both conservative request charges and actual enumerated source feature bases
    must fit the receipt's feature budget before allocating their maps.
    """
    try:
        return _check_result(document, received, expected_limits)
    except (
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise ValueError("Malformed public contract data") from exc


def _check_result(document, received, limits):
    _keys(limits, (*LIMIT_CEILINGS, "predictors"))
    for name, ceiling in LIMIT_CEILINGS.items():
        _integer(limits[name], 1, ceiling)
    _keys(limits["predictors"], ("promoter", "rbs"))
    _tree(document, limits)
    _require(
        len(canonical_bytes(document)) <= limits["max_input_json_bytes"],
        "Input byte cap",
    )
    _keys(
        document,
        (
            "schema_version",
            "pair",
            "calculator",
            "current_request",
            "recoded_request",
            "settings",
        ),
        ("projections",),
    )
    _same(document["schema_version"], "paired-regulatory-request-1", "Request schema")
    calculator = document["calculator"]
    _require(calculator in ("promoter", "rbs"), "Unknown calculator")
    mapping = build_map(document["pair"])
    _require(len(document["pair"]["edits"]) <= limits["max_edits"], "Edit cap")
    _keys(
        document["settings"],
        ("seconds_per_side", "profile")
        if calculator == "rbs"
        else ("seconds_per_side",),
    )
    seconds = document["settings"]["seconds_per_side"]
    _require(
        _finite(seconds) and 0 < seconds <= limits["max_seconds_per_side"],
        "Deadline cap",
    )
    if calculator == "promoter":
        _require("projections" not in document, "Promoter outer projections forbidden")
    else:
        _require(
            document["settings"]["profile"]
            in (
                "historical",
                "salis-v1-rnastructure-6.6-reconstruction-1",
                "footprint2017",
                "footprint2017-rnastructure-6.6-reconstruction-1",
                "context2017",
                "context2017-rnastructure-6.6-reconstruction-1",
                "standby2014",
                "standby2014-rnastructure-6.6-reconstruction-1",
                "joint_standby",
                "joint-standby-rnastructure-6.6-reconstruction-1",
            ),
            "Unknown RBS profile",
        )
        if "projections" in document:
            _keys(document["projections"], SIDES)
    rosters = {}
    for side in SIDES:
        request = document[side + "_request"]
        if calculator == "rbs":
            _keys(
                request,
                (
                    "id",
                    "sequence",
                    "strand",
                    "anti_sd",
                    "temperature_c",
                    "host",
                    "start_positions",
                ),
                ("schema_version",),
            )
            _require(
                type(request["start_positions"]) is list,
                "RBS requires explicit starts, never implicit scanning",
            )
        else:
            _keys(
                request,
                ("id", "sequence"),
                (
                    "schema_version",
                    "scan",
                    "calibration",
                    "host",
                    "output",
                    "projection",
                    "model",
                    "metadata",
                ),
            )
        _same(request.get("schema_version", "1.0"), "1.0", "Side request schema")
        source = document["pair"][side]
        _same(request["id"], source["id"], "Pair/request ID binding")
        _same(
            request["sequence"]
            .translate(str.maketrans("", "", " \t\n\v\f\r"))
            .upper()
            .replace("U", "T"),
            source["sequence"],
            "Pair/request sequence binding",
        )
        _require(len(source["sequence"]) <= limits["max_bases_per_side"], "Base cap")
        rosters[side] = _roster(request, calculator, len(source["sequence"]))
        _require(
            len(rosters[side] or []) <= limits["max_candidates_per_side"],
            "Candidate cap",
        )
    count = sum(len(rosters[s] or []) for s in SIDES)
    _require(
        count * (2000 if calculator == "rbs" else 100) <= limits["max_feature_bases"],
        "Conservative feature-base cap",
    )
    result = _parse(received, limits["max_result_json_bytes"])
    _require(
        len(result_bytes(result)) <= limits["max_result_json_bytes"],
        "Authoritative byte cap",
    )
    _keys(
        result,
        (
            "schema_version",
            "pair_id",
            "calculator",
            "status",
            "request_sha256",
            "prediction_sha256",
            "edit_map",
            "settings",
            "limits",
            "sides",
            "comparisons",
            "coverage",
            "warnings",
        ),
    )
    _same(result["schema_version"], "paired-regulatory-result-1", "Result schema")
    for key, expected in (
        ("pair_id", document["pair"]["pair_id"]),
        ("calculator", calculator),
        ("settings", document["settings"]),
        ("limits", limits),
        ("edit_map", mapping),
        ("request_sha256", sha256(document)),
    ):
        _same(result[key], expected, "Result " + key)
    _same(
        result["prediction_sha256"],
        sha256({k: v for k, v in result.items() if k != "prediction_sha256"}),
        "Whole result hash",
    )
    _keys(result["sides"], SIDES)
    coverage, remaining = {}, [limits["max_feature_bases"]]
    for side in SIDES:
        _, coverage[side] = _side(
            document, side, result["sides"][side], mapping, rosters[side], remaining
        )
    comparisons, mismatches = _comparisons(document, result["sides"], mapping)
    _same(result["comparisons"], comparisons, "Comparison arithmetic/order/accounting")
    paired = sum(row["status"] == "paired" for row in comparisons)
    comparable = sum(row["reason"] is None for row in comparisons)
    complete = all(coverage[s]["complete"] for s in SIDES)
    coverage.update(
        paired=paired,
        unmatched=len(comparisons) - paired,
        comparable=comparable,
        complete=complete,
        diagnostic_only=not complete,
    )
    _same(result["coverage"], coverage, "Coverage accounting")
    status = (
        ("incomparable" if mismatches else "complete")
        if complete
        else ("partial" if comparable else "unavailable")
    )
    _same(result["status"], status, "Completion status")
    _same(
        result["warnings"],
        [WARNING] if complete else [WARNING, PARTIAL_WARNING],
        "Warnings",
    )
    return {
        "audit_scope": AUDIT_SCOPE,
        "native_prediction_admitted": False,
        "request_sha256": result["request_sha256"],
        "prediction_sha256": result["prediction_sha256"],
        "wire_bytes": len(received),
        "authoritative_bytes": len(result_bytes(result)),
        "status": status,
        "coverage": coverage,
        "identity_mismatches": mismatches,
    }

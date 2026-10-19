"""Artificial public results only: no scientific runtime or private outputs."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from benchmarks.recoding import runtime_check as checker
from benchmarks.recoding.edit_maps import build_map, map_interval


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")
    ).hexdigest()


def limits():
    # These are artificial receipt limits, not candidate admission evidence.
    return {**checker.LIMIT_CEILINGS, "predictors": {"promoter": {}, "rbs": {}}}


def request(calculator="promoter", strand="+", circular=False):
    pair = {
        "schema_version": "paired-edit-input-1",
        "pair_id": "artificial",
        "topology": "circular" if circular else "linear",
        "current": {"id": "c", "sequence": "ATGAAAAA"},
        "recoded": {"id": "r", "sequence": "ATGAAAAA"},
        "edits": [],
    }
    document = {
        "schema_version": "paired-regulatory-request-1",
        "pair": pair,
        "calculator": calculator,
        "settings": {"seconds_per_side": 30.0},
    }
    for side in checker.SIDES:
        req = {"schema_version": "1.0", **pair[side]}
        if calculator == "promoter":
            req.update(
                scan={"mode": "positions", "positions": [{"strand": strand, "tss": 2}]},
                calibration="ecoli_mg1655",
            )
        else:
            req.update(
                strand=strand,
                start_positions=[0],
                anti_sd="ACCUCCUUU",
                temperature_c=37.0,
                host=None,
            )
        document[side + "_request"] = req
    if calculator == "rbs":
        document["settings"]["profile"] = "historical"
    return document


def native(document, side, values=1.0):
    req, calc = document[side + "_request"], document["calculator"]
    model = {"id": "artificial", "parameters": {"k": 1}}
    if calc == "promoter":
        positions = req["scan"].get("positions")
        if positions is None:
            positions = [
                {"strand": s, "tss": b}
                for s in req["scan"]["strands"]
                for b in range(*req["scan"]["range"])
            ]
        sites = [
            {
                "strand": p["strand"],
                "tss": {
                    "forward_base": p["tss"],
                    "oriented_base": p["tss"]
                    if p["strand"] == "+"
                    else len(req["sequence"]) - 1 - p["tss"],
                },
                "status": "ok",
                "reason": None,
                "selected": {
                    "terms": {k: values for k in checker.PROMOTER_TERMS},
                    "relative_transcription_score": values,
                    "log_relative_transcription_score": values,
                    "score_status": "ok",
                    "intervals": dict.fromkeys(checker.PROMOTER_FEATURES, [0, 3]),
                },
            }
            for p in positions
        ]
        return {
            "schema_version": "1.0",
            "model": model,
            "batch": {},
            "results": [
                {
                    "id": req["id"],
                    "status": "ok" if sites else "no_candidate",
                    "projection": req.get("projection"),
                    "calibration": {"profile": "artificial"},
                    "sites": sites,
                }
            ],
        }
    strand = req["strand"]
    length = len(req["sequence"])
    sites = []
    for start in sorted(req["start_positions"]):
        a, b = (
            [start, start + 3]
            if strand == "+"
            else [length - start - 3, length - start]
        )
        interval = {"start": a, "end": b, "strand": strand}
        sites.append(
            {
                "oriented_start": start,
                "status": "ok",
                "reason": None,
                "start_codon": interval,
                "window": {
                    "input_interval": {"start": 0, "end": length, "strand": strand}
                },
                "binding_interval": interval,
                "standby_interval": None,
                "energies": {
                    "units": "kcal/mol",
                    **dict.fromkeys(checker.RBS_ENERGIES, values),
                },
                "tir": values,
                "log_tir": values,
            }
        )
    return {
        "schema_version": "1.0",
        "id": req["id"],
        "status": "ok" if sites else "no_candidate",
        "model": model,
        "backend": {"kind": "artificial_no_execution"},
        "sites": sites,
    }


def record(prediction, calc):
    return prediction["results"][0] if calc == "promoter" else prediction


def artificial_result(document, predictions=None, receipt=None):
    """Independently assemble small wrapper expectations from artificial fields.

    This fixture intentionally omits unrelated native schema fields. It tests the
    documented extraction boundary, and is never a candidate/native admission.
    Geometry is from the frozen B oracle, with manually enumerated projections.
    """
    receipt = limits() if receipt is None else receipt
    predictions = predictions or {s: native(document, s) for s in checker.SIDES}
    calc = document["calculator"]
    mapping = build_map(document["pair"])
    result = {
        "schema_version": "paired-regulatory-result-1",
        "pair_id": document["pair"]["pair_id"],
        "calculator": calc,
        "request_sha256": digest(document),
        "edit_map": mapping,
        "settings": copy.deepcopy(document["settings"]),
        "limits": copy.deepcopy(receipt),
        "sides": {},
        "comparisons": [],
        "coverage": {},
        "warnings": [checker.WARNING],
    }
    for side in checker.SIDES:
        req, prediction = document[side + "_request"], predictions[side]
        rec = record(prediction, calc)
        length = len(req["sequence"])
        projection = (
            rec["projection"]
            if calc == "promoter"
            else document.get("projections", dict.fromkeys(checker.SIDES))[side]
        )
        hashes = [digest(prediction["model"])]
        if calc == "promoter":
            hashes += [
                digest({"selection": "minimum_source_total_first_visited_exact_tie"}),
                digest({"kind": "stdlib_no_folding_backend"}),
                digest(rec["calibration"]),
            ]
            scan = req.get("scan")
            if scan is None or scan.get("mode") == "invalid":
                roster = None
            elif scan["mode"] == "positions":
                roster = [(p["strand"], p["tss"]) for p in scan["positions"]]
            else:
                roster = [
                    (s, b) for s in scan["strands"] for b in range(*scan["range"])
                ]
            units = {k: "source_dG_units" for k in checker.PROMOTER_TERMS}
            units.update(
                relative_transcription_score="relative_transcription_score",
                log_relative_transcription_score="ln_relative_transcription_score",
            )
        else:
            hashes += [
                digest(
                    {
                        "anti_sd": req["anti_sd"].upper().replace("T", "U"),
                        "temperature_c": float(req["temperature_c"]),
                    }
                ),
                digest(prediction["backend"]),
                digest({"host": req["host"], "host_calibration": "not_calibrated"}),
            ]
            roster = [
                (req["strand"], s if req["strand"] == "+" else length - 1 - s)
                for s in sorted(req["start_positions"])
            ]
            if (
                req["strand"] not in ("+", "-")
                or any(
                    type(s) is not int or not 0 <= s <= length - 3
                    for s in req["start_positions"]
                )
                or len(req["start_positions"]) != len(set(req["start_positions"]))
            ):
                roster = None
            units = dict.fromkeys(checker.RBS_ENERGIES, "kcal/mol")
            units.update(
                tir="relative_initiation_score", log_tir="ln_relative_initiation_score"
            )
        identities = dict(zip(checker.IDENTITIES, hashes, strict=True))
        scope = digest(
            {"request": req, "identities": identities, "projection": projection}
        )[:32]
        candidates = []
        for strand, anchor in roster or []:
            idx, site = next(
                (
                    (i, s)
                    for i, s in enumerate(rec["sites"])
                    if (
                        s["tss"]["forward_base"]
                        if calc == "promoter"
                        else s["oriented_start"]
                        if strand == "+"
                        else length - 1 - s["oriented_start"]
                    )
                    == anchor
                    and (calc == "rbs" or s["strand"] == strand)
                ),
                (None, {}),
            )
            selected = site.get("selected")
            values = (
                {}
                if selected is None
                else {
                    **selected["terms"],
                    "relative_transcription_score": selected[
                        "relative_transcription_score"
                    ],
                    "log_relative_transcription_score": selected[
                        "log_relative_transcription_score"
                    ],
                }
            )
            if calc == "rbs":
                values = {
                    **(site.get("energies") or {}),
                    "tir": site.get("tir"),
                    "log_tir": site.get("log_tir"),
                }
            scalars = {
                k: {
                    "value": values.get(k),
                    "unit": u,
                    "reason": None
                    if values.get(k) is not None
                    else "value_unavailable",
                }
                for k, u in units.items()
            }
            if selected and selected["relative_transcription_score"] is None:
                scalars["relative_transcription_score"]["reason"] = selected[
                    "score_status"
                ]
            intervals = dict.fromkeys(
                checker.PROMOTER_FEATURES
                if calc == "promoter"
                else checker.RBS_FEATURES
            )
            if selected:
                intervals.update(selected["intervals"])
            if calc == "rbs":
                for k in checker.RBS_FEATURES:
                    v = site.get(k)
                    if k == "window" and v:
                        v = v["input_interval"]
                    intervals[k] = None if v is None else [v["start"], v["end"]]
                standby = site.get("standby")
                if standby:
                    for k in ("original_hairpin", "hairpin", "distal", "proximal"):
                        v = standby[k]
                        intervals["standby." + k] = (
                            None if v is None else [v["start"], v["end"]]
                        )
                    for i, hp in enumerate(standby["downstream_hairpins"]):
                        v = hp["interval"]
                        intervals[f"standby.downstream_hairpins.{i}"] = [
                            v["start"],
                            v["end"],
                        ]

            def genomic(bases, projection=projection, strand=strand):
                if projection is None:
                    return None
                d = 1 if projection["sequence_strand"] == "+" else -1
                return {
                    "projection": projection,
                    "strand": "+" if projection["sequence_strand"] == strand else "-",
                    "bases": [
                        (projection["origin"] + d * b) % projection["contig_length"]
                        for b in bases
                    ],
                }

            features = {}
            for k, v in intervals.items():
                m = None if v is None else map_interval(mapping, side, *v, strand)
                features[k] = {
                    "interval": v,
                    "strand": strand,
                    "mapping": m,
                    "genomic": None if m is None else genomic(m["source_bases"]),
                    "reason": "feature_unavailable" if v is None else None,
                }
            candidates.append(
                {
                    "id": f"pcandidate1:{scope}:{side}:{calc}:{strand}:{anchor}",
                    "strand": strand,
                    "anchor": anchor,
                    "codon_bases": None
                    if calc == "promoter"
                    else [anchor + i * (1 if strand == "+" else -1) for i in range(3)],
                    "status": site.get("status", "unavailable"),
                    "reason": site["reason"]
                    if idx is not None
                    else "prediction_candidate_unavailable",
                    "site_index": idx,
                    "scalars": scalars,
                    "features": features,
                    "genomic": genomic([anchor]),
                }
            )
        result["sides"][side] = {
            "request": req,
            "prediction": prediction,
            "prediction_sha256": digest(prediction),
            "identities": identities,
            "projection": projection,
            "roster_status": "unknown" if roster is None else "known",
            "candidates": candidates,
        }
        result["coverage"][side] = {
            "expected": None if roster is None else len(roster),
            "returned": len(rec["sites"]),
            "scored": sum(c["status"] == "ok" for c in candidates),
            "complete": roster is not None
            and len(rec["sites"]) == len(roster)
            and rec["status"] in ("ok", "no_candidate"),
        }
    mismatches = [
        k
        for k in checker.IDENTITIES
        if result["sides"]["current"]["identities"][k]
        != result["sides"]["recoded"]["identities"][k]
    ]
    current, recoded = [result["sides"][s]["candidates"] for s in checker.SIDES]
    used = set()
    visits = []
    for c in current:
        r = next(
            (
                r
                for r in recoded
                if r["strand"] == c["strand"]
                and mapping["current_to_recoded"][c["anchor"]] == r["anchor"]
            ),
            None,
        )
        interrupted = (
            r is not None
            and c["codon_bases"] is not None
            and [mapping["current_to_recoded"][b] for b in c["codon_bases"]]
            != r["codon_bases"]
        )
        if interrupted:
            visits.append((c, None, "interrupted_codon"))
        else:
            visits.append((c, r, None))
            if r:
                used.add(r["id"])
    for r in recoded:
        if r["id"] not in used:
            interrupted = any(
                c["codon_bases"] is not None
                and mapping["current_to_recoded"][c["anchor"]] == r["anchor"]
                and [mapping["current_to_recoded"][b] for b in c["codon_bases"]]
                != r["codon_bases"]
                for c in current
            )
            visits.append((None, r, "interrupted_codon" if interrupted else None))
    for c, r, reason in visits:
        status = "paired" if c and r else "unmatched"
        if status == "paired":
            reason = (
                "incompatible_identity"
                if mismatches
                else (
                    "unsuccessful_candidate"
                    if c["status"] != "ok" or r["status"] != "ok"
                    else None
                )
            )
        else:
            side, other, candidate = (
                ("current", "recoded", c) if c else ("recoded", "current", r)
            )
            if result["sides"][other]["roster_status"] == "unknown":
                status, reason = "unavailable", "counterpart_roster_unknown"
            elif reason is None:
                reason = (
                    "unmapped_" + side + "_anchor"
                    if mapping[side + "_to_" + other][candidate["anchor"]] is None
                    else ("mapped_anchor_absent_from_" + other + "_roster")
                )
        deltas = {}
        for k, scalar in (c or r)["scalars"].items():
            value, why = None, reason or "value_unavailable"
            if (
                reason is None
                and c["scalars"][k]["value"] is not None
                and r["scalars"][k]["value"] is not None
            ):
                value = r["scalars"][k]["value"] - c["scalars"][k]["value"]
                if not -sys.float_info.max <= value <= sys.float_info.max:
                    value, why = None, "nonfinite_delta"
            deltas[k] = {
                "value": value,
                "unit": scalar["unit"],
                "reason": why if value is None else None,
            }
        changes = {}
        if status == "paired":
            for k in c["features"].keys() | r["features"].keys():
                a, b = c["features"].get(k), r["features"].get(k)
                missing = not a or not b or a["mapping"] is None or b["mapping"] is None
                changes[k] = {
                    "mapped_bases_equal": None
                    if missing
                    else a["mapping"]["complete_base_mapping"]
                    and a["mapping"]["mapped_bases"] == b["mapping"]["source_bases"],
                    "reason": "feature_unavailable" if missing else None,
                }
        result["comparisons"].append(
            {
                "current_candidate_id": c["id"] if c else None,
                "recoded_candidate_id": r["id"] if r else None,
                "status": status,
                "reason": reason,
                "identity_mismatches": mismatches,
                "deltas": deltas,
                "feature_changes": changes,
            }
        )
    paired = sum(c["status"] == "paired" for c in result["comparisons"])
    comparable = sum(c["reason"] is None for c in result["comparisons"])
    complete = all(result["coverage"][s]["complete"] for s in checker.SIDES)
    result["coverage"].update(
        paired=paired,
        unmatched=len(visits) - paired,
        comparable=comparable,
        complete=complete,
        diagnostic_only=not complete,
    )
    result["status"] = (
        ("incomparable" if mismatches else "complete")
        if complete
        else ("partial" if comparable else "unavailable")
    )
    if not complete:
        result["warnings"].append(checker.PARTIAL_WARNING)
    return seal(result)


def seal(result):
    result["prediction_sha256"] = digest(
        {k: v for k, v in result.items() if k != "prediction_sha256"}
    )
    return result


def check(document, result, receipt=None):
    return checker.check_result(
        document, checker.result_bytes(result), receipt or limits()
    )


def test_frozen_builder():
    jobs, manifest = checker.build_requests()
    assert manifest["counts"] == {
        "promoter": {"jobs": 18, "positions": 4108},
        "rbs": {"jobs": 18, "positions": 17},
    }
    assert len(jobs) == 36
    assert manifest["jobs_sha256"] == digest(jobs)
    assert manifest["jobs_sha256"] == (
        "035ff8875ef9bca9c158a7b6ad7c72db15ef52fb242ce3247c7d7b8aa412ed8d"
    )
    assert digest(manifest) == (
        "40bcda46764c955b788623cf926b3b4749d948bddeef0f962066a0613663881e"
    )
    fixture = (
        Path(checker.__file__).with_name("runtime-pair-fixtures.json").read_bytes()
    )
    assert checker.build_requests(fixture) == (jobs, manifest)
    cases = json.loads(fixture)["cases"]
    for i, case in enumerate(cases):
        for job in jobs[4 * i : 4 * i + 4]:
            assert job["pair"] == case["input"]
            for side in checker.SIDES:
                req = job[side + "_request"]
                if job["calculator"] == "promoter":
                    strand = req["scan"]["strands"][0]
                    length = len(req["sequence"])
                    assert req["scan"]["range"] == (
                        [67, length - 19] if strand == "+" else [19, length - 67]
                    )
                    assert req["output"] == {
                        "states": "selected",
                        "legacy_keys": False,
                        "elements": False,
                    }
                    assert req["projection"] == case["projection"][side]
                    assert "host" not in req
                else:
                    strand = req["strand"]
                    assert req["start_positions"] == sorted(
                        r["base"]
                        if strand == "+"
                        else len(req["sequence"]) - 1 - r["base"]
                        for r in case["expected_rbs_candidates"][side]
                        if r["strand"] == strand
                    )
                    assert job["projections"] == case["projection"]
    assert any(j["current_request"].get("start_positions") == [] for j in jobs)
    jobs[0]["pair"]["pair_id"] = "changed"
    assert checker.build_requests()[0][0]["pair"]["pair_id"] == "unchanged"
    for invalid in (b"{}", "bad"):
        with pytest.raises(ValueError, match="Frozen"):
            checker.build_requests(invalid)


@pytest.mark.parametrize("calc", ["rbs", "promoter"])
@pytest.mark.parametrize("strand", ["+", "-"])
def test_success_and_zeros(calc, strand):
    doc = request(calc, strand)
    predictions = {s: native(doc, s, 0.0) for s in checker.SIDES}
    result = artificial_result(doc, predictions)
    audit = check(doc, result)
    assert audit["status"] == "complete"
    assert audit["coverage"]["comparable"] == 1
    assert audit["audit_scope"] == checker.AUDIT_SCOPE
    assert not audit["native_prediction_admitted"]
    assert all(
        v["value"] == 0.0 and v["reason"] is None
        for v in result["comparisons"][0]["deltas"].values()
    )
    assert doc == request(calc, strand)


@pytest.mark.parametrize(
    "calc,field",
    [
        ("promoter", "model"),
        ("promoter", "calibration"),
        ("rbs", "backend"),
        ("rbs", "temperature_c"),
    ],
)
def test_identity_controls(calc, field):
    doc = request(calc)
    if field == "temperature_c":
        doc["recoded_request"][field] = 38.0
    predictions = {s: native(doc, s) for s in checker.SIDES}
    if field == "calibration":
        record(predictions["recoded"], calc)[field] = {"profile": "different"}
    elif field != "temperature_c":
        predictions["recoded"][field] = {"changed": True}
    result = artificial_result(doc, predictions)
    assert check(doc, result)["status"] == "incomparable"
    assert result["comparisons"][0]["reason"] == "incompatible_identity"
    result["comparisons"][0]["identity_mismatches"] = []
    with pytest.raises(ValueError, match="Comparison"):
        check(doc, seal(result))


@pytest.mark.parametrize("calc", ["rbs", "promoter"])
@pytest.mark.parametrize("side", checker.SIDES)
@pytest.mark.parametrize(
    "status", ["failed", "unsupported", "invalid_input", "no_candidate", "missing"]
)
def test_failure_and_missing(calc, side, status):
    doc = request(calc)
    predictions = {s: native(doc, s) for s in checker.SIDES}
    rec = record(predictions[side], calc)
    rec["status"] = "failed" if status == "missing" else status
    if status == "missing":
        rec["sites"] = []
    else:
        rec["sites"][0].update(status=status, reason="artificial_failure")
        if calc == "promoter":
            rec["sites"][0]["selected"] = None
        else:
            rec["sites"][0].update(energies=None, tir=None, log_tir=None)
    result = artificial_result(doc, predictions)
    audit = check(doc, result)
    assert audit["coverage"][side]["complete"] == (status == "no_candidate")
    assert result["comparisons"][0]["reason"] == "unsuccessful_candidate"
    assert all(v["value"] is None for v in result["comparisons"][0]["deltas"].values())


def test_partial_and_unknown_versus_empty():
    doc = request()
    for side in checker.SIDES:
        doc[side + "_request"]["scan"]["positions"].append({"strand": "+", "tss": 3})
    predictions = {s: native(doc, s) for s in checker.SIDES}
    predictions["recoded"]["results"][0]["sites"].pop()
    predictions["recoded"]["results"][0]["status"] = "failed"
    assert check(doc, artificial_result(doc, predictions))["status"] == "partial"
    for unknown in (True, False):
        doc = request()
        doc["current_request"]["scan"]["positions"] = []
        predictions = {s: native(doc, s) for s in checker.SIDES}
        if unknown:
            doc["current_request"].pop("scan")
            predictions["current"]["results"][0]["status"] = "invalid_input"
        result = artificial_result(doc, predictions)
        audit = check(doc, result)
        assert audit["coverage"]["current"]["expected"] == (None if unknown else 0)
        assert result["comparisons"][0]["reason"] == (
            "counterpart_roster_unknown"
            if unknown
            else "mapped_anchor_absent_from_current_roster"
        )
    doc = request("rbs")
    for side in checker.SIDES:
        doc[side + "_request"]["start_positions"] = []
    assert check(doc, artificial_result(doc))["coverage"]["complete"]


@pytest.mark.parametrize("calc", ["promoter", "rbs"])
def test_overflow_and_optional_missing(calc):
    doc = request(calc)
    preds = {
        "current": native(doc, "current", -sys.float_info.max),
        "recoded": native(doc, "recoded", sys.float_info.max),
    }
    result = artificial_result(doc, preds)
    check(doc, result)
    assert (
        result["comparisons"][0]["deltas"]["tir" if calc == "rbs" else "total"][
            "reason"
        ]
        == "nonfinite_delta"
    )
    preds = {s: native(doc, s) for s in checker.SIDES}
    if calc == "promoter":
        record(preds["recoded"], calc)["sites"][0]["selected"].update(
            relative_transcription_score=None, score_status="underflow"
        )
    else:
        preds["recoded"]["sites"][0]["energies"].pop("dG_sliding")
    check(doc, artificial_result(doc, preds))


@pytest.mark.parametrize("calc", ["promoter", "rbs"])
@pytest.mark.parametrize("strand", ["+", "-"])
def test_projections_and_features(calc, strand):
    doc = request(calc, strand, circular=True)
    projections = {
        s: {
            "contig": s,
            "contig_length": 10,
            "origin": 2,
            "sequence_strand": "-",
            "topology": "circular",
            "origin_crossing": True,
        }
        for s in checker.SIDES
    }
    if calc == "rbs":
        doc["projections"] = projections
    else:
        for s in checker.SIDES:
            doc[s + "_request"]["projection"] = projections[s]
    preds = {s: native(doc, s) for s in checker.SIDES}
    if calc == "promoter":
        for s in checker.SIDES:
            record(preds[s], calc)["sites"][0]["selected"]["intervals"]["UP"] = [6, 10]
    else:
        for s in checker.SIDES:
            interval = {"start": 1, "end": 4, "strand": strand}
            preds[s]["sites"][0]["standby"] = {
                "original_hairpin": None,
                "hairpin": interval,
                "distal": interval,
                "proximal": interval,
                "downstream_hairpins": [{"interval": interval}],
            }
    result = artificial_result(doc, preds)
    check(doc, result)
    for mutate in ("mapping", "genomic"):
        wrong = copy.deepcopy(result)
        feature = next(
            v
            for v in wrong["sides"]["current"]["candidates"][0]["features"].values()
            if v["mapping"]
        )
        if mutate == "mapping":
            feature["mapping"]["mapped_runs"] = [[0, 8]]
        else:
            feature["genomic"]["bases"] = [999]
        with pytest.raises(ValueError, match="geometry"):
            check(doc, seal(wrong))


def test_interrupted_and_unmapped_geometry():
    doc = request("rbs")
    doc["pair"]["recoded"]["sequence"] = "ATGTGAAAAA"
    doc["pair"]["edits"] = [{"id": "e", "start": 1, "end": 1, "replacement": "TG"}]
    doc["recoded_request"]["sequence"] = "ATGTGAAAAA"
    doc["recoded_request"]["start_positions"] = [2, 0]
    result = artificial_result(doc)
    assert [r["reason"] for r in result["comparisons"]] == [
        "interrupted_codon",
        "interrupted_codon",
        "unmapped_recoded_anchor",
    ]
    assert check(doc, result)["coverage"]["unmatched"] == 3
    # Swap sides and invert the edit to exercise deleted anchors independently.
    doc["pair"]["current"]["sequence"], doc["pair"]["recoded"]["sequence"] = (
        doc["pair"]["recoded"]["sequence"],
        doc["pair"]["current"]["sequence"],
    )
    doc["pair"]["edits"] = [{"id": "e", "start": 1, "end": 3, "replacement": ""}]
    for s in checker.SIDES:
        doc[s + "_request"]["sequence"] = doc["pair"][s]["sequence"]
    doc["current_request"]["start_positions"] = [0, 2]
    doc["recoded_request"]["start_positions"] = [0]
    check(doc, artificial_result(doc))


@pytest.mark.parametrize(
    "field",
    [
        "request_sha256",
        "prediction_sha256",
        "edit_map",
        "limits",
        "settings",
        "pair_id",
        "calculator",
        "schema_version",
        "status",
        "coverage",
        "warnings",
        "comparisons",
        "extra",
    ],
)
def test_wrapper_tampering(field):
    doc = request()
    result = artificial_result(doc)
    if field == "extra":
        result[field] = 1
    elif field == "comparisons":
        result[field] *= 2
    else:
        result[field] = None
    if field != "prediction_sha256":
        seal(result)
    with pytest.raises(ValueError):
        check(doc, result)


@pytest.mark.parametrize(
    "field",
    [
        "request",
        "prediction_sha256",
        "identities",
        "projection",
        "roster_status",
        "candidates",
        "extra",
    ],
)
def test_side_tampering(field):
    doc = request()
    result = artificial_result(doc)
    result["sides"]["current"][field] = {} if field == "projection" else None
    with pytest.raises(ValueError):
        check(doc, seal(result))


@pytest.mark.parametrize(
    "field,value",
    [
        ("anchor", 2.0),
        ("strand", "-"),
        ("id", "stale"),
        ("codon_bases", [0, 1, 2]),
        ("site_index", True),
        ("status", "failed"),
        ("reason", "wrong"),
        ("scalars", {}),
        ("features", {}),
    ],
)
def test_candidate_tampering(field, value):
    doc = request()
    result = artificial_result(doc)
    result["sides"]["current"]["candidates"][0][field] = value
    with pytest.raises(ValueError, match="geometry"):
        check(doc, seal(result))


def test_strict_json_and_bytes():
    doc = request()
    result = artificial_result(doc)
    wire = checker.result_bytes(result)
    for bad in (
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1e999}',
        b"\xff",
        b"{",
        b"[" * 2000,
        wire.decode(),
    ):
        with pytest.raises(ValueError):
            checker.check_result(doc, bad, limits())
    receipt = limits()
    receipt["max_result_json_bytes"] = len(wire) + 1000
    result = artificial_result(doc, receipt=receipt)
    wire = checker.result_bytes(result)
    receipt["max_result_json_bytes"] = len(wire)
    result = artificial_result(doc, receipt=receipt)
    wire = checker.result_bytes(result)
    assert len(wire) == receipt["max_result_json_bytes"]
    checker.check_result(doc, wire, receipt)
    with pytest.raises(ValueError, match="Wire"):
        checker.check_result(doc, wire + b" ", receipt)
    receipt["max_result_json_bytes"] -= 1
    result = artificial_result(doc, receipt=receipt)
    with pytest.raises(ValueError, match="Authoritative"):
        checker.check_result(doc, checker.canonical_bytes(result), receipt)


def test_request_tree_and_limits():
    doc = request()
    for value in (float("nan"), float("inf"), (1, 2), {1: 2}):
        bad = copy.deepcopy(doc)
        bad["invalid"] = value
        with pytest.raises(ValueError):
            check(bad, {})
    bad = copy.deepcopy(doc)
    bad["invalid"] = bad
    with pytest.raises(ValueError, match="depth/node"):
        check(bad, {})
    for key in limits():
        receipt = limits()
        if key == "predictors":
            receipt[key] = {}
        else:
            receipt[key] = 0
        with pytest.raises(ValueError):
            checker.check_result(doc, b"{}", receipt)
    for key in (
        "max_json_depth",
        "max_json_nodes",
        "max_input_json_bytes",
        "max_bases_per_side",
        "max_seconds_per_side",
        "max_feature_bases",
    ):
        receipt = limits()
        receipt[key] = 1
        with pytest.raises(ValueError):
            check(doc, artificial_result(doc, receipt=receipt), receipt)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "bad"),
        ("calculator", "bad"),
        ("extra", 1),
        ("projections", {}),
        ("settings", {}),
        ("pair", {}),
    ],
)
def test_bad_requests(key, value):
    doc = request()
    doc[key] = value
    with pytest.raises(ValueError):
        check(doc, {})


@pytest.mark.parametrize("calc", ["promoter", "rbs"])
def test_binding_and_native_corruption(calc):
    doc = request(calc)
    for key, value in (
        ("sequence", "AAA"),
        ("id", "stale"),
        ("schema_version", "bad"),
        ("extra", 1),
    ):
        bad = copy.deepcopy(doc)
        bad["current_request"][key] = value
        with pytest.raises(ValueError):
            check(bad, {})
    predictions = {s: native(doc, s) for s in checker.SIDES}
    rec = record(predictions["current"], calc)
    for key, value in (("status", "unknown"), ("id", "stale"), ("sites", "bad")):
        bad = copy.deepcopy(predictions)
        record(bad["current"], calc)[key] = value
        # Build good wrapper first, then replace only the native fields/hash.
        result = artificial_result(doc, predictions)
        result["sides"]["current"]["prediction"] = bad["current"]
        result["sides"]["current"]["prediction_sha256"] = digest(bad["current"])
        with pytest.raises(ValueError):
            check(doc, seal(result))
    for value in (
        [*rec["sites"], *rec["sites"]],
        [{**rec["sites"][0], "status": "unknown"}],
    ):
        result = artificial_result(doc, predictions)
        bad = copy.deepcopy(predictions["current"])
        record(bad, calc)["sites"] = value
        result["sides"]["current"].update(prediction=bad, prediction_sha256=digest(bad))
        with pytest.raises(ValueError):
            check(doc, seal(result))


def test_range_order_and_request_caps():
    doc = request()
    for side in checker.SIDES:
        doc[side + "_request"]["scan"] = {
            "mode": "scan",
            "range": [1, 4],
            "strands": ["-", "+"],
        }
    # Distinct native values make candidate/row reordering observable.
    check(doc, artificial_result(doc))
    for strand in ("+", "-"):
        for side in checker.SIDES:
            doc[side + "_request"]["scan"]["strands"] = [strand]
        result = artificial_result(doc)
        check(doc, result)
        bad = copy.deepcopy(result)
        bad["comparisons"].reverse()
        with pytest.raises(ValueError, match="order"):
            check(doc, seal(bad))
        receipt = limits()
        receipt["max_candidates_per_side"] = 2
        with pytest.raises(ValueError, match="Candidate cap"):
            check(doc, artificial_result(doc, receipt=receipt), receipt)
    doc["pair"]["edits"] = [
        {"id": "e1", "start": 0, "end": 1, "replacement": "A"},
        {"id": "e2", "start": 1, "end": 2, "replacement": "T"},
    ]
    receipt = limits()
    receipt["max_edits"] = 1
    with pytest.raises(ValueError, match="Edit cap"):
        check(doc, {}, receipt)


@pytest.mark.parametrize("circular", [False, True])
def test_empty_terminal_feature(circular):
    doc = request(circular=circular)
    result = artificial_result(doc)
    for side in checker.SIDES:
        value = result["sides"][side]
        record(value["prediction"], "promoter")["sites"][0]["selected"]["intervals"][
            "itr"
        ] = [8, 8]
        feature = value["candidates"][0]["features"]["itr"]
        feature.update(
            interval=[8, 8],
            mapping={
                "source_bases": [],
                "mapped_bases": [],
                "mapped_runs": [],
                "unmatched_bases": 0,
                "complete_base_mapping": True,
                "contiguous_target_path": True,
            },
        )
        value["prediction_sha256"] = digest(value["prediction"])
    check(doc, seal(result))
    value = result["sides"]["current"]
    record(value["prediction"], "promoter")["sites"][0]["selected"]["intervals"][
        "itr"
    ] = [8, 8.0]
    value["prediction_sha256"] = digest(value["prediction"])
    with pytest.raises(ValueError):
        check(doc, seal(result))


@pytest.mark.parametrize("calc", ["rbs", "promoter"])
def test_missing_native_fields_and_nonfinite_values(calc):
    doc = request(calc)
    result = artificial_result(doc)
    side = result["sides"]["current"]
    prediction = side["prediction"]
    prediction.pop("model")
    side["prediction_sha256"] = digest(prediction)
    with pytest.raises(ValueError):
        check(doc, seal(result))
    bad = request(calc)
    bad["current_request"]["sequence"] = 12
    with pytest.raises(ValueError, match="Malformed"):
        check(bad, {})
    for number in (True, "1", 10**400):
        result = artificial_result(doc)
        value = result["sides"]["current"]
        site = record(value["prediction"], calc)["sites"][0]
        if calc == "promoter":
            site["selected"]["terms"]["total"] = number
        else:
            site["energies"]["dG_total"] = number
        value["prediction_sha256"] = digest(value["prediction"])
        with pytest.raises(ValueError):
            check(doc, seal(result))


@pytest.mark.parametrize(
    "scan",
    [
        None,
        {},
        {"mode": "positions", "positions": None},
        {"mode": "positions", "positions": [{"strand": "?", "tss": 1}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": True}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": 1}] * 2},
        {"mode": "bad", "range": [0, 2], "strands": ["+"]},
        {"mode": "scan", "range": [0], "strands": ["+"]},
        {"mode": "scan", "range": [2, 1], "strands": ["+"]},
        {"mode": "scan", "range": [0, 2], "strands": ["+", "+"]},
        {"mode": "scan", "range": [0, 2], "strands": ["?"]},
    ],
)
def test_unknown_scan_syntax(scan):
    # The original request is retained as diagnostic evidence, never an empty
    # candidate universe. No scoring/native validation is implied by this test.
    doc = request()
    doc["current_request"]["scan"]["positions"] = []
    preds = {s: native(doc, s) for s in checker.SIDES}
    doc["current_request"]["scan"] = scan
    rec = record(preds["current"], "promoter")
    rec["status"] = "invalid_input"
    # Assemble with a recognized unknown marker, then restore the actual raw scan.
    original = doc["current_request"]["scan"]
    doc["current_request"]["scan"] = {"mode": "invalid"}
    result = artificial_result(doc, preds)
    doc["current_request"]["scan"] = original
    result["request_sha256"] = digest(doc)
    assert check(doc, seal(result))["coverage"]["current"]["expected"] is None


def test_explicit_rbs_validation_and_failure_raw_identity():
    doc = request("rbs")
    for starts in (None, "scan"):
        bad = copy.deepcopy(doc)
        bad["current_request"]["start_positions"] = starts
        with pytest.raises(ValueError, match="explicit starts"):
            check(bad, {})
    for profile in (None, "unknown"):
        bad = copy.deepcopy(doc)
        bad["settings"]["profile"] = profile
        with pytest.raises(ValueError, match="profile"):
            check(bad, {})
    # Invalid scientific fields are raw diagnostic identity values, not coerced.
    doc["current_request"].update(anti_sd=None, temperature_c="bad")
    preds = {s: native(doc, s) for s in checker.SIDES}
    preds["current"].update(status="invalid_input", sites=[])
    result = artificial_result(request("rbs"))
    value = result["sides"]["current"]
    value["request"] = doc["current_request"]
    value["prediction"] = preds["current"]
    value["prediction_sha256"] = digest(preds["current"])
    value["identities"]["settings_sha256"] = digest(
        {"anti_sd": None, "temperature_c": "bad"}
    )
    scope = digest(
        {
            "request": value["request"],
            "identities": value["identities"],
            "projection": None,
        }
    )[:32]
    old = value["candidates"][0]["id"]
    new = f"pcandidate1:{scope}:current:rbs:+:0"
    candidate = value["candidates"][0]
    candidate.update(
        id=new,
        status="unavailable",
        reason="prediction_candidate_unavailable",
        site_index=None,
    )
    for scalar in candidate["scalars"].values():
        scalar.update(value=None, reason="value_unavailable")
    for feature in candidate["features"].values():
        feature.update(
            interval=None, mapping=None, genomic=None, reason="feature_unavailable"
        )
    row = result["comparisons"][0]
    assert row["current_candidate_id"] == old
    row.update(
        current_candidate_id=new,
        reason="incompatible_identity",
        identity_mismatches=["settings_sha256"],
    )
    for delta in row["deltas"].values():
        delta.update(value=None, reason="incompatible_identity")
    row["feature_changes"] = {
        k: {"mapped_bases_equal": None, "reason": "feature_unavailable"}
        for k in candidate["features"]
    }
    result["coverage"]["current"].update(returned=0, scored=0, complete=False)
    result["coverage"].update(comparable=0, complete=False, diagnostic_only=True)
    result.update(
        request_sha256=digest(doc),
        status="unavailable",
        warnings=[checker.WARNING, checker.PARTIAL_WARNING],
    )
    assert check(doc, seal(result))["status"] == "unavailable"


def test_all_frozen_jobs_with_artificial_public_fields():
    jobs, _ = checker.build_requests()
    for job in jobs:
        audit = check(job, artificial_result(job))
        assert audit["status"] == "complete"
        assert audit["native_prediction_admitted"] is False


def test_input_byte_boundary_and_numeric_delta():
    doc = request()
    receipt = limits()
    receipt["max_input_json_bytes"] = len(checker.canonical_bytes(doc))
    preds = {
        "current": native(doc, "current", 2.0),
        "recoded": native(doc, "recoded", 5.5),
    }
    result = artificial_result(doc, preds, receipt)
    assert check(doc, result, receipt)["status"] == "complete"
    assert result["comparisons"][0]["deltas"]["total"] == {
        "value": 3.5,
        "unit": "source_dG_units",
        "reason": None,
    }
    receipt["max_input_json_bytes"] -= 1
    with pytest.raises(ValueError, match="Input byte cap"):
        check(doc, result, receipt)


@pytest.mark.parametrize("calc", ["rbs", "promoter"])
def test_native_unknown_fields(calc):
    doc = request(calc)
    for location in ("record", "site", "nested"):
        result = artificial_result(doc)
        value = result["sides"]["current"]
        rec = record(value["prediction"], calc)
        if location == "record":
            rec["invented"] = 1
        elif location == "site":
            rec["sites"][0]["invented"] = 1
        elif calc == "promoter":
            rec["sites"][0]["selected"]["terms"]["invented"] = 1
        else:
            rec["schema_version"] = "unknown"
        value["prediction_sha256"] = digest(value["prediction"])
        with pytest.raises(ValueError):
            check(doc, seal(result))


@pytest.mark.parametrize("side", checker.SIDES)
@pytest.mark.parametrize(
    "starts,strand", [([-1], "+"), ([6], "+"), ([0, 0], "+"), ([True], "+"), ([0], "?")]
)
def test_unknown_rbs_roster_diagnostics(side, starts, strand):
    doc = request("rbs", circular=True)
    preds = {s: native(doc, s) for s in checker.SIDES}
    doc[side + "_request"].update(start_positions=starts, strand=strand)
    preds[side].update(status="invalid_input", sites=[])
    result = artificial_result(doc, preds)
    audit = check(doc, result)
    assert audit["coverage"][side]["expected"] is None
    assert result["comparisons"][0]["reason"] == "counterpart_roster_unknown"


def test_identity_mismatch_order_on_unpaired_rows():
    doc = request("rbs")
    doc["current_request"]["start_positions"] = []
    doc["recoded_request"].update(host="artificial", temperature_c=40.0)
    preds = {s: native(doc, s) for s in checker.SIDES}
    preds["recoded"]["model"] = {"id": "different"}
    preds["recoded"]["backend"] = {"kind": "different"}
    result = artificial_result(doc, preds)
    assert check(doc, result)["identity_mismatches"] == list(checker.IDENTITIES)
    assert result["comparisons"][0]["identity_mismatches"] == list(checker.IDENTITIES)
    result["comparisons"][0]["identity_mismatches"].reverse()
    with pytest.raises(ValueError, match="Comparison"):
        check(doc, seal(result))


@pytest.mark.parametrize("calc", ["rbs", "promoter"])
@pytest.mark.parametrize(
    "interval", [[-1, 2], [0, 9], [4, 2], [0, True], [0, 1.0], [0]]
)
def test_native_feature_interval_rejections(calc, interval):
    doc = request(calc)
    result = artificial_result(doc)
    value = result["sides"]["current"]
    site = record(value["prediction"], calc)["sites"][0]
    if calc == "promoter":
        site["selected"]["intervals"]["itr"] = interval
    else:
        site["binding_interval"] = {
            "start": interval[0],
            "end": interval[-1],
            "strand": "+",
        }
    value["prediction_sha256"] = digest(value["prediction"])
    with pytest.raises(ValueError):
        check(doc, seal(result))


def test_native_codon_and_feature_strands_rejected():
    doc = request("rbs", "-")
    for interval in (
        {"start": 4, "end": 7, "strand": "-"},
        {"start": 5, "end": 8, "strand": "+"},
    ):
        result = artificial_result(doc)
        value = result["sides"]["current"]
        value["prediction"]["sites"][0]["start_codon"] = interval
        value["prediction_sha256"] = digest(value["prediction"])
        with pytest.raises(ValueError):
            check(doc, seal(result))


def test_invalid_projection_on_empty_rbs_roster():
    doc = request("rbs")
    for s in checker.SIDES:
        doc[s + "_request"]["start_positions"] = []
    p = {
        "contig": "bad",
        "contig_length": 8,
        "origin": 7,
        "sequence_strand": "+",
        "topology": "linear",
        "origin_crossing": False,
    }
    doc["projections"] = {"current": p, "recoded": None}
    with pytest.raises(ValueError):
        check(doc, artificial_result(doc))


def test_source_feature_budget_before_map_allocation():
    doc = request()
    for side in checker.SIDES:
        doc["pair"][side]["sequence"] = "A" * 100
        doc[side + "_request"]["sequence"] = "A" * 100
    preds = {s: native(doc, s) for s in checker.SIDES}
    for side in checker.SIDES:
        rec = record(preds[side], "promoter")
        rec["sites"][0]["selected"]["intervals"] = dict.fromkeys(
            checker.PROMOTER_FEATURES, [0, 100]
        )
    receipt = limits()
    receipt["max_feature_bases"] = 200
    result = artificial_result(doc, preds, receipt)
    with pytest.raises(ValueError, match="Actual source feature"):
        check(doc, result, receipt)


def rebind_raw_request(result, document, side):
    """Rebind raw identity while preserving independently constructed native rows."""
    value = result["sides"][side]
    value["request"] = copy.deepcopy(document[side + "_request"])
    scope = digest({k: value[k] for k in ("request", "identities", "projection")})[:32]
    replacements = {}
    for candidate in value["candidates"]:
        name = (
            f"pcandidate1:{scope}:{side}:{document['calculator']}:"
            f"{candidate['strand']}:{candidate['anchor']}"
        )
        replacements[candidate["id"]] = name
        candidate["id"] = name
    for row in result["comparisons"]:
        key = side + "_candidate_id"
        row[key] = replacements.get(row[key], row[key])
    result["request_sha256"] = digest(document)
    return seal(result)


@pytest.mark.parametrize(
    "anti_sd", ["accu ccuuu", " \taccu\nccuuu\r\v\f", "acct ccttt"]
)
def test_effective_anti_sd_whitespace_normalization(anti_sd):
    doc = request("rbs")
    result = artificial_result(doc)
    expected = digest({"anti_sd": "ACCUCCUUU", "temperature_c": 37.0})
    doc["current_request"]["anti_sd"] = anti_sd
    rebind_raw_request(result, doc, "current")
    original = copy.deepcopy(doc)
    audit = check(doc, result)
    assert audit["identity_mismatches"] == []
    assert result["sides"]["current"]["identities"]["settings_sha256"] == expected
    assert doc == original
    # Hashing whitespace-bearing text is specifically forbidden, even when all
    # scope and whole-result hashes are recomputed to make it self-consistent.
    result["sides"]["current"]["identities"]["settings_sha256"] = digest(
        {
            "anti_sd": anti_sd.upper().replace("T", "U"),
            "temperature_c": 37.0,
        }
    )
    rebind_raw_request(result, doc, "current")
    with pytest.raises(ValueError, match="Scientific identity"):
        check(doc, result)


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("integral_coordinates", [False, True])
def test_promoter_projection_resolves_default_without_rewriting_request(
    strand, integral_coordinates
):
    doc = request("promoter", strand)
    projection = {
        "contig": "artificial",
        "contig_length": 20,
        "origin": 2,
        "sequence_strand": "+",
        "topology": "linear",
        "origin_crossing": False,
    }
    for side in checker.SIDES:
        doc[side + "_request"]["projection"] = dict(projection)
    result = copy.deepcopy(artificial_result(doc))
    for side in checker.SIDES:
        raw = doc[side + "_request"]["projection"]
        del raw["sequence_strand"]
        if integral_coordinates:
            raw.update(origin=2.0, contig_length=20.0)
        rebind_raw_request(result, doc, side)
    original = copy.deepcopy(doc)
    assert check(doc, result)["status"] == "complete"
    assert result["sides"]["current"]["projection"] == projection
    assert "sequence_strand" not in result["sides"]["current"]["request"]["projection"]
    assert doc == original
    doc["current_request"]["projection"]["sequence_strand"] = "-"
    rebind_raw_request(result, doc, "current")
    with pytest.raises(ValueError, match="projection disagrees"):
        check(doc, result)


@pytest.mark.parametrize("side", checker.SIDES)
@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("start", [0.0, -0.0, 2.0])
def test_rbs_integral_float_starts_retain_integer_geometry(side, strand, start):
    doc = request("rbs", strand)
    for s in checker.SIDES:
        doc[s + "_request"]["start_positions"] = [int(start)]
    result = artificial_result(doc)
    original_scope = result["sides"][side]["candidates"][0]["id"]
    doc[side + "_request"]["start_positions"] = [start]
    rebind_raw_request(result, doc, side)
    original = copy.deepcopy(doc)
    audit = check(doc, result)
    assert audit["coverage"][side]["expected"] == 1
    assert audit["coverage"]["paired"] == 1
    candidate = result["sides"][side]["candidates"][0]
    assert type(candidate["anchor"]) is int
    assert all(type(b) is int for b in candidate["codon_bases"])
    assert candidate["id"] != original_scope
    assert doc == original


@pytest.mark.parametrize(
    "anti_sd",
    [None, 42, False, "", "ACCUCCUU", "ACCUCCUUUU", "ACCNCCUUU", "accu\x00ccuuu"],
)
def test_invalid_anti_sd_preserves_raw_diagnostic_identity(anti_sd):
    doc = request("rbs")
    preds = {s: native(doc, s) for s in checker.SIDES}
    for value in preds.values():
        value.update(status="invalid_input", sites=[])
    result = artificial_result(doc, preds)
    raw_identity = digest({"anti_sd": anti_sd, "temperature_c": 37.0})
    for side in checker.SIDES:
        doc[side + "_request"]["anti_sd"] = anti_sd
        result["sides"][side]["identities"]["settings_sha256"] = raw_identity
        rebind_raw_request(result, doc, side)
    assert check(doc, result)["status"] == "unavailable"
    # The same malformed scientific input cannot acquire a successful audit by
    # retaining an otherwise successful artificial native result.
    success_doc = request("rbs")
    success = artificial_result(success_doc)
    success_doc["current_request"]["anti_sd"] = anti_sd
    rebind_raw_request(success, success_doc, "current")
    with pytest.raises(ValueError):
        check(success_doc, success)


@pytest.mark.parametrize(
    "starts", [[False], ["0"], [None], [0.5], [-0.5], [-1.0], [6.0], [0, 0.0], [1e20]]
)
def test_rbs_bad_numeric_starts_are_diagnostic_unknown(starts):
    doc = request("rbs")
    preds = {s: native(doc, s) for s in checker.SIDES}
    preds["current"].update(status="invalid_input", sites=[])
    doc["current_request"]["start_positions"] = starts
    result = artificial_result(doc, preds)
    audit = check(doc, result)
    assert audit["coverage"]["current"]["expected"] is None
    assert result["comparisons"][0]["reason"] == "counterpart_roster_unknown"
    success_doc = request("rbs")
    success = artificial_result(success_doc)
    success_doc["current_request"]["start_positions"] = starts
    rebind_raw_request(success, success_doc, "current")
    with pytest.raises(ValueError, match="Roster status"):
        check(success_doc, success)


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_rbs_start_rejected(number):
    doc = request("rbs")
    doc["current_request"]["start_positions"] = [number]
    with pytest.raises(ValueError, match="finite JSON"):
        checker.check_result(doc, b"{}", limits())


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", False),
        ("origin", 2.5),
        ("origin", "2"),
        ("contig_length", True),
        ("contig_length", 20.5),
    ],
)
def test_promoter_projection_rejects_bad_input_numbers(field, value):
    doc = request()
    doc["current_request"]["projection"] = {
        "contig": "artificial",
        "contig_length": 20,
        "origin": 2,
        "sequence_strand": "+",
        "topology": "linear",
        "origin_crossing": False,
    }
    result = copy.deepcopy(artificial_result(doc))
    doc["current_request"]["projection"][field] = value
    rebind_raw_request(result, doc, "current")
    with pytest.raises(ValueError, match="integral input"):
        check(doc, result)

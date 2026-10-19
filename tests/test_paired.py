"""Paired public predictors: exact accounting, native scores and refusals."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from regsite import paired as p
from regsite import promoter_io
from regsite.backend import RnaStructure
from regsite.edits import build_edit_map
from regsite.structures import BackendError


def document(calculator="promoter", current=None, edits=None):
    current = current or "A" * 200
    edits = edits or []
    cursor = 0
    chunks = []
    for edit in edits:
        chunks.extend([current[cursor : edit["start"]], edit["replacement"]])
        cursor = edit["end"]
    recoded = "".join(chunks) + current[cursor:]
    pair = {
        "schema_version": "paired-edit-input-1",
        "pair_id": "synthetic",
        "topology": "linear",
        "current": {"id": "current", "sequence": current},
        "recoded": {"id": "recoded", "sequence": recoded},
        "edits": edits,
    }
    requests = {}
    for side in p.SIDES:
        request = dict(pair[side])
        if calculator == "promoter":
            request.update(
                calibration="in_vitro",
                scan={
                    "mode": "positions",
                    "positions": [
                        {"strand": "+", "tss": 100},
                        {"strand": "-", "tss": 100},
                    ],
                },
            )
        else:
            request.update(anti_sd="ACCUCCUUA", strand="+", host=None, temperature_c=37)
        requests[side + "_request"] = request
    settings: dict = {"seconds_per_side": 30}
    if calculator == "rbs":
        settings["profile"] = "historical"
    return {
        "schema_version": "paired-regulatory-request-1",
        "pair": pair,
        "calculator": calculator,
        **requests,
        "settings": settings,
    }


def edit(start, end, replacement):
    return {"id": "edit", "start": start, "end": end, "replacement": replacement}


def projection(length=200, strand="+", origin=10, circular=False):
    return {
        "contig": "synthetic-contig",
        "origin": origin,
        "contig_length": 1000,
        "sequence_strand": strand,
        "topology": "circular" if circular else "linear",
        "origin_crossing": origin + length > 1000
        if strand == "+"
        else origin - length + 1 < 0,
    }


@pytest.fixture
def failed_backend(monkeypatch):
    backend = RnaStructure(Path("."), {"name": "failure-injection-only"})

    def fail(*args):
        raise BackendError("injected backend session failure")

    monkeypatch.setattr(RnaStructure, "session", fail)
    return backend


def test_real_promoter_controls_and_hashes():
    request = document()
    original = copy.deepcopy(request)
    result = p.predict_pair(request)
    assert request == original
    assert result == p.predict_pair(request)
    assert result["status"] == "complete"
    assert result["coverage"]["comparable"] == 2
    assert all(
        d["value"] == 0 for row in result["comparisons"] for d in row["deltas"].values()
    )
    assert (
        result["request_sha256"]
        == hashlib.sha256(p.canonical_bytes(request)).hexdigest()
    )
    unhashed = {k: v for k, v in result.items() if k != "prediction_sha256"}
    assert (
        result["prediction_sha256"]
        == hashlib.sha256(p.canonical_bytes(unhashed)).hexdigest()
    )
    assert p.result_bytes(result).endswith(b"\n")
    for side in p.SIDES:
        value = result["sides"][side]
        assert value["prediction_sha256"] == p._hash(value["prediction"])
        assert all(len(h) == 64 for h in value["identities"].values())
        assert value["prediction"]["model"]["claims"]["physical_free_energy"] is False
    request["settings"]["seconds_per_side"] = 1
    assert result["settings"]["seconds_per_side"] == 30


def test_real_changed_promoter_and_independent_projections():
    request = document(current="ACGT" * 50, edits=[edit(70, 71, "A")])
    request["pair"]["topology"] = "circular"
    request["current_request"]["projection"] = projection(origin=980, circular=True)
    request["recoded_request"]["projection"] = projection(
        strand="-", origin=10, circular=True
    )
    result = p.predict_pair(request)
    assert result["status"] == "complete"
    assert any(row["deltas"]["total"]["value"] != 0 for row in result["comparisons"])
    for side in p.SIDES:
        for candidate in result["sides"][side]["candidates"]:
            for feature in candidate["features"].values():
                mapping = feature["mapping"]
                assert mapping["mapped_bases"] == mapping["source_bases"]
                pr = request[side + "_request"]["projection"]
                step = 1 if pr["sequence_strand"] == "+" else -1
                assert feature["genomic"]["bases"] == [
                    (pr["origin"] + step * b) % 1000 for b in mapping["source_bases"]
                ]
    assert (
        result["sides"]["current"]["identities"]
        == result["sides"]["recoded"]["identities"]
    )


def test_real_promoter_indel_feature_splits_and_missing_bases():
    for operation in (edit(80, 80, "CG"), edit(80, 82, "")):
        request = document(edits=[operation])
        request["recoded_request"]["scan"]["positions"] = [
            {
                "strand": "+",
                "tss": 100
                + len(operation["replacement"])
                - (operation["end"] - operation["start"]),
            }
        ]
        request["current_request"]["scan"]["positions"] = [{"strand": "+", "tss": 100}]
        result = p.predict_pair(request)
        row = result["comparisons"][0]
        assert row["status"] == "paired"
        mapped = result["sides"]["current"]["candidates"][0]["features"]["hex10"][
            "mapping"
        ]
        if operation["replacement"]:
            assert mapped["complete_base_mapping"]
            # Probe an interval that necessarily straddles the insertion.
            probe = build_edit_map(request["pair"]).map_interval("current", 79, 83, "+")
            assert probe["mapped_runs"] == [[79, 80], [82, 85]]
        else:
            probe = build_edit_map(request["pair"]).map_interval("current", 79, 83, "-")
            assert probe["mapped_bases"] == [80, None, None, 79]
            assert not probe["complete_base_mapping"]


@pytest.mark.parametrize("side", p.SIDES)
def test_unknown_roster_never_asserts_opposite_absence(side):
    request = document()
    request[side + "_request"]["scan"] = {"mode": "bad"}
    result = p.predict_pair(request)
    assert result["status"] == "unavailable"
    assert result["sides"][side]["roster_status"] == "unknown"
    assert result["coverage"][side]["expected"] is None
    assert all(
        row["status"] == "unavailable" and row["reason"] == "counterpart_roster_unknown"
        for row in result["comparisons"]
    )


def test_empty_rosters_and_no_context_are_explicit():
    request = document()
    for side in p.SIDES:
        request[side + "_request"]["scan"]["positions"] = []
    result = p.predict_pair(request)
    assert result["status"] == "complete" and result["comparisons"] == []
    assert result["coverage"]["current"]["expected"] == 0
    request["current_request"]["scan"]["positions"] = [{"strand": "+", "tss": 0}]
    result = p.predict_pair(request)
    assert (
        result["comparisons"][0]["reason"] == "mapped_anchor_absent_from_recoded_roster"
    )
    request["recoded_request"]["scan"]["positions"] = [{"strand": "+", "tss": 0}]
    result = p.predict_pair(request)
    assert result["comparisons"][0]["reason"] == "unsuccessful_candidate"
    assert result["comparisons"][0]["deltas"]["total"]["value"] is None


def test_calibration_mismatch_and_stale_model():
    request = document()
    request["recoded_request"]["calibration"] = "ecoli_mg1655"
    result = p.predict_pair(request)
    assert result["status"] == "incomparable"
    assert result["comparisons"][0]["identity_mismatches"] == ["calibration_sha256"]
    assert all(
        v["reason"] == "incompatible_identity"
        for v in result["comparisons"][0]["deltas"].values()
    )
    request["recoded_request"]["model"] = {
        "id": "stale",
        "parameter_json_sha256": "0" * 64,
    }
    result = p.predict_pair(request)
    assert (
        result["sides"]["recoded"]["prediction"]["results"][0]["status"]
        == "unsupported"
    )
    assert result["coverage"]["recoded"]["expected"] == 2
    assert result["sides"]["recoded"]["candidates"][0]["status"] == "unavailable"


@pytest.mark.parametrize("side", p.SIDES)
def test_partial_promoter_failure_preserves_diagnostic_success(monkeypatch, side):
    original = promoter_io.predict_batch

    def failed(value, **kwargs):
        result = original(value, **kwargs)
        if value["id"] == side:
            record = result["results"][0]
            record["status"] = "failed"
            record["sites"][1].update(
                status="failed", reason="injected_failure", selected=None
            )
        return result

    monkeypatch.setattr(promoter_io, "predict_batch", failed)
    result = p.predict_pair(document())
    assert result["status"] == "partial"
    assert result["coverage"]["comparable"] == 1
    assert result["coverage"]["diagnostic_only"]
    assert result["comparisons"][0]["deltas"]["total"]["value"] == 0
    assert result["comparisons"][1]["reason"] == "unsuccessful_candidate"


@pytest.mark.parametrize("side", p.SIDES)
def test_rbs_backend_failure_retains_complete_rosters(failed_backend, side):
    request = document("rbs", current="AAAGGAGGAAAAAAATG" + "A" * 35)
    request[side + "_request"]["temperature_c"] = -1
    result = p.predict_pair(request, failed_backend)
    assert result["status"] == "unavailable"
    assert all(result["coverage"][s]["expected"] == 1 for s in p.SIDES)
    assert all(
        row["reason"] == "incompatible_identity" for row in result["comparisons"]
    )
    assert result["sides"][side]["prediction"]["status"] == "invalid_input"


@pytest.mark.parametrize("side", p.SIDES)
def test_rbs_unknown_roster_and_empty(failed_backend, side):
    request = document("rbs", current="A" * 20)
    request[side + "_request"]["strand"] = "?"
    result = p.predict_pair(request, failed_backend)
    assert result["sides"][side]["roster_status"] == "unknown"
    other = "recoded" if side == "current" else "current"
    assert result["coverage"][other]["expected"] == 0
    request[other + "_request"]["start_positions"] = [2]
    result = p.predict_pair(request, failed_backend)
    assert result["comparisons"][0]["reason"] == "counterpart_roster_unknown"


@pytest.mark.parametrize("strand", ["+", "-"])
def test_rbs_interrupted_codon_keeps_both_rows(failed_backend, strand):
    request = document("rbs", current="A" * 20, edits=[edit(5, 5, "C")])
    for side in p.SIDES:
        request[side + "_request"]["strand"] = strand
        request[side + "_request"]["start_positions"] = [
            4
            if strand == "+"
            else len(request["pair"][side]["sequence"])
            - 1
            - (6 if side == "current" else 7)
        ]
    result = p.predict_pair(request, failed_backend)
    assert len(result["comparisons"]) == 2
    assert all(row["reason"] == "interrupted_codon" for row in result["comparisons"])


@pytest.mark.parametrize(
    "operation,source,target,reasons",
    [
        (
            edit(5, 6, ""),
            5,
            5,
            {"unmapped_current_anchor", "mapped_anchor_absent_from_current_roster"},
        ),
        (
            edit(5, 5, "C"),
            6,
            5,
            {"mapped_anchor_absent_from_recoded_roster", "unmapped_recoded_anchor"},
        ),
    ],
)
def test_unmatched_coordinate_accounting(
    failed_backend, operation, source, target, reasons
):
    request = document("rbs", current="A" * 20, edits=[operation])
    request["current_request"]["start_positions"] = [source]
    request["recoded_request"]["start_positions"] = [target]
    result = p.predict_pair(request, failed_backend)
    assert {r["reason"] for r in result["comparisons"]} == reasons


@pytest.mark.parametrize("bad", [None, [], True, 1, "text"])
def test_outer_type_errors(bad):
    with pytest.raises(p.PairError, match="request: expected fields"):
        p.predict_pair(bad)


@pytest.mark.parametrize(
    "key,value,error",
    [
        ("schema_version", "wrong", "schema_version: expected"),
        ("calculator", "wrong", "calculator: expected"),
        ("settings", {}, "settings: expected fields"),
        ("settings", {"seconds_per_side": False}, "seconds_per_side: expected"),
        ("settings", {"seconds_per_side": 0}, "seconds_per_side: expected"),
        ("settings", {"seconds_per_side": 121}, "seconds_per_side: expected"),
        ("projections", {}, "projections: only supported"),
        ("current_request", {}, "current_request: missing"),
    ],
)
def test_targeted_setup_errors(key, value, error):
    request = document()
    request[key] = value
    with pytest.raises(p.PairError, match=error):
        p.predict_pair(request)


@pytest.mark.parametrize(
    "value,error",
    [
        ({1: "value"}, "object keys must be strings"),
        ({"x": (1, 2)}, "expected JSON values"),
        ({"x": float("nan")}, "expected finite JSON"),
        ({"x": float("inf")}, "expected finite JSON"),
    ],
)
def test_strict_json(value, error):
    with pytest.raises(p.PairError, match=error):
        p.predict_pair(value)


def test_json_depth_cycle_nodes_and_bytes(monkeypatch):
    cyclic: list = []
    cyclic.append(cyclic)
    with pytest.raises(p.PairError, match="depth/node limit"):
        p.predict_pair(cyclic)
    monkeypatch.setitem(p.LIMITS, "max_json_nodes", 1)
    with pytest.raises(p.PairError, match="depth/node limit"):
        p.predict_pair([1])
    monkeypatch.setitem(p.LIMITS, "max_json_nodes", 100_000)
    request = document()
    size = len(p.canonical_bytes(request))
    monkeypatch.setitem(p.LIMITS, "max_input_json_bytes", size)
    assert p.predict_pair(request)["status"] == "complete"
    monkeypatch.setitem(p.LIMITS, "max_input_json_bytes", size - 1)
    with pytest.raises(p.PairError, match="max_input_json_bytes"):
        p.predict_pair(request)


@pytest.mark.parametrize("side", p.SIDES)
def test_exact_sequence_identity_binding(side):
    request = document()
    request[side + "_request"]["id"] = "stale"
    with pytest.raises(p.PairError, match=side + "_request.id: does not match"):
        p.predict_pair(request)
    request[side + "_request"]["id"] = side
    request[side + "_request"]["sequence"] = "C" * 200
    with pytest.raises(p.PairError, match=side + "_request.sequence: does not match"):
        p.predict_pair(request)
    request[side + "_request"]["sequence"] = "N"
    with pytest.raises(
        p.PairError, match=side + "_request.sequence: sequence accepts only"
    ):
        p.predict_pair(request)
    request[side + "_request"]["sequence"] = " a " * 200
    assert p.predict_pair(request)["status"] == "complete"


def test_bad_geometry_and_resource_preflight(monkeypatch, failed_backend):
    request = document()
    request["pair"]["recoded"]["sequence"] = "C" * 200
    with pytest.raises(p.PairError, match="edits: do not reproduce"):
        p.predict_pair(request)
    request = document(edits=[edit(5, 6, "C")])
    monkeypatch.setitem(p.LIMITS, "max_edits", 0)
    with pytest.raises(p.PairError, match="max_edits"):
        p.predict_pair(request)
    request = document()
    monkeypatch.setitem(p.LIMITS, "max_candidates_per_side", 1)
    with pytest.raises(p.PairError, match="current: max_candidates_per_side"):
        p.predict_pair(request)
    monkeypatch.setitem(p.LIMITS, "max_candidates_per_side", 512)
    monkeypatch.setitem(p.LIMITS, "max_feature_bases", 399)
    with pytest.raises(p.PairError, match="max_feature_bases"):
        p.predict_pair(request)
    request = document("rbs")
    with pytest.raises(p.PairError, match="requires a verified"):
        p.predict_pair(request)
    request["settings"]["profile"] = "typo"
    with pytest.raises(p.PairError, match="unknown RBS profile"):
        p.predict_pair(request, failed_backend)
    request["settings"]["profile"] = "historical"
    request["projections"] = {"current": None}
    with pytest.raises(p.PairError, match="projections: expected fields"):
        p.predict_pair(request, failed_backend)
    request["projections"]["recoded"] = {}
    with pytest.raises(p.PairError, match="projections.recoded: expected fields"):
        p.predict_pair(request, failed_backend)


@pytest.mark.parametrize(
    "starts", ["bad", [True], [0.5], [-1], [18], [2, 2], [0] * 1001, [[0]]]
)
def test_bad_rbs_rosters_are_unknown(failed_backend, starts):
    request = document("rbs", current="A" * 20)
    request["current_request"]["start_positions"] = starts
    result = p.predict_pair(request, failed_backend)
    assert result["sides"]["current"]["roster_status"] == "unknown"
    assert result["sides"]["current"]["prediction"]["status"] == "invalid_input"


def test_authoritative_output_cap(monkeypatch):
    result = p.predict_pair(document())
    # Changing the visible limit changes output byte length; solve at its size.
    cap = len(p.result_bytes(result))
    for _ in range(3):
        monkeypatch.setitem(p.LIMITS, "max_result_json_bytes", cap)
        result = p.predict_pair(document())
        cap = len(p.result_bytes(result))
    monkeypatch.setitem(p.LIMITS, "max_result_json_bytes", cap - 1)
    with pytest.raises(p.PairError, match="output: max_result_json_bytes"):
        p.predict_pair(document())


@pytest.mark.parametrize(
    "a,b",
    [
        (None, p._scalar(1, "u")),
        (p._scalar(1, "u"), None),
        (p._scalar(None, "u"), p._scalar(1, "u")),
        (p._scalar(1, "u"), p._scalar(None, "u")),
    ],
)
def test_scalar_missingness(a, b):
    assert p._delta(a, b, None) == p._scalar(None, "u", "value_unavailable")


def test_finite_overflow_delta_and_units():
    assert p._delta(p._scalar(-1e308, "u"), p._scalar(1e308, "u"), None) == p._scalar(
        None, "u", "nonfinite_delta"
    )
    assert p._delta(p._scalar(1, "u"), p._scalar(1, "u"), None) == p._scalar(0, "u")


def test_candidate_prediction_contract_guard(monkeypatch):
    original = promoter_io.predict_batch
    for mode in ("duplicate", "unexpected", "unknown"):

        def corrupt(value, mode=mode, **kwargs):
            result = original(value, **kwargs)
            sites = result["results"][0]["sites"]
            if mode == "duplicate":
                sites.append(copy.deepcopy(sites[0]))
            elif mode == "unexpected":
                sites[0]["tss"]["forward_base"] = 99
            return result

        monkeypatch.setattr(promoter_io, "predict_batch", corrupt)
        request = document()
        if mode == "unknown":
            monkeypatch.setattr(p, "_roster", lambda *a: None)
        with pytest.raises(p.PairError, match="unexpected or duplicate candidate"):
            p.predict_pair(request)


def test_public_panel_rosters_fit_without_scoring():
    data = json.loads(
        Path("benchmarks/recoding/runtime-pair-fixtures.json").read_text()
    )
    assert data
    # The public panel's ~230 positions per side are below this wrapper's cap.
    request = document()
    request["current_request"]["scan"] = {
        "mode": "scan",
        "range": [20, 140],
        "strands": ["+", "-"],
    }
    roster = p._roster(request["current_request"], "promoter", "A" * 200)
    assert roster is not None and len(roster) == 240
    assert p.LIMITS["max_candidates_per_side"] >= 240


def test_real_rbs_controls_changed_input_and_reverse_features(real_backend):
    """Six real folding records maximum; sequential and 30 seconds per record."""
    from test_paired_schemas import RESULT_VALIDATOR

    backend = real_backend
    dna = "AAAGGAGGAAAAAAATG" + "A" * 35
    unchanged = p.predict_pair(document("rbs", current=dna), backend)
    assert unchanged["status"] == "complete"
    assert all(
        v["value"] == 0
        for v in unchanged["comparisons"][0]["deltas"].values()
        if v["value"] is not None
    )
    changed = p.predict_pair(
        document("rbs", current=dna, edits=[edit(6, 7, "C")]), backend
    )
    assert changed["status"] == "complete"
    assert changed["comparisons"][0]["deltas"]["dG_total"]["value"] != 0
    request = document("rbs", current=dna)
    reverse = dna.translate(str.maketrans("ACGT", "TGCA"))[::-1]
    for side in p.SIDES:
        request["pair"][side]["sequence"] = reverse
        request[side + "_request"].update(sequence=reverse, strand="-")
    request["settings"]["profile"] = "standby2014"
    request["pair"]["topology"] = "circular"
    request["projections"] = {
        s: projection(length=len(dna), strand="-", origin=10, circular=True)
        for s in p.SIDES
    }
    result = p.predict_pair(request, backend)
    assert result["status"] == "complete"
    candidate = result["sides"]["current"]["candidates"][0]
    assert candidate["codon_bases"] == [len(dna) - 1 - 14 - i for i in range(3)]
    assert candidate["features"]["coding_footprint"]["mapping"]["complete_base_mapping"]
    assert candidate["features"]["standby.proximal"]["mapping"] is not None
    assert (
        result["sides"]["current"]["prediction"]["sites"][0]["structures"] is not None
    )
    for side in p.SIDES:
        distal = result["sides"][side]["candidates"][0]["features"]["standby.distal"]
        assert distal["interval"] == [len(dna), len(dna)]
        assert distal["mapping"]["source_bases"] == []
        assert distal["mapping"]["mapped_bases"] == []
        assert distal["genomic"]["bases"] == []
    assert all(
        value["value"] == 0
        for value in result["comparisons"][0]["deltas"].values()
        if value["value"] is not None
    )
    for actual in (unchanged, changed, result):
        RESULT_VALIDATOR.validate(actual)


@pytest.mark.parametrize("side", p.SIDES)
@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("topology", ["linear", "circular"])
def test_empty_native_feature_at_boundary_preserves_interval(side, strand, topology):
    request = document("rbs", current="A" * 20)
    request["pair"]["topology"] = topology
    geometry = build_edit_map(request["pair"])
    raw = {"standby": {"distal": {"start": 20, "end": 20, "strand": strand}}}
    feature = p._features(raw, "rbs", geometry, side, strand, None)["standby.distal"]
    assert feature["interval"] == [20, 20]
    assert feature["reason"] is None
    assert feature["mapping"] == {
        "source_bases": [],
        "mapped_bases": [],
        "mapped_runs": [],
        "unmatched_bases": 0,
        "complete_base_mapping": True,
        "contiguous_target_path": True,
    }


def test_standby_feature_geometry_and_circular_unrolling():
    """Literal intervals test projection only; no fabricated prediction scores."""
    request = document("rbs", current="A" * 20)
    request["pair"]["topology"] = "circular"
    geometry = build_edit_map(request["pair"])
    interval = {"start": 18, "end": 22, "strand": "-"}
    raw = {
        "standby": {
            "original_hairpin": interval,
            "hairpin": None,
            "distal": interval,
            "proximal": interval,
            "downstream_hairpins": [{"interval": interval}],
        }
    }
    features = p._features(
        raw,
        "rbs",
        geometry,
        "current",
        "-",
        projection(length=20, strand="-", origin=1, circular=True),
    )
    expected = [1, 0, 19, 18]
    assert (
        features["standby.downstream_hairpins.0"]["mapping"]["source_bases"] == expected
    )
    assert features["standby.original_hairpin"]["mapping"]["mapped_runs"] == [
        [0, 2],
        [18, 20],
    ]
    assert features["standby.distal"]["genomic"]["strand"] == "+"
    assert features["binding_interval"]["interval"] is None


def test_all_public_edit_fixture_features_by_base_enumeration():
    cases = json.loads(
        Path("benchmarks/recoding/synthetic-edit-fixtures.json").read_text()
    )["cases"]
    for case in cases:
        geometry = build_edit_map(case["input"])
        for side in p.SIDES:
            expected = case[
                "expected_"
                + side
                + "_to_"
                + ("recoded" if side == "current" else "current")
            ]
            length = len(expected)
            for strand in ("+", "-"):
                for start in range(length):
                    end = min(length, start + 3)
                    intervals = {"selected": {"intervals": {"hex10": [start, end]}}}
                    feature = p._features(
                        intervals, "promoter", geometry, side, strand, None
                    )["hex10"]
                    bases = list(range(start, end))
                    if strand == "-":
                        bases.reverse()
                    assert feature["mapping"]["source_bases"] == bases
                    assert feature["mapping"]["mapped_bases"] == [
                        expected[b] for b in bases
                    ]


@pytest.mark.parametrize("side", p.SIDES)
def test_unsupported_controls_retain_known_candidates(side):
    request = document()
    request[side + "_request"]["sigma"] = "unsupported"
    result = p.predict_pair(request)
    record = result["sides"][side]["prediction"]["results"][0]
    assert record["status"] == "unsupported"
    assert result["coverage"][side]["expected"] == 2
    assert result["comparisons"][0]["reason"] == "unsuccessful_candidate"


def test_rbs_unsupported_start_is_retained_without_backend_folding(monkeypatch):
    # session creation succeeds; leaderless/unsupported starts never call folding.
    backend = RnaStructure(Path("."), {"name": "unreachable-folding-failure-test"})

    def no_fold(*args):
        return object()

    monkeypatch.setattr(RnaStructure, "session", no_fold)
    request = document("rbs", current="A" * 20)
    for side in p.SIDES:
        request[side + "_request"]["start_positions"] = [0]
    result = p.predict_pair(request, backend)
    assert (
        result["sides"]["current"]["prediction"]["sites"][0]["status"] == "unsupported"
    )
    assert result["comparisons"][0]["reason"] == "unsuccessful_candidate"


def test_complete_rbs_empty_roster_without_folding(monkeypatch):
    backend = RnaStructure(Path("."), {"name": "empty-no-fold"})
    monkeypatch.setattr(RnaStructure, "session", lambda *args: object())
    result = p.predict_pair(document("rbs", current="A" * 20), backend)
    assert result["status"] == "complete"
    assert result["coverage"]["current"]["expected"] == 0
    assert result["comparisons"] == []


@pytest.mark.parametrize(
    "key", ("model_sha256", "settings_sha256", "backend_sha256", "calibration_sha256")
)
def test_every_identity_dimension_blocks_delta(key):
    request = document()
    result = p.predict_pair(request)
    result["sides"]["recoded"]["identities"][key] = "f" * 64
    rows = p._comparisons(result["sides"], build_edit_map(request["pair"]))
    assert all(
        row["identity_mismatches"] == [key] and row["reason"] == "incompatible_identity"
        for row in rows
    )
    assert all(d["value"] is None for row in rows for d in row["deltas"].values())


def test_rbs_settings_identity_retains_actual_settings(failed_backend):
    request = document("rbs", current="A" * 20)
    request["current_request"]["anti_sd"] = "accuccuua"
    request["recoded_request"]["temperature_c"] = 36
    result = p.predict_pair(request, failed_backend)
    assert (
        result["sides"]["current"]["identities"]["settings_sha256"]
        != result["sides"]["recoded"]["identities"]["settings_sha256"]
    )
    assert result["sides"]["current"]["prediction"]["input"]["anti_sd"] == "ACCUCCUUA"


@pytest.mark.parametrize(
    "operation",
    (
        "unknown_field",
        "caller_map",
        "missing_field",
        "overlap",
        "invalid_projection",
        "missing_rbs_field",
    ),
)
def test_more_atomic_preflight_refusals(failed_backend, operation):
    request = document("rbs", current="A" * 20)
    error = ""
    if operation == "unknown_field":
        request["unknown"] = True
        error = "request: expected fields"
    elif operation == "caller_map":
        request["pair"] = build_edit_map(request["pair"])
        error = "expected JSON values"
    elif operation == "missing_field":
        del request["pair"]["current"]["sequence"]
        error = "current: expected exactly"
    elif operation == "overlap":
        request["pair"]["edits"] = [
            edit(2, 5, "AAA"),
            {"id": "second", "start": 3, "end": 4, "replacement": "A"},
        ]
        error = "nonoverlapping"
    elif operation == "invalid_projection":
        request["projections"] = {
            "current": projection(length=20, origin=999),
            "recoded": None,
        }
        error = "projections.current: invalid_projection"
    else:
        del request["current_request"]["host"]
        error = "current_request: missing required"
    with pytest.raises(p.PairError, match=error):
        p.predict_pair(request, failed_backend)


@pytest.mark.parametrize(
    "field,value", [("schema_version", "wrong"), ("records", []), ("defaults", {})]
)
def test_promoter_envelopes_rejected_before_either_prediction(
    monkeypatch, field, value
):
    request = document()
    request["recoded_request"][field] = value

    def forbidden(*args, **kwargs):
        pytest.fail("preflight must reject before prediction")

    monkeypatch.setattr(promoter_io, "predict_batch", forbidden)
    with pytest.raises(
        p.PairError,
        match="recoded_request: expected a single Promoter schema 1.0 record",
    ):
        p.predict_pair(request)


@pytest.mark.parametrize(
    "case",
    json.loads(Path("benchmarks/recoding/runtime-pair-fixtures.json").read_text())[
        "cases"
    ],
    ids=lambda case: case["input"]["pair_id"],
)
def test_public_long_pair_exact_rbs_rosters_and_accounting(case):
    """Validate label-free public geometry without running a folding cohort."""
    geometry = build_edit_map(case["input"])
    sides = {}
    for side in p.SIDES:
        dna = case["input"][side]["sequence"]
        found: list[dict] = []
        for strand in ("+", "-"):
            roster = p._roster({"strand": strand}, "rbs", dna)
            assert roster is not None
            for local_strand, anchor in roster:
                found.append({"base": anchor, "strand": local_strand})
        expected = [
            {"base": c["base"], "strand": c["strand"]}
            for c in case["expected_rbs_candidates"][side]
        ]
        assert sorted(found, key=lambda c: (c["strand"], c["base"])) == sorted(
            expected, key=lambda c: (c["strand"], c["base"])
        )
        candidates = [
            {
                "id": f"{side}:{c['strand']}:{c['base']}",
                "strand": c["strand"],
                "anchor": c["base"],
                "codon_bases": [
                    c["base"] + i * (1 if c["strand"] == "+" else -1) for i in range(3)
                ],
                "status": "unavailable",
                "scalars": {},
                "features": {},
            }
            for c in found
        ]
        sides[side] = {
            "candidates": candidates,
            "roster_status": "known",
            "identities": {},
        }
    rows = p._comparisons(sides, geometry)
    counts: dict[str, int] = {}
    names = {
        "unmapped_current_anchor": "unmatched_current:deleted_coordinate",
        "unmapped_recoded_anchor": "unmatched_recoded:inserted_coordinate",
        "mapped_anchor_absent_from_recoded_roster": (
            "unmatched_current:mapped_anchor_absent"
        ),
        "mapped_anchor_absent_from_current_roster": (
            "unmatched_recoded:mapped_anchor_absent"
        ),
    }
    for row in rows:
        name = "paired" if row["status"] == "paired" else names[row["reason"]]
        counts[name] = counts.get(name, 0) + 1
    assert counts == case["expected_rbs_accounting"]

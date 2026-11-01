"""Independent enumeration, native equality, coordinates and pure preflight."""

import copy
import hashlib
import itertools
import json
import math
from pathlib import Path

import pytest

from regsite import (
    promoter,
    promoter_io,
)
from regsite import (
    promoter_design as design,
)
from regsite import (
    promoter_design_io as io,
)


def request():
    return json.loads(Path("examples/promoter-design-single.json").read_text())


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def oracle_sequences(seed, positions, maximum):
    # Independent exhaustive Cartesian alphabet, filtered by Hamming distance.
    variants = []
    for bases in itertools.product("ACGT", repeat=len(positions)):
        candidate = list(seed)
        for index, base in zip(sorted(positions), bases, strict=True):
            candidate[index] = base
        changes = tuple(
            index for index, base in enumerate(candidate) if base != seed[index]
        )
        if len(changes) <= maximum:
            variants.append(
                (
                    len(changes),
                    changes,
                    tuple(candidate[p] for p in changes),
                    "".join(candidate),
                )
            )
    return [entry[-1] for entry in sorted(variants)]


@pytest.mark.parametrize(
    "positions,maximum", [([], 0), ([81, 80], 1), ([82, 80, 81], 2)]
)
def test_full_roster_and_independent_ranking(positions, maximum):
    value = request()
    value.update(
        editable_positions=positions, immutable_intervals=[], max_changes=maximum
    )
    value["limits"]["max_candidates"] = 64
    original = copy.deepcopy(value)
    result = design.design(value, clock=lambda: 0.0)
    assert value == original
    assert result["status"] == "complete"
    rows = result["candidates"]
    seed = value["promoter"]["sequence"]
    assert [row["sequence"] for row in rows] == oracle_sequences(
        seed, positions, maximum
    )
    assert result["coverage"] == {
        "planned": len(rows),
        "attempted": len(rows),
        "successful": len(rows),
        "failed": 0,
        "not_run": 0,
        "prediction_calls": len(rows) + 1,
        "all_candidates_scored": True,
        "deadline_exceeded": False,
        "stop_reason": None,
    }
    ranking = []
    for index, row in enumerate(rows):
        assert row["index"] == index and row["native_admitted"] and row["attempted"]
        assert row["native_request"] == {
            **value["promoter"],
            "sequence": row["sequence"],
        }
        assert row["native_request_sha256"] == canonical_hash(row["native_request"])
        native = row["native"]
        observed = [
            site["selected"]["log_relative_transcription_score"]
            for site in native["results"][0]["sites"]
        ]
        errors = [
            abs(a - b)
            for a, b in zip(observed, value["target_log_scores"], strict=True)
        ]
        objective = math.fsum(errors) / len(errors)
        assert row["observed_log_scores"] == observed
        assert row["absolute_log_errors"] == errors and row["objective"] == objective
        changes = [
            (i, a, b)
            for i, (a, b) in enumerate(zip(seed, row["sequence"], strict=True))
            if a != b
        ]
        assert [(e["position"], e["from"], e["to"]) for e in row["edits"]] == changes
        ranking.append((objective, len(changes), row["sequence"], index))
    assert result["proposal"]["index"] == min(ranking)[-1]
    assert result["selected"] == result["proposal"]
    assert result["confirmation"]["status"] == "matched"
    assert (
        result["confirmation"]["native_sha256"] == result["selected"]["native_sha256"]
    )
    assert result["result_sha256"] == canonical_hash(
        {k: v for k, v in result.items() if k != "result_sha256"}
    )


def test_direct_unchanged_native_equality_fixed_budgets_and_identities(monkeypatch):
    value = request()
    value["limits"]["seconds_per_candidate"] = 2
    value["limits"]["seconds_total"] = 1
    real = promoter_io.predict_batch
    calls = []

    def track(native_request, params, **options):
        calls.append((copy.deepcopy(native_request), dict(options)))
        return real(native_request, params, **options)

    monkeypatch.setattr(promoter_io, "predict_batch", track)
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "complete" and len(calls) == 5
    assert result["request_sha256"] == canonical_hash(value)
    assert result["design_id"] == canonical_hash(
        {
            "request_sha256": result["request_sha256"],
            "algorithm": result["algorithm"],
            "model_identity": result["model_identity"],
            "targets": result["targets"],
            "limits": result["limits"],
        }
    )
    for row, (native_request, options) in zip(
        result["candidates"], calls[:4], strict=True
    ):
        assert options["seconds_per_record"] == options["seconds_per_batch"] == 2.0
        assert type(options["seconds_per_record"]) is float
        expected = real(
            native_request,
            seconds_per_record=2.0,
            seconds_per_batch=2.0,
            clock=lambda: 0.0,
        )
        assert row["native"] == expected
        raw = (
            json.dumps(
                expected, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode()
        assert row["native_bytes"] == len(raw)
        assert row["native_sha256"] == hashlib.sha256(raw).hexdigest()
        assert (
            row["sequence_sha256"]
            == hashlib.sha256(row["sequence"].encode()).hexdigest()
        )
        assert row["candidate_id"] == canonical_hash(
            {
                "design_id": result["design_id"],
                "index": row["index"],
                "sequence_sha256": row["sequence_sha256"],
            }
        )
    assert (
        calls[-1][0]
        == result["candidates"][result["selected"]["index"]]["native_request"]
    )


def test_both_strand_mapping_projection_provenance_and_locks():
    value = request()
    value["promoter"]["host"] = {"name": "artificial e\u0301 host", "taxon_id": 1.0}
    value["promoter"]["projection"] = {
        "contig": "artificial",
        "origin": 199,
        "contig_length": 200,
        "topology": "linear",
        "origin_crossing": False,
        "sequence_strand": "-",
    }
    value["promoter"]["calibration"] = "in_vitro"
    value["editable_positions"] = [115.0]
    value["immutable_intervals"] = [[0, 115], [116, 200]]
    value["max_changes"] = 1.0
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "complete"
    assert result["targets"] == [
        {
            "index": 0,
            "strand": "+",
            "forward_base": 100,
            "oriented_base": 100,
            "target_log_score": 0.0,
            "admission_interval": [33, 120],
        },
        {
            "index": 1,
            "strand": "-",
            "forward_base": 129,
            "oriented_base": 70,
            "target_log_score": 0.0,
            "admission_interval": [110, 197],
        },
    ]
    complement = dict(zip("ACGT", "TGCA", strict=True))
    for row in result["candidates"]:
        assert row["sequence"][:115] == value["promoter"]["sequence"][:115]
        assert row["sequence"][116:] == value["promoter"]["sequence"][116:]
        for edit in row["edits"]:
            assert edit["oriented"] == [
                {
                    "target_index": 0,
                    "position": 115,
                    "from": edit["from"],
                    "to": edit["to"],
                },
                {
                    "target_index": 1,
                    "position": 84,
                    "from": complement[edit["from"]],
                    "to": complement[edit["to"]],
                },
            ]
        native = row["native"]["results"][0]
        assert native["metadata"] == value["promoter"]["metadata"]
        assert native["projection"] == value["promoter"]["projection"]
        assert native["calibration"]["host"]["name"] == "artificial é host"
        assert native["calibration"]["host_status"] == "extrapolated"
        assert native["warnings"][0]["code"] == "host_extrapolation"


def test_neutral_plus18_edits_retained_seed_wins_fewer_edits():
    value = request()
    value["promoter"]["scan"]["positions"] = [{"strand": "+", "tss": 100}]
    value.update(
        target_log_scores=[0], editable_positions=[118], immutable_intervals=[]
    )
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "complete" and len(result["candidates"]) == 4
    assert len({row["objective"] for row in result["candidates"]}) == 1
    assert result["selected"]["index"] == 0
    assert [len(row["edits"]) for row in result["candidates"]] == [0, 1, 1, 1]


@pytest.mark.parametrize(
    "forward,strand,position",
    [(67, "+", 0), (180, "+", 199), (132, "-", 199), (19, "-", 0)],
)
def test_inclusive_context_and_edit_boundaries(forward, strand, position):
    value = request()
    value["promoter"]["scan"]["positions"] = [{"strand": strand, "tss": forward}]
    value.update(
        target_log_scores=[0],
        editable_positions=[position],
        immutable_intervals=[],
        max_changes=0,
    )
    assert design.design(value, clock=lambda: 0.0)["status"] == "complete"


def set_path(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), "wrong"),
        (("promoter",), []),
        (("promoter", "schema_version"), "wrong"),
        (("promoter", "id"), "bad id"),
        (("promoter", "sequence"), "a" * 200),
        (("promoter", "sequence"), "A" * 1001),
        (("promoter", "sequence"), ""),
        (("promoter", "sequence"), "ACGU" * 50),
        (("promoter", "calibration"), "unknown"),
        (("promoter", "host"), None),
        (
            ("promoter", "output"),
            {"states": "selected", "elements": True, "legacy_keys": 0},
        ),
        (("promoter", "scan"), {}),
        (("promoter", "scan", "mode"), "scan"),
        (("promoter", "scan", "positions"), []),
        (("promoter", "scan", "positions", 0), {}),
        (("promoter", "scan", "positions", 0, "strand"), "x"),
        (("promoter", "scan", "positions", 0, "tss"), True),
        (("promoter", "scan", "positions", 0, "tss"), 1.5),
        (("promoter", "scan", "positions", 0, "tss"), 66),
        (("promoter", "scan", "positions", 0, "tss"), 181),
        (("target_log_scores",), []),
        (("target_log_scores", 0), True),
        (("target_log_scores", 0), "0"),
        (("target_log_scores", 0), 1e6 + 1),
        (("editable_positions",), [80, 80.0]),
        (("editable_positions",), [True]),
        (("editable_positions",), [200]),
        (("editable_positions",), [32]),
        (("editable_positions",), [79]),
        (("editable_positions",), {}),
        (("immutable_intervals",), None),
        (("immutable_intervals",), [[]]),
        (("immutable_intervals",), [[1, 1]]),
        (("immutable_intervals",), [[0, 100], [99, 101]]),
        (("immutable_intervals",), [[0, 201]]),
        (("max_changes",), 2),
        (("max_changes",), True),
        (("max_changes",), -1),
        (("limits",), {}),
        (("limits", "max_candidates"), 3),
        (("limits", "max_candidates"), 65),
        (("limits", "max_candidates"), True),
        (("limits", "seconds_per_candidate"), 0),
        (("limits", "seconds_per_candidate"), 11),
        (("limits", "seconds_total"), 121),
        (("limits", "seconds_total"), "1"),
        (("limits", "seconds_total"), 10**1000),
    ],
)
def test_invalid_preflight_never_calls_predictor(path, replacement, monkeypatch):
    value = request()
    set_path(value, path, replacement)

    def forbidden(*args, **kwargs):
        pytest.fail("prediction during invalid preflight")

    monkeypatch.setattr(promoter_io, "predict_batch", forbidden)
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "invalid_input"
    assert result["candidates"] == [] and result["selected"] is None


def test_unknown_duplicate_and_native_setup_refusals(monkeypatch):
    values = []
    value = request()
    value["extra"] = 1
    values.append(value)
    value = request()
    del value["promoter"]["id"]
    values.append(value)
    value = request()
    value["promoter"]["sigma"] = "extra"
    values.append(value)
    value = request()
    value["promoter"]["scan"]["positions"][1] = value["promoter"]["scan"]["positions"][
        0
    ]
    values.append(value)
    value = request()
    value["promoter"]["model"] = {
        "id": "unavailable",
        "parameter_json_sha256": "0" * 64,
    }
    values.append(value)
    for value in values:
        assert design.design(value, clock=lambda: 0.0)["status"] == "invalid_input"
    monkeypatch.setattr(
        promoter,
        "load_parameters",
        lambda: (_ for _ in ()).throw(promoter.ParameterError("private setup detail")),
    )
    result = design.design(request(), clock=lambda: 0.0)
    assert result["reason"] == "model_or_native_setup"
    assert "private" not in json.dumps(result)


def test_exact_search_cap_eight_targets_and_explicit_model_pin():
    value = request()
    value.update(editable_positions=list(range(80, 101)), immutable_intervals=[])
    value["limits"]["max_candidates"] = 64
    value["promoter"]["scan"]["positions"] = [
        {"strand": "+", "tss": i} for i in range(100, 108)
    ]
    value["target_log_scores"] = [-1e6, 1e6, 0, 0, 0, 0, 0, 0]
    value["promoter"]["model"] = {
        "id": promoter.MODEL_ID,
        "parameter_json_sha256": promoter.PARAMETER_JSON_SHA256,
    }
    plan = design.parse_request(value)
    assert len(list(design._sequences(plan))) == 64 and len(plan.targets) == 8
    value["limits"]["max_candidates"] = 63
    assert design.design(value)["reason"] == "candidate_limit"
    value["limits"]["max_candidates"] = 64
    value["max_changes"] = 2
    assert design.design(value)["reason"] == "candidate_limit"
    value["promoter"]["scan"]["positions"].append({"strand": "+", "tss": 108})
    assert design.design(value)["reason"] == "target_roster"


def test_exact_canonical_limit_and_whole_result_limit(monkeypatch):
    value = request()
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    monkeypatch.setattr(io, "INPUT_LIMIT", len(raw))
    assert design.parse_request(value).request == value
    monkeypatch.setattr(io, "INPUT_LIMIT", len(raw) - 1)
    assert design.design(value, clock=lambda: 0.0)["reason"] == "canonical_input_limit"
    monkeypatch.setattr(io, "INPUT_LIMIT", 65536)
    baseline = design.design(value, clock=lambda: 0.0)
    length = len(io.result_bytes(baseline))
    monkeypatch.setattr(io, "OUTPUT_LIMIT", length)
    assert design.design(value, clock=lambda: 0.0) == baseline
    monkeypatch.setattr(io, "OUTPUT_LIMIT", length - 1)
    assert (
        design.design(value, clock=lambda: 0.0)["reason"]
        == "result_serialization_failure"
    )

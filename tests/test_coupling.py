"""Independent arithmetic controls and failure accounting for reinitiation."""

import copy
import json
import math
from pathlib import Path

import pytest

from regsite.coupling import BETA, predict_coupling
from regsite.coupling_io import canonical_hash
from regsite.sequence import reverse_complement


def record(distance=0, **kwargs):
    if distance == -4:
        upstream, downstream = [0, 9], [5, 14]
        # The overlapping AUGA spans positions 5..8; complete the downstream CDS.
        sequence = "AUGCCAUGACCUAA"
    else:
        sequence = "AUGCCCUAA" + "C" * distance + "GUGCCCUAG"
        upstream, downstream = [0, 9], [9 + distance, 18 + distance]
    result = {
        "id": "synthetic",
        "sequence": sequence,
        "strand": "+",
        "upstream": {"id": "first", "interval": upstream},
        "downstream": {"id": "second", "interval": downstream},
        "energies": {
            "upstream_total_kcal_mol": 0.0,
            "downstream_independent_total_kcal_mol": 0.0,
            "beta_mol_per_kcal": BETA,
            "provenance": "original synthetic zero-energy algebra control",
        },
    }
    result.update(kwargs)
    return result


def request(*records):
    return {
        "schema_version": "coupling-request-1",
        "settings": {"seconds_total": 10},
        "records": list(records) or [record()],
    }


def run(value):
    return predict_coupling(value, clock=lambda: 0.0)


def test_frozen_arithmetic_fixtures():
    fixtures = json.loads(
        Path("benchmarks/operon-coupling/synthetic-fixtures.json").read_text()
    )
    for case in fixtures["cases"]:
        item = record(case["distance_nt"])
        item["energies"]["upstream_total_kcal_mol"] = (
            -math.log(float(case["upstream_rate"])) / BETA
        )
        item["energies"]["downstream_independent_total_kcal_mol"] = (
            -math.log(float(case["independent_rate"])) / BETA
        )
        result = run(request(item))
        row = result["records"][0]
        assert result["status"] == "complete", row
        assert row["coefficient"] == float(case["k_reinit"])
        assert row["scores"]["reinitiation_contribution"]["value"] == pytest.approx(
            float(case["reinitiation_rate"]), rel=1e-14
        )
        assert row["scores"]["downstream_total"]["value"] == pytest.approx(
            float(case["total_rate"]), rel=1e-14
        )
        assert row["scores"]["fold_change"]["value"] == pytest.approx(
            float(case["total_rate"]) / float(case["independent_rate"]), rel=1e-14
        )
        assert row["unfolding_correction"] is None


def test_reverse_strand_mirror_and_input_identity():
    plus = record(-4)
    minus = copy.deepcopy(plus)
    length = len(plus["sequence"])
    minus["sequence"] = reverse_complement(plus["sequence"])
    minus["strand"] = "-"
    for key in ("upstream", "downstream"):
        a, b = plus[key]["interval"]
        minus[key]["interval"] = [length - b, length - a]
    original = copy.deepcopy(minus)
    forward, reverse = run(request(plus)), run(request(minus))
    assert forward["records"][0]["scores"] == reverse["records"][0]["scores"]
    assert reverse["records"][0]["geometry"]["distance_nt"] == -4
    assert reverse["request_sha256"] != forward["request_sha256"]
    assert minus == original
    saved_hash = reverse.pop("prediction_sha256")
    assert canonical_hash(reverse) == saved_hash


@pytest.mark.parametrize("distance", [26, 100, 25])
def test_distance_boundary(distance):
    result = run(request(record(distance)))
    row = result["records"][0]
    assert row["status"] == ("ok" if distance == 25 else "unsupported_distance")
    if distance != 25:
        assert row["scores"] is None and row["coefficient"] is None
        assert row["geometry"]["distance_nt"] == distance


@pytest.mark.parametrize("change", [None, [], {}, {"id": "bad space"}, {"extra": True}])
def test_invalid_record_preserved(change):
    bad = change if not isinstance(change, dict) else dict(record(), **change)
    if change == {}:
        bad = {}
    result = run(request(bad, record(id="valid")))
    assert result["status"] == "partial"
    assert [r["status"] for r in result["records"]] == ["invalid_input", "ok"]
    assert result["coverage"] == {
        "requested": 2,
        "returned": 2,
        "successful": 1,
        "failed_or_unsupported": 1,
        "not_evaluated": 0,
    }


@pytest.mark.parametrize("energy", [None, {}, [], {"extra": 0}])
def test_energy_shape(energy):
    result = run(request(record(energies=energy)))
    assert result["records"][0]["reason"] == "invalid_or_incompatible_energies"


@pytest.mark.parametrize(
    "key,value",
    [
        ("upstream_total_kcal_mol", True),
        ("upstream_total_kcal_mol", 1e6 + 1),
        ("upstream_total_kcal_mol", "0"),
        ("downstream_independent_total_kcal_mol", -1e6 - 1),
        ("beta_mol_per_kcal", 1),
        ("beta_mol_per_kcal", False),
        ("provenance", None),
        ("provenance", ""),
        ("provenance", "   "),
        ("provenance", "x" * 1001),
        ("provenance", "x" + " " * 1000),
    ],
)
def test_invalid_energy_value(key, value):
    item = record()
    item["energies"][key] = value
    assert run(request(item))["records"][0]["status"] == "invalid_input"


def test_invalid_geometry_and_unsupported_codons():
    malformed = record(id="bad", strand="?")
    unsupported = record(id="unsupported", sequence="AAACCCUAAGUGCCCUAG")
    rows = run(request(malformed, unsupported))["records"]
    assert [row["status"] for row in rows] == ["invalid_input", "unsupported_geometry"]
    assert all(row["scores"] is None for row in rows)


@pytest.mark.parametrize("energy", [-1e6, 1e6])
def test_extreme_scores_keep_finite_logs_and_null_linear(energy):
    item = record()
    item["energies"]["upstream_total_kcal_mol"] = energy
    item["energies"]["downstream_independent_total_kcal_mol"] = energy
    result = run(request(item))
    row = result["records"][0]
    assert row["status"] == "numerical_range"
    assert row["scores"]["downstream_total"]["value"] is None
    assert all(math.isfinite(score["log_value"]) for score in row["scores"].values())
    assert row["scores"]["fold_change"]["value"] == pytest.approx(1.072)
    json.dumps(result, allow_nan=False)


def test_huge_difference_keeps_dominant_total():
    item = record()
    item["energies"]["upstream_total_kcal_mol"] = 1e6
    row = run(request(item))["records"][0]
    assert row["scores"]["downstream_total"]["value"] == 1
    assert row["scores"]["reinitiation_contribution"]["value"] is None


@pytest.mark.parametrize(
    "bad", [None, [], {}, {"extra": 0}, float("nan"), {1}, {"x": object()}]
)
def test_invalid_envelopes(bad):
    result = run(bad)
    assert result["status"] == "invalid_input"
    assert result["records"] == [] and result["coverage"] is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "bad"),
        ("records", []),
        ("records", None),
        ("records", [record()] * 101),
        ("settings", None),
        ("settings", {}),
        ("settings", {"seconds_total": 0}),
        ("settings", {"seconds_total": -1}),
        ("settings", {"seconds_total": 61}),
        ("settings", {"seconds_total": True}),
    ],
)
def test_envelope_fields(key, value):
    data = request()
    data[key] = value
    assert run(data)["reason"] == "invalid_envelope"


def test_duplicate_ids_and_input_cap():
    assert run(request(record(), record()))["reason"] == "duplicate_record_id"
    assert run({"sequence": "A" * 1_048_576})["reason"] == "input_byte_limit"


def test_recursive_python_input_is_refused():
    data = []
    data.append(data)
    assert run(data)["status"] == "invalid_input"


@pytest.mark.parametrize(
    "ticks,expected",
    [
        ([0, 0, 0, 10], ["ok", "not_evaluated", "not_evaluated"]),
        ([0, 0, 10], ["not_evaluated"] * 3),
        ([0, 10], ["not_evaluated"] * 3),
    ],
)
def test_deadline_keeps_every_record(ticks, expected):
    clock = iter(ticks)
    result = predict_coupling(
        request(record(id="a"), record(id="b"), record(id="c")),
        clock=lambda: next(clock),
    )
    assert [r["status"] for r in result["records"]] == expected
    assert result["coverage"]["returned"] == 3
    assert result["coverage"]["not_evaluated"] == expected.count("not_evaluated")

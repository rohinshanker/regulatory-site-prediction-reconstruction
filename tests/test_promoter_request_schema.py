"""Structural contract tests only: no parser, scorer or prediction is exercised."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/promoter-request-1.0.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)


def record(**overrides):
    """Return synthetic input with an explicit calibration and local scan."""
    return {
        "id": "synthetic",
        "sequence": "ACGT" * 50,
        "calibration": "ecoli_mg1655",
        "scan": {"mode": "scan", "range": [67, 71], "strands": ["+"]},
        **overrides,
    }


def positions(count):
    """Return distinct synthetic points, without claiming coordinate validity."""
    return {
        "mode": "positions",
        "positions": [{"strand": "+", "tss": i} for i in range(count)],
    }


def projection(**overrides):
    """Return explicit mapping metadata, independent of any genome."""
    return {
        "contig": "synthetic-contig",
        "origin": 50,
        "contig_length": 1000,
        "sequence_strand": "-",
        "topology": "circular",
        "origin_crossing": True,
        **overrides,
    }


def test_schema_is_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize("name", ["single", "batch"])
def test_examples_are_structurally_valid_synthetic_requests(name):
    value = json.loads(
        (ROOT / f"examples/promoter-contract-{name}.json").read_text(encoding="utf-8")
    )
    VALIDATOR.validate(value)
    records = value["records"] if name == "batch" else [value]
    for item in records:
        sequence = item["sequence"]
        assert sequence == ("ACGT" * 50)[: len(sequence)]
        assert "sites" not in item
    if name == "single":
        assert [p["strand"] for p in value["scan"]["positions"]] == ["+", "-"]
    else:
        grid, override = records
        assert len(grid["sequence"]) == 67 + 4 + 19
        assert grid["scan"] == {"mode": "scan", "range": [67, 71], "strands": ["+"]}
        assert grid["projection"] == projection(contig="synthetic-circular-contig")
        assert grid["projection"]["origin"] - (len(grid["sequence"]) - 1) < 0
        assert value["defaults"]["calibration"] == "ecoli_mg1655"
        assert "calibration" not in grid
        assert override["calibration"] == "in_vitro"
        assert override["output"]["states"] == "all"


@pytest.mark.parametrize("field", ["id", "sequence", "scan"])
def test_required_record_fields_in_single_and_envelope(field):
    value = record()
    del value[field]
    assert not VALIDATOR.is_valid(value)
    assert not VALIDATOR.is_valid({"records": [value]})


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        "request",
        [],
        [record()],
        {},
        {"defaults": {}},
        {"records": None},
        {"records": {}},
        {"records": [None]},
        {"records": [[record()]]},
        {"records": [], "id": "envelope-cannot-be-record"},
        {"records": [], "sequence": "ACGT"},
        record(records=[]),
        record(defaults={}),
        {"records": [record(schema_version="1.0")]},
        {"records": [{"records": []}]},
    ],
)
def test_record_and_envelope_shapes_are_exclusive(value):
    assert not VALIDATOR.is_valid(value)


@pytest.mark.parametrize("version", [None, 1.0, True, "", "2.0"])
def test_unsupported_schema_versions(version):
    assert not VALIDATOR.is_valid(record(schema_version=version))
    assert not VALIDATOR.is_valid({"schema_version": version, "records": []})


def test_defaults_are_annotations_and_cli_calibration_is_not_falsely_rejected():
    """These omissions require --calibration later; this does not run a CLI."""
    single = record()
    del single["calibration"]
    for value in [single, {"records": [single]}, {"defaults": {}, "records": [single]}]:
        original = copy.deepcopy(value)
        VALIDATOR.validate(value)
        assert value == original
    VALIDATOR.validate({"defaults": {"calibration": "in_vitro"}, "records": [single]})
    VALIDATOR.validate({"defaults": {"calibration": "in_vitro"}, "records": [record()]})
    VALIDATOR.validate(record(schema_version="1.0", output={}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"id": "a" * 129},
        {"id": "-leading"},
        {"id": "white space"},
        {"id": "trailing\n"},
        {"id": "nonascii-α"},
        {"id": 20},
        {"sequence": None},
        {"sequence": []},
        {"sequence": ""},
        {"sequence": " \t\n\v\f\r"},
        {"sequence": "A" * 50001},
        {"sequence": "ACGN"},
        {"sequence": "ACGTU"},
        {"sequence": "uacgt"},
        {"sequence": ">fasta\nACGT"},
        {"sequence": "ACG1"},
        {"sequence": "ACG\u00a0"},
        {"calibration": "unknown"},
        {"calibration": None},
        {"calibration": True},
        {"host": None},
        {"host": "E. coli"},
        {"host": {}},
        {"host": {"name": ""}},
        {"host": {"name": "a" * 201}},
        {"host": {"name": False}},
        {"host": {"name": "synthetic", "taxon_id": None}},
        {"host": {"name": "synthetic", "taxon_id": 0}},
        {"host": {"name": "synthetic", "taxon_id": True}},
        {"host": {"name": "synthetic", "taxon_id": 1.5}},
        {"output": None},
        {"output": []},
        {"output": {"states": "none"}},
        {"output": {"states": None}},
        {"output": {"legacy_keys": 0}},
        {"output": {"elements": "true"}},
        {"metadata": []},
        {"metadata": None},
    ],
)
def test_invalid_scalars_and_options(overrides):
    assert not VALIDATOR.is_valid(record(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "A"},
        {"id": "9" + "._:-a" * 25 + "ab"},
        {"sequence": "A"},
        {"sequence": " a\tCg\nU\v\f\r "},
        {"sequence": " a\tCg\nT\v\f\r "},
        {"sequence": " " * 49999 + "A"},
        {"host": {"name": "a" * 200, "taxon_id": 20.0}},
        {"host": {"name": "unregistered synthetic host"}},
        {"calibration": "in_vitro"},
        {"output": {"states": "all", "legacy_keys": True, "elements": False}},
        {"metadata": {"arbitrary": [None, True, 1, "text", {"sigma": "metadata"}]}},
    ],
)
def test_valid_scalars_and_boundaries(overrides):
    VALIDATOR.validate(record(**overrides))


@pytest.mark.parametrize(
    "scan",
    [
        None,
        [],
        {},
        {"mode": "scan", "strands": ["+"]},
        {"mode": "scan", "range": [0, 1]},
        {"mode": "scan", "range": [0, 1], "strands": []},
        {"mode": "scan", "range": [0, 1], "strands": ["+", "+"]},
        {"mode": "scan", "range": [0, 1], "strands": ["+", "-", "+"]},
        {"mode": "scan", "range": [0, 1], "strands": ["both"]},
        {"mode": "scan", "range": [0, 1], "strands": "+"},
        {"mode": "scan", "range": [0, 1], "strands": [True]},
        {"mode": "scan", "range": [0, 1], "strands": ["+"], "positions": []},
        {"mode": "positions"},
        {"mode": "positions", "positions": None},
        {"mode": "positions", "positions": [{}]},
        {"mode": "positions", "positions": [{"tss": 0}]},
        {"mode": "positions", "positions": [{"strand": "+"}]},
        {"mode": "positions", "positions": [{"strand": "both", "tss": 0}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": 0, "typo": 1}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": 0}] * 2},
        {"mode": "positions", "positions": [], "range": [0, 1]},
        {"mode": "positions", "positions": [], "strands": ["+"]},
        {"mode": "discover", "range": [0, 1], "strands": ["+"]},
    ],
)
def test_scan_modes_require_explicit_disjoint_controls(scan):
    assert not VALIDATOR.is_valid(record(scan=scan))


@pytest.mark.parametrize("bounds", [[], [0], [0, 1, 2], None, "0,1", [0, "1"]])
def test_range_is_exactly_two_coordinates(bounds):
    assert not VALIDATOR.is_valid(
        record(scan={"mode": "scan", "range": bounds, "strands": ["+"]})
    )


@pytest.mark.parametrize("coordinate", [True, False, -1, 0.5, "20", None])
def test_coordinates_reject_booleans_fractions_and_negative_values(coordinate):
    for bounds in [[coordinate, 20], [0, coordinate]]:
        assert not VALIDATOR.is_valid(
            record(scan={"mode": "scan", "range": bounds, "strands": ["+"]})
        )
    assert not VALIDATOR.is_valid(
        record(
            scan={
                "mode": "positions",
                "positions": [{"strand": "+", "tss": coordinate}],
            }
        )
    )


def test_integral_floats_and_numeric_duplicate_positions():
    VALIDATOR.validate(
        record(scan={"mode": "scan", "range": [0.0, 20.0], "strands": ["-", "+"]})
    )
    value = record(
        scan={
            "mode": "positions",
            "positions": [{"strand": "+", "tss": 20.0}, {"strand": "-", "tss": 20}],
        }
    )
    VALIDATOR.validate(value)
    value["scan"]["positions"][1]["strand"] = "+"
    assert not VALIDATOR.is_valid(value)


@pytest.mark.parametrize("length", [1, 77, 78, 87])
def test_short_sequences_and_boundary_candidates_remain_valid(length):
    VALIDATOR.validate(record(sequence="A" * length, scan=positions(1)))
    for bounds in [[0, 0], [length, length], [0, length]]:
        VALIDATOR.validate(
            record(
                sequence="A" * length,
                scan={"mode": "scan", "range": bounds, "strands": ["+"]},
            )
        )
    VALIDATOR.validate(
        record(sequence="A" * length, scan={"mode": "positions", "positions": []})
    )


def test_record_and_position_array_ceilings():
    value = {"records": [record(id=f"record-{i}") for i in range(100)]}
    VALIDATOR.validate(value)
    value["records"].append(record(id="one-too-many"))
    assert not VALIDATOR.is_valid(value)
    VALIDATOR.validate({"records": []})
    VALIDATOR.validate(record(sequence="A" * 5000, scan=positions(5000)))
    assert not VALIDATOR.is_valid(record(scan=positions(5001)))
    VALIDATOR.validate(record(scan=positions(100), output={"states": "all"}))
    assert not VALIDATOR.is_valid(record(scan=positions(101), output={"states": "all"}))
    VALIDATOR.validate(record(scan=positions(101), output={"states": "selected"}))


def test_inherited_all_states_position_limit_and_explicit_record_override():
    value = {
        "defaults": {"output": {"states": "all"}},
        "records": [record(scan=positions(100))],
    }
    VALIDATOR.validate(value)
    value["records"][0]["scan"] = positions(101)
    assert not VALIDATOR.is_valid(value)
    value["records"][0]["output"] = {"states": "selected"}
    VALIDATOR.validate(value)
    value["records"][0]["output"] = {"states": "all"}
    assert not VALIDATOR.is_valid(value)


@pytest.mark.parametrize(
    "defaults",
    [
        None,
        [],
        {"id": "not-defaultable"},
        {"sequence": "ACGT"},
        {"scan": {}},
        {"projection": projection()},
        {"model": {}},
        {"metadata": {}},
        {"calibration": None},
        {"calibration": "unknown"},
        {"host": None},
        {"output": None},
        {"output": {"states": "unknown"}},
    ],
)
def test_defaults_are_restricted_and_null_is_not_omission(defaults):
    assert not VALIDATOR.is_valid({"defaults": defaults, "records": [record()]})


@pytest.mark.parametrize(
    "path",
    [(), ("host",), ("scan",), ("projection",), ("output",), ("model",)],
)
def test_unknown_fields_are_rejected_at_each_control_object(path):
    value = record(
        host={"name": "synthetic"},
        projection=projection(),
        output={},
        model={
            "id": "promoter-lafleur2022-historical-1",
            "parameter_json_sha256": "a" * 64,
        },
    )
    target = value
    for part in path:
        target = target[part]
    target["typo"] = True
    assert not VALIDATOR.is_valid(value)
    assert not VALIDATOR.is_valid({"records": [value]})
    assert not VALIDATOR.is_valid({"records": [], "typo": True})
    assert not VALIDATOR.is_valid({"records": [], "defaults": {"typo": True}})


@pytest.mark.parametrize(
    "control",
    [
        "sigma",
        "sigma_factor",
        "sigma_levels",
        "temperature",
        "temperature_c",
        "design",
        "optimize",
        "k",
        "beta",
    ],
)
def test_unmodeled_controls_are_not_accepted_as_effective_settings(control):
    assert not VALIDATOR.is_valid(record(**{control: 1}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"contig": ""},
        {"contig": "a" * 129},
        {"contig": None},
        {"origin": -1},
        {"origin": True},
        {"origin": 0.5},
        {"contig_length": 0},
        {"contig_length": False},
        {"contig_length": 2.5},
        {"sequence_strand": "both"},
        {"sequence_strand": None},
        {"topology": "unknown"},
        {"origin_crossing": 1},
        {"origin_crossing": None},
        {"topology": "linear", "origin_crossing": True},
    ],
)
def test_projection_shape_and_linear_crossing_constraint(overrides):
    assert not VALIDATOR.is_valid(record(projection=projection(**overrides)))


@pytest.mark.parametrize(
    "field", ["contig", "origin", "contig_length", "topology", "origin_crossing"]
)
def test_projection_requires_mapping_metadata(field):
    value = projection()
    del value[field]
    assert not VALIDATOR.is_valid(record(projection=value))


def test_projection_defaults_and_structural_boundaries():
    value = projection(
        contig="a" * 128,
        origin=0.0,
        contig_length=1000.0,
        topology="linear",
        origin_crossing=False,
    )
    del value["sequence_strand"]
    VALIDATOR.validate(record(projection=value))
    assert "sequence_strand" not in value
    VALIDATOR.validate(
        record(projection=projection(sequence_strand="+", origin_crossing=False))
    )
    for value in [None, [], {}]:
        assert not VALIDATOR.is_valid(record(projection=value))


@pytest.mark.parametrize(
    "pin",
    [
        None,
        [],
        {},
        {"id": "model"},
        {"parameter_json_sha256": "a" * 64},
        {"id": "", "parameter_json_sha256": "a" * 64},
        {"id": 1, "parameter_json_sha256": "a" * 64},
    ],
)
def test_model_pin_requires_a_typed_identity_and_parameter_digest(pin):
    assert not VALIDATOR.is_valid(record(model=pin))


@pytest.mark.parametrize(
    "digest", [None, 1, "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"]
)
def test_model_pin_digest_format(digest):
    assert not VALIDATOR.is_valid(
        record(model={"id": "model", "parameter_json_sha256": digest})
    )


@pytest.mark.parametrize(
    "value",
    [
        record(sequence="A", scan={"mode": "scan", "range": [0, 2], "strands": ["+"]}),
        record(scan={"mode": "scan", "range": [71, 67], "strands": ["+"]}),
        record(sequence="A", scan=positions(2)),
        record(sequence="A" * 5001),
        record(projection=projection(origin=1000)),
        record(projection=projection(contig_length=100)),
        record(projection=projection(topology="linear", origin_crossing=False)),
        record(projection=projection(origin_crossing=False)),
        record(projection=projection(origin=500, origin_crossing=True)),
        record(scan={"mode": "scan", "range": [0, 5000], "strands": ["+", "-"]}),
        {
            "defaults": {"output": {"states": "all"}},
            "records": [record(scan=positions(101), output={"elements": False})],
        },
        {"records": [record(), record()]},
        {
            "records": [
                record(id="one", projection=projection()),
                record(id="two", projection=projection(contig_length=2000)),
            ]
        },
        record(model={"id": "unavailable-model", "parameter_json_sha256": "0" * 64}),
        record(metadata={"text": "a" * 4096}),
        record(metadata={"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}),
    ],
)
def test_semantic_validation_is_explicitly_deferred(value):
    """These need runtime validation; schema acceptance is not prediction success.

    Cases cover normalized bounds/length, arithmetic site budgets, projection
    traversal/crossing, atomic output-default resolution, batch ID/contig consistency,
    installed-model comparison and canonical metadata byte/depth limits.
    """
    VALIDATOR.validate(value)

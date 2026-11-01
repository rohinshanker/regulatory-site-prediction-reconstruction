"""Offline schemas bind native supported shapes without a runtime dependency."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from test_conditional_sweep import example

from regsite import conditional_sweep as sweep

NAMES = [
    "conditional-aptamer-request-1.schema.json",
    "conditional-aptamer-result-1.schema.json",
    "conditional-sweep-request-1.schema.json",
    "conditional-sweep-result-1.schema.json",
]
SCHEMAS = {name: json.loads((Path("schemas") / name).read_text()) for name in NAMES}
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(schema)) for name, schema in SCHEMAS.items()
)


def validator(kind):
    schema = SCHEMAS[f"conditional-sweep-{kind}-1.schema.json"]
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema, registry=REGISTRY)


def test_supported_request_and_complete_result():
    request = example()
    validator("request").validate(request)
    result = sweep.sweep(request)
    validator("result").validate(result)
    for field in request:
        changed = copy.deepcopy(request)
        del changed[field]
        assert not validator("request").is_valid(changed)
    for field in result:
        changed = copy.deepcopy(result)
        del changed[field]
        assert not validator("result").is_valid(changed)


@pytest.mark.parametrize(
    "path,bad",
    [
        (["schema_version"], "bad"),
        (["ligand_total_molar"], []),
        (["ligand_total_molar"], [0] * 65),
        (["ligand_total_molar"], [-1]),
        (["ligand_total_molar"], [True]),
        (["seconds_total"], 0),
        (
            ["template", "input", "occupancy"],
            {"mode": "supplied_fraction", "fraction": 0.5},
        ),
        (["template", "profile"], "canonical_structure_pair"),
        (["extra"], 1),
    ],
)
def test_refused_request_shapes(path, bad):
    value = example()
    cursor = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = bad
    assert not validator("request").is_valid(value)
    validator("result").validate(sweep.sweep(value))


def test_failed_null_and_unstarted_states(monkeypatch):
    value = example()
    value["template"]["input"]["occupancy"]["mrna_total_molar"] = 0
    result = sweep.sweep(value)
    validator("result").validate(result)
    assert result["status"] == "partial"
    result["points"][0]["reasons"] = []
    assert not validator("result").is_valid(result)
    monkeypatch.setattr(sweep.conditional, "predict_conditional", lambda *a: [])
    result = sweep.sweep(example())
    validator("result").validate(result)
    assert result["points"][0]["native"] is None and result["coverage"]["not_run"] == 5
    result["points"][1]["attempted"] = True
    assert not validator("result").is_valid(result)


def test_inconsistent_complete_result_is_rejected():
    original = sweep.sweep(example())
    for path, bad in [
        (["reason"], "failure"),
        (["coverage", "deadline_exceeded"], True),
        (["coverage", "not_run"], 1),
        (["points", 0, "status"], "not_run"),
        (["points", 0, "native_json_sha256"], None),
        (["model", "backend"], {}),
        (["extra"], 1),
    ]:
        result = copy.deepcopy(original)
        cursor = result
        for part in path[:-1]:
            cursor = cursor[part]
        cursor[path[-1]] = bad
        assert not validator("result").is_valid(result), path


@pytest.mark.parametrize(
    "path,bad",
    [
        (["response"], {}),
        (["response", "ar_actual"], None),
        (["response", "ar_actual"], True),
        (["response", "ar_actual"], 0),
        (["response", "ar_max"], "1"),
        (["response", "metastability_factor"], 2),
        (["response", "metastability_applied"], 1),
        (["response", "occupancy"], {}),
        (["response", "occupancy", "mode"], "supplied_fraction"),
        (["response", "occupancy", "status"], "failed"),
        (["response", "occupancy", "fraction"], -1),
        (["response", "occupancy", "fraction"], 2),
        (["response", "occupancy", "concentrations"], None),
        (["response", "occupancy", "concentrations", "complex_molar"], -1),
        (["response", "occupancy", "concentrations", "mrna_balance_error_molar"], True),
        (["response", "occupancy", "volume_fractions"], {}),
        (["response", "occupancy", "volume_fractions", "sum"], -1),
        (["response", "occupancy", "solver"], {}),
        (["response", "occupancy", "solver", "iterations"], True),
        (["response", "occupancy", "solver", "iterations"], -1),
        (["response", "occupancy", "solver", "iterations"], 257),
        (["response", "occupancy", "solver", "bracket_molar"], None),
        (["response", "occupancy", "solver", "bracket_molar"], [0]),
        (["response", "occupancy", "solver", "bracket_molar"], [-1, 0]),
        (["response", "occupancy", "solver", "scaled_residual"], True),
        (["errors"], [{"code": "bad", "message": "bad"}]),
        (["warnings"], None),
        (["warnings"], [{}]),
        (["warnings"], [{"code": "", "message": ""}]),
        (["warnings"], [{"code": "test", "message": 1}]),
        (["structural_cost_kcal_mol"], None),
        (["structural_cost_kcal_mol"], -1),
    ],
)
def test_malformed_success_is_retained_as_failure(monkeypatch, path, bad):
    original = sweep.conditional.predict_conditional

    def changed(request):
        native = original(request)
        cursor = native
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = bad
        return native

    monkeypatch.setattr(sweep.conditional, "predict_conditional", changed)
    result = sweep.sweep(example())
    assert result["status"] == "partial" and result["reason"] == "native_shape"
    assert result["coverage"]["attempted"] == 1
    assert result["coverage"]["failed"] == 1
    assert result["coverage"]["not_run"] == 5
    assert result["points"][0]["native"] is not None
    validator("result").validate(result)


@pytest.mark.parametrize("offset,accepted", [(0, True), (1, False)])
def test_raw_integer_conversion_ceiling_matches_schemas(monkeypatch, offset, accepted):
    request = example()
    request["ligand_total_molar"] = [2**1024 - 2**970 - 1 + offset]
    assert validator("request").is_valid(request) is accepted
    ticks = iter([0, 121, 121])
    monkeypatch.setattr(
        sweep, "time", type("Clock", (), {"monotonic": lambda: next(ticks)})
    )

    def forbidden(*args):
        raise AssertionError("deadline must prevent prediction")

    monkeypatch.setattr(sweep.conditional, "predict_conditional", forbidden)
    result = sweep.sweep(request)
    assert result["status"] == ("partial" if accepted else "invalid_input")
    validator("result").validate(result)
    if accepted:
        assert result["request"] == request
        assert result["coverage"]["not_run"] == 1
        assert result["points"][0]["ligand_total_molar"] == float.fromhex(
            "0x1.fffffffffffffp1023"
        )

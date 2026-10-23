"""Strict public shape contracts and status-dependent missingness."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from regsite.coupling import invalid_result, predict_coupling


def validator(name):
    schema = json.loads(Path(f"schemas/coupling-{name}-1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def example():
    return json.loads(Path("examples/coupling-single.json").read_text())


def test_all_examples_and_result_variants():
    request_schema, result_schema = validator("request"), validator("result")
    for name in ("single", "batch", "unsupported"):
        value = json.loads(Path(f"examples/coupling-{name}.json").read_text())
        request_schema.validate(value)
        result_schema.validate(predict_coupling(value, clock=lambda: 0))
    result_schema.validate(invalid_result("transport_refusal"))
    data = example()
    data["records"][0]["energies"]["upstream_total_kcal_mol"] = -1e6
    result_schema.validate(predict_coupling(data, clock=lambda: 0))
    data["records"][0]["sequence"] = "AAA"
    result_schema.validate(predict_coupling(data, clock=lambda: 0))
    data["records"][0] = None
    result_schema.validate(predict_coupling(data, clock=lambda: 0))
    ticks = iter([0, 10])
    result_schema.validate(predict_coupling(example(), clock=lambda: next(ticks)))


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("settings",),
        ("records", 0),
        ("records", 0, "energies"),
        ("records", 0, "upstream"),
    ],
)
def test_request_rejects_extra_fields(path):
    data = example()
    node = data
    for key in path:
        node = node[key]
    node["undeclared"] = 1
    assert not validator("request").is_valid(data)


@pytest.mark.parametrize("bad_id", ["x\n", "a b", "", "x" * 129, 3, "\u03b2"])
def test_schema_and_runtime_reject_invalid_id(bad_id):
    data = example()
    data["records"][0]["id"] = bad_id
    assert not validator("request").is_valid(data)
    assert (
        predict_coupling(data, clock=lambda: 0)["records"][0]["status"]
        == "invalid_input"
    )


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "other"),
        (("model", "backend"), {}),
        (("model", "beta_mol_per_kcal"), 1),
        (("model", "coefficient_domain", "distance_minus_4"), 0.0072),
        (("records", 0, "scores", "downstream_total", "value"), None),
        (("records", 0, "unfolding_correction"), 0),
        (("records", 0, "coefficient"), 0),
        (("records", 0, "reason"), "hidden_failure"),
        (("records", 0, "status"), "not_evaluated"),
        (("status",), "partial"),
        (("status",), "invalid_input"),
        (("coverage", "requested"), True),
        (("prediction_sha256",), "bad"),
    ],
)
def test_result_rejects_corrupted_states(path, value):
    result = copy.deepcopy(predict_coupling(example(), clock=lambda: 0))
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert not validator("result").is_valid(result)


def test_numerical_range_requires_an_explicit_missing_linear_value():
    result = predict_coupling(example(), clock=lambda: 0)
    result["status"] = "partial"
    result["records"][0].update(
        status="numerical_range", reason="linear_score_outside_binary64"
    )
    assert not validator("result").is_valid(result)
    result["records"][0]["scores"]["upstream_independent"]["value"] = None
    assert validator("result").is_valid(result)

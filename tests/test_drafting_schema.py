"""Public schemas enforce finite representations and status-dependent missingness."""

import copy
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from regsite import drafting


def validator(name):
    schema = json.loads(Path(f"schemas/drafting-{name}-1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def example():
    return json.loads(Path("examples/drafting-single.json").read_text())


def test_examples_and_all_failure_representations(monkeypatch):
    request_schema, result_schema = validator("request"), validator("result")
    for name in ("single", "batch", "unsupported"):
        request = json.loads(Path(f"examples/drafting-{name}.json").read_text())
        request_schema.validate(request)
        result_schema.validate(drafting.predict(request))
    result_schema.validate(drafting.invalid_result("invalid_transport"))
    for malformed in (None, {"id": "valid"}, {"id": "bad id"}):
        request = example()
        request["records"].append(malformed)
        result_schema.validate(drafting.predict(request))
    request = example()
    request["records"][0]["rates"].update(
        a1=1,
        a2=math.ulp(0.0),
        a_fold=float.fromhex("0x1.fffffffffffffp+1023"),
        a_elong=2,
    )
    result_schema.validate(drafting.predict(request))
    monkeypatch.setattr(drafting.math, "log", lambda value: math.inf)
    result_schema.validate(drafting.predict(example()))


@pytest.mark.parametrize("path", [(), ("records", 0), ("records", 0, "rates")])
def test_request_rejects_unknown_fields(path):
    data = example()
    node = data
    for key in path:
        node = node[key]
    node["extra"] = 1
    assert not validator("request").is_valid(data)
    result = drafting.predict(data)
    assert result["status"] != "complete"


@pytest.mark.parametrize(
    "path,value",
    [
        (("records", 0, "id"), "x\n"),
        (("records", 0, "id"), ""),
        (("records", 0, "rate_provenance"), " \n\t"),
        (("records", 0, "rate_provenance"), "x" * 1025),
        (("records", 0, "rates", "a1"), True),
        (("records", 0, "rates", "a1"), math.inf),
        (("records", 0, "rates", "a1"), 10**400),
        (("records",), []),
        (("records",), [None] * 101),
    ],
)
def test_schema_rejects_malformed_fields(path, value):
    data = example()
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert not validator("request").is_valid(data)
    assert drafting.predict(data)["status"] != "complete"


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "bad"),
        (("model", "backend"), {}),
        (("model", "theory_sha256"), "bad"),
        (("model", "rate_origin"), "default"),
        (("model", "id"), "other"),
        (("model", "source_doi"), "other"),
        (("prediction_sha256",), "a" * 64 + "\n"),
        (("request_sha256",), None),
        (("reason",), "hidden_failure"),
        (("coverage",), None),
        (("coverage", "complete"), False),
        (("coverage", "evaluated_records"), True),
        (("warnings",), []),
        (("records", 0, "index"), 100),
        (("records", 0, "id"), None),
        (("records", 0, "status"), "invalid_input"),
        (("records", 0, "reason"), "hidden_failure"),
        (("records", 0, "occupancies"), None),
        (("records", 0, "occupancies", "accessible", "value"), 1.1),
        (("records", 0, "occupancies", "accessible", "ln_value"), 1),
        (("records", 0, "occupancies", "accessible", "value"), None),
        (
            ("records", 0, "occupancies", "folded"),
            {"value": 0, "ln_value": None, "representation": "exact_zero"},
        ),
        (("records", 0, "throughput", "quantity", "value"), 0),
        (("records", 0, "throughput", "quantity", "ln_value"), None),
        (("records", 0, "throughput", "quantity", "ln_value"), math.inf),
        (("records", 0, "throughput", "quantity", "representation"), "underflow"),
        (("records", 0, "throughput", "quantity", "extra"), 1),
        (("status",), "partial"),
        (("status",), "invalid_input"),
    ],
)
def test_result_rejects_corrupted_states(path, value):
    result = copy.deepcopy(drafting.predict(example()))
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert not validator("result").is_valid(result)


def test_exact_zero_only_for_zero_fold_boundary():
    request = example()
    request["records"][0]["rates"]["a_fold"] = 0
    result = drafting.predict(request)
    validator("result").validate(result)
    result["records"][0]["occupancies"]["folded"] = {
        "value": None,
        "ln_value": -800,
        "representation": "underflow",
    }
    assert not validator("result").is_valid(result)


def test_refusals_require_reasons_and_no_values():
    request = example()
    request["records"][0]["rates"]["a1"] = 0
    result = drafting.predict(request)
    result["records"][0]["occupancies"] = drafting.predict(example())["records"][0][
        "occupancies"
    ]
    assert not validator("result").is_valid(result)
    invalid = drafting.invalid_result("reason")
    invalid["reason"] = None
    assert not validator("result").is_valid(invalid)

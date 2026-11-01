"""Offline machine contracts preserve missingness and the exact target roster."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from test_rbs_vector_design import Backend, example
from test_rbs_vector_design import fake as fake

from regsite import rbs
from regsite import rbs_vector_design as module


def validator(kind):
    schemas = {
        name: json.loads((Path("schemas") / name).read_text())
        for name in (
            "rbs-vector-design-request-1.schema.json",
            "rbs-vector-design-result-1.schema.json",
        )
    }
    registry = Registry().with_resources(
        (name, Resource.from_contents(schema)) for name, schema in schemas.items()
    )
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schemas[f"rbs-vector-design-{kind}-1.schema.json"], registry=registry
    )


def test_complete_schema_and_every_required_field(fake):
    value = example()
    request = validator("request")
    result = validator("result")
    request.validate(value)
    output = json.loads(json.dumps(module.design(value, Backend())))
    result.validate(output)
    for key in value:
        changed = copy.deepcopy(value)
        del changed[key]
        assert not request.is_valid(changed), key
    for key in output:
        changed = copy.deepcopy(output)
        del changed[key]
        assert not result.is_valid(changed), key


@pytest.mark.parametrize(
    "path,value",
    [
        (("unknown",), 1),
        (("selected",), None),
        (("proposal",), None),
        (("confirmation",), None),
        (("reason",), "wrong"),
        (("coverage", "all_candidates_scored"), False),
        (("coverage", "deadline_exceeded"), True),
        (("coverage", "failed"), 1),
        (("coverage", "stop_reason"), "wrong"),
        (("candidates", 0, "attempted"), False),
        (("candidates", 0, "native_admitted"), False),
        (("candidates", 0, "native_json_sha256"), None),
        (("candidates", 0, "objective"), None),
        (("candidates", 0, "targets", 0, "tir"), 0),
        (("candidates", 0, "targets", 0, "reason"), "wrong"),
        (("confirmation", "status"), "failed"),
        (("confirmation", "attempted"), False),
    ],
)
def test_contradictory_success_fields_rejected(fake, path, value):
    result = module.design(example(), Backend())
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert not validator("result").is_valid(result), path


def test_refusal_and_opaque_failed_payloads(monkeypatch):
    schema = validator("result")
    for value in (None, {}, [], {"wrong": True}):
        result = module.design(value, Backend())
        schema.validate(result)
        result["selected"] = {}
        assert not schema.is_valid(result)
    monkeypatch.setattr(rbs, "predict", lambda *args, **kwargs: {"unexpected": True})
    result = module.design(example(), Backend())
    schema.validate(result)
    assert result["coverage"]["not_run"] == 3
    result["candidates"][0]["native_admitted"] = True
    assert not schema.is_valid(result)
    result = module.design(example(), Backend())
    result["candidates"][1]["attempted"] = True
    assert not schema.is_valid(result)


@pytest.mark.parametrize("partial", [False, True])
def test_native_failure_and_partial_schema(monkeypatch, fake, partial):
    score = rbs.predict

    def fail(value, backend, **kwargs):
        native = score(value, backend, **kwargs)
        if not partial or value["sequence"][55] == "G":
            native.update(status="failed", sites=[], reason="artificial failure")
        return native

    monkeypatch.setattr(rbs, "predict", fail)
    result = module.design(example(), Backend())
    assert result["status"] == ("partial" if partial else "no_candidate")
    schema = validator("result")
    schema.validate(json.loads(json.dumps(result)))
    result["candidates"][0]["targets"][0]["tir"] = 0
    assert not schema.is_valid(result)

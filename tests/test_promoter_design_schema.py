"""Offline structural request/result schemas and explicit evidence distinctions."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from regsite import promoter_design as design
from regsite import promoter_io


def validator(name):
    names = (
        "promoter-design-request-1.schema.json",
        "promoter-design-result-1.schema.json",
        "promoter-request-1.0.schema.json",
        "promoter-result-1.0.schema.json",
    )
    schemas = {key: json.loads((Path("schemas") / key).read_bytes()) for key in names}
    registry = Registry().with_resources(
        (key, Resource.from_contents(schema)) for key, schema in schemas.items()
    )
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schemas[name], registry=registry)


def example():
    return json.loads(Path("examples/promoter-design-single.json").read_text())


def test_example_and_complete_native_result_validate():
    request = example()
    validator("promoter-design-request-1.schema.json").validate(request)
    result = design.design(request, clock=lambda: 0.0)
    assert result["status"] == "complete"
    check = validator("promoter-design-result-1.schema.json")
    check.validate(result)
    invalid = copy.deepcopy(result)
    invalid["confirmation"] = None
    assert not check.is_valid(invalid)
    invalid = copy.deepcopy(result)
    invalid["candidates"][0]["objective"] = None
    assert not check.is_valid(invalid)


@pytest.mark.parametrize("value", [None, [], {}, {"schema_version": "wrong"}])
def test_invalid_refusals_validate(value):
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "invalid_input"
    validator("promoter-design-result-1.schema.json").validate(result)


def test_opaque_failure_evidence_is_not_mistaken_for_admitted_native(monkeypatch):
    monkeypatch.setattr(
        promoter_io, "predict_batch", lambda *a, **k: {"unexpected": "shape"}
    )
    result = design.design(example(), clock=lambda: 0.0)
    check = validator("promoter-design-result-1.schema.json")
    check.validate(result)
    result["candidates"][0]["native_admitted"] = True
    assert not check.is_valid(result)


def test_integral_numbers_accepted_but_boolean_controls_rejected():
    request = example()
    request["editable_positions"] = [80.0]
    request["max_changes"] = 1.0
    check = validator("promoter-design-request-1.schema.json")
    assert check.is_valid(request)
    assert design.design(request, clock=lambda: 0.0)["status"] == "complete"
    request["max_changes"] = True
    assert not check.is_valid(request)
    request["max_changes"] = 1
    request["promoter"]["output"]["legacy_keys"] = 0
    assert not check.is_valid(request)


@pytest.mark.parametrize(
    "kind", ["failed", "unsupported", "late", "nonfinite", "nonobject"]
)
def test_partial_and_failure_envelopes_remain_schema_valid(kind, monkeypatch):
    value = example()
    value["limits"]["seconds_total"] = 1.0
    real = promoter_io.predict_batch
    now, calls = 0.0, 0

    def predict(*args, **kwargs):
        nonlocal now, calls
        calls += 1
        native = real(*args, **kwargs)
        if calls == 1:
            if kind == "nonfinite":
                return {"x": float("nan")}
            if kind == "nonobject":
                return []
            if kind == "late":
                now = 1.0
            record = native["results"][0]
            if kind == "failed":
                record["sites"][0].update(
                    status="failed",
                    reason="nonfinite_arithmetic",
                    selected=None,
                    tie_count=None,
                )
                promoter_io._summarize(record)
            if kind == "unsupported":
                record.update(
                    status="unsupported",
                    reasons=["model_unavailable"],
                    prediction_id=None,
                    coverage=None,
                    sites=[],
                    errors=[
                        {
                            "code": "model_unavailable",
                            "field": "model",
                            "message": "artificial refusal",
                        }
                    ],
                )
            native["batch"].update(
                status_counts={
                    status: int(status == record["status"])
                    for status in promoter_io.STATUSES
                },
                complete=record["status"] != "failed",
            )
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(value, clock=lambda: now)
    validator("promoter-design-result-1.schema.json").validate(result)
    assert result["status"] == (
        "no_candidate" if kind in ("nonfinite", "nonobject") else "partial"
    )

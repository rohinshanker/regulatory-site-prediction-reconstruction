"""Machine contracts retain null/failure distinctions and identity fields."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from test_design import backend, example, native

from regsite import design


def validator(kind):
    schema = json.loads(Path(f"schemas/rbs-design-{kind}-1.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def test_request_and_complete_result(monkeypatch):
    monkeypatch.setattr(design, "predict", native)
    value = example()
    validator("request").validate(value)
    result = design.design(value, backend())
    validator("result").validate(json.loads(json.dumps(result)))
    for key in list(result):
        changed = copy.deepcopy(result)
        del changed[key]
        assert not validator("result").is_valid(changed), key
    for key in list(value):
        changed = copy.deepcopy(value)
        del changed[key]
        assert not validator("request").is_valid(changed), key


@pytest.mark.parametrize("status", ["failed", "unsupported", "no_candidate"])
@pytest.mark.parametrize("some_success", [False, True])
def test_failed_results_schema(monkeypatch, status, some_success):
    def scorer(value, engine, **kwargs):
        result = native(value, engine, **kwargs)
        if not some_success or value["sequence"][4] == "G":
            result.update(status=status, reason="test_failure", sites=[])
        return result

    monkeypatch.setattr(design, "predict", scorer)
    result = design.design(example(), backend())
    validator("result").validate(json.loads(json.dumps(result)))
    assert result["status"] == ("partial" if some_success else "no_candidate")
    result["candidates"][0]["score"] = {"tir": 0, "log_tir": 0, "absolute_log_error": 0}
    assert not validator("result").is_valid(result)


def test_invalid_and_unstarted_results(monkeypatch):
    schema = validator("result")
    value = design.invalid_result("invalid")
    schema.validate(value)
    value["selected"] = {}
    assert not schema.is_valid(value)
    monkeypatch.setattr(design, "predict", lambda *a, **kw: {})
    result = design.design(example(), backend())
    schema.validate(result)
    assert result["coverage"]["not_run"] == 3
    result["candidates"][1]["attempted"] = True
    assert not schema.is_valid(result)


def test_cross_status_and_unknown_fields_rejected(monkeypatch):
    monkeypatch.setattr(design, "predict", native)
    original = design.design(example(), backend())
    for path, value in [
        (["unknown"], 1),
        (["selected"], None),
        (["reason"], "wrong"),
        (["confirmation", "status"], "failed"),
        (["coverage", "all_candidates_scored"], False),
        (["candidates", 0, "native_sha256"], None),
        (["candidates", 0, "reason"], "wrong"),
    ]:
        result = copy.deepcopy(original)
        target = result
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert not validator("result").is_valid(result), path

"""Independent-review regressions for complete typed native failure results."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from test_design import backend, example, native

from regsite import design
from regsite.design_io import digest
from regsite.profiles import get_profile


def assert_schema(result):
    schema = json.loads(Path("schemas/rbs-design-result-1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(json.loads(json.dumps(result)))


@pytest.mark.parametrize("reply", [[], "unexpected payload", True])
@pytest.mark.parametrize("phase", ["candidate", "confirmation"])
def test_nonobject_native_payload_retains_hash_and_valid_refusal(
    monkeypatch, reply, phase
):
    calls = []

    def score(value, engine, **kwargs):
        calls.append(value)
        if len(calls) == (1 if phase == "candidate" else 5):
            return copy.deepcopy(reply)
        result = native(value, engine, **kwargs)
        result.update(
            schema_version=get_profile(kwargs["profile"]).schema_version, id=value["id"]
        )
        return result

    monkeypatch.setattr(design, "predict", score)
    result = design.design(example(), backend())
    assert result["selected"] is None
    assert len(result["candidates"]) == 4
    failed = result["candidates"][0] if phase == "candidate" else result["confirmation"]
    assert failed["native"] is None
    assert failed["native_sha256"] == digest(reply)
    assert failed["status"] == "failed"
    assert_schema(result)


@pytest.mark.parametrize("field", ["schema_version", "id"])
@pytest.mark.parametrize("mode", ["mismatch", "missing"])
@pytest.mark.parametrize("phase", ["candidate", "confirmation"])
def test_record_identity_contradiction_is_fatal(monkeypatch, field, mode, phase):
    calls = []

    def score(value, engine, **kwargs):
        calls.append(value)
        result = native(value, engine, **kwargs)
        result.update(
            schema_version=get_profile(kwargs["profile"]).schema_version, id=value["id"]
        )
        if phase == "candidate" or len(calls) == 5:
            if mode == "missing":
                del result[field]
            else:
                result[field] = "contradictory-identity"
        return result

    monkeypatch.setattr(design, "predict", score)
    result = design.design(example(), backend())
    assert result["selected"] is None
    assert result["coverage"]["prediction_calls"] == (1 if phase == "candidate" else 5)
    assert result["confirmation"]["status"] != "verified"
    assert_schema(result)


def test_full_256_candidate_boundary_and_refusal_before_scoring(monkeypatch):
    value = example()
    value["profile"] = "context2017"
    value["rbs"].update(sequence="A" * 100 + "ATG" + "A" * 97, start_positions=[100])
    value.update(editable_positions=list(range(85)), max_changes=1)
    value["limits"].update(max_candidates=256, seconds_total=120)
    calls = []

    def score(request, engine, **kwargs):
        calls.append(request)
        result = native(request, engine, **kwargs)
        result.update(
            schema_version=get_profile(kwargs["profile"]).schema_version,
            id=request["id"],
        )
        return result

    monkeypatch.setattr(design, "predict", score)
    result = design.design(value, backend())
    assert result["status"] == "complete" and result["coverage"]["planned"] == 256
    assert len(calls) == 257
    value["editable_positions"].append(85)
    refused = design.design(value, backend())
    assert refused["reason"] == "search_space_limit" and len(calls) == 257
    assert_schema(result)
    assert_schema(refused)

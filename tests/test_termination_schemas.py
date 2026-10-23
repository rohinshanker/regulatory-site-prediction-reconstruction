"""Strict schema shapes, missingness and source-identity constraints."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from test_termination import FakeBackend, request

from regsite import termination
from regsite.termination_backend import TerminationBackendError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    name: json.loads((ROOT / f"schemas/termination-{name}-1.schema.json").read_text())
    for name in ("request", "result", "backend")
}


def validate(name, value):
    jsonschema.Draft202012Validator(SCHEMAS[name]).validate(value)


def backend_identity():
    """Synthetic build labels for structural tests, not an executable receipt."""
    source = json.loads(
        (ROOT / "benchmarks/termination/source-manifest.json").read_text()
    )
    return {
        "schema_version": "termination-backend-1",
        "profile": "transtermhp-2.09-fragment-1",
        "source": {
            "archive_sha256": source["source_archive"]["sha256"],
            "null_patch_sha256": source["compatibility_patch"]["sha256"],
            "prototype_patch_sha256": source["prototype_correction"]["patch_sha256"],
        },
        "build": {
            "compiler": "structural-test",
            "compiler_sha256": "a" * 64,
            "compiler_version": "structural-test",
            "platform": "structural-test",
            "machine": "structural-test",
            "standard_library": "structural-test",
            "flags": [
                "-g",
                "-O3",
                "-Wall",
                "-pedantic",
                "-std=c++11",
                "-ffp-contract=off",
            ],
            "extra_flags_sha256": "b" * 64,
        },
        "binary": {"bytes": 10, "sha256": "c" * 64},
        "table": {"bytes": 45788, "sha256": source["background"]["sha256"]},
    }


def candidate():
    return {
        "candidate_id": "candidate-0001",
        "strand": "+",
        "hairpin": {"start": 70, "end": 86},
        "tail": {"start": 86, "end": 101},
        "status": "ok",
        "confidence": 78,
        "hairpin_score": "-11.8",
        "tail_score": "-3.87583",
        "native": {
            "id": "TERM 1",
            "context": "F",
            "printed_confidence": 78,
            "notes": "",
        },
    }


@pytest.fixture
def completed(monkeypatch):
    backend = FakeBackend()
    backend.identity = backend_identity()
    monkeypatch.setattr(termination, "parse_output", lambda *args: [candidate()])
    sequence = json.loads(
        (ROOT / "benchmarks/termination/native-tie-control.json").read_text()
    )["sequence"]
    return termination.predict_termination(
        request({"id": "fixture", "sequence": sequence}),
        backend=backend,
        clock=lambda: 0,
    )


def test_schema_documents_and_embedded_backend_agree():
    for schema in SCHEMAS.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    backend = {
        k: v
        for k, v in SCHEMAS["backend"].items()
        if k not in {"$schema", "$id", "title"}
    }
    assert SCHEMAS["result"]["$defs"]["backend"] == backend
    validate("backend", backend_identity())


@pytest.mark.parametrize("name", ["single", "batch", "unsupported"])
def test_shipped_artificial_examples_are_valid_requests(name):
    value = json.loads((ROOT / f"examples/termination-{name}.json").read_text())
    validate("request", value)
    validate("result", termination.predict_termination(value, clock=lambda: 0))


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"records": []},
        request(max_seconds=True),
        request(per_record_seconds=61),
        request({"id": "not safe", "sequence": "AC"}),
        request({"id": "a", "sequence": []}),
    ],
)
def test_invalid_request_shapes(value):
    with pytest.raises(jsonschema.ValidationError):
        validate("request", value)


def test_request_unknown_fields_rejected():
    value = request()
    value["settings"]["temperature"] = 37
    with pytest.raises(jsonschema.ValidationError):
        validate("request", value)


def test_complete_result(completed):
    validate("result", completed)
    assert completed["coverage"]["admitted_candidate_scores"] == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        request(None),
        request({"id": "short", "sequence": "AC"}),
        request({"id": "zero", "sequence": "AC" * 37 + "A"}),
        request({"id": "uniform", "sequence": "AC" + "G" * 76 + "AC"}),
    ],
)
def test_refusal_and_unsupported_results(value):
    validate("result", termination.predict_termination(value, clock=lambda: 0))


def test_deadline_and_process_failure_results():
    times = iter([0, 1])
    result = termination.predict_termination(
        request(max_seconds=1), clock=lambda: next(times)
    )
    validate("result", result)
    error = TerminationBackendError("fixture", code="native_exit", diagnostics=None)
    backend = FakeBackend(error)
    backend.identity = backend_identity()
    validate("result", termination.predict_termination(request(), backend=backend))


def test_boundary_missing_confidence_is_valid(completed):
    value = copy.deepcopy(completed)
    item = value["records"][0]["candidates"][0]
    item.update(
        status="boundary_ambiguous",
        confidence=None,
        hairpin={"start": 1, "end": 60},
        tail={"start": 60, "end": 75},
    )
    item["native"].update(context="G", printed_confidence=None)
    value["coverage"]["admitted_candidate_scores"] = 0
    validate("result", value)


@pytest.mark.parametrize(
    "path,value",
    [
        (("unknown",), 1),
        (("model", "extra"), 1),
        (("model", "source_doi"), "other"),
        (("model", "backend", "source", "archive_sha256"), "0" * 64),
        (("model", "backend", "build", "flags"), ["-flto"]),
        (("model", "backend", "build", "compiler"), "/private/compiler"),
        (("model", "backend", "build", "machine"), "bad\nlabel"),
        (("model", "backend", "binary", "bytes"), True),
        (("model", "backend", "table", "sha256"), "0" * 64),
        (("prediction_sha256",), "short"),
        (("settings", "max_seconds"), False),
        (("coverage", "successful_records"), -1),
        (("records", 0, "status"), "maybe"),
        (("records", 0, "index"), True),
        (("records", 0, "input"), None),
        (("records", 0, "attempted"), False),
        (("records", 0, "execution", "stdout_complete"), False),
        (("records", 0, "execution", "returncode"), -6),
        (("records", 0, "execution", "stderr_bytes"), 65537),
        (("records", 0, "candidates"), None),
        (("records", 0, "candidates", 0, "extra"), 1),
        (("records", 0, "candidates", 0, "native", "extra"), 1),
        (("records", 0, "candidates", 0, "native", "context"), "g"),
        (("records", 0, "candidates", 0, "confidence"), None),
        (("records", 0, "candidates", 0, "confidence"), True),
        (("records", 0, "candidates", 0, "hairpin_score"), -11.8),
        (("records", 0, "candidates", 0, "tail_score"), "NaN"),
        (("records", 0, "candidates", 0, "strand"), "?"),
        (("records", 0, "candidates", 0, "hairpin", "start"), -1),
        (("records", 0, "candidates", 0, "tail", "end"), 100001),
    ],
)
def test_result_semantic_shape_negatives(completed, path, value):
    result = copy.deepcopy(completed)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(jsonschema.ValidationError):
        validate("result", result)


def test_complete_cannot_hide_failed_record(completed):
    value = copy.deepcopy(completed)
    value["records"][0].update(
        status="backend_failure", reason="native_timeout", candidates=None
    )
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)
    value["status"] = "partial"
    validate("result", value)
    value["records"][0]["candidates"] = []
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)


@pytest.mark.parametrize("context", ["F", "G"])
def test_boundary_cannot_export_either_confidence(completed, context):
    value = copy.deepcopy(completed)
    item = value["records"][0]["candidates"][0]
    item.update(hairpin={"start": 1, "end": 60}, tail={"start": 60, "end": 75})
    item["native"]["context"] = context
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)
    item.update(status="boundary_ambiguous", confidence=None)
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)
    item["native"]["printed_confidence"] = None
    validate("result", value)
    item["confidence"] = 78
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)


@pytest.mark.parametrize("context", ["G", "f"])
def test_forward_normal_candidate_requires_context_f(completed, context):
    value = copy.deepcopy(completed)
    value["records"][0]["candidates"][0]["native"]["context"] = context
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)


@pytest.mark.parametrize(
    "path",
    [
        ("request_sha256",),
        ("prediction_sha256",),
        ("result_sha256",),
        ("model", "backend", "build", "compiler"),
        ("model", "backend", "build", "compiler_sha256"),
        ("records", 0, "id"),
        ("records", 0, "input", "sequence_sha256"),
        ("records", 0, "candidates", 0, "candidate_id"),
        ("records", 0, "candidates", 0, "hairpin_score"),
        ("records", 0, "candidates", 0, "tail_score"),
        ("records", 0, "candidates", 0, "native", "id"),
    ],
)
def test_pattern_fields_reject_final_newline(completed, path):
    value = copy.deepcopy(completed)
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] += "\n"
    with pytest.raises(jsonschema.ValidationError):
        validate("result", value)


def test_request_id_rejects_final_newline():
    with pytest.raises(jsonschema.ValidationError):
        validate("request", request({"id": "a\n", "sequence": "AC"}))


def test_normal_candidate_requires_printed_confidence(completed):
    completed["records"][0]["candidates"][0]["native"]["printed_confidence"] = None
    with pytest.raises(jsonschema.ValidationError):
        validate("result", completed)

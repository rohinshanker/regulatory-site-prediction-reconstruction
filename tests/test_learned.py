"""Learned score provenance, domain disclosure, failures and offline CLI."""

import io
import json
import sys
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest
from test_rbs import AlgebraBackend, request

from regsite.backend import RnaStructure
from regsite.features import feature_names
from regsite.learned import predict_learned, validate_model
from regsite.learned_cli import main
from regsite.learning import fit_ridge
from regsite.sequence import reverse_complement

DOMAIN = {"hosts": ["synthetic"], "anti_sd": ["ACCUCCUUA"], "temperatures_c": [37]}


def model(kind="sequence-v1", **metadata):
    names = feature_names(kind)
    return fit_ridge(
        [[0] * len(names)] * 2,
        [2, 4],
        feature_names=names,
        record_ids=["a", "b"],
        penalty=1,
        provenance={
            "dataset_id": "synthetic",
            "split_id": "synthetic-train",
            "feature_kind": kind,
            "target_name": "synthetic assay response",
            "target_units": "log2 arbitrary units",
            "training_domain": json.dumps(DOMAIN),
            **metadata,
        },
    )


def test_sequence_inference_is_backend_free_and_not_an_energy():
    artifact = model()
    result = predict_learned(request(host="synthetic"), artifact)
    assert result["status"] == "ok"
    assert result["score_log2"] == 3
    assert result["score_scale"] == "log2_assay_response"
    assert result["mechanistic_reference"] is None
    assert "energies" not in result
    assert result["artifact_sha256"] == artifact.to_dict()["artifact_sha256"]
    assert result["target"]["training_dataset"] == "synthetic"
    assert "outside_declared_training_host_or_settings" not in result["warnings"]
    assert result == predict_learned(request(host="synthetic"), artifact)
    reverse = predict_learned(
        request(
            host="synthetic",
            strand="-",
            sequence=reverse_complement(request()["sequence"].replace("T", "U")),
        ),
        artifact,
    )
    assert reverse["features"] == result["features"]
    assert reverse["score_log2"] == result["score_log2"]
    assert reverse["start_codon"] == {"start": 50, "end": 53, "strand": "-"}


@pytest.mark.parametrize(
    "changes",
    [
        {"host": None},
        {"host": "synthetic", "anti_sd": "ACCUCCUUU"},
        {"host": "synthetic", "temperature_c": 30},
    ],
)
def test_domain_mismatch_is_disclosed(changes):
    result = predict_learned(request(**changes), model())
    assert result["status"] == "ok"
    assert "outside_declared_training_host_or_settings" in result["warnings"]


@pytest.mark.parametrize(
    "domain",
    [
        None,
        [],
        {},
        {**DOMAIN, "extra": 1},
        {**DOMAIN, "hosts": None},
        {**DOMAIN, "hosts": []},
        {**DOMAIN, "hosts": ["x"] * 101},
        {**DOMAIN, "hosts": [1]},
        {**DOMAIN, "hosts": [" "]},
        {**DOMAIN, "temperatures_c": [True]},
        {**DOMAIN, "temperatures_c": [float("inf")]},
        {**DOMAIN, "temperatures_c": [101]},
        {**DOMAIN, "anti_sd": ["accticctt"]},
        {**DOMAIN, "anti_sd": ["ACCUCCUU"]},
        {**DOMAIN, "anti_sd": [None]},
    ],
)
def test_invalid_training_domains(domain):
    with pytest.raises(ValueError):
        validate_model(model(training_domain=json.dumps(domain)))


def test_invalid_model_recipes_and_missing_provenance():
    with pytest.raises(ValueError, match="JSON"):
        validate_model(model(training_domain="not JSON"))
    missing = replace(model(), provenance={"dataset_id": "d", "split_id": "s"})
    with pytest.raises(ValueError, match="provenance"):
        validate_model(missing)
    with pytest.raises(ValueError, match="feature names"):
        validate_model(model(feature_kind="context-energy-sequence-v1"))
    with pytest.raises(ValueError, match="unsupported feature"):
        validate_model(model(feature_kind="unknown"))


def test_explicit_failures_and_setup_errors(monkeypatch):
    artifact = model()
    assert predict_learned(None, artifact)["status"] == "invalid_input"
    assert (
        predict_learned(request(start_positions=None), artifact)["status"]
        == "unsupported"
    )
    for seconds in (0, 121, True, float("nan")):
        with pytest.raises(ValueError, match="budget"):
            predict_learned(request(), artifact, seconds=seconds)
    with pytest.raises(ValueError, match="backend"):
        predict_learned(request(), model("context-energy-sequence-v1"))

    def fail(*args):
        raise ValueError("numeric failure")

    monkeypatch.setattr(type(artifact), "predict", fail)
    result = predict_learned(request(), artifact)
    assert result["status"] == "failed" and result["score_log2"] is None
    assert result["reason"] == "numeric failure"


def test_energy_reference_is_separate_and_failures_remain_missing():
    artifact = model("context-energy-sequence-v1")
    result = predict_learned(request(), artifact, AlgebraBackend())
    assert result["status"] == "ok" and result["score_log2"] == 3
    assert result["mechanistic_reference"]["model"]["id"].startswith("context2017-")
    assert len(result["features"]["values"]) == 24
    failed = predict_learned(request(), artifact, AlgebraBackend(fail=True))
    assert failed["status"] == "failed" and failed["score_log2"] is None
    assert failed["reason"] == "mechanistic_feature_unavailable"


def test_learned_cli_batch_stdin_and_setup_errors(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "model.json"
    inputs = tmp_path / "requests.json"
    artifact.write_text(json.dumps(model().to_dict()))
    inputs.write_text(json.dumps(request()))
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    assert main([str(artifact), str(inputs)]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["score_log2"] == 3
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([None, request()])))
    assert main([str(artifact), "-"]) == 1
    assert len(json.loads(capsys.readouterr().out)["results"]) == 2
    artifact.write_text(json.dumps(model("context-energy-sequence-v1").to_dict()))
    assert main([str(artifact), str(inputs)]) == 2
    assert "requires --backend-root" in capsys.readouterr().err
    monkeypatch.setattr(RnaStructure, "open", lambda root: AlgebraBackend())
    assert main([str(artifact), str(inputs), "--backend-root", "/synthetic"]) == 0
    capsys.readouterr()
    assert main([str(artifact), "/nonexistent"]) == 2
    assert "regsite-learned" in capsys.readouterr().err
    artifact.write_text("{}")
    assert main([str(artifact), str(inputs)]) == 2
    assert "artifact" in capsys.readouterr().err


def test_real_learned_energy_pipeline(real_backend):
    result = predict_learned(
        request(), model("context-energy-sequence-v1"), real_backend
    )
    assert result["status"] == "ok"
    assert result["mechanistic_reference"]["backend"]["version"] == "6.6"


def test_versioned_learned_result_schema():
    schema = json.loads(Path("schemas/rbs-learned-result-1.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    for value in (request(), None, request(start_positions=None)):
        result = predict_learned(value, model())
        jsonschema.validate(result, schema)
    result["score_log2"] = 0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, schema)

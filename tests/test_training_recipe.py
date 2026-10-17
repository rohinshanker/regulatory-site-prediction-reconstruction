"""Reproducible public-data recipe boundaries and exact cached-feature joins."""

import hashlib
import json
import runpy
import sys

import pytest
from test_rbs import AlgebraBackend, request

from experiments.rbs import standby
from regsite.rbs import predict


def fixture(tmp_path, monkeypatch):
    rows = [
        {
            "id": str(i),
            "sequence": request()["sequence"],
            "start": 20,
            "family": str(i // 2),
            "observed": i + 1,
        }
        for i in range(6)
    ]
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"records": rows}))
    monkeypatch.setattr(
        standby, "SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest()
    )
    predictions = tmp_path / "context.json"
    predictions.write_text(
        json.dumps(
            {
                "results": [
                    predict(
                        request(id=r["id"], host=standby.HOST),
                        AlgebraBackend(),
                        profile="context2017",
                    )
                    for r in rows
                ]
            }
        )
    )
    return source, predictions, tmp_path / "models"


def test_reproducible_recipe_and_cli(tmp_path, monkeypatch, capsys):
    source, predictions, output = fixture(tmp_path, monkeypatch)
    args = [str(source), str(predictions), str(output), "--code-commit", "a" * 40]
    standby.main(args)
    result = json.loads(capsys.readouterr().out)
    assert result["data_role"] == "development"
    assert set(result["models"]) == set(standby.KINDS)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert standby.train(source, predictions, output, "a" * 40) == result
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    artifact = json.loads((output / "sequence-v1.json").read_text())
    assert artifact["provenance"]["code_commit"] == "a" * 40
    assert artifact["provenance"]["data_licence"].startswith("CC-BY-3.0")
    monkeypatch.setattr(sys, "argv", ["standby", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exc:
        runpy.run_module("experiments.rbs.standby", run_name="__main__")
    assert exc.value.code == 0


def test_source_and_identity_rejection(tmp_path, monkeypatch):
    source, predictions, output = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Git SHA"):
        standby.train(source, predictions, output, "unversioned")
    cached = json.loads(predictions.read_text())
    cached["results"].append(cached["results"][0])
    predictions.write_text(json.dumps(cached))
    with pytest.raises(ValueError, match="exactly"):
        standby.train(source, predictions, output, "a" * 40)


def test_bad_energy_cache_does_not_write_partial_models(tmp_path, monkeypatch):
    source, predictions, output = fixture(tmp_path, monkeypatch)
    cached = json.loads(predictions.read_text())
    cached["results"][0]["status"] = "failed"
    predictions.write_text(json.dumps(cached))
    with pytest.raises(ValueError, match="successful prediction"):
        standby.train(source, predictions, output, "a" * 40)
    assert not output.exists()
    cached["results"] = cached["results"][:1]
    predictions.write_text(json.dumps(cached))
    with pytest.raises(ValueError, match="exactly"):
        standby.train(source, predictions, output, "a" * 40)
    source.write_text("{}")
    with pytest.raises(ValueError, match="source hash"):
        standby.train(source, predictions, output, "a" * 40)


@pytest.mark.parametrize("observed", [True, 0, float("inf")])
def test_nonpositive_or_invalid_assay_target(tmp_path, monkeypatch, observed):
    source, predictions, output = fixture(tmp_path, monkeypatch)
    data = json.loads(source.read_text())
    data["records"][0]["observed"] = observed
    source.write_text(json.dumps(data))
    monkeypatch.setattr(
        standby, "SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="positive finite"):
        standby.train(source, predictions, output, "a" * 40)

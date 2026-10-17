"""Real CLI single/batch use and explicit command/setup failures."""

import io
import json
import runpy
import sys

import pytest
from test_rbs import AlgebraBackend, request

from regsite.backend import RnaStructure
from regsite.cli import main
from regsite.structures import BackendError


def test_single_batch_csv_and_exit_status(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(RnaStructure, "open", lambda root: AlgebraBackend())
    path = tmp_path / "input.json"
    path.write_text(json.dumps(request()))
    assert main([str(path), "--backend-root", "/unused"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["status"] == "ok"
    path.write_text(json.dumps([request(), None]))
    assert main([str(path), "--backend-root", "/unused", "--format", "csv"]) == 1
    output = capsys.readouterr().out
    assert "invalid_input" in output and "ok" in output
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request())))
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/unused")
    assert main(["-"]) == 0
    assert len(json.loads(capsys.readouterr().out)["results"]) == 1


def test_command_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    assert main(["-"]) == 2
    assert "backend-root" in capsys.readouterr().err
    assert main(["-", "--backend-root", "/unused", "--seconds-per-record", "nan"]) == 2
    assert "seconds-per-record" in capsys.readouterr().err
    assert main([str(tmp_path / "missing"), "--backend-root", "/unused"]) == 2
    assert "No such file" in capsys.readouterr().err
    monkeypatch.setattr(sys, "stdin", io.StringIO("bad-json"))
    assert main(["-", "--backend-root", "/unused"]) == 2
    assert "JSON" in capsys.readouterr().err

    def fail(root):
        raise BackendError("installation incomplete")

    monkeypatch.setattr(RnaStructure, "open", fail)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert main(["-", "--backend-root", "/unused"]) == 2
    assert "installation incomplete" in capsys.readouterr().err


def test_module_entrypoint(monkeypatch):
    monkeypatch.setattr("regsite.cli.main", lambda: 2)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite", run_name="__main__")
    assert exc.value.code == 2


def test_real_single_and_batch_cli(real_backend, tmp_path, capsys):
    path = tmp_path / "input.json"
    value = {
        "id": "synthetic-smoke",
        "sequence": "AAAGGAGGAAAAAAATGAAAAAA",
        "anti_sd": "ACCUCCUUA",
    }
    path.write_text(json.dumps(value))
    assert main([str(path), "--backend-root", str(real_backend.root)]) == 0
    single = json.loads(capsys.readouterr().out)["results"][0]
    path.write_text(json.dumps([value, dict(value, id="invalid", sequence="N")]))
    assert main([str(path), "--backend-root", str(real_backend.root)]) == 1
    batch = json.loads(capsys.readouterr().out)["results"]
    assert batch[0] == single
    assert batch[1]["status"] == "invalid_input"


def test_refined_profile_cli_schema(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(RnaStructure, "open", lambda root: AlgebraBackend())
    path = tmp_path / "input.json"
    path.write_text(json.dumps(request()))
    assert (
        main([str(path), "--backend-root", "/unused", "--profile", "footprint2017"])
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "1.1"
    assert output["results"][0]["model"]["parameters"]["coding_footprint_nt"] == 13
    assert (
        main(
            [
                str(path),
                "--backend-root",
                "/unused",
                "--profile",
                "footprint2017",
                "--format",
                "csv",
            ]
        )
        == 0
    )
    csv_output = capsys.readouterr().out
    assert "schema_version,model_id,prediction_id" in csv_output.splitlines()[0]
    assert "footprint2017-rnastructure-6.6-reconstruction-1" in csv_output

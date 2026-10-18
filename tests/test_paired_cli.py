"""Offline paired command, atomic setup errors and explicit completion exits."""

import io
import json
import runpy
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from test_paired import document

from regsite import paired_cli
from regsite.backend import RnaStructure


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_offline_real_promoter(tmp_path, capsys, monkeypatch, fmt):
    def prohibited(*args, **kwargs):
        raise AssertionError("Promoter comparison attempted network or subprocess")

    monkeypatch.setattr(socket, "socket", prohibited)
    monkeypatch.setattr(subprocess, "Popen", prohibited)
    path = tmp_path / "pair.json"
    path.write_text(json.dumps(document()))
    assert paired_cli.main([str(path), "--format", fmt]) == 0
    result = capsys.readouterr()
    assert result.err == ""
    assert result.out.startswith("{" if fmt == "json" else "schema_version,")


@pytest.mark.parametrize(
    "state,code",
    [("partial", 1), ("unavailable", 1), ("incomparable", 0), ("complete", 0)],
)
def test_explicit_exit_semantics(monkeypatch, capsys, state, code):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    monkeypatch.setattr(paired_cli, "predict_pair", lambda *args: {"status": state})
    monkeypatch.setattr(paired_cli, "export_text", lambda *args: state + "\n")
    assert paired_cli.main(["-"]) == code
    assert capsys.readouterr().out == state + "\n"


def test_rbs_requires_backend_and_accepts_existing_environment(monkeypatch, capsys):
    request = document("rbs")
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    assert paired_cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "set --backend-root" in output.err
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/fixture-no-fold")
    seen = []

    def open_backend(root):
        seen.append(root)
        return RnaStructure(Path(root), {"fixture": "empty-roster"})

    monkeypatch.setattr(RnaStructure, "open", open_backend)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    assert paired_cli.main(["-"]) == 0
    assert seen == ["/fixture-no-fold"]
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


def test_setup_and_encoding_errors_emit_no_partial_stdout(
    monkeypatch, tmp_path, capsys
):
    assert paired_cli.main([str(tmp_path / "absent")]) == 2
    assert capsys.readouterr().out == ""
    monkeypatch.setattr(sys, "stdin", io.StringIO("[]"))
    assert paired_cli.main(["-"]) == 2
    assert capsys.readouterr().out == ""
    request = document()
    request["pair"]["pair_id"] = "\ud800"
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    assert paired_cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err.startswith("regsite-compare:")


def test_module_entrypoint(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["regsite-compare", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(document())))
    with pytest.raises(SystemExit) as error:
        runpy.run_module("regsite.paired_cli", run_name="__main__")
    assert error.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"

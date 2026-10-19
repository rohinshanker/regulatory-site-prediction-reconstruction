"""Offline paired command, atomic setup errors and explicit completion exits."""

import io
import json
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from test_paired import document

from regsite import paired_cli, promoter
from regsite.backend import RnaStructure


def stdin(text):
    """Expose the same binary interface as the interpreter's real stdin."""
    return io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")


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
    monkeypatch.setattr(sys, "stdin", stdin("{}"))
    monkeypatch.setattr(paired_cli, "predict_pair", lambda *args: {"status": state})
    monkeypatch.setattr(paired_cli, "export_text", lambda *args: state + "\n")
    assert paired_cli.main(["-"]) == code
    assert capsys.readouterr().out == state + "\n"


def test_rbs_requires_backend_and_accepts_existing_environment(monkeypatch, capsys):
    request = document("rbs")
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(request)))
    assert paired_cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "set --backend-root" in output.err
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/fixture-no-fold")
    seen = []

    def open_backend(root):
        seen.append(root)
        return RnaStructure(Path(root), {"fixture": "empty-roster"})

    monkeypatch.setattr(RnaStructure, "open", open_backend)
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(request)))
    assert paired_cli.main(["-"]) == 0
    assert seen == ["/fixture-no-fold"]
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


def test_setup_and_encoding_errors_emit_no_partial_stdout(
    monkeypatch, tmp_path, capsys
):
    assert paired_cli.main([str(tmp_path / "absent")]) == 2
    assert capsys.readouterr().out == ""
    monkeypatch.setattr(sys, "stdin", stdin("[]"))
    assert paired_cli.main(["-"]) == 2
    assert capsys.readouterr().out == ""
    request = document()
    request["pair"]["pair_id"] = "\ud800"
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(request)))
    assert paired_cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err.startswith("regsite-compare:")


def test_module_entrypoint(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["regsite-compare", "-"])
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(document())))
    with pytest.raises(SystemExit) as error:
        runpy.run_module("regsite.paired_cli", run_name="__main__")
    assert error.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


def test_missing_promoter_parameters_is_atomic(monkeypatch, capsys):
    def absent():
        raise promoter.ParameterError("missing parameter resource")

    monkeypatch.setattr(promoter, "load_parameters", absent)
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(document())))
    assert paired_cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "missing parameter resource" in output.err


def test_raw_file_crlf_limit_before_newline_translation(tmp_path):
    raw = json.dumps(document()).encode("utf-8")
    maximum = 2_000_000
    padding = maximum - len(raw)
    raw += b"\r\n" * (padding // 2) + b" " * (padding % 2)
    path = tmp_path / "raw.json"
    path.write_bytes(raw)
    command = [sys.executable, "-m", "regsite.paired_cli", str(path)]
    accepted = subprocess.run(command, capture_output=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    path.write_bytes(raw + b" ")
    refused = subprocess.run(command, capture_output=True, check=False)
    assert refused.returncode == 2 and refused.stdout == b""
    assert b"received input" in refused.stderr


def test_stdin_and_stdout_remain_utf8_under_encoding_override():
    request = document()
    request["pair"]["pair_id"] = "unicode-µ"
    raw = json.dumps(request, ensure_ascii=False).encode("utf-8")
    command = [sys.executable, "-m", "regsite.paired_cli", "-", "--format", "csv"]
    env = dict(os.environ, PYTHONIOENCODING="latin-1")
    good = subprocess.run(command, input=raw, env=env, capture_output=True, check=False)
    assert good.returncode == 0, good.stderr
    assert "unicode-µ" in good.stdout.decode("utf-8")
    bad = subprocess.run(
        command,
        input=raw.replace("µ".encode(), b"\xff"),
        env=env,
        capture_output=True,
        check=False,
    )
    assert bad.returncode == 2 and bad.stdout == b""
    assert b"invalid paired JSON" in bad.stderr

"""Installed-style module execution, refusal exits and stdout failures."""

import io
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import coupling_cli, coupling_io


def test_single_and_batch_cli(capsys):
    for name, count in [("single", 1), ("batch", 3)]:
        assert coupling_cli.main([f"examples/coupling-{name}.json"]) == 0
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert captured.err == ""
        assert result["coverage"]["successful"] == count
        assert result["records"][0]["scores"]["downstream_total"][
            "value"
        ] == pytest.approx(1.072)


def test_partial_exit(capsys):
    assert coupling_cli.main(["examples/coupling-unsupported.json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["records"][0]["status"] == "unsupported_distance"


def test_stdin_and_module_entry(monkeypatch, capsys):
    raw = Path("examples/coupling-single.json").read_bytes()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    monkeypatch.setattr(sys, "argv", ["coupling", "-"])
    monkeypatch.delitem(sys.modules, "regsite.coupling_cli")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite.coupling_cli", run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b"\xff", b"[]", b"NaN"])
def test_invalid_json_or_envelope_returns_atomic_result(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert coupling_cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "invalid_input"
    assert output.err == ""


def test_missing_input_no_json(tmp_path, capsys):
    assert coupling_cli.main([str(tmp_path / "absent-private-path")]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "absent-private-path" not in output.err
    assert "Input or output unavailable" in output.err


def test_output_limit_is_atomic(monkeypatch, capsys):
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", 1)
    assert coupling_cli.main(["examples/coupling-single.json"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "exceeds byte limit" in output.err


def test_broken_pipe_redirects_shutdown_flush(monkeypatch):
    redirects = []

    def fail_write(value):
        raise BrokenPipeError("closed consumer")

    stream = SimpleNamespace(
        buffer=SimpleNamespace(write=fail_write), fileno=lambda: 77
    )
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(
        coupling_cli.os, "dup2", lambda src, dest: redirects.append(dest)
    )
    assert coupling_cli.main(["examples/coupling-single.json"]) == 2
    assert redirects == [77]

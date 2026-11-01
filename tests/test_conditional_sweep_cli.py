"""Backend-free CLI transport and complete refusal behavior."""

import io
import json
import os
import runpy
import sys
from types import SimpleNamespace

import pytest
from test_conditional_sweep import example

from regsite import conditional_sweep as model
from regsite import conditional_sweep_cli as cli


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))


def test_stdin_and_file_identical_scientific_points(monkeypatch, tmp_path, capsys):
    request = example()
    stdin(monkeypatch, request)
    assert cli.main(["-"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "complete" and output.err == ""
    assert len(result["points"]) == 6
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    assert cli.main([str(path)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert (
        second["sweep_id"] == result["sweep_id"]
        and second["points"] == result["points"]
    )
    assert model.result_bytes(second).decode().endswith("\n")


@pytest.mark.parametrize(
    "raw", [b"{", b"\xff", b'{"a":1,"a":2}', b"NaN", b"1e400", b" " * 65537]
)
def test_invalid_transport(raw, monkeypatch, capsys):
    stdin(monkeypatch, raw)
    assert cli.main(["-"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid_input" and result["points"] == []


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_nonregular_inputs_are_refused(kind, tmp_path, capsys):
    path = tmp_path / kind
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_text(json.dumps(example()))
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    assert cli.main([str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


def test_platform_without_nofollow(monkeypatch, capsys):
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert cli.main(["request.json"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


def test_descriptor_closed_on_fdopen_failure(monkeypatch, tmp_path, capsys):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(example()))
    opened = []

    def fail(fd, *args, **kwargs):
        opened.append(fd)
        raise OSError("failed")

    monkeypatch.setattr(os, "fdopen", fail)
    assert cli.main([str(path)]) == 2
    with pytest.raises(OSError):
        os.fstat(opened[0])
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


def test_partial_no_rna_exit(monkeypatch, capsys):
    value = example()
    value["template"]["input"]["occupancy"]["mrna_total_molar"] = 0
    stdin(monkeypatch, value)
    assert cli.main(["-"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "partial" and len(result["points"]) == 6
    assert all(r["status"] == "no_mrna" for r in result["points"])


def test_serialization_refusal_has_no_original_prefix(monkeypatch, capsys):
    monkeypatch.setattr(cli, "sweep", lambda *a: {"bad": float("nan")})
    stdin(monkeypatch, example())
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["reason"] == "result_serialization_failure"
    assert "NaN" not in output.out


def test_cap_on_refusal_itself_is_clean_transport_error(monkeypatch, capsys):
    monkeypatch.setattr(model, "OUTPUT_LIMIT", 1)
    stdin(monkeypatch, example())
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "output unavailable" in output.err


@pytest.mark.parametrize("stage", ["write", "flush", "broken_pipe"])
def test_output_device_failure(monkeypatch, capsys, stage):
    class Broken:
        def __init__(self):
            self.buffer = self

        def write(self, raw):
            if stage == "broken_pipe":
                raise BrokenPipeError("closed")
            if stage == "write":
                raise OSError("full")
            return len(raw)

        def flush(self):
            if stage == "flush":
                raise OSError("full")

        def fileno(self):
            return 1234

    targets = []
    monkeypatch.setattr(sys, "stdout", Broken())
    monkeypatch.setattr(os, "dup2", lambda source, target: targets.append(target))
    stdin(monkeypatch, example())
    assert cli.main(["-"]) == 2
    assert "output unavailable" in capsys.readouterr().err
    assert targets == ([1234] if stage == "broken_pipe" else [])


def test_entrypoint_and_help(monkeypatch, capsys):
    stdin(monkeypatch, example())
    monkeypatch.setattr(sys, "argv", ["regsite-conditional-sweep", "-"])
    monkeypatch.delitem(sys.modules, "regsite.conditional_sweep_cli")
    with pytest.raises(SystemExit) as error:
        runpy.run_module("regsite.conditional_sweep_cli", run_name="__main__")
    assert error.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0 and "ligand" in capsys.readouterr().out

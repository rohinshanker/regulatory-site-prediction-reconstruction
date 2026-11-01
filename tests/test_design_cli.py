"""Design CLI input/output lifecycle without native folding."""

import io
import json
import os
import runpy
import sys
from types import SimpleNamespace

import pytest
from test_design import backend, example, native

from regsite import design, design_cli, design_io
from regsite.structures import BackendError


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))


@pytest.fixture
def artificial(monkeypatch):
    calls = []
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)

    def load(path):
        calls.append(path)
        return backend()

    monkeypatch.setattr(design_cli.RnaStructure, "open", load)
    monkeypatch.setattr(design, "predict", native)
    return calls


def test_stdin_without_backend_refuses(monkeypatch, capsys, artificial):
    stdin(monkeypatch, example())
    assert design_cli.main(["-"]) == 2
    value = json.loads(capsys.readouterr().out)
    assert value["reason"] == "backend_required" and not artificial


@pytest.mark.parametrize("source", ["stdin", "file"])
@pytest.mark.parametrize("configuration", ["explicit", "env"])
def test_complete_command(
    source, configuration, monkeypatch, capsys, tmp_path, artificial
):
    value = example()
    if source == "stdin":
        stdin(monkeypatch, value)
        path = "-"
    else:
        path = str(tmp_path / "request.json")
        with open(path, "w") as stream:
            json.dump(value, stream)
    args = [path]
    if configuration == "explicit":
        args.extend(["--backend-root", "artificial"])
    else:
        monkeypatch.setenv("REGSITE_RNASTRUCTURE", "artificial")
    assert design_cli.main(args) == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["status"] == "complete" and output["selected"] is not None
    assert captured.out.encode() == design_io.pretty(output)
    assert artificial == ["artificial"]
    assert captured.err == ""


@pytest.mark.parametrize("raw", [b"{", b"\xff", b'{"x":1,"x":2}', b"NaN", b"{}"])
def test_invalid_requests_precede_backend(raw, monkeypatch, capsys, artificial):
    stdin(monkeypatch, raw)
    assert design_cli.main(["-", "--backend-root", "artificial"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid_input"
    assert not artificial


@pytest.mark.parametrize(
    "exception", [BackendError("bad"), OSError("bad"), UnicodeError("bad")]
)
def test_backend_errors(exception, monkeypatch, capsys, artificial):
    def fail(path):
        raise exception

    monkeypatch.setattr(design_cli.RnaStructure, "open", fail)
    stdin(monkeypatch, example())
    assert design_cli.main(["-", "--backend-root", "bad"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "backend_unavailable"


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_unsafe_or_unavailable_files_do_not_block(kind, tmp_path, capsys, artificial):
    path = tmp_path / kind
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_text(json.dumps(example()))
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path)
    assert design_cli.main([str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"
    assert not artificial


def test_without_nofollow(monkeypatch, capsys):
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert design_cli.main(["a.json"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


def test_descriptor_closed_on_wrap_failure(monkeypatch, tmp_path, capsys):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(example()))
    descriptors = []

    def fail(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("wrap failed")

    monkeypatch.setattr(os, "fdopen", fail)
    assert design_cli.main([str(path)]) == 2
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


@pytest.mark.parametrize("status", ["partial", "no_candidate"])
def test_partial_exits_preserve_all_results(status, monkeypatch, capsys, artificial):
    def fail(value, engine, **kwargs):
        result = native(value, engine, **kwargs)
        if status == "no_candidate" or value["sequence"][4] == "G":
            result.update(status="failed", reason="test_failure", sites=[])
        return result

    monkeypatch.setattr(design, "predict", fail)
    stdin(monkeypatch, example())
    assert design_cli.main(["-", "--backend-root", "test"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status and len(result["candidates"]) == 4


def test_serialization_failure_returns_small_refusal(monkeypatch, capsys, artificial):
    monkeypatch.setattr(design_cli, "design", lambda *args: {"bad": float("nan")})
    stdin(monkeypatch, example())
    assert design_cli.main(["-", "--backend-root", "test"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "result_serialization_failure"
    assert result["selected"] is None


def test_refusal_also_exceeding_output_cap_writes_no_prefix(
    monkeypatch, capsys, artificial
):
    monkeypatch.setattr(design_io, "OUTPUT_LIMIT", 1)
    stdin(monkeypatch, example())
    assert design_cli.main(["-", "--backend-root", "test"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "output unavailable" in captured.err


@pytest.mark.parametrize("stage", ["write", "flush", "broken_pipe"])
def test_device_errors(stage, monkeypatch, capsys, artificial):
    class Broken:
        def __init__(self):
            self.buffer = self

        def write(self, value):
            if stage == "broken_pipe":
                raise BrokenPipeError("closed")
            if stage == "write":
                raise OSError("full")
            return len(value)

        def flush(self):
            if stage == "flush":
                raise OSError("full")

        def fileno(self):
            return 1234

    redirects = []
    monkeypatch.setattr(os, "dup2", lambda source, target: redirects.append(target))
    monkeypatch.setattr(sys, "stdout", Broken())
    stdin(monkeypatch, example())
    assert design_cli.main(["-", "--backend-root", "test"]) == 2
    assert "output unavailable" in capsys.readouterr().err
    assert redirects == ([1234] if stage == "broken_pipe" else [])


def test_module_entrypoint(monkeypatch, capsys, artificial):
    stdin(monkeypatch, example())
    monkeypatch.setattr(sys, "argv", ["regsite-design", "-"])
    monkeypatch.delitem(sys.modules, "regsite.design_cli")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite.design_cli", run_name="__main__")
    assert exc.value.code == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "backend_required"


def test_help_has_no_backend_open(capsys, artificial):
    with pytest.raises(SystemExit) as exc:
        design_cli.main(["--help"])
    assert exc.value.code == 0 and not artificial
    assert "--backend-root" in capsys.readouterr().out

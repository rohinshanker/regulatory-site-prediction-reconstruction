"""CLI transport, failure and output lifecycle tests without native scoring."""

import io
import json
import os
import runpy
import sys
from types import SimpleNamespace

import pytest
from test_termination import FakeBackend, request

from regsite import termination, termination_cli
from regsite.termination_backend import TerminationBackendError
from regsite.termination_io import TerminationInputError


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))


def test_stdin_without_backend_keeps_record(monkeypatch, capsys):
    stdin(monkeypatch, request())
    assert termination_cli.main(["-"]) == 1
    capture = capsys.readouterr()
    result = json.loads(capture.out)
    assert result["records"][0]["reason"] == "backend_unavailable"
    assert capture.err == ""


def test_regular_file_with_explicit_backend(monkeypatch, tmp_path, capsys):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    backend = FakeBackend()
    paths = []

    def load(path):
        paths.append(path)
        return backend

    monkeypatch.setattr(termination_cli, "load_backend", load)
    monkeypatch.setattr(termination, "parse_output", lambda *args: [])
    assert (
        termination_cli.main(
            [str(source), "--backend-manifest", "/explicit/backend.json"]
        )
        == 0
    )
    assert paths == ["/explicit/backend.json"]
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    assert len(backend.calls) == 1


def test_invalid_backend_is_structured_per_record(monkeypatch, capsys):
    stdin(monkeypatch, request())

    def fail(path):
        raise TerminationBackendError("invalid", code="backend_manifest")

    monkeypatch.setattr(termination_cli, "load_backend", fail)
    assert termination_cli.main(["-", "--backend-manifest", "invalid.json"]) == 1
    assert (
        json.loads(capsys.readouterr().out)["records"][0]["reason"]
        == "backend_manifest"
    )


@pytest.mark.parametrize("raw", [b"{", b'{"x":1,"x":2}', b"\xff", b'{"x":NaN}'])
def test_bad_json_has_json_refusal(monkeypatch, capsys, raw):
    stdin(monkeypatch, raw)
    assert termination_cli.main(["-"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid_input"
    assert result["records"] == []


def test_oversized_transport(monkeypatch, capsys):
    from regsite import termination_io

    monkeypatch.setattr(termination_io, "INPUT_LIMIT", 10)
    stdin(monkeypatch, b" " * 11)
    assert termination_cli.main(["-"]) == 2
    assert (
        json.loads(capsys.readouterr().out)["reason"] == "invalid_json_or_input_limit"
    )


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_nonregular_inputs_are_refused_without_following_or_blocking(
    tmp_path, capsys, kind
):
    path = tmp_path / kind
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        actual = tmp_path / "actual"
        actual.write_text(json.dumps(request()))
        path.symlink_to(actual)
    elif kind == "fifo":
        os.mkfifo(path)
    assert termination_cli.main([str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unavailable" in captured.err


def test_platform_without_nofollow_refuses_file(monkeypatch, capsys):
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert termination_cli.main(["request.json"]) == 2
    assert "unavailable" in capsys.readouterr().err


def test_descriptor_is_closed_when_wrapping_fails(monkeypatch, tmp_path, capsys):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request()))
    descriptors = []

    def fail(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("cannot wrap")

    monkeypatch.setattr(os, "fdopen", fail)
    assert termination_cli.main([str(path)]) == 2
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert capsys.readouterr().out == ""


def test_read_failure(monkeypatch, capsys):
    class FailedRead:
        def read(self, count):
            raise OSError("unavailable")

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=FailedRead()))
    assert termination_cli.main(["-"]) == 2
    assert "unavailable" in capsys.readouterr().err


def test_serialization_limit_never_writes_a_prefix(monkeypatch, capsys):
    stdin(monkeypatch, request())

    def fail(result):
        raise TerminationInputError("too much output")

    monkeypatch.setattr(termination_cli, "result_bytes", fail)
    assert termination_cli.main(["-"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "oversized" in captured.err


def test_broken_pipe_redirects_only_owned_output_descriptor(
    monkeypatch, tmp_path, capsys
):
    stdin(monkeypatch, request())

    class BrokenBuffer:
        def write(self, raw):
            raise BrokenPipeError()

    with (tmp_path / "output").open("wb") as stream:
        with monkeypatch.context() as patch:
            patch.setattr(
                sys,
                "stdout",
                SimpleNamespace(buffer=BrokenBuffer(), fileno=stream.fileno),
            )
            assert termination_cli.main(["-"]) == 2
        assert os.write(stream.fileno(), b"safe") == 4
    assert (tmp_path / "output").read_bytes() == b""
    assert "unavailable" in capsys.readouterr().err


def test_module_entry_point(monkeypatch, capsys):
    stdin(monkeypatch, request())
    monkeypatch.setattr(sys, "argv", ["regsite-termination", "-"])
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        with pytest.raises(SystemExit) as caught:
            runpy.run_module("regsite.termination_cli", run_name="__main__")
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "partial"


def test_argument_error(capsys):
    with pytest.raises(SystemExit) as caught:
        termination_cli.main([])
    assert caught.value.code == 2
    assert "usage:" in capsys.readouterr().err

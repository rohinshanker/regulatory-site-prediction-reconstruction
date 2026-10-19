"""Offline CLI transport, explicit backend selection and honest failure exits."""

import io
import json
import os
import runpy
import subprocess
import sys

import pytest
from test_transcript import annotation, document
from test_transcript import backend as backend

from regsite import transcript_cli as cli
from regsite.backend import RnaStructure
from regsite.structures import BackendError
from regsite.transcript import TranscriptError

ERROR = "regsite-transcript: Input, backend or output is unavailable or invalid\n"


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))


def backend_free():
    request = document()
    request["cds"] = [annotation("before", 1, 4)]
    return request


@pytest.mark.parametrize("environment", [False, True])
def test_explicit_and_environment_backend_selection(
    monkeypatch, capsys, backend, environment
):
    observed = []

    def open_backend(root):
        observed.append(root)
        return backend

    monkeypatch.setattr(RnaStructure, "open", open_backend)
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/environment-engine")
    args = ["-"] + ([] if environment else ["--backend-root", "/explicit-engine"])
    stdin(monkeypatch, document())
    assert cli.main(args) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "complete"
    assert output.err == ""
    assert observed == ["/environment-engine" if environment else "/explicit-engine"]
    assert (
        output.out
        == json.dumps(
            result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    )


def test_file_csv_and_partial_without_backend(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(backend_free()), encoding="utf-8")
    assert cli.main([str(path), "--format", "csv"]) == 1
    output = capsys.readouterr()
    assert output.out.startswith("schema_version,id,request_sha256,")
    assert "test α" in output.out and "start_before_transcript" in output.out
    assert output.err == ""


@pytest.mark.parametrize(
    "status,exit_code", [("complete", 0), ("partial", 1), ("unavailable", 1)]
)
def test_exit_codes_retain_predictor_result(monkeypatch, capsys, status, exit_code):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    result = {"status": status}
    monkeypatch.setattr(cli, "predict_transcript", lambda *args: result)
    stdin(monkeypatch, {})
    assert cli.main(["-"]) == exit_code
    assert json.loads(capsys.readouterr().out) == result


def test_malformed_wire_precedes_backend_and_scoring(monkeypatch, capsys):
    def forbidden(*args):
        raise AssertionError("malformed wire reached backend or predictor")

    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/must-not-open")
    monkeypatch.setattr(RnaStructure, "open", forbidden)
    monkeypatch.setattr(cli, "predict_transcript", forbidden)
    stdin(monkeypatch, b'{"a":1,"a":2}')
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == ERROR


@pytest.mark.parametrize(
    "error",
    [
        TranscriptError("bad input"),
        BackendError("bad engine"),
        OSError("private path"),
        UnicodeError("bad output"),
    ],
)
def test_atomic_failures_have_no_result_or_private_diagnostic(
    monkeypatch, capsys, error
):
    def fail(*args):
        raise error

    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    monkeypatch.setattr(cli, "predict_transcript", fail)
    stdin(monkeypatch, {})
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == ERROR


def test_missing_file_and_missing_required_backend(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    assert cli.main([str(tmp_path / "missing")]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == ERROR
    stdin(monkeypatch, document())
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == ERROR


def test_module_entrypoint(monkeypatch, capsys):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    stdin(monkeypatch, backend_free())
    monkeypatch.setattr(sys, "argv", ["regsite-transcript", "-"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite.transcript_cli", run_name="__main__")
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "partial"


def test_binary_streams_ignore_inherited_encoding():
    request = backend_free()
    raw = json.dumps(request, ensure_ascii=False).encode()
    command = [sys.executable, "-m", "regsite.transcript_cli", "-"]
    env = dict(os.environ, PYTHONIOENCODING="latin-1")
    env.pop("REGSITE_RNASTRUCTURE", None)
    good = subprocess.run(command, input=raw, env=env, capture_output=True, check=False)
    assert good.returncode == 1, good.stderr
    assert json.loads(good.stdout)["id"] == "test α"
    bad = subprocess.run(
        command, input=b"\xff", env=env, capture_output=True, check=False
    )
    assert bad.returncode == 2 and bad.stdout == b"" and bad.stderr == ERROR.encode()


def test_closed_stdout_pipe_has_documented_exit_without_shutdown_traceback(tmp_path):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(backend_free()), encoding="utf-8")
    env = dict(os.environ)
    env.pop("REGSITE_RNASTRUCTURE", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "regsite.transcript_cli", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()
    error = process.stderr.read()
    process.stderr.close()
    assert process.wait(timeout=10) == 2
    assert error == ERROR.encode()


def test_flush_error_is_inside_handled_boundary(monkeypatch, capsys):
    class BrokenOutput:
        buffer = io.BytesIO()

        def flush(self):
            raise BrokenPipeError("closed downstream")

        def fileno(self):
            return 123

    observed = []
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    stdin(monkeypatch, backend_free())
    monkeypatch.setattr(sys, "stdout", BrokenOutput())
    monkeypatch.setattr(os, "dup2", lambda source, target: observed.append(target))
    assert cli.main(["-"]) == 2
    assert observed == [123]
    assert capsys.readouterr().err == ERROR

"""Binary stdin/regular no-follow transport and complete typed output failures."""

import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import promoter_design_cli as cli
from regsite import promoter_design_io as transport
from regsite.promoter_design import invalid_result

EXAMPLE = "examples/promoter-design-single.json"


def test_regular_file_real_prediction(capsys):
    assert cli.main([EXAMPLE]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert (
        result["status"] == "complete" and result["coverage"]["prediction_calls"] == 5
    )
    assert captured.err == ""


def test_stdin_module_entry(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(Path(EXAMPLE).read_bytes()))
    )
    monkeypatch.setattr(sys, "argv", ["regsite-promoter-design", "-"])
    monkeypatch.delitem(sys.modules, "regsite.promoter_design_cli")
    with pytest.raises(SystemExit) as error:
        runpy.run_module("regsite.promoter_design_cli", run_name="__main__")
    assert error.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.parametrize(
    "raw", [b"NaN", b"\xff", b"[]", b' {"x":0,"x":1}', b"{}" + b" " * 65536]
)
def test_invalid_stdin_is_one_typed_refusal(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert cli.main(["-"]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "invalid_input" and result["candidates"] == []
    assert captured.err == ""


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_nonregular_or_missing_file_refused_without_private_name(
    kind, tmp_path, capsys
):
    path = tmp_path / "private-name"
    if kind == "directory":
        path.mkdir()
    if kind == "symlink":
        path.symlink_to(Path(EXAMPLE).resolve())
    if kind == "fifo":
        os.mkfifo(path)
    assert cli.main([str(path)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["reason"] == "input_unavailable"
    assert "private-name" not in captured.out + captured.err


def test_no_follow_capability_is_required(monkeypatch, capsys):
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert cli.main([EXAMPLE]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "input_unavailable"


@pytest.mark.parametrize("status", ["partial", "no_candidate"])
def test_partial_and_empty_exits(status, monkeypatch, capsys):
    result = invalid_result("artificial")
    result["status"] = status
    monkeypatch.setattr(cli, "design", lambda request: result)
    assert cli.main([EXAMPLE]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_serialization_fallback_and_impossible_cap(monkeypatch, capsys):
    monkeypatch.setattr(cli, "design", lambda request: {"x": float("nan")})
    assert cli.main([EXAMPLE]) == 2
    captured = capsys.readouterr()
    assert (
        json.loads(captured.out)["reason"] == "result_serialization_failure"
        and captured.err == ""
    )
    monkeypatch.setattr(transport, "OUTPUT_LIMIT", 1)
    assert cli.main([EXAMPLE]) == 2
    captured = capsys.readouterr()
    assert (
        captured.out == ""
        and captured.err == "regsite-promoter-design: output unavailable\n"
    )


@pytest.mark.parametrize(
    "where,error",
    [("write", BrokenPipeError()), ("write", OSError()), ("flush", OSError())],
)
def test_write_and_flush_failures(where, error, monkeypatch, capsys):
    redirects = []
    writes = []

    def write(raw):
        if where == "write":
            raise error
        writes.append(raw)

    def flush():
        raise error

    monkeypatch.setattr(
        sys,
        "stdout",
        SimpleNamespace(
            buffer=SimpleNamespace(write=write), flush=flush, fileno=lambda: 77
        ),
    )
    monkeypatch.setattr(
        os, "dup2", lambda source, destination: redirects.append(destination)
    )
    assert cli.main([EXAMPLE]) == 2
    assert redirects == ([77] if isinstance(error, BrokenPipeError) else [])
    assert len(writes) == int(where == "flush")
    assert capsys.readouterr().err == "regsite-promoter-design: output unavailable\n"


def test_real_module_import_is_backend_free_and_stdin_works():
    imported = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import regsite.promoter_design_cli; "
            "assert 'regsite.backend' not in sys.modules; "
            "assert 'regsite.rbs' not in sys.modules",
        ],
        capture_output=True,
        timeout=10,
    )
    assert imported.returncode == 0, imported.stderr
    completed = subprocess.run(
        [sys.executable, "-m", "regsite.promoter_design_cli", "-"],
        input=Path(EXAMPLE).read_bytes(),
        capture_output=True,
        timeout=10,
    )
    assert completed.returncode == 0 and completed.stderr == b""
    assert json.loads(completed.stdout)["status"] == "complete"

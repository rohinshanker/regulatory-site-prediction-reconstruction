"""Strict binary transport, complete failure receipts and offline conditional CLI."""

import copy
import io
import json
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from regsite import conditional_cli as cli
from regsite.conditional import INPUT_LIMIT, invalid_result
from regsite.conditional_math import ConditionalError

EXAMPLE = (
    Path(__file__).parents[1] / "examples/conditional-supplied-half-occupancy.json"
)


def request():
    return json.loads(EXAMPLE.read_bytes())


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))


def test_offline_scalar_and_explicit_backend_ignored(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("scalar profile attempted a process or network")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert cli.main([str(EXAMPLE), "--backend-root", "/not-needed"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert output.err == "" and result["complete"]
    assert result["response"]["ar_actual"] == pytest.approx(2.5)
    assert result["model"]["backend"] is None
    assert (
        output.out
        == json.dumps(
            result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"\xff",
        b"{}{}",
        b'{"a":1,"a":2}',
        b'{"a":{"b":1,"b":2}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"[" * 2000,
        b"1" * 5000,
    ],
)
def test_invalid_wire_emits_receipt_without_request_identity(monkeypatch, capsys, raw):
    stdin(monkeypatch, raw)
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "invalid_input"
    assert result["request_sha256"] is None
    assert result["reasons"] == ["invalid_json"]
    assert output.err == ""


@pytest.mark.parametrize(
    "document,reason",
    [
        (None, "invalid_object"),
        ([], "invalid_object"),
        (1e999, "invalid_json"),
        ({}, "missing_field"),
    ],
)
def test_parsed_invalid_input_keeps_native_diagnostics(
    monkeypatch, capsys, document, reason
):
    stdin(monkeypatch, document)
    assert cli.main(["-"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert reason in result["reasons"]


@pytest.mark.parametrize(
    "status,exit_code",
    [
        ("ok", 0),
        ("failed", 1),
        ("no_mrna", 1),
        ("invalid_input", 2),
        ("unsupported", 2),
    ],
)
def test_exit_codes_preserve_returned_result(monkeypatch, capsys, status, exit_code):
    result = invalid_result()
    result["status"] = status
    monkeypatch.setattr(cli, "predict_conditional", lambda *args: copy.deepcopy(result))
    stdin(monkeypatch, {})
    assert cli.main(["-"]) == exit_code
    assert json.loads(capsys.readouterr().out) == result


def test_actual_no_mrna_and_missing_backend(monkeypatch, capsys):
    value = request()
    value["input"]["occupancy"] = dict(
        mode="published2015_volume",
        mrna_total_molar=0,
        ligand_total_molar=1,
        mrna_relative_volume=1,
        ligand_relative_volume=1,
        solvent_molar=1,
    )
    stdin(monkeypatch, value)
    assert cli.main(["-"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "no_mrna" and result["response"]["ar_actual"] is None
    value = json.loads(
        (EXAMPLE.parent / "conditional-hairpin-structure-control.json").read_bytes()
    )
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    stdin(monkeypatch, value)
    assert cli.main(["-"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["reasons"] == ["backend_unavailable"]
    assert len(result["states"]) == 2 and all(
        s["status"] == "not_run" for s in result["states"]
    )


def test_received_crlf_byte_limit_is_inclusive(tmp_path, capsys):
    raw = EXAMPLE.read_bytes()
    remaining = INPUT_LIMIT - len(raw)
    raw += b"\r\n" * (remaining // 2) + b" " * (remaining % 2)
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    assert cli.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    path.write_bytes(raw + b" ")
    assert cli.main([str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["reasons"] == ["input_limit"]


def test_io_and_serialization_failures_do_not_publish_json(
    monkeypatch, tmp_path, capsys
):
    assert cli.main([str(tmp_path / "missing")]) == 2
    output = capsys.readouterr()
    assert output.out == "" and str(tmp_path) not in output.err

    def refuse(*args):
        raise ConditionalError("result_limit", "oversized")

    monkeypatch.setattr(cli, "result_bytes", refuse)
    stdin(monkeypatch, request())
    assert cli.main(["-"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "output byte limit" in output.err


def test_binary_streams_ignore_inherited_encoding():
    value = request()
    value["id"] = "µ-control"
    raw = json.dumps(value, ensure_ascii=False).encode()
    command = [sys.executable, "-m", "regsite.conditional_cli", "-"]
    env = dict(os.environ, PYTHONIOENCODING="latin-1")
    good = subprocess.run(command, input=raw, env=env, capture_output=True, check=False)
    assert good.returncode == 0, good.stderr
    assert json.loads(good.stdout)["id"] == "µ-control"
    bad = subprocess.run(
        command,
        input=raw.replace("µ".encode(), b"\xff"),
        env=env,
        capture_output=True,
        check=False,
    )
    assert bad.returncode == 2 and json.loads(bad.stdout)["status"] == "invalid_input"


def test_module_entrypoint(monkeypatch, capsys):
    stdin(monkeypatch, request())
    monkeypatch.setattr(sys, "argv", ["regsite-conditional", "-"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite.conditional_cli", run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"

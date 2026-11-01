"""Strict binary transport, complete failure receipts and offline conditional CLI."""

import copy
import csv
import hashlib
import io
import json
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from regsite import conditional
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
    with (
        pytest.warns(RuntimeWarning, match="found in sys.modules"),
        pytest.raises(SystemExit) as exc,
    ):
        runpy.run_module("regsite.conditional_cli", run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_closed_stdout_pipe_has_documented_exit_and_no_shutdown_traceback():
    process = subprocess.Popen(
        [sys.executable, "-m", "regsite.conditional_cli", str(EXAMPLE)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()
    error = process.stderr.read()
    process.stderr.close()
    assert process.wait(timeout=10) == 2
    assert error == b"regsite-conditional: Input or output is unavailable\n"


def test_broken_pipe_redirects_descriptor_inside_handled_boundary(monkeypatch, capsys):
    class BrokenOutput:
        buffer = io.BytesIO()

        def flush(self):
            raise BrokenPipeError("closed downstream")

        def fileno(self):
            return 123

    observed = []
    monkeypatch.setattr(sys, "stdout", BrokenOutput())
    monkeypatch.setattr(os, "dup2", lambda source, target: observed.append(target))
    assert cli.main([str(EXAMPLE)]) == 2
    assert observed == [123]
    assert (
        capsys.readouterr().err
        == "regsite-conditional: Input or output is unavailable\n"
    )


def csv_rows(text):
    return list(csv.DictReader(io.StringIO(text, newline="")))


def test_default_explicit_json_and_csv_bind_identical_native_bytes(monkeypatch, capsys):
    value = request()
    value["id"] = 'µ,"artificial"\r\nrecord'
    stdin(monkeypatch, value)
    assert cli.main(["-"]) == 0
    original = capsys.readouterr()
    stdin(monkeypatch, value)
    assert cli.main(["-", "--format", "json"]) == 0
    explicit = capsys.readouterr()
    assert explicit == original
    stdin(monkeypatch, value)
    assert cli.main(["-", "--format", "csv"]) == 0
    tabular = capsys.readouterr()
    assert tabular.err == ""
    rows = csv_rows(tabular.out)
    assert [row["row_type"] for row in rows] == ["result", "response"]
    for row in rows:
        assert row["json_sha256"] == hashlib.sha256(original.out.encode()).hexdigest()
        assert row["id"] == value["id"]
    assert rows[1]["ar_actual"] == "2.5"


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
def test_csv_retains_all_native_exit_statuses(monkeypatch, capsys, status, exit_code):
    result = invalid_result()
    result.update(status=status, complete=status == "ok")
    monkeypatch.setattr(cli, "predict_conditional", lambda *args: result)
    stdin(monkeypatch, {})
    assert cli.main(["-", "--format", "csv"]) == exit_code
    output = capsys.readouterr()
    row = csv_rows(output.out)[0]
    assert output.err == "" and row["result_status"] == status
    assert row["complete"] == ("true" if status == "ok" else "false")


@pytest.mark.parametrize(
    "raw",
    [b"{", b"\xff", b'{"a":1,"a":2}', b"NaN", b"[" * 2000, b" " * (INPUT_LIMIT + 1)],
)
def test_csv_wire_refusal_always_retains_one_envelope(monkeypatch, capsys, raw):
    stdin(monkeypatch, raw)
    assert cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    rows = csv_rows(output.out)
    assert output.err == "" and len(rows) == 1
    assert rows[0]["row_type"] == "result"
    assert rows[0]["request_sha256"] == ""
    expected = "input_limit" if len(raw) > INPUT_LIMIT else "invalid_json"
    assert json.loads(rows[0]["reasons_json"]) == [expected]


def test_csv_regular_file_module_entry_and_invalid_format(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["regsite-conditional", str(EXAMPLE), "--format", "csv"]
    )
    with (
        pytest.warns(RuntimeWarning, match="found in sys.modules"),
        pytest.raises(SystemExit) as error,
    ):
        runpy.run_module("regsite.conditional_cli", run_name="__main__")
    assert error.value.code == 0
    assert csv_rows(capsys.readouterr().out)[1]["ar_actual"] == "2.5"
    with pytest.raises(SystemExit) as error:
        cli.main([str(EXAMPLE), "--format", "xml"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == "" and "invalid choice" in output.err


def test_csv_actual_no_mrna_and_missing_backend_retains_not_run(monkeypatch, capsys):
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
    assert cli.main(["-", "--format", "csv"]) == 1
    rows = csv_rows(capsys.readouterr().out)
    assert rows[1]["occupancy_status"] == "no_mrna"
    assert rows[1]["ar_actual"] == rows[1]["occupancy_fraction"] == ""
    assert rows[1]["complex_molar"] == "0.0"
    value = json.loads(
        (EXAMPLE.parent / "conditional-hairpin-structure-control.json").read_bytes()
    )
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    stdin(monkeypatch, value)
    assert cli.main(["-", "--format", "csv"]) == 1
    rows = csv_rows(capsys.readouterr().out)
    assert [row["row_type"] for row in rows] == ["result", "state", "state"]
    assert [row["state_status"] for row in rows[1:]] == ["not_run", "not_run"]
    assert json.loads(rows[0]["reasons_json"]) == ["backend_unavailable"]


def test_csv_cap_failure_and_unavailable_file_publish_no_prefix(
    monkeypatch, tmp_path, capsys
):
    result = invalid_result()
    limit = len(cli.csv_bytes(result)) - 1
    monkeypatch.setattr(conditional, "RESULT_LIMIT", limit)
    monkeypatch.setattr(cli, "predict_conditional", lambda *args: result)
    stdin(monkeypatch, {})
    assert cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "regsite-conditional: Result exceeds output byte limit\n"
    assert cli.main([str(tmp_path / "missing"), "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and str(tmp_path) not in output.err
    assert output.err == "regsite-conditional: Input or output is unavailable\n"


def test_csv_lone_surrogate_is_clean_error_but_json_stays_unchanged(
    monkeypatch, capsys
):
    value = request()
    value["id"] = "\ud800"
    stdin(monkeypatch, value)
    assert cli.main(["-"]) == 0
    original = capsys.readouterr()
    assert json.loads(original.out)["id"] == "\ud800"
    stdin(monkeypatch, value)
    assert cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "regsite-conditional: Input or output is unavailable\n"


def test_csv_stdout_write_failure_uses_existing_boundary(monkeypatch, capsys):
    class BrokenBuffer:
        def write(self, raw):
            raise OSError("artificial write failure")

    class Output:
        buffer = BrokenBuffer()

    monkeypatch.setattr(sys, "stdout", Output())
    assert cli.main([str(EXAMPLE), "--format", "csv"]) == 2
    assert (
        capsys.readouterr().err
        == "regsite-conditional: Input or output is unavailable\n"
    )


def test_csv_closed_pipe_retains_exit_without_shutdown_traceback():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "regsite.conditional_cli",
            str(EXAMPLE),
            "--format",
            "csv",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()
    error = process.stderr.read()
    process.stderr.close()
    assert process.wait(timeout=10) == 2
    assert error == b"regsite-conditional: Input or output is unavailable\n"

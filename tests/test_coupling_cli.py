"""Installed-style module execution, refusal exits and stdout failures."""

import csv
import io
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import coupling, coupling_cli, coupling_io


@pytest.mark.parametrize("case", ["unicode-provenance", "unicode-whitespace"])
def test_received_unicode_bytes_do_not_use_ascii_hash_limit(case):
    request = json.loads(Path("examples/coupling-single.json").read_text())
    if case == "unicode-provenance":
        template = request["records"][0]
        request["records"] = []
        for index in range(100):
            record = json.loads(json.dumps(template))
            record["id"] = f"synthetic-{index}"
            record["sequence"] += "C" * (8000 - len(record["sequence"]))
            record["energies"]["provenance"] = "β" * 500
            request["records"].append(record)
    else:
        request["records"][0]["sequence"] += "\u2003" * 180_000
    raw = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
    assert (
        len(raw) < coupling_io.INPUT_LIMIT < len(coupling_io.canonical_bytes(request))
    )
    result = subprocess.run(
        [sys.executable, "-m", "regsite.coupling_cli", "-"],
        input=raw,
        capture_output=True,
        timeout=10,
        check=True,
    )
    report = json.loads(result.stdout)
    assert result.stderr == b""
    assert report["status"] == "complete"
    assert report["coverage"]["successful"] == len(request["records"])
    assert all(
        row["scores"]["downstream_total"]["value"] == pytest.approx(1.072)
        for row in report["records"]
    )
    assert report["request_sha256"] == coupling_io.canonical_hash(request)


def test_received_byte_limit_still_rejects_before_evaluation():
    raw = Path("examples/coupling-single.json").read_bytes()
    raw += b" " * (coupling_io.INPUT_LIMIT + 1 - len(raw))
    result = subprocess.run(
        [sys.executable, "-m", "regsite.coupling_cli", "-"],
        input=raw,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2 and result.stderr == b""
    report = json.loads(result.stdout)
    assert report["reason"] == "invalid_json_or_input_limit"
    assert report["records"] == [] and report["request_sha256"] is None


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


@pytest.mark.parametrize("name,code", [("single", 0), ("batch", 0), ("unsupported", 1)])
def test_default_explicit_json_and_csv_bind_same_native_result(name, code):
    path = f"examples/coupling-{name}.json"
    request = json.loads(Path(path).read_text())
    expected = coupling_io.result_bytes(coupling.predict_coupling(request))
    outputs = []
    for suffix in ([], ["--format", "json"], ["--format", "csv"]):
        process = subprocess.run(
            [sys.executable, "-m", "regsite.coupling_cli", path, *suffix],
            capture_output=True,
            timeout=10,
        )
        assert process.returncode == code and process.stderr == b""
        outputs.append(process.stdout)
    assert outputs[0] == outputs[1] == expected
    table = list(csv.DictReader(io.StringIO(outputs[2].decode(), newline="")))
    result = json.loads(expected)
    assert len(table) == 1 + len(result["records"])
    assert all(row["prediction_sha256"] == result["prediction_sha256"] for row in table)
    assert [row["record_status"] for row in table[1:]] == [
        r["status"] for r in result["records"]
    ]


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b"\xff", b"[]", b"NaN"])
def test_csv_invalid_stdin_preserves_native_refusal(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert coupling_cli.main(["-", "--format", "csv"]) == 2
    captured = capsys.readouterr()
    table = list(csv.DictReader(io.StringIO(captured.out, newline="")))
    assert captured.err == "" and len(table) == 1
    assert table[0]["row_type"] == "result"
    assert table[0]["result_status"] == "invalid_input"
    assert table[0]["requested_records"] == ""


def test_csv_valid_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "stdin",
        io.TextIOWrapper(io.BytesIO(Path("examples/coupling-batch.json").read_bytes())),
    )
    assert coupling_cli.main(["-", "--format", "csv"]) == 0
    captured = capsys.readouterr()
    table = list(csv.DictReader(io.StringIO(captured.out, newline="")))
    assert len(table) == 4 and captured.err == ""
    assert [row["record_id"] for row in table[1:]] == [
        "separated",
        "overlap",
        "reverse_overlap",
    ]


@pytest.mark.parametrize("kind", ["missing", "cap", "surrogate"])
def test_csv_transport_failure_has_no_prefix(kind, tmp_path, monkeypatch, capsys):
    path = "examples/coupling-single.json"
    if kind == "missing":
        path = str(tmp_path / "absent")
    elif kind == "cap":
        monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", 1)
    else:
        request = json.loads(Path(path).read_text())
        request["records"][0]["energies"]["provenance"] = "artificial \ud800"
        target = tmp_path / "request.json"
        target.write_text(json.dumps(request))
        path = str(target)
    assert coupling_cli.main([path, "--format", "csv"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Input or output unavailable" in captured.err


@pytest.mark.parametrize("operation", ["write", "flush"])
@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_output_device_errors_preserve_exit_and_generic_diagnostic(
    operation, format_name, monkeypatch, capsys
):
    def fail(*args):
        raise OSError("artificial private device detail")

    stream = SimpleNamespace(
        buffer=SimpleNamespace(
            write=fail if operation == "write" else lambda raw: len(raw)
        ),
        flush=fail,
    )
    monkeypatch.setattr(sys, "stdout", stream)
    assert (
        coupling_cli.main(["examples/coupling-single.json", "--format", format_name])
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == "" and "private device detail" not in captured.err
    assert "Input or output unavailable" in captured.err


def test_invalid_format_is_argparse_failure(capsys):
    with pytest.raises(SystemExit) as exc:
        coupling_cli.main(["examples/coupling-single.json", "--format", "tsv"])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "invalid choice" in captured.err

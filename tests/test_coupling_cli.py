"""Installed-style module execution, refusal exits and stdout failures."""

import io
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import coupling_cli, coupling_io


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

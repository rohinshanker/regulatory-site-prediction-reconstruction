"""Offline public command dispatch and atomic exit behavior."""

import io
import json
import os
import socket
import subprocess
import sys

import pytest

from regsite import promoter_cli


def stdin(text):
    return io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")


def request():
    return {
        "id": "offline",
        "sequence": "A" * 100,
        "calibration": "in_vitro",
        "scan": {"mode": "positions", "positions": [{"strand": "+", "tss": 67}]},
    }


@pytest.mark.parametrize(
    "fmt,prefix", [("json", "{"), ("csv", "record_id,"), ("gff3", "##gff-version 3")]
)
def test_offline_dispatch(fmt, prefix, tmp_path, capsys, monkeypatch):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(request()))

    def prohibited(*args, **kwargs):
        raise AssertionError("offline scoring attempted external execution")

    monkeypatch.setattr(socket, "socket", prohibited)
    monkeypatch.setattr(subprocess, "Popen", prohibited)
    assert promoter_cli.main([str(path), "--format", fmt]) == 0
    output = capsys.readouterr()
    assert output.out.startswith(prefix) and output.err == ""


def test_record_error_and_stdin(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", stdin('{"records":[{}]}'))
    assert promoter_cli.main(["-"]) == 1
    assert (
        json.loads(capsys.readouterr().out)["results"][0]["status"] == "invalid_input"
    )


def test_setup_failure_is_atomic(tmp_path, capsys):
    assert promoter_cli.main([str(tmp_path / "missing")]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err.startswith("regsite-promoter:")
    path = tmp_path / "input.json"
    path.write_text(json.dumps(request()))
    assert promoter_cli.main([str(path), "--seconds-per-record", "0"]) == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("fmt", ["json", "csv", "gff3"])
def test_surrogate_record_preserves_good_sibling_and_exit_one(fmt, monkeypatch, capsys):
    bad = request() | {"sequence": "\ud800"}
    good = request() | {"id": "valid-sibling"}
    monkeypatch.setattr(sys, "stdin", stdin(json.dumps({"records": [bad, good]})))
    assert promoter_cli.main(["-", "--format", fmt]) == 1
    output = capsys.readouterr()
    assert "valid-sibling" in output.out and output.err == ""


def test_render_error_cannot_emit_partial_stdout(monkeypatch, capsys):
    def failing_export(result, stream):
        stream.write("partial header\n")
        raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogate")

    monkeypatch.setattr(sys, "stdin", stdin(json.dumps(request())))
    monkeypatch.setattr(promoter_cli, "write_gff3", failing_export)
    assert promoter_cli.main(["-", "--format", "gff3"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "regsite-promoter:" in output.err


def test_raw_file_boundary_and_strict_utf8_stdin(tmp_path, monkeypatch, capsys):
    raw = json.dumps(request()).encode("utf-8") + b"\r\n" * 10
    monkeypatch.setitem(promoter_cli.LIMITS, "max_input_json_bytes", len(raw))
    path = tmp_path / "wire.json"
    path.write_bytes(raw)
    assert promoter_cli.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["status"] == "ok"
    path.write_bytes(raw + b" ")
    assert promoter_cli.main([str(path)]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "received input" in output.err
    bad = raw.replace(b"offline", b"offlin\xff")
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(bad), encoding="latin-1")
    )
    assert promoter_cli.main(["-"]) == 2
    assert capsys.readouterr().out == ""


def test_subprocess_ignores_text_stream_encoding():
    value = request() | {"metadata": {"description": "unicode-µ"}}
    raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
    # promoter_cli intentionally has no module entry point; invoke its public main.
    command = [
        sys.executable,
        "-c",
        "from regsite.promoter_cli import main; raise SystemExit(main())",
        "-",
        "--format",
        "json",
    ]
    env = dict(os.environ, PYTHONIOENCODING="latin-1")
    good = subprocess.run(command, input=raw, env=env, capture_output=True, check=False)
    assert good.returncode == 0, good.stderr
    assert (
        json.loads(good.stdout)["results"][0]["metadata"]["description"] == "unicode-µ"
    )
    bad = subprocess.run(
        command,
        input=raw.replace("µ".encode(), b"\xff"),
        env=env,
        capture_output=True,
        check=False,
    )
    assert bad.returncode == 2 and bad.stdout == b""

"""Offline public command dispatch and atomic exit behavior."""

import io
import json
import socket
import subprocess
import sys

import pytest

from regsite import promoter_cli


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
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"records":[{}]}'))
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
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"records": [bad, good]})))
    assert promoter_cli.main(["-", "--format", fmt]) == 1
    output = capsys.readouterr()
    assert "valid-sibling" in output.out and output.err == ""


def test_render_error_cannot_emit_partial_stdout(monkeypatch, capsys):
    def failing_export(result, stream):
        stream.write("partial header\n")
        raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogate")

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request())))
    monkeypatch.setattr(promoter_cli, "write_gff3", failing_export)
    assert promoter_cli.main(["-", "--format", "gff3"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "regsite-promoter:" in output.err

"""CLI exits, stdin/module/file execution, and atomic serialization failures."""

import io
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import drafting_cli, drafting_io
from regsite.drafting import invalid_result, predict


@pytest.mark.parametrize(
    "name,exit_code", [("single", 0), ("batch", 0), ("unsupported", 1)]
)
def test_file_examples(name, exit_code, capsys):
    path = Path(f"examples/drafting-{name}.json")
    assert drafting_cli.main([str(path)]) == exit_code
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.encode() == drafting_io.result_bytes(
        predict(json.loads(path.read_text()))
    )


def test_stdin_module_entry(monkeypatch, capsys):
    raw = Path("examples/drafting-single.json").read_bytes()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    monkeypatch.setattr(sys, "argv", ["regsite-drafting", "-"])
    monkeypatch.delitem(sys.modules, "regsite.drafting_cli")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("regsite.drafting_cli", run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.parametrize(
    "raw",
    [
        b"NaN",
        b'{"x":0,"x":1}',
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{}" + b" " * drafting_io.INPUT_LIMIT,
        b"[]",
    ],
)
def test_wire_envelope_failures_write_one_typed_result(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert drafting_cli.main(["-"]) == 2
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "invalid_input" and output.err == ""
    assert result["coverage"] is None and result["records"] == []


def test_missing_file_has_typed_result_and_no_private_path(tmp_path, capsys):
    assert drafting_cli.main([str(tmp_path / "private-name")]) == 2
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["reason"] == "input_unavailable"
    assert "private-name" not in output.out + output.err


def test_result_cap_falls_back_to_small_typed_result(monkeypatch, capsys):
    small = drafting_io.result_bytes(invalid_result("result_serialization_failure"))
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(small))
    assert drafting_cli.main(["examples/drafting-single.json"]) == 2
    output = capsys.readouterr()
    assert output.out.encode() == small
    assert output.err == ""


def test_nonfinite_result_falls_back_without_emitting_partial_output(
    monkeypatch, capsys
):
    monkeypatch.setattr(drafting_cli, "predict", lambda request: {"x": float("nan")})
    assert drafting_cli.main(["examples/drafting-single.json"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["reason"] == "result_serialization_failure"
    assert output.err == ""


def test_impossible_result_cap_has_no_partial_stdout(monkeypatch, capsys):
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", 1)
    assert drafting_cli.main(["examples/drafting-single.json"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "output unavailable" in output.err


@pytest.mark.parametrize("error", [BrokenPipeError("closed"), OSError("unavailable")])
def test_output_failures(monkeypatch, error, capsys):
    redirects = []

    def write(raw):
        raise error

    stream = SimpleNamespace(buffer=SimpleNamespace(write=write), fileno=lambda: 77)
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(
        drafting_cli.os, "dup2", lambda src, dest: redirects.append(dest)
    )
    assert drafting_cli.main(["examples/drafting-single.json"]) == 2
    assert redirects == ([77] if isinstance(error, BrokenPipeError) else [])
    assert "output unavailable" in capsys.readouterr().err


def test_wire_and_api_caps_are_independent_in_real_process():
    # One received Unicode codepoint expands to twelve escaped ASCII bytes.
    # This envelope fits the wire cap, yet exceeds the canonical API object cap.
    raw = json.dumps(
        {"schema_version": "drafting-request-1", "records": [], "extra": "😀" * 90_000},
        ensure_ascii=False,
    ).encode()
    assert len(raw) < drafting_io.INPUT_LIMIT
    completed = subprocess.run(
        [sys.executable, "-m", "regsite.drafting_cli", "-"],
        input=raw,
        capture_output=True,
        timeout=10,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == 2 and completed.stderr == b""
    assert result["reason"] == "api_object_byte_limit"
    assert result["request_sha256"] is None


def test_explicit_imports_do_not_load_backend():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import regsite.drafting, regsite.drafting_cli; "
            "assert 'regsite.backend' not in sys.modules; "
            "assert 'regsite.rbs' not in sys.modules",
        ],
        capture_output=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr

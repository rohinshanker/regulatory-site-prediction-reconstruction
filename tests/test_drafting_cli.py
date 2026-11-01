"""CLI exits, stdin/module/file execution, and atomic serialization failures."""

import csv
import hashlib
import io
import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import drafting_cli, drafting_export, drafting_io
from regsite.drafting import invalid_result, predict


@pytest.mark.parametrize(
    "name,exit_code", [("single", 0), ("batch", 0), ("unsupported", 1)]
)
@pytest.mark.parametrize("options", [[], ["--format", "json"]])
def test_file_examples(name, exit_code, options, capsys):
    path = Path(f"examples/drafting-{name}.json")
    assert drafting_cli.main([str(path), *options]) == exit_code
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
@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_output_failures(monkeypatch, error, format_name, capsys):
    redirects = []

    def write(raw):
        raise error

    stream = SimpleNamespace(buffer=SimpleNamespace(write=write), fileno=lambda: 77)
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(
        drafting_cli.os, "dup2", lambda src, dest: redirects.append(dest)
    )
    assert (
        drafting_cli.main(["examples/drafting-single.json", "--format", format_name])
        == 2
    )
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


def csv_rows(text):
    return list(csv.DictReader(io.StringIO(text, newline="")))


@pytest.mark.parametrize(
    "name,exit_code", [("single", 0), ("batch", 0), ("unsupported", 1)]
)
def test_csv_files_match_native_status_hashes_and_record_rosters(
    name, exit_code, capsys
):
    path = Path(f"examples/drafting-{name}.json")
    result = predict(json.loads(path.read_text()))
    assert drafting_cli.main(["--format", "csv", str(path)]) == exit_code
    output = capsys.readouterr()
    assert output.err == ""
    rows = csv_rows(output.out)
    assert len(rows) == 1 + len(result["records"])
    assert [row["record_id"] for row in rows[1:]] == [
        r["id"] for r in result["records"]
    ]
    for row in rows:
        assert row["result_status"] == result["status"]
        assert row["prediction_sha256"] == result["prediction_sha256"]
        assert (
            row["json_sha256"]
            == hashlib.sha256(drafting_io.result_bytes(result)).hexdigest()
        )


@pytest.mark.parametrize(
    "raw,reason",
    [
        (b"NaN", "invalid_json_or_input_limit"),
        (b'{"x":0,"x":1}', "invalid_json_or_input_limit"),
        (b"\xff", "invalid_json_or_input_limit"),
        (b"\xef\xbb\xbf{}", "invalid_json_or_input_limit"),
        (b"{}" + b" " * drafting_io.INPUT_LIMIT, "invalid_json_or_input_limit"),
        (b"[]", "invalid_envelope"),
    ],
)
def test_csv_stdin_failures_keep_one_result_row(raw, reason, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert drafting_cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    rows = csv_rows(output.out)
    assert len(rows) == 1 and output.err == ""
    assert rows[0]["result_status"] == "invalid_input"
    assert rows[0]["result_reason"] == reason
    assert rows[0]["requested_records"] == rows[0]["complete"] == ""


def test_missing_csv_file_preserves_format_and_does_not_leak_path(tmp_path, capsys):
    assert drafting_cli.main([str(tmp_path / "private-name"), "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert csv_rows(output.out)[0]["result_reason"] == "input_unavailable"
    assert "private-name" not in output.out + output.err


def test_csv_cap_falls_back_to_exact_small_csv_and_never_leaks_prefix(
    monkeypatch, capsys
):
    small = drafting_export.csv_bytes(invalid_result("result_serialization_failure"))
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(small))
    assert drafting_cli.main(["examples/drafting-batch.json", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out.encode() == small and output.err == ""
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(small) - 1)
    assert drafting_cli.main(["examples/drafting-batch.json", "--format", "csv"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == "regsite-drafting: output unavailable\n"


@pytest.mark.parametrize("fault", ["nonfinite", "surrogate"])
def test_csv_serialization_failure_keeps_selected_format(fault, monkeypatch, capsys):
    request = json.loads(Path("examples/drafting-single.json").read_text())
    request["records"][0]["rate_provenance"] = "artificial \ud800"
    if fault == "nonfinite":
        monkeypatch.setattr(
            drafting_cli, "predict", lambda request: {"x": float("nan")}
        )
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(request).encode()))
    )
    assert drafting_cli.main(["-", "--format", "csv"]) == 2
    output = capsys.readouterr()
    rows = csv_rows(output.out)
    assert len(rows) == 1 and output.err == ""
    assert rows[0]["result_reason"] == "result_serialization_failure"
    assert rows[0]["request_sha256"] == ""


def test_csv_stdin_real_module_process():
    completed = subprocess.run(
        [sys.executable, "-m", "regsite.drafting_cli", "-", "--format", "csv"],
        input=Path("examples/drafting-batch.json").read_bytes(),
        capture_output=True,
        timeout=10,
    )
    assert completed.returncode == 0 and completed.stderr == b""
    assert b"\r\n" in completed.stdout
    rows = csv_rows(completed.stdout.decode())
    assert [row["row_type"] for row in rows] == ["result"] + ["record"] * 3


@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_flush_failure_has_diagnostic_and_exit_two(format_name, monkeypatch, capsys):
    written = []

    def flush():
        raise OSError("artificial flush failure")

    monkeypatch.setattr(
        sys,
        "stdout",
        SimpleNamespace(buffer=SimpleNamespace(write=written.append), flush=flush),
    )
    assert (
        drafting_cli.main(["examples/drafting-single.json", "--format", format_name])
        == 2
    )
    assert len(written) == 1
    assert capsys.readouterr().err == "regsite-drafting: output unavailable\n"


def test_invalid_format_has_no_stdout(capsys):
    with pytest.raises(SystemExit) as error:
        drafting_cli.main(["examples/drafting-single.json", "--format", "tsv"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == "" and "invalid choice" in output.err

"""CLI transport, failure and output lifecycle tests without native scoring."""

import io
import json
import os
import runpy
import sys
from types import SimpleNamespace

import pytest
from test_termination import FakeBackend, assert_identity, request
from test_termination_export import CASES, fixture_result, rows

from regsite import termination, termination_cli, termination_export, termination_io
from regsite.termination_backend import TerminationBackendError
from regsite.termination_io import TerminationInputError


def stdin(monkeypatch, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))


def test_stdin_without_backend_keeps_record(monkeypatch, capsys):
    stdin(monkeypatch, request())
    assert termination_cli.main(["-"]) == 1
    capture = capsys.readouterr()
    result = json.loads(capture.out)
    assert result["records"][0]["reason"] == "backend_unavailable"
    assert capture.err == ""


def test_regular_file_with_explicit_backend(monkeypatch, tmp_path, capsys):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    backend = FakeBackend()
    paths = []

    def load(path):
        paths.append(path)
        return backend

    monkeypatch.setattr(termination_cli, "load_backend", load)
    monkeypatch.setattr(termination, "parse_output", lambda *args: [])
    assert (
        termination_cli.main(
            [str(source), "--backend-manifest", "/explicit/backend.json"]
        )
        == 0
    )
    assert paths == ["/explicit/backend.json"]
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    assert len(backend.calls) == 1


def test_invalid_backend_is_structured_per_record(monkeypatch, capsys):
    stdin(monkeypatch, request())

    def fail(path):
        raise TerminationBackendError("invalid", code="backend_manifest")

    monkeypatch.setattr(termination_cli, "load_backend", fail)
    assert termination_cli.main(["-", "--backend-manifest", "invalid.json"]) == 1
    assert (
        json.loads(capsys.readouterr().out)["records"][0]["reason"]
        == "backend_manifest"
    )


@pytest.mark.parametrize("raw", [b"{", b'{"x":1,"x":2}', b"\xff", b'{"x":NaN}'])
def test_bad_json_has_json_refusal(monkeypatch, capsys, raw):
    stdin(monkeypatch, raw)
    assert termination_cli.main(["-"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid_input"
    assert result["records"] == []


def test_oversized_transport(monkeypatch, capsys):
    from regsite import termination_io

    monkeypatch.setattr(termination_io, "INPUT_LIMIT", 10)
    stdin(monkeypatch, b" " * 11)
    assert termination_cli.main(["-"]) == 2
    assert (
        json.loads(capsys.readouterr().out)["reason"] == "invalid_json_or_input_limit"
    )


@pytest.mark.parametrize("output_format", ["json", "csv"])
@pytest.mark.parametrize("kind", ["missing", "directory", "symlink", "fifo"])
def test_nonregular_inputs_are_refused_without_following_or_blocking(
    tmp_path, capsys, kind, output_format
):
    path = tmp_path / kind
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        actual = tmp_path / "actual"
        actual.write_text(json.dumps(request()))
        path.symlink_to(actual)
    elif kind == "fifo":
        os.mkfifo(path)
    assert termination_cli.main([str(path), "--format", output_format]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unavailable" in captured.err


def test_platform_without_nofollow_refuses_file(monkeypatch, capsys):
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert termination_cli.main(["request.json"]) == 2
    assert "unavailable" in capsys.readouterr().err


def test_descriptor_is_closed_when_wrapping_fails(monkeypatch, tmp_path, capsys):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request()))
    descriptors = []

    def fail(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("cannot wrap")

    monkeypatch.setattr(os, "fdopen", fail)
    assert termination_cli.main([str(path)]) == 2
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_read_failure(monkeypatch, capsys, output_format):
    class FailedRead:
        def read(self, count):
            raise OSError("unavailable")

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=FailedRead()))
    assert termination_cli.main(["-", "--format", output_format]) == 2
    assert "unavailable" in capsys.readouterr().err


def test_serialization_limit_never_writes_a_prefix(monkeypatch, capsys):
    stdin(monkeypatch, request())

    def fail(result):
        raise TerminationInputError("too much output")

    monkeypatch.setattr(termination_cli, "result_bytes", fail)
    assert termination_cli.main(["-"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "oversized" in captured.err


@pytest.mark.parametrize("output_format", ["json", "csv"])
@pytest.mark.parametrize("stage", ["write", "flush"])
def test_broken_pipe_redirects_only_owned_output_descriptor(
    monkeypatch, tmp_path, capsys, output_format, stage
):
    stdin(monkeypatch, request())

    class BrokenBuffer:
        def write(self, raw):
            if stage == "write":
                raise BrokenPipeError()
            return len(raw)

    def flush():
        raise BrokenPipeError()

    with (tmp_path / "output").open("wb") as stream:
        with monkeypatch.context() as patch:
            patch.setattr(
                sys,
                "stdout",
                SimpleNamespace(
                    buffer=BrokenBuffer(), fileno=stream.fileno, flush=flush
                ),
            )
            assert termination_cli.main(["-", "--format", output_format]) == 2
        assert os.write(stream.fileno(), b"safe") == 4
    assert (tmp_path / "output").read_bytes() == b""
    assert "unavailable" in capsys.readouterr().err


def test_module_entry_point(monkeypatch, capsys):
    stdin(monkeypatch, request())
    monkeypatch.setattr(sys, "argv", ["regsite-termination", "-"])
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        with pytest.raises(SystemExit) as caught:
            runpy.run_module("regsite.termination_cli", run_name="__main__")
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "partial"


def test_argument_error(capsys):
    with pytest.raises(SystemExit) as caught:
        termination_cli.main([])
    assert caught.value.code == 2
    assert "usage:" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["positive", "negative", "boundary_mixed"])
def test_default_and_explicit_json_preserve_original_bytes_and_hashes(
    monkeypatch, capsys, name
):
    result = fixture_result(monkeypatch, name)
    # Independent spelling of the unchanged original canonical JSON contract.
    expected = (
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    )
    monkeypatch.setattr(
        termination_cli, "predict_termination", lambda *args, **kwargs: result
    )
    for options in ([], ["--format", "json"]):
        stdin(monkeypatch, request())
        assert termination_cli.main(["-", *options]) == 0
        captured = capsys.readouterr()
        assert captured.out == expected
        assert captured.err == ""
        assert_identity(json.loads(captured.out))


@pytest.mark.parametrize(
    "raw,reason", [(b"{", "invalid_json_or_input_limit"), (b"{}", "invalid_envelope")]
)
def test_csv_invalid_input_keeps_envelope(monkeypatch, capsys, raw, reason):
    stdin(monkeypatch, raw)
    assert termination_cli.main(["-", "--format", "csv"]) == 2
    captured = capsys.readouterr()
    actual = rows(captured.out.encode())
    assert captured.err == "" and len(actual) == 1
    assert actual[0]["row_type"] == "envelope"
    assert actual[0]["result_status"] == "invalid_input"
    assert actual[0]["result_reason"] == reason


def test_csv_stdin_without_backend_keeps_record(monkeypatch, capsys):
    stdin(monkeypatch, request())
    assert termination_cli.main(["-", "--format", "csv"]) == 1
    captured = capsys.readouterr()
    actual = rows(captured.out.encode())
    assert captured.err == "" and len(actual) == 2
    assert actual[0]["result_status"] == "partial"
    assert actual[1]["record_id"] == "fragment"
    assert actual[1]["record_reason"] == "backend_unavailable"
    assert actual[1]["attempted"] == "false" and actual[1]["candidate_count"] == ""


def test_csv_regular_file_with_explicit_backend_keeps_candidates(
    monkeypatch, tmp_path, capsys
):
    expected = fixture_result(monkeypatch)
    source = tmp_path / "request.json"
    source.write_text(
        json.dumps(
            request({"id": "positive", "sequence": CASES["positive"]["sequence"]})
        )
    )
    backend = FakeBackend()
    calls = []

    def load(path):
        calls.append(path)
        return backend

    monkeypatch.setattr(termination_cli, "load_backend", load)
    assert (
        termination_cli.main(
            [
                str(source),
                "--format",
                "csv",
                "--backend-manifest",
                "/explicit/backend.json",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    actual = rows(captured.out.encode())
    assert calls == ["/explicit/backend.json"] and len(backend.calls) == 1
    assert captured.err == "" and len(actual) == 4
    assert [row["candidate_id"] for row in actual[2:]] == [
        item["candidate_id"] for item in expected["records"][0]["candidates"]
    ]
    assert actual[1]["attempted"] == "true" and actual[1]["candidate_count"] == "2"


@pytest.mark.parametrize("short_by", [0, 1])
def test_csv_actual_limit_is_all_or_error(monkeypatch, capsys, short_by):
    result = fixture_result(monkeypatch)
    raw = termination_export.csv_bytes(result)
    monkeypatch.setattr(termination_io, "OUTPUT_LIMIT", len(raw) - short_by)
    monkeypatch.setattr(
        termination_cli, "predict_termination", lambda *args, **kwargs: result
    )
    stdin(monkeypatch, request())
    assert termination_cli.main(["-", "--format", "csv"]) == (2 if short_by else 0)
    captured = capsys.readouterr()
    assert captured.out == ("" if short_by else raw.decode())
    assert captured.err == (
        "regsite-termination: input or output unavailable or oversized\n"
        if short_by
        else ""
    )


@pytest.mark.parametrize("stage", ["write", "flush"])
@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_output_device_error(monkeypatch, capsys, output_format, stage):
    stdin(monkeypatch, request())

    class FailedOutput:
        def write(self, raw):
            if stage == "write":
                raise OSError("device failure")
            return len(raw)

        def flush(self):
            raise OSError("device failure")

    output = FailedOutput()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", SimpleNamespace(buffer=output, flush=output.flush))
        assert termination_cli.main(["-", "--format", output_format]) == 2
    assert "unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("options", [["--format", "gff"], ["--format"]])
def test_invalid_format_options_produce_no_response(capsys, options):
    with pytest.raises(SystemExit) as caught:
        termination_cli.main(["-", *options])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "usage:" in captured.err

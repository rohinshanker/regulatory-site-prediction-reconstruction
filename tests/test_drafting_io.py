"""Strict wire parsing, complete canonical hashes, and independent byte caps."""

import io
import json
from pathlib import Path

import pytest

from regsite import drafting_io
from regsite.drafting import predict


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x": 1, "x": 2}',
        b'{"nested":{"x": 1,"x":2}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{",
        b"",
        b"{} {}",
        b"1" * 5000,
    ],
)
def test_strict_wire_refusals(raw):
    with pytest.raises(drafting_io.DraftingInputError):
        drafting_io.load_request(io.BytesIO(raw))


def test_valid_numbers_and_utf8_preserve_hash_number_forms():
    parsed = drafting_io.load_request(io.BytesIO('{"v":[1,1.0,1e0,-0.0,"β"]}'.encode()))
    assert parsed == {"v": [1, 1.0, 1.0, -0.0, "β"]}
    assert drafting_io.canonical_bytes(parsed) == b'{"v":[1,1.0,1.0,-0.0,"\\u03b2"]}'
    assert drafting_io.canonical_bytes([True, None, "a"]) == b'[true,null,"a"]'


def test_wire_limit_reads_only_cap_plus_one_and_accepts_exact_cap():
    raw = b"{}" + b" " * (drafting_io.INPUT_LIMIT - 2)
    assert drafting_io.load_request(io.BytesIO(raw)) == {}
    stream = io.BytesIO(raw + b" " * 100)
    with pytest.raises(drafting_io.DraftingInputError, match="input_byte_limit"):
        drafting_io.load_request(stream)
    assert stream.tell() == drafting_io.INPUT_LIMIT + 1


def test_canonical_shared_containers_are_json_but_cycles_are_not():
    child = {"z": [1, 2]}
    assert drafting_io.canonical_bytes([child, child]) == b'[{"z":[1,2]},{"z":[1,2]}]'
    child["cycle"] = child
    with pytest.raises(ValueError):
        drafting_io.canonical_bytes(child)


@pytest.mark.parametrize(
    "value", [{1: 1}, {None: 0}, (1,), b"bytes", {1}, object(), float("nan")]
)
def test_canonical_does_not_coerce_python_objects(value):
    with pytest.raises((ValueError, TypeError)):
        drafting_io.canonical_bytes(value)


def test_pretty_result_is_authoritative_and_separately_bounded(monkeypatch):
    request = json.loads(Path("examples/drafting-single.json").read_text())
    result = predict(request)
    raw = drafting_io.result_bytes(result)
    expected = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode()
    assert raw == expected
    assert (
        len(drafting_io.canonical_bytes(result)) < len(raw) < drafting_io.OUTPUT_LIMIT
    )
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(raw))
    assert drafting_io.result_bytes(result) == raw
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(drafting_io.DraftingInputError, match="output_byte_limit"):
        drafting_io.result_bytes(result)


@pytest.mark.parametrize("result", [{"value": float("inf")}, {"value": object()}])
def test_result_serialization_errors_are_typed(result):
    with pytest.raises(
        drafting_io.DraftingInputError, match="result_is_not_finite_json"
    ):
        drafting_io.result_bytes(result)


def test_cyclic_result_serialization_error_is_typed():
    result = {}
    result["cycle"] = result
    with pytest.raises(drafting_io.DraftingInputError):
        drafting_io.result_bytes(result)


def test_decoder_recursion_error_is_typed(monkeypatch):
    def reject(*args, **kwargs):
        raise RecursionError("decoder nesting limit")

    monkeypatch.setattr(drafting_io.json, "loads", reject)
    with pytest.raises(drafting_io.DraftingInputError, match="invalid_json"):
        drafting_io.load_request(io.BytesIO(b"[]"))

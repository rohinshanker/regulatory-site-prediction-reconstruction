"""Strict finite design JSON and whole-output bounds."""

import hashlib
import io
import json
import math

import pytest

from regsite import design_io as wire


def test_authoritative_spelling_and_hash():
    value = {"z": "é\n", "a": [1, None, False, 2.0]}
    canonical = b'{"a":[1,null,false,2.0],"z":"\\u00e9\\n"}'
    assert wire.canonical(value) == canonical
    assert wire.digest(value) == hashlib.sha256(canonical).hexdigest()
    expected = (
        json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2)
        + "\n"
    ).encode()
    assert wire.result_bytes(value) == wire.pretty(value) == expected


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"\xff",
        b'{"a":1,"a":2}',
        b'{"x":{"a":1,"a":2}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e400",
        b'{"x":' + b"9" * 5000 + b"}",
    ],
)
def test_invalid_json(raw):
    with pytest.raises(wire.DesignError, match="invalid_json"):
        wire.load_request(io.BytesIO(raw))


def test_json_numbers_and_exact_input_cap(monkeypatch):
    raw = b'{"a":2.5,"b":-1e-4,"c":100}'
    monkeypatch.setattr(wire, "INPUT_LIMIT", len(raw))
    assert wire.load_request(io.BytesIO(raw)) == {"a": 2.5, "b": -0.0001, "c": 100}
    with pytest.raises(wire.DesignError, match="input_byte_limit"):
        wire.load_request(io.BytesIO(raw + b" "))


def test_exact_result_limit_and_complete_rejection(monkeypatch):
    value = {"text": '"\ré\n'}
    raw = wire.pretty(value)
    monkeypatch.setattr(wire, "OUTPUT_LIMIT", len(raw))
    assert wire.result_bytes(value) == raw
    monkeypatch.setattr(wire, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(wire.DesignError, match="output_byte_limit"):
        wire.result_bytes(value)


@pytest.mark.parametrize("value", [{"a": math.nan}, {"a": math.inf}, {"a": object()}])
def test_nonfinite_or_nonjson_result(value):
    with pytest.raises(wire.DesignError, match="nonfinite_result"):
        wire.result_bytes(value)


def test_recursive_result():
    value = {}
    value["cycle"] = value
    with pytest.raises(wire.DesignError, match="nonfinite_result"):
        wire.result_bytes(value)

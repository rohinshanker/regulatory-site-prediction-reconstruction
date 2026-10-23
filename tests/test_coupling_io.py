"""Byte-boundary, strict decoding and canonical transport regression checks."""

import hashlib
import io
import json

import pytest

from regsite import coupling_io
from regsite.coupling_io import (
    CouplingInputError,
    canonical_bytes,
    canonical_hash,
    load_request,
    result_bytes,
)


def test_finite_json_and_canonical_identity():
    value = load_request(io.BytesIO(b'{"z":1.5,"a":{"x":2}}'))
    expected = b'{"a":{"x":2},"z":1.5}'
    assert canonical_bytes(value) == expected
    assert canonical_hash(value) == hashlib.sha256(expected).hexdigest()
    assert result_bytes(value) == expected + b"\n"
    assert json.loads(canonical_bytes({"label": "\u03b2"})) == {"label": "\u03b2"}


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":{"x":1,"x":2}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"\xff",
        b"{",
        b"",
        b"[" * 10000 + b"]" * 10000,
    ],
    ids=[
        "duplicate",
        "nested-duplicate",
        "nan",
        "inf",
        "negative-inf",
        "overflow",
        "utf8",
        "syntax",
        "empty",
        "deep",
    ],
)
def test_rejects_malformed_json(raw):
    with pytest.raises(CouplingInputError, match="finite UTF-8 JSON"):
        load_request(io.BytesIO(raw))


def test_received_byte_cap(monkeypatch):
    monkeypatch.setattr(coupling_io, "INPUT_LIMIT", 4)
    assert load_request(io.BytesIO(b"null")) is None
    stream = io.BytesIO(b"null  remaining")
    with pytest.raises(CouplingInputError, match="input byte limit"):
        load_request(stream)
    assert stream.tell() == 5


def test_nesting_boundary():
    raw = b"[" * 32 + b"0" + b"]" * 32
    assert isinstance(load_request(io.BytesIO(raw)), list)
    with pytest.raises(CouplingInputError):
        load_request(io.BytesIO(b"[" + raw + b"]"))


def test_output_cap_includes_newline_and_ascii_escapes(monkeypatch):
    result = {"value": "\u03b2"}
    size = len(canonical_bytes(result)) + 1
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", size)
    assert len(result_bytes(result)) == size
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", size - 1)
    with pytest.raises(CouplingInputError, match="output byte limit"):
        result_bytes(result)


def test_nonfinite_output_never_serializes():
    with pytest.raises(ValueError):
        result_bytes({"score": float("inf")})

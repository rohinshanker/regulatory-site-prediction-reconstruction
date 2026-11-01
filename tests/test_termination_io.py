"""Transport rejection and canonical identity contracts for termination."""

import io
import json

import pytest

from regsite import termination_io as subject


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":{"b":1,"b":2}}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":1e999}',
        b"\xff",
        b"{} {}",
        b"\xef\xbb\xbf{}",
        b"{",
        b"",
        b"[" * 33 + b"0" + b"]" * 33,
        b"[" * 2000 + b"0" + b"]" * 2000,
        b"1" * 5000,
    ],
)
def test_rejects_malformed_or_ambiguous_json(raw):
    with pytest.raises(subject.TerminationInputError):
        subject.load_request(io.BytesIO(raw))


def test_accepts_finite_nested_values_and_boundary_depth():
    value = {"value": [0, -1.25, 1e20, True, None, "é"]}
    assert subject.load_request(io.BytesIO(json.dumps(value).encode())) == value
    nested = b"[" * 32 + b"0" + b"]" * 32
    assert subject.load_request(io.BytesIO(nested)) is not None


def test_received_byte_cap_does_not_measure_ascii_escapes(monkeypatch):
    raw = '{"x":"éééé"}'.encode()
    monkeypatch.setattr(subject, "INPUT_LIMIT", len(raw))
    value = subject.load_request(io.BytesIO(raw))
    assert len(subject.canonical_bytes(value)) > len(raw)
    with pytest.raises(subject.TerminationInputError, match="byte limit"):
        subject.load_request(io.BytesIO(raw + b" "))


def test_only_reads_cap_plus_one(monkeypatch):
    monkeypatch.setattr(subject, "INPUT_LIMIT", 8)
    stream = io.BytesIO(b" " * 100)
    with pytest.raises(subject.TerminationInputError):
        subject.load_request(stream)
    assert stream.tell() == 9


def test_canonical_identity_is_key_order_independent_and_field_complete():
    first = {"b": [1, 2], "a": "é"}
    second = {"a": "é", "b": [1, 2]}
    assert subject.canonical_bytes(first) == b'{"a":"\\u00e9","b":[1,2]}'
    assert subject.canonical_hash(first) == subject.canonical_hash(second)
    assert subject.canonical_hash(first) != subject.canonical_hash({**first, "c": None})
    assert subject.result_bytes(first) == subject.canonical_bytes(first) + b"\n"


def test_output_limit_includes_newline(monkeypatch):
    monkeypatch.setattr(subject, "OUTPUT_LIMIT", 3)
    assert subject.result_bytes({}) == b"{}\n"
    with pytest.raises(subject.TerminationInputError, match="output byte"):
        subject.result_bytes({"x": 1})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1, 2}])
def test_canonical_serialization_rejects_non_json_values(value):
    with pytest.raises((ValueError, TypeError)):
        subject.canonical_bytes(value)

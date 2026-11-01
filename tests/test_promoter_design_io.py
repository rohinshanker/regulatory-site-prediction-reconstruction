"""Strict JSON types/bytes, duplicates, nonfinite values and inclusive caps."""

import io as streams
import json

import pytest

from regsite import promoter_design_io as io


@pytest.mark.parametrize("value", [{1: "key"}, (1, 2), {"x": object()}, {"x": {1}}])
def test_non_json_types_refused(value):
    for encode in (io.canonical, io.pretty):
        with pytest.raises(io.DesignError, match="non_json"):
            encode(value)


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), -float("inf"), 10**5000],
    ids=["nan", "positive-infinity", "negative-infinity", "integer-digit-limit"],
)
def test_unserializable_numbers_refused(value):
    for encode in (io.canonical, io.pretty):
        with pytest.raises(io.DesignError, match="invalid_json_value"):
            encode(value)


def test_cycle_refused_and_shared_acyclic_container_admitted():
    shared = {"nested": [1, None, False]}
    assert json.loads(io.canonical([shared, shared])) == [shared, shared]
    cyclic = []
    cyclic.append(cyclic)
    for encode in (io.canonical, io.pretty):
        with pytest.raises(io.DesignError, match="invalid_json_value"):
            encode(cyclic)


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b' {"x":1,"x":2}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e10000",
    ],
    ids=[
        "syntax",
        "utf8",
        "bom",
        "duplicate",
        "nan",
        "infinity",
        "negative-infinity",
        "overflow",
    ],
)
def test_invalid_wire_is_one_typed_error(raw):
    with pytest.raises(io.DesignError, match="invalid_json"):
        io.load_request(streams.BytesIO(raw))


def test_nested_json_cannot_be_admitted_as_a_design():
    from regsite.promoter_design import design

    raw = b"[" * 2000 + b"]" * 2000
    try:
        parsed = io.load_request(streams.BytesIO(raw))
    except io.DesignError as error:
        assert str(error) == "invalid_json"
    else:
        assert design(parsed)["status"] == "invalid_input"


def test_exact_wire_cap_and_read_size(monkeypatch):
    monkeypatch.setattr(io, "INPUT_LIMIT", 4)

    class Input:
        def read(self, count):
            assert count == 5
            return b"null "

    with pytest.raises(io.DesignError, match="input_byte_limit"):
        io.load_request(Input())
    assert io.load_request(streams.BytesIO(b"null")) is None
    assert io.load_request(streams.BytesIO(b"1.25")) == 1.25


def test_pretty_format_ascii_and_result_boundary(monkeypatch):
    value = {"z": "β\ud800", "a": [0, False, None]}
    expected = (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode()
    assert io.pretty(value) == expected
    monkeypatch.setattr(io, "OUTPUT_LIMIT", len(expected))
    assert io.result_bytes(value) == expected
    monkeypatch.setattr(io, "OUTPUT_LIMIT", len(expected) - 1)
    with pytest.raises(io.DesignError, match="output_byte_limit"):
        io.result_bytes(value)

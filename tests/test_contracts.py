"""Request validation and coordinate invariants, independent of model scores."""

import hashlib
from dataclasses import asdict

import pytest

from regsite.contracts import RbsRequest
from regsite.sequence import (
    InputError,
    input_interval,
    normalize_rna,
    reverse_complement,
)


def request(**overrides):
    """Build a complete request while preserving the field under test."""
    return {"sequence": "  AcgT\nATGCCC ", "anti_sd": "acctcctta", **overrides}


def test_normalization_and_provenance():
    raw = request()
    parsed = RbsRequest.from_dict(raw)
    assert parsed.sequence == "ACGUAUGCCC"
    assert parsed.oriented_sequence == parsed.sequence
    assert parsed.anti_sd == "ACCUCCUUA"
    assert parsed.input_sha256 == hashlib.sha256(raw["sequence"].encode()).hexdigest()
    assert parsed.normalized_sha256 == parsed.oriented_sha256
    assert parsed.input_sha256 != parsed.normalized_sha256
    assert parsed.temperature_c == 37.0
    assert parsed.start_positions is None


def test_reverse_orientation_and_explicit_starts():
    parsed = RbsRequest.from_dict(request(strand="-", start_positions=[7, 0]))
    assert parsed.oriented_sequence == "GGGCAUACGU"
    assert parsed.start_positions == (0, 7)
    assert parsed.oriented_sha256 != parsed.normalized_sha256
    assert RbsRequest.from_dict(request(start_positions=[])).start_positions == ()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        request(unknown=True),
        request(id=1),
        request(id=""),
        request(id="x" * 129),
        request(id="bad\nname"),
        request(id="bad\x7fname"),
        request(sequence=None),
        request(sequence="A" * 100_001),
        request(sequence="A" * 10_001),
        request(sequence=" \n"),
        request(sequence="ACGN"),
        request(anti_sd="ACGU"),
        request(strand="both"),
        request(temperature_c=True),
        request(temperature_c="37"),
        request(temperature_c=float("nan")),
        request(temperature_c=float("inf")),
        request(temperature_c=10**400),
        request(temperature_c=-1),
        request(temperature_c=101),
        request(start_positions="0"),
        request(start_positions=list(range(1001))),
        request(start_positions=[True]),
        request(start_positions=[1.5]),
        request(start_positions=[-1]),
        request(start_positions=[8]),
        request(start_positions=[0, 0]),
    ],
)
def test_invalid_requests_are_rejected(raw):
    with pytest.raises(InputError):
        RbsRequest.from_dict(raw)


@pytest.mark.parametrize("temperature", [0, 100, 25.5])
def test_temperature_boundaries(temperature):
    assert RbsRequest.from_dict(request(temperature_c=temperature)).temperature_c == (
        temperature
    )


def test_short_sequence_is_valid_without_a_supplied_start():
    assert RbsRequest.from_dict(request(sequence="A")).sequence == "A"


def test_normalization_limit_and_alphabet():
    assert normalize_rna(" a\tUgc ", "test", max_length=4) == "AUGC"
    assert reverse_complement("ACGU") == "ACGU"


@pytest.mark.parametrize("strand", ["+", "-"])
def test_coordinate_round_trips(strand):
    source = "ACGUAUGCCCUU"
    oriented = source if strand == "+" else reverse_complement(source)
    for start in range(len(source) + 1):
        for end in range(start, len(source) + 1):
            interval = input_interval(start, end, len(source), strand)
            extracted = source[interval.start : interval.end]
            if strand == "-":
                extracted = reverse_complement(extracted)
            assert extracted == oriented[start:end]
            assert asdict(interval)["strand"] == strand


@pytest.mark.parametrize(
    "args",
    [
        (True, 1, 3, "+"),
        (0, 1.0, 3, "+"),
        (-1, 1, 3, "+"),
        (1, 0, 3, "+"),
        (0, 4, 3, "+"),
        (0, 1, 3, "both"),
    ],
)
def test_invalid_intervals(args):
    with pytest.raises(InputError):
        input_interval(*args)


def test_schema_version_and_host_metadata():
    request = RbsRequest.from_dict(
        {
            "sequence": "ATG",
            "anti_sd": "ACCUCCUUA",
            "schema_version": "1.0",
            "host": "explicit uncalibrated host",
        }
    )
    assert request.host == "explicit uncalibrated host"
    for host in ["", 0, "a" * 129, "bad\n", "bad\x7f"]:
        with pytest.raises(InputError):
            RbsRequest.from_dict(
                {"sequence": "ATG", "anti_sd": "ACCUCCUUA", "host": host}
            )
    with pytest.raises(InputError, match="schema_version"):
        RbsRequest.from_dict({"schema_version": "2.0"})

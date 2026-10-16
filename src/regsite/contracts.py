"""Strict, versioned requests for sequence-relative RBS prediction."""

from dataclasses import dataclass

from regsite.sequence import (
    InputError,
    normalize_rna,
    reverse_complement,
    sequence_hash,
)

SCHEMA_VERSION = "1.0"
MAX_SEQUENCE_LENGTH = 10_000
MAX_EXPLICIT_STARTS = 1_000
REQUEST_FIELDS = frozenset(
    {
        "id",
        "sequence",
        "anti_sd",
        "strand",
        "start_positions",
        "temperature_c",
        "schema_version",
        "host",
    }
)


@dataclass(frozen=True)
class RbsRequest:
    """Validated RNA input and settings; start positions use oriented coordinates.

    No host label is inferred from anti_sd. Both the original supplied orientation
    and the sequence in transcript orientation remain available for provenance.
    """

    id: str
    host: str | None
    sequence: str
    oriented_sequence: str
    anti_sd: str
    strand: str
    start_positions: tuple[int, ...] | None
    temperature_c: float
    input_sha256: str
    normalized_sha256: str
    oriented_sha256: str

    @classmethod
    def from_dict(cls, value: object) -> "RbsRequest":
        """Validate a JSON object without silently accepting unknown settings."""
        if not isinstance(value, dict):
            raise InputError("each request must be a JSON object")
        unknown = set(value) - REQUEST_FIELDS
        if unknown:
            raise InputError(f"unknown request fields: {sorted(map(str, unknown))}")
        if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise InputError("only input schema_version 1.0 is supported")
        host = value.get("host")
        if host is not None and (
            not isinstance(host, str)
            or not host
            or len(host) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in host)
        ):
            raise InputError("host must be null or 1–128 characters without controls")
        identifier = value.get("id", "sequence")
        if (
            not isinstance(identifier, str)
            or not identifier
            or len(identifier) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in identifier)
        ):
            raise InputError("id must be 1–128 characters without control characters")
        sequence = normalize_rna(
            value.get("sequence"), "sequence", max_length=MAX_SEQUENCE_LENGTH
        )
        anti_sd = normalize_rna(value.get("anti_sd"), "anti_sd", max_length=9)
        if len(anti_sd) != 9:
            raise InputError("anti_sd must contain exactly 9 nucleotides")
        strand = value.get("strand", "+")
        if strand not in ("+", "-"):
            raise InputError("strand must be '+' or '-'")
        temperature = value.get("temperature_c", 37.0)
        if type(temperature) not in (int, float) or not 0 <= temperature <= 100:
            raise InputError("temperature_c must be a finite number from 0 to 100")
        starts = value.get("start_positions")
        if starts is not None:
            if not isinstance(starts, list) or len(starts) > MAX_EXPLICIT_STARTS:
                raise InputError(
                    "start_positions must be a list of at most 1000 indices"
                )
            if any(type(index) is not int for index in starts):
                raise InputError("start_positions must contain integer indices")
            if any(not 0 <= index <= len(sequence) - 3 for index in starts):
                raise InputError("a start codon must fit within the sequence")
            if len(set(starts)) != len(starts):
                raise InputError("start_positions must not contain duplicates")
            starts = tuple(sorted(starts))
        oriented = sequence if strand == "+" else reverse_complement(sequence)
        return cls(
            id=identifier,
            host=host,
            sequence=sequence,
            oriented_sequence=oriented,
            anti_sd=anti_sd,
            strand=strand,
            start_positions=starts,
            temperature_c=float(temperature),
            input_sha256=sequence_hash(value["sequence"]),
            normalized_sha256=sequence_hash(sequence),
            oriented_sha256=sequence_hash(oriented),
        )

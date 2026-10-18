"""Sequence normalization and zero-based, half-open coordinate conversion."""

import hashlib
from dataclasses import dataclass


class InputError(ValueError):
    """An input violates the public request contract."""


def normalize_rna(value: object, field: str, *, max_length: int) -> str:
    """Normalize DNA/RNA letters and whitespace without accepting ambiguity.

    Coordinates always count nucleotides after whitespace removal. The original
    input text is hashed separately by the request contract.
    """
    if not isinstance(value, str):
        raise InputError(f"{field} must be a string")
    if len(value) > max_length * 10:
        raise InputError(f"{field} text exceeds {max_length * 10} characters")
    normalized = "".join(value.upper().split()).replace("T", "U")
    if not normalized or len(normalized) > max_length:
        raise InputError(f"{field} must contain 1–{max_length} nucleotides")
    if set(normalized) - set("ACGU"):
        raise InputError(f"{field} accepts only A, C, G, T, U and whitespace")
    return normalized


def sequence_hash(value: str) -> str:
    """Hash exact UTF-8 text; callers identify its normalization in metadata."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def reverse_complement(sequence: str) -> str:
    """Reverse-complement an already normalized RNA sequence."""
    return sequence.translate(str.maketrans("ACGU", "UGCA"))[::-1]


@dataclass(frozen=True)
class Interval:
    """An interval in the normalized supplied sequence, not a genome assembly."""

    start: int
    end: int
    strand: str


def input_interval(start: int, end: int, sequence_length: int, strand: str) -> Interval:
    """Map an oriented transcript interval back onto the supplied sequence.

    Args:
        start: Zero-based start on the oriented sequence.
        end: Exclusive end on the oriented sequence.
        sequence_length: Length of the supplied normalized sequence.
        strand: '+' for supplied orientation, '-' for its reverse complement.

    Returns:
        An ascending, zero-based, half-open interval with explicit strand.

    Raises:
        InputError: If the bounds, types or strand are invalid.
    """
    if any(type(value) is not int for value in (start, end, sequence_length)):
        raise InputError("interval coordinates must be integers")
    if not 0 <= start <= end <= sequence_length:
        raise InputError("interval lies outside the supplied sequence")
    if strand not in ("+", "-"):
        raise InputError("strand must be '+' or '-'")
    if strand == "-":
        return Interval(sequence_length - end, sequence_length - start, strand)
    return Interval(start, end, strand)

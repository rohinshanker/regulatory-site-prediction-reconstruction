"""Finite strict JSON transport for bounded RBS design."""

import hashlib
import json
import math
from typing import BinaryIO

INPUT_LIMIT = 65_536
OUTPUT_LIMIT = 67_108_864
NATIVE_LIMIT = 131_072


class DesignError(ValueError):
    """A design input, native response or output violates its explicit contract."""


def canonical(value: object) -> bytes:
    """Encode finite canonical JSON without a trailing newline."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def digest(value: object) -> str:
    """Hash the complete canonical value."""
    return hashlib.sha256(canonical(value)).hexdigest()


def pretty(value: object) -> bytes:
    """Encode authoritative finite, sorted, ASCII JSON with one trailing LF."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode()


def _pairs(items: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in items:
        if key in result:
            raise DesignError("duplicate_json_key")
        result[key] = value
    return result


def _number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise DesignError("nonfinite_json_number")
    return value


def load_request(stream: BinaryIO) -> object:
    """Read at most the input cap plus one byte; reject ambiguous JSON."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise DesignError("input_byte_limit")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_number,
            parse_constant=_number,
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DesignError("invalid_json") from exc


def result_bytes(value: dict) -> bytes:
    """Bound complete serialization before any stdout write."""
    try:
        raw = pretty(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise DesignError("nonfinite_result") from exc
    if len(raw) > OUTPUT_LIMIT:
        raise DesignError("output_byte_limit")
    return raw

"""Bounded, strict JSON transport for supplied-energy coupling requests."""

import hashlib
import json
import math
from typing import BinaryIO

INPUT_LIMIT = 1_048_576
# Independent guard for Python objects, allowing escaped Unicode and number expansion.
OBJECT_LIMIT = 6 * INPUT_LIMIT
OUTPUT_LIMIT = 4_194_304


class CouplingInputError(ValueError):
    """A request or serialized result violates the transport contract."""


def _pairs(items: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in items:
        if key in result:
            raise CouplingInputError("duplicate JSON key")
        result[key] = value
    return result


def _number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise CouplingInputError("JSON numbers must be finite")
    return value


def load_request(stream: BinaryIO) -> object:
    """Read at most the input cap plus one byte before decoding strict JSON."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise CouplingInputError("input byte limit exceeded")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_number,
            parse_constant=_number,
        )
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if isinstance(item, (dict, list)):
                if depth >= 32:
                    raise CouplingInputError("JSON nesting limit exceeded")
                children = item.values() if isinstance(item, dict) else item
                pending.extend((child, depth + 1) for child in children)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CouplingInputError("expected finite UTF-8 JSON with unique keys") from exc


def canonical_bytes(value: object) -> bytes:
    """Serialize finite JSON deterministically, without excluding any fields."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def canonical_hash(value: object) -> str:
    """Hash the complete finite canonical JSON value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def result_bytes(result: dict) -> bytes:
    """Finish and bound serialization before a CLI writes any output."""
    raw = canonical_bytes(result) + b"\n"
    if len(raw) > OUTPUT_LIMIT:
        raise CouplingInputError("output byte limit exceeded")
    return raw

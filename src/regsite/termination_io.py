"""Strict bounded JSON transport for intrinsic-termination requests."""

import hashlib
import json
import math
from typing import BinaryIO

INPUT_LIMIT = 4_194_304
OBJECT_LIMIT = 6 * INPUT_LIMIT
OUTPUT_LIMIT = 33_554_432


class TerminationInputError(ValueError):
    """A JSON value violates the termination transport contract."""


def _pairs(items: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in items:
        if key in result:
            raise TerminationInputError("duplicate JSON key")
        result[key] = value
    return result


def _number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise TerminationInputError("JSON numbers must be finite")
    return value


def validate_depth(value: object) -> None:
    """Reject nested containers beyond the documented transport depth."""
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth >= 32:
                raise TerminationInputError("JSON nesting limit exceeded")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)


def load_request(stream: BinaryIO) -> object:
    """Read at most the byte cap plus one, then decode finite unique-key JSON."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise TerminationInputError("input byte limit exceeded")
    try:
        result = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_number,
            parse_constant=_number,
        )
        validate_depth(result)
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise TerminationInputError("expected bounded finite UTF-8 JSON") from exc


def canonical_bytes(value: object) -> bytes:
    """Serialize a complete finite JSON value in stable ASCII form."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def canonical_hash(value: object) -> str:
    """Hash every field of a canonical JSON value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def result_bytes(result: dict) -> bytes:
    """Finish bounded serialization before the CLI writes a response."""
    raw = canonical_bytes(result) + b"\n"
    if len(raw) > OUTPUT_LIMIT:
        raise TerminationInputError("output byte limit exceeded")
    return raw

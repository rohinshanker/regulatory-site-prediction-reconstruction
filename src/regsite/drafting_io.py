"""Strict, independently bounded JSON transport for supplied-rate drafting."""

import hashlib
import json
import math
from typing import BinaryIO, cast

INPUT_LIMIT = 1_048_576
OBJECT_LIMIT = 1_048_576
OUTPUT_LIMIT = 4_194_304


class DraftingInputError(ValueError):
    """Input or output cannot satisfy the finite JSON transport contract."""


def _pairs(items: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in items:
        if key in result:
            raise DraftingInputError("duplicate_json_key")
        result[key] = value
    return result


def _number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise DraftingInputError("nonfinite_json_number")
    return value


def load_request(stream: BinaryIO) -> object:
    """Read no more than the wire cap plus one byte and decode strict UTF-8 JSON."""
    raw = stream.read(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT:
        raise DraftingInputError("input_byte_limit")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_number,
            parse_constant=_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DraftingInputError("invalid_json") from exc


def canonical_bytes(value: object) -> bytes:
    """Encode actual JSON types without Python's tuple/key coercions.

    The visited set only bounds the type walk; the encoder rejects cycles.
    Integers retain their pre-normalization representation for request identity.
    """
    pending = [value]
    visited: set[int] = set()
    while pending:
        item = pending.pop()
        if type(item) in (dict, list):
            if id(item) in visited:
                continue
            visited.add(id(item))
            if isinstance(item, dict):
                if any(type(key) is not str for key in item):
                    raise DraftingInputError("non_json_object_key")
                pending.extend(item.values())
            else:
                pending.extend(cast(list, item))
        elif type(item) not in (str, int, float, bool, type(None)):
            raise DraftingInputError("non_json_value")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def canonical_hash(value: object) -> str:
    """Hash the entire canonical JSON value without a newline."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def result_bytes(result: dict) -> bytes:
    """Serialize the authoritative pretty result before writing any bytes."""
    try:
        raw = (
            json.dumps(
                result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise DraftingInputError("result_is_not_finite_json") from exc
    if len(raw) > OUTPUT_LIMIT:
        raise DraftingInputError("output_byte_limit")
    return raw

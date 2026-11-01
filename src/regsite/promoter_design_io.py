"""Strict bounded JSON transport for the original Promoter design wrapper."""

import hashlib
import json
import math
from typing import BinaryIO, cast

INPUT_LIMIT = 65_536
NATIVE_LIMIT = 131_072
OUTPUT_LIMIT = 16_777_216


class DesignError(ValueError):
    """A request, native response or output violates the wrapper contract."""


def _types(value: object) -> None:
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
                    raise DesignError("non_json_key")
                pending.extend(item.values())
            else:
                pending.extend(cast(list, item))
        elif type(item) not in (str, int, float, bool, type(None)):
            raise DesignError("non_json_value")


def canonical(value: object) -> bytes:
    """Encode only actual finite JSON types, with no trailing newline."""
    _types(value)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise DesignError("invalid_json_value") from exc


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def pretty(value: object) -> bytes:
    """Encode authoritative finite pretty JSON and its final LF."""
    _types(value)
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                indent=2,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise DesignError("invalid_json_value") from exc


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
    """Read at most cap+1 bytes; reject invalid UTF-8 and ambiguous JSON."""
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
    """Bound full serialization before a caller writes any stdout bytes."""
    raw = pretty(value)
    if len(raw) > OUTPUT_LIMIT:
        raise DesignError("output_byte_limit")
    return raw
